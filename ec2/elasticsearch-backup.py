#!/usr/bin/env python

import sys
import requests
import json
import logging
import argparse
import datetime
from boto.utils import get_instance_identity
from lockfile import FileLock

if sys.version_info < (2, 6):
    if __name__ == "__main__":
        sys.exit("Error: we need python >= 2.6.")
    else:
        raise Exception("we need python >= 2.6")

# Global variables
ES_LOCAL_URL = 'http://127.0.0.1:9200'
# Requests timeout in seconds
REQUESTS_TIMEOUT = 30


def es_leadership_check():
    '''The simple check to verify if this node is the leader
       in the cluster and can run the script by schedule with many nodes
       available.  '''

    # Get info through API
    es_state_master_url = ES_LOCAL_URL + '/_cluster/state/master_node'
    es_state_local_url = ES_LOCAL_URL + '/_nodes/_local/nodes'
    try:
        master_state = requests.get(es_state_master_url,
                                    timeout=REQUESTS_TIMEOUT).json()
        local_state = requests.get(es_state_local_url,
                                   timeout=REQUESTS_TIMEOUT).json()
    except:
        logging.exception("Failure getting ES status information through API")
        raise
    # Do research if we're master node
    try:
        local_node_name = local_state['nodes'].keys()[0]
        master_node_name = master_state['master_node']
    except:
        logging.exception("Failure parsing node data")
        raise
    # Finally decide if we passed
    if local_node_name == master_node_name:
        logging.debug("We're master node, ID %s matches"
                      % (master_node_name))
        return True
    else:
        logging.debug("We're NOT master node, master ID is %s"
                      % (master_node_name))
        return False


def create_repository(args):
    '''Initial create of repository'''
    create_repository_url = '/'.join([ES_LOCAL_URL, '_snapshot',
                                      args.repository])
    # Get the region from the instance
    try:
        instance_metadata = get_instance_identity()
        instance_region = instance_metadata['document']['region']
    except:
        logging.exception("Failure getting EC2 instance data")
        raise
    # Repository data
    create_repository_data = {
        "type": "s3",
        "settings": {
            "bucket": args.s3_bucket,
            "region": instance_region,
            "base_path": args.s3_path
        }
    }
    try:
        headers = {'content-type': 'application/json'}
        create_repository_request = requests.put(create_repository_url,
                                                 data=json.dumps(create_repository_data),
                                                 headers=headers,
                                                 timeout=REQUESTS_TIMEOUT)
        create_repository_request.raise_for_status()
    except:
        logging.exception("Failure creating repository")
        raise

    repository_ = ("Created or updated repository: %s" % args.repository)
    return repository_


def delete_repository(args):
    '''Deletion of repository'''
    delete_repository_url = '/'.join([ES_LOCAL_URL, '_snapshot',
                                      args.repository])
    # Get the region from the instance
    try:
        delete_repository_request = requests.delete(delete_repository_url,
                                                    timeout=REQUESTS_TIMEOUT)
        delete_repository_request.raise_for_status()
    except:
        logging.exception("Failure deleting repository")
        raise

    return "Deleted repository: %s" % args.repository


def list_snapshots(args):
    '''Wrapper for list ES snapshot function to handle args passing'''
    snapshots = list_es_snapshots(args.repository)
    # Pretty print
    if snapshots:
        snapshots_info = json.dumps(snapshots,
                                    sort_keys=True,
                                    indent=4,
                                    separators=(',', ': '))
    return snapshots_info


def list_es_snapshots(repository):
    '''List avaliable snapshots'''
    # Get info through API
    repository_info_url = '/'.join([ES_LOCAL_URL, '_snapshot',
                                    repository, '_all'])
    try:
        snapshots_list = requests.get(repository_info_url,
                                      timeout=REQUESTS_TIMEOUT)
        snapshots_list.raise_for_status()
    except:
        logging.exception("Failure getting ES status information through API")
        raise
    if snapshots_list:
        return snapshots_list.json()['snapshots']


def list_repositories(args):
    '''List avaliable repositories'''
    # Get info through API
    repository_info_url = '/'.join([ES_LOCAL_URL, '_snapshot'])
    try:
        repositories_info = requests.get(repository_info_url,
                                         timeout=REQUESTS_TIMEOUT)
        repositories_info.raise_for_status()
    except:
        logging.exception("Failure getting ES status information through API")
        raise
    # Print data
    if repositories_info.json():
        repositories_list = json.dumps(repositories_info.json(),
                                       sort_keys=True,
                                       indent=4,
                                       separators=(',', ': '))
    else:
        repositories_list = False
    return repositories_list


