import boto3
import os
import json
import argparse
import sys
import glob
from datetime import datetime
from pprint import pprint


def process_args():
    """ Process CLI arguments """

    arguments = ["rollback", "migrate", "backup"]

    if len(sys.argv) != 2:
        print_help()

    if sys.argv[1] not in arguments:
        print_help()

    arg = [x for x in arguments if x in sys.argv[1]][0]

    return arg


def print_help():
    """ Prints help and example CLI commands """

    print("""You must specify one of these arguments:

    backup
    migrate
    rollback

    Example #1: python tgw_migrate.py backup
    Example #2: python tgw_migrate.py migrate
    Example #3: python tgw_migrate.py rollback

    """)
    sys.exit()


def rollback():
    """ Rolls back route table configuration based on backup file """

    gw_types = [
        "VpcPeeringConnectionId",
        "TransitGatewayId",
        "GatewayId",
        "LocalGatewayId",
        "NatGatewayId"
    ]

    print("You selected rollback...rolling back now")

    backup_files = glob.glob('backups/*.json')
    
    for i, file in enumerate(backup_files):
        print(f"{i}. {file}")
    
    try:
        selection = int(input("Enter selection: "))
        backup_filename = backup_files[selection]
    except:
        print("Try again, perhaps you typed an invalid selection")
        return None
    
    print(f"Backing up routes from {backup_filename}...")

    f = open(backup_filename, 'r')
    backup_data = json.load(f)

    route_list = []

    for routes in backup_data:
        for route in routes['routes']:
            #print(route.keys())
            rt_entry = {}
            rt_entry['DestinationCidrBlock'] = route['DestinationCidrBlock']
            rt_entry['RouteTableId'] = routes['table']
            for gw_type in gw_types:
                if gw_type in route.keys():
                    print(route.values())
                    if "local" in route.values():
                        print("skipping local route")
                        break
                    else:
                        next_hop = {gw_type:route[gw_type]}
                        print(next_hop)
                        rt_entry.update(next_hop)
                        route_list.append(rt_entry)

    print(route_list)
                        
    for entry in route_list:
        print(entry)
        session = boto3.Session()
        src_client = session.client("ec2")
        response = src_client.replace_route(**(entry))

    return None


def migrate():
    """ This is a test function for arg selection """

    print("You selected migrate")
    return None


def tgw_migrate():
    """ This function migrates the VPC route table next-hops to the TGW """

    # set the tgw id from env or prompt user for it
    tgw_id = os.environ.get('TGW_ID')
    if not tgw_id:
        tgw_id = input("Please enter tgw id: ")

    # define tag for matching which Route Tables to modify
    tag = {'Key': 'migrate', 'Value': 'true'}

    # get all the route tables
    session = boto3.Session()
    src_client = session.client('ec2')
    response = src_client.describe_route_tables()
    route_tables = response['RouteTables']

    # initialize updated route list
    mod_routes = []

    # backup_routes()
    # initlize backup file and list
    # backup_file = open('route_backup.json', 'w')
    # backup_list = []

    for table in route_tables:

        # we only want route tables with the matching tag
        if tag in table['Tags']:

            # backup routes first
            '''
            backup_dict = {}
            backup_dict['table'] = table['RouteTableId']
            backup_dict['routes'] = table['Routes']
            backup_list.append(backup_dict)
            '''
            for route in table['Routes']:

                # only grab routes that are not local
                if 'local' not in route.values():

                    # build new dict for creating new routes
                    new_route = {}            
                    new_route['table'] = table['RouteTableId']
                    new_route['dest'] = route['DestinationCidrBlock']

                    # add route to list of routes to be modified
                    mod_routes.append(new_route)

    #json.dump(backup_list, backup_file)
    #backup_file.close

    '''
    cli command for reference:
    aws ec2 replace-route --route-table-id rtb-22574640 
    --destination-cidr-block 10.0.0.0/16 --gateway-id vgw-9a4cacf3
    '''

    # for each route in the list, replace it and use TGW as next-hop
    for route in mod_routes:
        session = boto3.Session()
        src_client = session.client("ec2")
        response = src_client.replace_route(
            DestinationCidrBlock = route['dest'],
            RouteTableId = route['table'],
            TransitGatewayId = tgw_id
            )
        #pprint(response)


def backup_routes():
    """ Backs up route tables that have the migrate tag """

    try:
        os.mkdir("backups")
    except OSError:
        print ("Backup folder exists or other error...continuing...")

    # define tag for matching which Route Tables to modify
    tag = {'Key': 'migrate', 'Value': 'true'}

    # get all the route tables
    session = boto3.Session()
    src_client = session.client('ec2')
    response = src_client.describe_route_tables()
    route_tables = response['RouteTables']

    # initialize updated route list
    mod_routes = []

    # initlize backup file and list
    now = datetime.now()
    date_time = now.strftime("%Y%m%d-%H%M%S")
    filename = 'backups/route_backups_' + date_time + '.json'  
    backup_file = open(filename, 'w')
    backup_list = []

    for table in route_tables:

        # we only want route tables with the matching tag
        if tag in table['Tags']:

            # backup routes first
            backup_dict = {}
            backup_dict['table'] = table['RouteTableId']
            backup_dict['routes'] = table['Routes']
            backup_list.append(backup_dict)

    json.dump(backup_list, backup_file)
    backup_file.close
    
    print("\nBackup completed.\n")

    return None

if __name__ == '__main__':
    arg = process_args()
    if arg == "backup":
        backup_routes()
    if arg == "migrate":
        backup_routes()
        tgw_migrate()
    elif arg == "rollback":
        rollback()