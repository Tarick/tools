#!/usr/bin/env python

import os
import sys
import errno
import boto.ec2
from boto.utils import get_instance_metadata
import logging
import argparse
import time
import subprocess

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
        # 3 seconds sleep period for repeatable tasks
        self.TIME_SLEEP = 3
        logging.debug("Our instanceID is %s in %s availability zone" %
                      (self.instance_id, self.availability_zone))

    def prepare_mount(self, mount_dir):
        '''Check mount directory and create if needed'''

        if os.path.exists(mount_dir):
            logging.debug("%s is already present", mount_dir)
            if os.path.isdir(mount_dir):
                if os.path.ismount(mount_dir):
                    logging.debug("%s is already mounted" % mount_dir)
                    return False
                elif os.listdir(mount_dir):
                    logging.debug("%s is already present and not empty" % mount_dir)
                    return False
                else:
                    return True
            else:
                # this is empty directory, we'll use it
                return True
        else:
            # Create directory recursively
            try:
                os.makedirs(mount_dir)
            except OSError, exc:
                if exc.errno == errno.EEXIST and os.path.isdir(mount_dir):
                    pass
                else:
                    raise
            logging.debug("Directory %s was created" % mount_dir)
            return True

    def check_device(self, device):
        '''Check if block defice is present'''
        if os.path.exists(device):
            logging.debug("Device %s is present" % device)
            return True
        else:
            logging.debug("Device %s is not present" % device)
            return False

    def get_snapshot(self, snapshot_id=None, snapshot_description=None):
        '''Get snapshot object from the description or snapshot_id.
        In case there are many snapshots - take the last created'''
        if snapshot_id:
            snapshot = self.conn.get_all_snapshots(snapshot_ids=[snapshot_id],
                                                   filters={"status": "completed"})[0]
        elif snapshot_description:
            snapshot_list = self.conn.get_all_snapshots(owner="self",
                                                        filters={"description": snapshot_description,
                                                                 "status": "completed"})
            if snapshot_list:
                snapshot = sorted(snapshot_list, key=lambda snapshot: snapshot.start_time)[-1]
            else:
                snapshot = None
        else:
            snapshot = None

        logging.debug("Snapshot to use: %s" % snapshot)
        return snapshot

    def create_volume(self, snapshot=None, size=None, provisioned_iops=None):
        '''Create new volume'''
        if provisioned_iops:
            volume_type = "io1"
        else:
            volume_type = None
        try:
            logging.debug("Creating volume with parameters size: %s, snapshot: %s, piops: %s, volume type: %s" %
                         (size, snapshot, provisioned_iops, volume_type))
            volume = self.conn.create_volume(zone=self.availability_zone,
                                             size=size,
                                             snapshot=snapshot,
                                             iops=provisioned_iops,
                                             volume_type=volume_type)
        except:
            logging.critical("Failure creating volume")
            raise
        logging.info("Created volume %s" % volume)
        return volume

    def attach_volume(self, volume, device, instance_id,
                      delete_on_shutdown=False):
        '''Attaches the volume to the instance'''
        while volume.status != 'available':
            logging.debug("%s is not yet available" % volume)
            volume.update()
            time.sleep(self.TIME_SLEEP)
        try:
            volume.attach(instance_id, device)
            logging.info("Attached %s as %s" % (volume, device))
        except:
            logging.critical("Failure attaching the volume")
            raise

        if delete_on_shutdown:
            while volume.status != 'in-use':
                logging.debug("%s is not yet attached" % volume)
                volume.update()
                time.sleep(self.TIME_SLEEP)
            self.conn.modify_instance_attribute(instance_id,
                                                'blockDeviceMapping', {device: True})
            logging.info("Device was set to be deleted on instance shutdown")
        # Wait for device to appear on host
        while not self.check_device(device):
            time.sleep(self.TIME_SLEEP)

    def format_volume(self, device, format_fs=None):
        '''Unconditionally formats the volume.
        Will try the best guess on options depending on FS used'''
        logging.debug("Formatting volume with mkfs.%s" % format_fs)
        try:
            if "ext" in format_fs:
                subprocess.check_call([".".join(["mkfs", format_fs]),
                                       '-q', '-F', device])
            elif format_fs == "xfs":
                subprocess.check_call([".".join(["mkfs", format_fs]),
                                       '-q', '-f', device])
            else:
                subprocess.check_call([".".join(["mkfs", format_fs]),
                                       device])


            logging.info("Volume was successfully formatted in %s" % format_fs)
        except subprocess.CalledProcessError:
            logging.critical("Failure formatting the volume")
            raise

    def mount_volume(self, device, mount_dir, mount_options=None):
        '''mounts volume, cap'''
        try:
            if mount_options:
                subprocess.check_call(["mount", "-o", mount_options, device, mount_dir])
                logging.debug("Mounted volume %s to %s with mount parameters: %s" %
                              (device, mount_dir, mount_options))
            else:
                subprocess.check_call(["mount", device, mount_dir])
                logging.debug("Mounted volume %s" % device)
        except subprocess.CalledProcessError:
            logging.critical("Failure mounting the %s device to %s" % (device, mount_dir))
            raise
        logging.info("Successfully mounted the volume to %s" % mount_dir)

    def setup_volume(self, snapshot_id=None,
                     snapshot_description=None,
                     device="/dev/sdh",
                     mount_dir="/mnt/data",
                     mount_options=None,
                     format_fs="xfs",
                     size=None,
                     provisioned_iops=None,
                     delete_on_shutdown=False):
        ''' Generic function to setup volume'''
        # Check if device is present
        if self.check_device(device):
            raise Exception("Device is already used", device)

        # Check if mount dir is present/mounted, create if needed
        if not self.prepare_mount(mount_dir):
            raise Exception("Cannot use directory for mount", mount_dir)
        # Get from snapshot if defined, otherwise create new and format it
        if snapshot_id or snapshot_description:
            logging.debug("Creating from snapshot")
            try:
                snapshot = self.get_snapshot(snapshot_id, snapshot_description)
                if not snapshot:
                    logging.error("Failure getting the snapshot")
                    raise Exception("Failure getting the snapshot")
                volume = self.create_volume(snapshot=snapshot, size=size,
                                            provisioned_iops=provisioned_iops)
                self.attach_volume(volume, device, self.instance_id,
                                   delete_on_shutdown)
                self.mount_volume(device, mount_dir, mount_options)
            except:
                logging.error("Failure setting up the volume from snapshot")
                raise
        else:
            try:
                logging.debug("Creating new volume")
                volume = self.create_volume(snapshot=None,
                                            size=size,
                                            provisioned_iops=provisioned_iops)
                self.attach_volume(volume, device, self.instance_id,
                                   delete_on_shutdown)
                self.format_volume(device, format_fs)
                self.mount_volume(device, mount_dir, mount_options)
            except:
                logging.error("Failure setting up the new volume")
                raise