def create_snapshot(args):
    '''Trigger snapshot of ES'''
    # Check if we're the leader to do this job
    if args.check_leadership:
        if not es_leadership_check():
            logging.warn("Our instance isn't suitable"
                         "to make snapshots in the cluster")
            return False
    # If not defined snapshot name,
    # then default snapshot naming uses repository name plus date-time
    if not args.snapshot_name:
        snapshot_timestamp = datetime.datetime.today().strftime('%Y-%m-%d_%H:%M:%S')
        snapshot_name = ".".join([args.repository, snapshot_timestamp])
        logging.debug("Using auto created snapshot name %s" % (snapshot_name))
    else:
        snapshot_name = args.snapshot_name
    snapshot_url = "/".join([ES_LOCAL_URL, '_snapshot', args.repository,
                             snapshot_name])
    # Trigger snapshot
    try:
        trigger_snapshot = requests.put(snapshot_url,
                                        timeout=REQUESTS_TIMEOUT)
        trigger_snapshot.raise_for_status()
    except:
        logging.exception("Failure triggering snapshot through API")
        raise
    return 'Triggered snapshot with name: %s' % (snapshot_name)


def restore_snapshot(args):
    '''Trigger snapshot restore to ES. Note - existing index should be closed before'''
    # Check if we're the leader to do this job
    if args.check_leadership:
        if not es_leadership_check():
            logging.warn("Our instance isn't suitable"
                         "to make snapshots in the cluster")
            return False
    restore_url = "/".join([ES_LOCAL_URL, '_snapshot', args.repository,
                            args.snapshot_name, '_restore']) + '?wait_for_completion=true'

    # Restore
    try:
        logging.info("Starting restore of snapshot data from repo."
                     "Note: this is the long process, the script will exit once it finished")
        restore_snapshot = requests.post(restore_url)
        restore_snapshot.raise_for_status()
    except:
        logging.exception("Failure triggering snapshot restore through API")
        raise
    return 'Finished snapshot restore with name: %s' % (args.snapshot_name)


def delete_snapshot(args):
    '''Wrapper around real delete snapshot function
    to handle args passing'''
    # Check if we're the leader to do this job
    if args.check_leadership:
        if not es_leadership_check():
            logging.warn("Our instance isn't suitable"
                         "to make snapshots in the cluster")
            return False
    return delete_es_snapshot(args.repository, args.snapshot_name)


def delete_es_snapshot(repository, snapshot_name):
    '''Delete snapshot'''
    snapshot_delete_url = "/".join([ES_LOCAL_URL, '_snapshot', repository,
                                    snapshot_name]) + '?wait_for_completion=true'
    # Trigger snapshot deletion and wait for completion.
    try:
        trigger_snapshot_deletion = requests.delete(snapshot_delete_url)
        trigger_snapshot_deletion.raise_for_status()
    except:
        logging.exception("Failure deleting snapshot through API")
        raise
    return 'Deleted snapshot with name: %s' % (snapshot_name)


def cleanup_snapshots(args):
    '''Delete older than retention age snapshots with specified tags.'''
    # Check if we're the leader to do this job
    if args.check_leadership:
        if not es_leadership_check():
            logging.warn("Our instance isn't suitable"
                         "to make snapshots in the cluster")
            return False
    # Get the list of available snapshots
    snapshots = list_es_snapshots(args.repository)
    logging.debug("Snapshots list: %s" % (snapshots))
    # Delete stale snapshots older than retention date
    if snapshots:
        # Retention date for older snapshots
        retention_date = datetime.datetime.today() - datetime.timedelta(days=args.retention)
        logging.debug("Retention date: %s" % (retention_date))
        stale_snapshots = [snapshot for snapshot in snapshots
                           if datetime.datetime.strptime(snapshot['start_time'],
                                                         '%Y-%m-%dT%H:%M:%S.%fZ') < retention_date]
        logging.info("Stale snapshots that are older "
                     "than retention date %s: %s"
                     % (retention_date, stale_snapshots))
        for snapshot in stale_snapshots:
            try:
                delete_es_snapshot(args.repository, snapshot['snapshot'])
            except:
                logging.exception("Failure deleting snapshot %s through API" %
                                  (snapshot['snapshot']))
                raise
            logging.info("Deleted snapshot: %s" % snapshot['snapshot'])
    else:
        stale_snapshots = None

    return "Deleted stale snapshots: %s" % ([snapshot['snapshot']
                                            for snapshot in stale_snapshots])


