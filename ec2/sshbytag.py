#!/usr/bin/env python

import sys
import boto
import subprocess
import argparse

if sys.version_info < (2, 6):
    if __name__ == "__main__":
        sys.exit("Error: we need python >= 2.6.")
    else:
        raise Exception("we need python >= 2.6")

username1 = "ubuntu"
username2 = "ec2-user"


def main():

    # Parse all arguments
    parser = argparse.ArgumentParser(description="Make ssh connection"
                                     "to the internal ip address of the instance"
                                     "based on provided Name or Environment and Role tags")
    parser.add_argument("tags",
                        nargs='*',
                        default=None,
                        help="Tag of environment and role to connect to, e.g. dev dbmst")
    args = parser.parse_args()
    # Print help on missing arguments
    if len(sys.argv) == 0:
        parser.print_help()
        sys.exit(1)

    con = boto.connect_ec2()
    matched_instances = []
    # Processing depends on whether we supply one tag (use for Name) or two
    # (use for Env and Role tags)
    if len(sys.argv) == 2:
        instances = con.get_only_instances(filters={'instance-state-name': 'running'})
        name = args.tags[0]
        for instance in instances:
            if "Name" not in instance.tags.keys():
                continue
            if name in instance.tags.get("Name"):
                matched_instances.append(instance)
    else:
        env, role = args.tags
        instances = con.get_only_instances(filters={'instance-state-name': 'running',
                                           'tag:Environment': env})
        for instance in instances:
            if "Role" not in instance.tags.keys():
                continue
            if role in instance.tags.get("Role"):
                matched_instances.append(instance)

    if not matched_instances:
        print("No instances found")
        sys.exit(1)

    if len(matched_instances) == 1:
        connect_instance = matched_instances[0]
    else:
        print("Mulitple instance found:")
        number = 0
        for instance in matched_instances:
            number += 1
            print("%d) %s: Name: %s, Roles: %s") % (number, instance.id,
                                                    instance.tags.get("Name"),
                                                    instance.tags.get("Role"))
        while True:
            choice = input("Enter number: ")
            if choice > len(matched_instances):
                print("WARN: Incorrect choice, do again")
            else:
                break
        connect_instance = matched_instances[choice - 1]

    ip_address = connect_instance.private_ip_address
    print("Connecting to %s address %s") % (connect_instance.tags.get("Name"), ip_address)
    try:
        subprocess.check_call("ssh " + "@".join([username1, ip_address]), shell=True)
    except:
        print("ERROR: failure running with %s user, trying %s") % (username1, username2)
        subprocess.check_call("ssh " + "@".join([username2, ip_address]), shell=True)

if __name__ == '__main__':
    main()
