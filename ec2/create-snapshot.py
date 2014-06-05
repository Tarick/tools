#!/usr/bin/env python

import sys
import boto.ec2
from boto.utils import get_instance_metadata
import logging
import argparse
import time
import datetime
import subprocess

if sys.version_info < (2, 6):
    if __name__ == "__main__":
        sys.exit("Error: we need python >= 2.6.")
    else:
        raise Exception("we need python >= 2.6")


def get_volume(conn, device):
    '''Returns volume to make snapshot'''
    instance_id = get_instance_metadata()["instance-id"]
    logging.debug("Our instanceID is %s" % instance_id)
    volumes = conn.get_all_volumes(filters={
                                   'attachment.instance-id': instance_id,
                                   'attachment.device': device})
    logging.debug("Our volume is %s" % volumes[0])
    return volumes[0]


def stop_service(name):
    '''Stop some service, e.g. db, before doing the snapshot'''
    logging.debug("Stopping %s" % name)
    subprocess.check_call(["/sbin/stop", name])
    # Sync and sleep for 2 seconds to settle things
    subprocess.check_call(["/bin/sync"])
    time.sleep(2)


def start_service(name):
    '''Start service after doing the snapshot'''
    logging.debug("Starting %s" % name)
    subprocess.check_call(["/sbin/start", name])


def create_snapshot(conn, volume, snapshot_tags, snapshot_description=None):
    '''Create snapshot object with the description and tags.'''
    snapshot = volume.create_snapshot(snapshot_description)
    logging.debug("Created snapshot: %s" % snapshot)
    # Add tags to the snapshot
    for tagname, tagvalue in snapshot_tags.iteritems():
        snapshot.add_tag(tagname, tagvalue)
        logging.debug("Tagged snapshot: %s with tags: %s"
                      % (snapshot, snapshot_tags))
    return snapshot


def params_to_dict(tags):
    """ Reformat tag-value params into dictionary. """
    tags_name_value_list = [tag[0].split(':') for tag in tags]
    return dict(tags_name_value_list)


def cleanup_snapshots(conn, snapshots_tags, retention):
    '''Delete older than retention age snapshots with specified tags.'''
    # Date for older snapshots
    retention_date = (datetime.datetime.today() -
                      datetime.timedelta(days=retention)
                      ).strftime('%Y-%m-%dT%H:%M:%S')
    logging.debug("Retention date: %s" % retention_date)
    # Form filter dictionary
    filter_dict = {}
    for key, val in snapshots_tags.iteritems():
        filter_dict["tag:" + key] = val
    snapshots = conn.get_all_snapshots(owner="self", filters=filter_dict)
    logging.debug("Snapshots list that matches tags:" % snapshots)
    # Delete stale snapshots
    if snapshots:
        stale_snapshots = [snapshot for snapshot in snapshots
                           if snapshot.start_time < retention_date]
        logging.debug("Stale snapshots that are older"
                      "than retention date %s: %s"
                      % (retention_date, stale_snapshots))
        for snapshot in stale_snapshots:
            snapshot.delete()
            logging.info("Deleted snapshot: %s" % snapshot)
    else:
        stale_snapshots = None

    return stale_snapshots


def main():

    # Parse all arguments
    epilog = "EXAMPLE: %(prog)s --device /dev/xvdg --tag-value Environment:dev --tag-value Role:mysql-backup"
    description = "Create snapshot for EBS volume with some data with optional stop of some service"
    "that produced that data. Older than retention time snapshots are deleted"

    parser = argparse.ArgumentParser(description=description, epilog=epilog)
    parser.add_argument("--snapshot-description", "-T",
                        type=str, default=None,
                        help="The description to create snapshot with")
    parser.add_argument("--service", "-s",
                        type=str, default=None,
                        help="Service to stop before and start after the volume snapshot")
    parser.add_argument("--device", "-d",
                        type=str,
                        required=True,
                        help="Device of the volume snapshot")
    parser.add_argument("--retention", "-r",
                        type=int, default=30,
                        help="Delete snapshots older than specified"
                             "retention days period")
    parser.add_argument("--tag-value", "-t",
                        dest="tags",
                        action="append",
                        nargs="*",
                        required=True,
                        help="Tag:value to mark volume with,"
                        "used to cleanup older volumes as well.")
    parser.add_argument("--loglevel",
                        type=str, default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING',
                                 'ERROR', 'CRITICAL',
                                 'debug', 'info', 'warning',
                                 'error', 'critical'],
                        help="set output verbosity level")

    args = parser.parse_args()

    # Print help on missing arguments
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    tags_dict = params_to_dict(args.tags)

    logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s: %(message)s',
                        level=getattr(logging, args.loglevel.upper(), None))
    # Output will be like: "2013-05-12 13:00:09,934 root WARNING: some warning text"
    logging.info("====================================================")
    logging.info("Started backup of volume")
    logging.debug("Used volume device: %s" % args.device)
    logging.debug("Used snapshot tags: %s" % tags_dict)
    logging.debug("Used snapshot retention period: %s" % args.retention)
    logging.debug("Used snapshot description: %s" % args.snapshot_description)

    # Provides AWS_ID and AWS_SECRET for Boto connection
    # NOTE: we rely on:
    #   * ~/.boto or /etc/boto.cfg config files or
    #   * AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environmental variables
    #   * or IAM instance profile
    # to automatically provide credentials to boto.
    try:
        conn = boto.ec2.connect_to_region(get_instance_metadata()
                                          ["placement"]
                                          ["availability-zone"][:-1])
    except:
        logging.exception("Failure getting EC2 API connection")
        sys.exit(1)

    try:
        volume = get_volume(conn, args.device)
    except:
        logging.exception("Failure getting the volume")
        sys.exit(1)

    # Stop service before making snapshot
    if args.service:
        try:
            stop_service(args.service)
        except:
            logging.exception("Failure stopping %s" % args.service)
        else:
            logging.info("%s stopped for backup" % args.service)

    # Make snapshot, tag it and start any service
    try:
        snapshot = create_snapshot(conn, volume,
                                   tags_dict,
                                   args.snapshot_description)
    except:
        logging.exception("Failure making snapshot")
        sys.exit(1)
    else:
        logging.info("Created new snapshot %s" % snapshot)
        logging.info("Tagged snapshot with tags %s" % tags_dict)
    finally:
        if args.service:
            start_service(args.service)

    # Perform cleanup of older snapshots
    try:
        removed_snapshots = cleanup_snapshots(conn,
                                              tags_dict,
                                              args.retention)
    except:
        logging.exception("Failure cleaning up snapshots")
        sys.exit(1)
    else:
        if removed_snapshots:
            logging.info("Deleted stale snapshots %s" % removed_snapshots)
        else:
            logging.info("No stale snapshots were removed")

    logging.info("====================================================")

if __name__ == '__main__':
    main()