def argument_parser():
    # Parse all arguments
    epilog = "EXAMPLE: %(prog)s create_snapshot --repository elasticsearch-dev"
    description = "Manage backup of ES cluster indices to S3 and restore"

    parser = argparse.ArgumentParser(description=description, epilog=epilog)
    subparsers = parser.add_subparsers(help='valid subcommands')
    # Here goes a list of subcommands, that call related functions
    parser_create_snapshot = subparsers.add_parser('create_snapshot',
                                                   help='Trigger ES to create snapshot')
    parser_create_snapshot.add_argument("--repository", "-r",
                                        type=str,
                                        required=True,
                                        help="Registered in ES cluster repository for snapshots")
    parser_create_snapshot.add_argument("--snapshot-name", "-s",
                                        type=str,
                                        required=False,
                                        help="Custome name to make snapshot")
    parser_create_snapshot.add_argument("--check-leadership",
                                        action='store_true',
                                        required=False,
                                        help="Checks if we're allowed to do the job with multiple nodes available")
    parser_create_snapshot.set_defaults(script_action=create_snapshot)

    parser_restore_snapshot = subparsers.add_parser('restore_snapshot',
                                                    help='Restore index to instance/cluster from repository snapshot in S3')
    parser_restore_snapshot.add_argument("--repository", "-r",
                                         type=str,
                                         required=True,
                                         help="Registered in ES cluster repository for snapshots")
    parser_restore_snapshot.add_argument("--snapshot-name", "-s",
                                         type=str,
                                         required=True,
                                         help="Snapshot name to restore")
    parser_restore_snapshot.add_argument("--check-leadership",
                                         action='store_true',
                                         required=False,
                                         help="Checks if we're allowed to do the job with multiple nodes available")
    parser_restore_snapshot.set_defaults(script_action=restore_snapshot)

    parser_list_repositories = subparsers.add_parser('list_repositories',
                                                     help='List available repositories')
    parser_list_repositories.set_defaults(script_action=list_repositories)

    parser_list_snapshots = subparsers.add_parser('list_snapshots',
                                                  help='List available snapshots')
    parser_list_snapshots.add_argument("--repository", "-r",
                                       type=str,
                                       required=True,
                                       help="Registered in ES cluster repository for snapshots")
    parser_list_snapshots.set_defaults(script_action=list_snapshots)

    parser_create_repository = subparsers.add_parser('create_repository',
                                                     help='Initial create of repository')
    parser_create_repository.add_argument("--repository", "-r",
                                          type=str,
                                          required=True,
                                          help="Repository name for snapshots")
    parser_create_repository.add_argument("--s3-bucket",
                                          type=str,
                                          required=True,
                                          help="Created S3 BUCKET_NAME")
    parser_create_repository.add_argument("--s3-path",
                                          type=str,
                                          default="/",
                                          help="Path within S3 BUCKET_NAME if any, e.g. ROLE/ENV")
    parser_create_repository.set_defaults(script_action=create_repository)

    parser_delete_repository = subparsers.add_parser('delete_repository',
                                                     help='Initial delete of repository')
    parser_delete_repository.add_argument("--repository", "-r",
                                          type=str,
                                          required=True,
                                          help="Repository name for snapshots")
    parser_delete_repository.set_defaults(script_action=delete_repository)

    parser_cleanup_snapshots = subparsers.add_parser('cleanup_snapshots',
                                                     help='Cleanup old snapshots with retention period')
    parser_cleanup_snapshots.add_argument("--check-leadership",
                                          action='store_true',
                                          required=False,
                                          help="Checks if we're allowed to do the job with multiple nodes available")
    parser_cleanup_snapshots.add_argument("--repository", "-r",
                                          type=str,
                                          required=True,
                                          help="Registered in ES cluster repository for snapshots")
    parser_cleanup_snapshots.add_argument("--retention",
                                          type=int, default=30,
                                          help="Delete snapshots older than specified"
                                               "retention days period")
    parser_cleanup_snapshots.set_defaults(script_action=cleanup_snapshots)

    parser_delete_snapshot = subparsers.add_parser('delete_snapshot',
                                                   help='Delete specified snapshot')
    parser_delete_snapshot.add_argument("--repository", "-r",
                                        type=str,
                                        required=True,
                                        help="Registered in ES cluster repository for snapshots")
    parser_delete_snapshot.add_argument("--snapshot-name", "-s",
                                        type=str,
                                        required=False,
                                        help="Snapshot name to delete")
    parser_delete_snapshot.add_argument("--check-leadership",
                                        action='store_true',
                                        required=False,
                                        help="Checks if we're allowed to do the job with multiple nodes available")
    parser_delete_snapshot.set_defaults(script_action=delete_snapshot)

    parser.add_argument("--loglevel",
                        type=str, default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING',
                                 'ERROR', 'CRITICAL',
                                 'debug', 'info', 'warning',
                                 'error', 'critical'],
                        help="set output verbosity level")

    # Parse all arguments
    args = parser.parse_args()
    return args


def main():
    args = argument_parser()
    logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s: %(message)s',
                        level=getattr(logging, args.loglevel.upper(), None))

    # Use function accordingly to action specified
    try:
        output = args.script_action(args)
        if output:
            print(output)
    except:
        print("ERROR: failure running with script action")
        print("ERROR:", sys.exc_info())
        sys.exit(-1)


if __name__ == '__main__':
    # Initialise locking
    lockfile = FileLock("/var/lock/elasticsearch-backup.lock")
    if lockfile.is_locked():
        print("ERROR: /var/lock/elasticsearch-backup.lock is already locked,"
              "probably we're already running")
        sys.exit(1)
    else:
        with lockfile:
            main()
