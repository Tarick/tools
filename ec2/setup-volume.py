#!/usr/bin/env python

import os
import sys
import errno
import boto.ec2
from boto.utils import get_instance_metadata
import logging
import argparse
import time

if sys.version_info < (2, 6):
    if __name__ == "__main__":
        sys.exit("Error: we need python >= 2.6.")
    else:
        raise Exception("we need python >= 2.6")


class CreateAndMountEBSVolume(object):

    '''Create and mount ebs volume on EC2 instance, either from snapshot or completely new.
    In later case - format it to needed FS.

    '''
    def __init__(self, conn):
        self.conn = conn
        self.availability_zone = get_instance_metadata()["placement"]["availability-zone"]
        self.instance_id = get_instance_metadata()["instance-id"]
        logging.debug("Our instanceID is %s in %s availability zone",
                      self.instance_id, self.availability_zone)

    def check_mount(self, mount_dir):
        '''Check mount directory and create if needed'''

        if os.path.exists(mount_dir):
            logging.debug("%s is already present", mount_dir)
            if os.isdir(mount_dir):
                if os.path.ismount(mount_dir):
                    logging.error("%s is already mounted", mount_dir)
                    return False
                elif os.listdir(mount_dir):
                    logging.error("%s is already present and not empty",
                                  mount_dir)
                    return False
            else:
                # this is empty directory, we'll use it
                return True
        else:
            # Create directory recursively
            try:
                os.makedirs(mount_dir)
            except OSError as exc:
                if exc.errno == errno.EEXIST and os.path.isdir(mount_dir):
                    pass
                else:
                    raise
            logging.debug("%s created", mount_dir)
            return True

    def check_device(self, device_name):
        '''Check if block defice is present'''
        if os.path.exists(device_name):
            logging.debug("%s is present", device_name)
            return True
        else:
            logging.debug("%s is not present", device_name)
            return False

    def get_snapshot(self, snapshot_description):
        '''Get snapshot from the description
        In case there are many snapshots - take the last created'''
        snapshot_list = conn.get_all_snapshots(owner="self",
                                          filters={"description": snapshot_description,
                                                   "status": "completed"})
        if snapshot_list:
            snapshot = sorted(snaplist, key=lambda snapshot: snapshot.start_time)[-1]
            return snapshot
        else:
            return None

    def create_volume_from_snapshot(self, snapshot,
                                    size=None,
                                    provisioned_iops=None,
                                    ):
        '''Create volume from provided snapshot object'''
        if provisioned_iops:
            volume_type = io1
        else:
            volume_type = None
        volume = snapshot.create_volume(availability_zone,
                                        size=size,
                                        iops=provisioned_iops,
                                        volume_type=volume_type)
        return volume

    def create_new_volume(self, size, provisioned_iops=None):
        '''Create new volume'''
        if provisioned_iops:
            volume_type = io1
        else:
            volume_type = None
        volume = conn.create_volume(availability_zone,
                                        size=size,
                                        iops=provisioned_iops,
                                        volume_type=volume_type)
        return volume

    def attach_volume(self, volume, device, instance_id,
                      delete_on_shutdown=False):
        '''Attaches the volume to the instance'''
        while volume.status != 'available':
            logging.debug("%s is not yet created and available", volume)
            volume.update()
            time.sleep(3)
        volume.attach(instance_id, device)
        if delete_on_shutdown:
            while volume.status != 'in-use':
                logging.debug("%s is not yet attached", volume)
                volume.update()
                time.sleep(3)
            conn.modify_instance_attribute(instance_id,
                                           'blockDeviceMapping', {device: True})

    def format_volume(self, device_name, format_parameters):
        pass

    def mount_volume(self, mount_dir):
        pass


def main():

    # Parse all arguments
    parser = argparse.ArgumentParser(description="Create and mount EBS volume to the instance we run the script on")
    group = parser.add_mutually_exclusive_group()

    group.add_argument("--snapshot", "-S", metavar="SNAPSHOT_ID",
                       help="Snapshot ID to create volume from")
    group.add_argument("--snapshot-description", "-t", type=int,
                       metavar="SNAPSHOT_DESCRIPTION",
                       help="The latest created snapshot with the description to create volume from")
    parser.add_argument("--delete-on-shutdown", "-z", type=bool,
                        metavar="DELETE_ON_SHUTDOWN", action="store_true",
                        help="delete volume on instance shutdown")
    parser.add_argument("--provisioned-iops", "-p", type=int,
                        metavar="PROVISIONED_IOPS",
                        help="Provisioned IOPS to setup volume with")
    parser.add_argument("--device", "-d", metavar="DEVICE", default="/dev/sdh",
                        help="Device to attach volume")
    parser.add_argument("--mount-point", "-m", metavar="MOUNT_POINT", default="/mnt/data",
                        help="Mount point for volume, by default /mnt/data")
    parser.add_argument("--size", "-s", type=int, metavar="SIZE", default=10,
                        help="Volume size, by default 10G if created from scratch")
    parser.add_argument("--verbose", help="maximum verbosity",
                        action="store_true")
    parser.add_argument("--loglevel", type=str, choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        default='INFO',
                        help="set output verbosity level")

    args = parser.parse_args()

    loglevel = "logging." + args.loglevel

    if args.verbose is True:
        print("Verbosity is turned on")
        loglevel = "logging.DEBUG"

    logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s: %(message)s', level=loglevel)
    # Output will be like: "2013-05-12 13:00:09,934 root WARNING: some warning text"
    logging.debug("====================================================")
    logging.debug("Program started")

    # Provides AWS_ID and AWS_SECRET
    # NOTE: we rely on:
    #   * .boto or /etc/boto.cfg config files
    #   * AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environmental variables
    # to automatically provide credentials to boto.
    # In case you need pass those via the file - uncomment the code below

    #try:
    #    # The awsauth.py file should have AWS_ACCESS_KEY_ID
    #    # and AWS_SECRET_ACCESS_KEY defined.
    #    import awsauth
    #except Exception, ex:
    #    logging.exception("Failure importing AWS credentials")
    #    sys.exit(1)

if __name__ == '__main__':
    main()
