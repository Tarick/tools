#!/usr/bin/env python26

import os,sys
import boto
import logging
import argparse

def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--verbose", help="maximum verbosity",
                       action="store_true")
    parser.add_argument("--snapshot", "-S", metavar="SNAPSHOT_ID",
                       help="Snapshot ID to use for volume")
    parser.add_argument("--snapshot-description", "-t", type=int, metavar="SNAPSHOT_DESCRIPTION",
                       help="Most recent snapshot descriptsion to use for volume.")
    parser.add_argument("--delete-on-shutdown", "-z", type=bool, metavar="DELETE_ON_SHUTDOWN",
                       default=False, action="store_true",
                       help="delete on instance shutdown")
    parser.add_argument("--provisioned-iops", "-p", type=int, metavar="PROVISIONED_IOPS",
                       help="Provisioned IOPS to setup volume with")
    parser.add_argument("--device", "-d", metavar="DEVICE", default="/dev/sdh",
                       help="Device to attach volume")
    parser.add_argument("--mount-point", "-m", metavar="MOUNT_POINT", default="/mnt/data",
                       help="Mount point for volume")
    parser.add_argument("--size", "-s", type=int, metavar="VOLUME_SIZE", default=10,
                       help="Size for the volume")
    parser.add_argument("--instance", "-i", metavar="INSTANCE_ID",
                       help="Instance to attach to, default to the instance where we are running script on")
    parser.add_argument("--loglevel", type=str, choices=['DEBUG','INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                       default='INFO',
                       help="set output verbosity level")

    args = parser.parse_args()

    loglevel = "logging." + args.loglevel

    if args.verbose = True:
        print("Verbosity is turned on")
        loglevel = "logging.DEBUG"

    logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s: %(message)s', level=loglevel)
    # Output will be like: "013-05-12 13:00:09,934 root WARNING: some warning text"
    logging.debug("====================================================")
    logging.debug("Program started")
    logging.debug("value x is %s", somestringvariable)
    logging.error("Failure connecting to %s, retrying in %d minute(s)", (url,RETRY)
    logging.critical("ABORT")

    # Provides AWS_ID and AWS_SECRET
    try:
        import aws_auth
    except Exception, ex:
        logging.exception("Failure importing AWS credentials")
        sys.exit(1)

if __name__ == '__main__':
    main()
