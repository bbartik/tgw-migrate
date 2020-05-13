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

    arguments = ["rollback", "migrate", "backup", "tag", "check"]
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
    tag
    migrate
    rollback
    check

    Example #1: python tgw_migrate.py backup
    Example #2: python tgw_migrate.py tag
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
                    if "local" in route.values():
                        print("skipping local route")
                        break
                    else:
                        next_hop = {gw_type:route[gw_type]}
                        print(next_hop)
                        rt_entry.update(next_hop)
                        route_list.append(rt_entry)
                      
    for entry in route_list:
        print(entry)
        session = boto3.Session()
        src_client = session.client("ec2")
        response = src_client.replace_route(**(entry))

    return None


def add_migrate_tag():
    """ Adds "migrate" tag to the route tables """

    session = boto3.Session()
    src_client = session.client('ec2')
    vpc_response = src_client.describe_vpcs()

    for vpc in vpc_response['Vpcs']:
        vpc_name = [x['Value'] for x in vpc['Tags'] if 'Name' in x['Key']][0]
        vpc_id = str(vpc['VpcId'])
        msg = "Add Migrate tags to Route Tables for {0:s}? (y/n)[n] ".format(vpc_name)
        answer = input(msg)
        if answer == 'y':
            print("\nOk...")
    
            # only retrieve route tables from specific vpc
            filter = {'Name':'vpc-id','Values': [vpc_id]},
            rt_response = src_client.describe_route_tables(Filters=filter)

            # add tags to each route table
            for route_table in rt_response['RouteTables']:
    
                rt_id = route_table['RouteTableId']
                src_client.create_tags(Resources=[rt_id], Tags=[{'Key': 'migrate', 'Value': 'true'}])

                # use list comprehension to get table name
                table_name = [x['Value'] for x in route_table['Tags'] if 'Name' in x['Key']]
                print("Tag added to Route Table {0:s}.".format(table_name[0]))

    print('\n*** Route table tagging completed ***\n')


def check_tag(**kwargs):
    """ 
    This function gets the route tables with the migrate tag and 
    returns prints it if called with "check" option or returns route
    list to the migrate function
    """
      
    # set the tgw id from env or prompt user for it
    tgw_id = os.environ.get('TGW_ID')
    if not tgw_id:
        tgw_id = input("Please enter tgw id: ")

    # set filter for query
    filters = [{'Name':'tag:migrate', 'Values':['true']}]

    # get all the route tables with migrate tag set to true
    session = boto3.Session()
    src_client = session.client('ec2')
    response = src_client.describe_route_tables(Filters=filters)
    route_tables = response['RouteTables']

    # print tables and also assemble route lists for later printing
    route_list = []
    table_name_list = []

    for table in route_tables:
        table_name = [x['Value'] for x in table['Tags'] if 'Name' in x['Key']][0]
        table_name_list.append(table_name)
        for route in table['Routes']:
            route_list.append(route)

    # return object based on query value
    if kwargs['query'] == "check":
        print("\nThe following tables are tagged to be migrated:\n")
        for t in table_name_list:
            print(t)
        print('\n')
    elif kwargs['query'] == "migrate":
        return table_list
    elif kwargs['query'] == "routes":
        for table in route_tables:
            pprint([x['Value'] for x in table['Tags'] if 'Name' in x['Key']][0])
            print("--------------------------------------")
            pprint(table['Routes'])
            print("--------------------------------------")
            #pprint(table)

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

    for table in route_tables:

        # we only want route tables with the matching tag
        if tag in table['Tags']:
            for route in table['Routes']:

                # only grab routes that are not local
                if 'local' not in route.values():

                    # build new dict for creating new routes
                    new_route = {}            
                    new_route['table'] = table['RouteTableId']
                    new_route['dest'] = route['DestinationCidrBlock']

                    # add route to list of routes to be modified
                    mod_routes.append(new_route)

    # for each route in the list, replace it and use TGW as next-hop
    for route in mod_routes:
        session = boto3.Session()
        src_client = session.client("ec2")
        response = src_client.replace_route(
            DestinationCidrBlock = route['dest'],
            RouteTableId = route['table'],
            TransitGatewayId = tgw_id
            )

    print("Migration completed. The following routes have been updated: \n")
    check_tag(query="routes")

    return None


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
    elif arg == "migrate":
        backup_routes()
        tgw_migrate()
    elif arg == "rollback":
        rollback()
    elif arg == "tag":
        add_migrate_tag()
    elif arg == "check":
        check_tag(query="check")