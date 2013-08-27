#!/usr/bin/env python

import boto
import logging
import argparse
import sys

if sys.version_info < (2, 6):
    if __name__ == "__main__":
        sys.exit("Error: we need python >= 2.6.")
    else:
        raise Exception("we need python >= 2.6")


def main():

    # Parse all arguments
    parser = argparse.ArgumentParser(description="Create and mount EBS volume to the instance")
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
    parser.add_argument("--size", "-s", type=int, metavar="VOLUME_SIZE", default=10,
                        help="Volume size, by default 10G if created from scratch")
    parser.add_argument("--instance", "-i", metavar="INSTANCE_ID",
                        help="Instance ID to attach to, by default the instance where we are running the script on")
    parser.add_argument("--verbose", help="maximum verbosity",
                        action="store_true")
    parser.add_argument("--loglevel", type=str, choices=['DEBUG','INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        default='INFO',
                        help="set output verbosity level")

    args = parser.parse_args()

    loglevel = "logging." + args.loglevel

    if args.verbose = True:
        print("Verbosity is turned on")
        loglevel = "logging.DEBUG"

    logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s: %(message)s', level=loglevel)
    # Output will be like: "13-05-12 13:00:09,934 root WARNING: some warning text"
    logging.debug("====================================================")
    logging.debug("Program started")

    # Provides AWS_ID and AWS_SECRET
    try:
        import aws_auth
    except Exception, ex:
        logging.exception("Failure importing AWS credentials")
        sys.exit(1)

if __name__ == '__main__':
    main()