def main():

    # Parse all arguments
    parser = argparse.ArgumentParser(description="Create and mount EBS volume to the instance we run the script on")
    group = parser.add_mutually_exclusive_group()

    group.add_argument("--snapshot-id", "-S",
                       default=None,
                       help="Snapshot ID to create volume from")
    group.add_argument("--snapshot-description", "-T",
                       type=str, default=None,
                       help="The description of latest created snapshot to create volume from")
    parser.add_argument("--delete-on-shutdown", "-z",
                        action="store_true", default=False,
                        help="delete volume on instance shutdown")
    parser.add_argument("--provisioned-iops", "-p",
                        type=int, default=None,
                        help="Provisioned IOPS to setup volume with")
    parser.add_argument("--device", "-d",
                        type=str, default="/dev/sdh",
                        help="Device to attach the volume")
    parser.add_argument("--mount-dir", "-m",
                        type=str, default="/mnt/data",
                        help="Mount point for the volume, by default /mnt/data")
    parser.add_argument("--mount-options",
                        type=str, default=None,
                        help="Mount options")
    parser.add_argument("--size", "-s",
                        type=int, default=None,
                        help="Volume size. Doesn't mean that FS will be resized"
                        "automatically if volume is created from snapshot.")
    parser.add_argument("--format-fs",
                        type=str, default="xfs",
                        help="FS to format the volume with, by default XFS")
    parser.add_argument("--loglevel",
                        type=str, default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL',
                                 'debug', 'info', 'warning', 'error', 'critical'],
                        help="set output verbosity level")

    args = parser.parse_args()

    # Print help on missing arguments
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s: %(message)s',
                        level=getattr(logging, args.loglevel.upper(), None))
    # Output will be like: "2013-05-12 13:00:09,934 root WARNING: some warning text"
    logging.info("====================================================")
    logging.info("Started setup of volume")

    # Provides AWS_ID and AWS_SECRET for Boto connection
    # NOTE: we rely on:
    #   * ~/.boto or /etc/boto.cfg config files or
    #   * AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environmental variables
    # to automatically provide credentials to boto.
    try:
        conn = boto.ec2.connect_to_region(get_instance_metadata()["placement"]["availability-zone"][:-1])
    except:
        logging.exception("Failure getting EC2 API connection")
        sys.exit(1)

    try:
        CreateAndMountEBSVolume(conn).setup_volume(snapshot_id=args.snapshot_id,
                                                   snapshot_description=args.snapshot_description,
                                                   device=args.device,
                                                   mount_dir=args.mount_dir,
                                                   mount_options=args.mount_options,
                                                   format_fs=args.format_fs,
                                                   size=args.size,
                                                   provisioned_iops=args.provisioned_iops,
                                                   delete_on_shutdown=args.delete_on_shutdown)
    except:
        logging.exception("Failure setting up the volume")
        sys.exit(1)
    else:
        logging.info("Finished setup of volume")

    logging.info("====================================================")

if __name__ == '__main__':
    main()
