#!/usr/bin/env python
import argparse
from itertools import chain
import subprocess
import sys

import boto3

if sys.version_info < (2, 7):
    if __name__ == "__main__":
        sys.exit("Error: we need python >= 2.7.")
    else:
        raise Exception("we need python >= 2.7")


def main():
    # Parse all arguments
    parser = argparse.ArgumentParser(description="Make ssh connection to the internal ip address "
                                     "of the instance and optionally run command based on provided "
                                     "Name or Environment and Role tags")
    parser.add_argument("tags",
                        nargs='*',
                        default=None,
                        help="Tag of environment and role to client.ect to, e.g. dev dbmst")
    parser.add_argument("--username", "-u",
                        type=str,
                        required=False,
                        default="ec2-user",
                        help="Username to client.ect with")
    parser.add_argument("--command", "-c",
                        type=str,
                        required=False,
                        default="",
                        help="Run command instead of ssh")
    parser.add_argument("--aws-service", "-s",
                        type=str,
                        required=False,
                        default='ec2',
                        choices=['ec2', 'ecs'],
                        help="Use AWS service")

    args = parser.parse_args()
    # Print help on missing arguments
    if len(sys.argv) == 0:
        parser.print_help()
        sys.exit(1)

    if args.aws_service == "ec2":
        handle_ec2_instances(args)
    elif args.aws_service == "ecs":
        handle_ecs_instances(args)


def handle_ec2_instances(args):
    client = boto3.client("ec2")
    # Processing depends on whether we supply one tag (use for Name) or two
    # (use for Env and Role tags)
    if len(args.tags) == 1:
        response = client.describe_instances(Filters=[{'Name': 'instance-state-name',
                                                       'Values': ['running']}])
        tag_name = 'Name'
        tag_value = args.tags[0]
    else:
        env, role = args.tags
        response = client.describe_instances(Filters=[{'Name': 'instance-state-name',
                                                       'Values': ['running']},
                                                      {"Name": "tag:Environment",
                                                       "Values": [env]}])
        tag_name = 'Role'
        tag_value = role

    instances = chain.from_iterable([reservation['Instances']
                                    for reservation in response['Reservations']])
    matched_instances = get_instances_by_tag(instances, tag_name, tag_value)
    if not matched_instances:
        print("No instances found")
        sys.exit(0)

    if len(matched_instances) == 1:
        connect_instances_addresses = [matched_instances[0]['PrivateIpAddress']]
    else:
        print("Mulitple instance found:")
        number = 0
        for instance in matched_instances:
            number += 1
            tags = {tag['Key']: tag['Value'] for tag in instance['Tags']}
            print("{choice:>3}) {instance_id:<12} {private_address:<15} "
                  "{name:<20} {role:<20} {function: <20}".format(
                    choice=number,
                    instance_id=instance['InstanceId'],
                    private_address=instance['PrivateIpAddress'],
                    name=tags.get('Name', ''),
                    role=tags.get('Role', ''),
                    function=tags.get('Function', '')))
        while True:
            choice = raw_input("Choose number or press Enter to connect to each in cycle: ")
            if choice == '':
                connect_instances_addresses = [instance['PrivateIpAddress'] for instance
                                               in matched_instances]
                break
            elif int(choice) > len(matched_instances):
                print("WARN: Incorrect choice, do again")
            else:
                connect_instances_addresses = [matched_instances[int(choice) - 1]
                                               ['PrivateIpAddress']]
                break
    for instance_ip_address in connect_instances_addresses:
        connect_to_ec2_instance(instance_ip_address, args.username, args.command)


def handle_ecs_instances(args):
    client = boto3.client("ecs")
    cluster_arns = client.list_clusters()['clusterArns']

    if len(args.tags) == 1:
        role = args.tags[0]
        matched_clusters_arns = cluster_arns
    else:
        env, role = args.tags
        matched_clusters_arns = [cluster_arn for cluster_arn in cluster_arns
                                 if "ecs-{0}".format(env) in cluster_arn]

    all_tasks_from_clusters = chain.from_iterable(
        [client.describe_tasks(cluster=cluster_arn,
                               tasks=client.list_tasks(cluster=cluster_arn)['taskArns']
                               )['tasks'] for cluster_arn in matched_clusters_arns])
    matched_instances = get_instances_by_task(all_tasks_from_clusters, role, client)
    if not matched_instances:
        print("No instances found")
        sys.exit(0)

    if len(matched_instances) == 1:
        key, values = matched_instances.popitem()
        connect_instances_addresses = [values['instance']['PrivateIpAddress']]
    else:
        print("Mulitple instance found:")
        number = 0
        for instance_data in matched_instances.itervalues():
            instance = instance_data['instance']
            number += 1
            tags = {tag['Key']: tag['Value'] for tag in instance['Tags']}
            print("{choice:>3}) {instance_id:<20} {private_address:<15} "
                  "{name:<20} {role:<40} {cluster: <30}".format(
                    choice=number,
                    instance_id=instance['InstanceId'],
                    private_address=instance['PrivateIpAddress'],
                    name=tags.get('Name', ''),
                    role=",".join(instance_data['role']),
                    cluster=tags.get('ECSCluster', '')))
        while True:
            choice = raw_input("Choose number or press Enter to connect to each in cycle: ")
            if choice == '':
                connect_instances_addresses = [instance_data['instance']['PrivateIpAddress']
                                               for instance_data in matched_instances.iteritems()]
                break
            elif int(choice) > len(matched_instances):
                print("WARN: Incorrect choice, do again")
            else:
                connect_instances_addresses = [matched_instances.values()
                                               [int(choice) - 1]['instance']['PrivateIpAddress']]
                break
    for instance_ip_address in connect_instances_addresses:
        connect_to_ec2_instance(instance_ip_address, args.username, args.command)


def connect_to_ec2_instance(instance_ip_address, username, command):
    print("Connecting to address %s" % (instance_ip_address))
    ssh_connection_command = "ssh " + username + "@" + instance_ip_address + " " + command
    try:
        subprocess.check_call(ssh_connection_command, shell=True)
    except:
        print("ERROR: failure running with %s user") % (username)
        raise


def get_instances_by_tag(instances, tag_name, tag_value):
    matched_instances = []
    for instance in instances:
        for tag in instance['Tags']:
            if tag['Key'] == tag_name:
                if tag_value in tag['Value']:
                    matched_instances.append(instance)
                    break
                else:
                    break
    return matched_instances


def get_instances_by_task(tasks, role, client):
    matched_instances = {}
    ec2_client = boto3.client("ec2")
    for task in tasks:
        for container in task['containers']:
            if role in container['name']:
                container_instance = client.describe_container_instances(
                    cluster=task['clusterArn'],
                    containerInstances=[task['containerInstanceArn']])['containerInstances'][0]
                container_instance_id = container_instance['ec2InstanceId']
                if container_instance_id in matched_instances:
                    matched_instances[container_instance_id]['role'].add(container['name'])
                else:
                    instance = ec2_client.describe_instances(
                        InstanceIds=[container_instance_id])['Reservations'][0]['Instances'][0]
                    matched_instances[container_instance_id] = {'instance': instance,
                                                                'role': set([container['name']])}
    return matched_instances

if __name__ == '__main__':
    main()
