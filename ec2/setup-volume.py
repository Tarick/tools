#!/usr/bin/env python26

import os,sys
import boto
import logging
import argparse

def main():
    parser = argparse.ArgumentParser()
    # Optional
    parser.add_argument("--verbose", help="maximum verbosity",
                       action="store_true")
    parser.add_argument("--snapshot", "-t", type=int, metavar="SOCKET_TIMEOUT", default=10,
                       help="set timeout for network connection")
    parser.add_argument("--snapshot-description", "-t", type=int, metavar="SOCKET_TIMEOUT", default=10,
                       help="set timeout for network connection")
    parser.add_argument("--snapshot-description", "-t", type=int, metavar="SOCKET_TIMEOUT", default=10,
                       help="set timeout for network connection")
    parser.add_argument("--snapshot-description", "-t", type=int, metavar="SOCKET_TIMEOUT", default=10,
                       help="set timeout for network connection")
    parser.add_argument("--snapshot-description", "-t", type=int, metavar="SOCKET_TIMEOUT", default=10,
                       help="set timeout for network connection")
    parser.add_argument("--snapshot-description", "-t", type=int, metavar="SOCKET_TIMEOUT", default=10,
                       help="set timeout for network connection")
    parser.add_argument("--size", "-s", type=int, metavar="VOLUME_SIZE", default=10,
                       help="Size for the volume")
    parser.add_argument("--loglevel", type=str, choices=['DEBUG','INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                       default='INFO',
                       help="set output verbosity level")
    # This one is required even if is an option. Please avoid such usage.
    parser.add_argument("--run", help="actually run the script, safe check", required=True)

    # This one is required positional argument when calling program
    parser.add_argument("importfile", type=file)

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
