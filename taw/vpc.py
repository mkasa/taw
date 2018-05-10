#!/usr/bin/env python3

from __future__ import print_function
from __future__ import absolute_import
import click
from taw.list import *
from taw.util import *
from taw.taw import *  # This must be the end of imports


# ==============
#  VPC COMMAND
# ==============
@taw.group("vpc")
@pass_global_parameters
def vpc_group(params):
    """ manage Virtual Private Cloud (VPC) """


@vpc_group.command("rm")
@click.argument('vpc', nargs=-1)
@click.option('--force', is_flag=True)
@pass_global_parameters
def rm_vpccmd(params, vpc, force):
    """ remove VPCs with specified names  """
    ec2 = get_ec2_connection()
    vpc = convert_vpc_name_to_vpc(vpc[0])
    instances = [i for i in ec2.instances.all() if i.vpc_id == vpc.vpc_id]
    if 0 < len(instances):
        error_exit("There are still running instances. You need to stop/terminate them first.\n\t" +
                "\n\t".join(map(lambda i: "%s (%s)" % (i.id, extract_name_from_tags(i.tags)), instances)))
    gateways = vpc.internet_gateways.all()
    print("Following resources will be removed:")
    for g in gateways:
        print("\tGateway %s" % g.id)
    subnets = [s for s in ec2.subnets.all() if s.vpc_id == vpc.vpc_id]
    for s in subnets:
        print("\tSubnet %s (%s)" % (s.subnet_id, extract_name_from_tags(s.tags)))
    print("\tVPC %s (%s)" % (vpc.id, extract_name_from_tags(vpc.tags)))
    if force:
        for g in gateways:
            g.detach_from_vpc(VpcId=vpc.vpc_id)
            g.delete()
        for s in subnets: s.delete()
        vpc.delete()
    else:
        print("Please add --force to actually remove those VPCs")


@vpc_group.command("name")
@click.argument('vpc_id')
@click.argument('name')
@pass_global_parameters
def name_vpccmd(param, vpc_id, name):
    """ name a specified VPC """
    ec2 = get_ec2_connection()
    vpc = convert_vpc_name_to_vpc(vpc_id)
    if is_debugging: print(vpc)
    vpc.create_tags(Tags=[{'Key': 'Name', 'Value': name}])


@vpc_group.command("create")
@click.argument('name')
@click.argument('cidr', required=False, default="172.16.0.0/16")
@click.option('--nosubnet')
@click.option('--nogateway')
@pass_global_parameters
def create_vpccmd(params, name, cidr, nosubnet, nogateway):
    """ create VPC with a specified block of CIDR """
    ec2 = get_ec2_connection()
    instances = list(ec2.vpcs.filter(Filters=[{'Name': 'tag:Name', 'Values': [name]}]))
    if 0 < len(instances):
        error_exit("There already exists a VPC with that name '%s'" % name)
    cidr_addr = is_private_cidr(cidr)
    if not cidr_addr:
        error_exit("CIDR block %s is not a private address block" % cidr)
    vpc = ec2.create_vpc(CidrBlock=cidr)
    if is_debugging: print(vpc)
    vpc.create_tags(Tags=[{'Key': 'Name', 'Value': name}])
    if not nosubnet:
        b1, b2, b3, b4, nbits = cidr_addr
        if nbits < 24: nbits = 24
        subnet = vpc.create_subnet(CidrBlock="%d.%d.%d.%d/%d" % (b1, b2, b3, b4, nbits))
        subnet.create_tags(Tags=[{'Key': 'Name', 'Value': name + "-default"}])
        if not nogateway:
            gateway = ec2.create_internet_gateway()
            gateway.attach_to_vpc(VpcId=vpc.vpc_id)


@vpc_group.command("list")
@click.option('--verbose', '-v', is_flag=True, help='Verbose output.')
@click.option('--argdoc', is_flag=True, help='Show available attributes in a web browser')
@click.option('--attr', '-a', multiple=True, help='Attribute name(s).')
@click.option('--allregions', is_flag=True, help='List for all regions.')
@pass_global_parameters
def list_vpccmd(params, verbose, argdoc, attr, allregions):
    """ list VPCs """
    if argdoc:
        click.launch('https://boto3.readthedocs.io/en/latest/reference/services/ec2.html#vpc')
        return
    if allregions:
        list_for_all_regions(params, [], 'vpc', lambda x: list_vpccmd(params, verbose, argdoc, attr, False))
        return
    all_list_columns = [
            (True , "tags"            , "Name"           , extract_name_from_tags),
            (True , "vpc_id"          , "ID"             , ident)                      ,
            (True , "cidr_block"      , "CIDR Block"     , ident)                      ,
            (False, "state"           , "State"          , ident)                      ,
            (True , "is_default"      , "Default"        , ident)                      ,
            (False, "dhcp_options_id" , "DHCP Options ID", ident)                      ,
            (False, "instance_tenancy", "Tenancy"        , ident)                      ,
        ]
    list_columns = [x for x in all_list_columns if verbose or x[0]]
    for v in attr: list_columns.append((True, v, v, ident))
    header = [x[2] for x in list_columns]
    if verbose: header.append('Gateway')
    header += ['Subnet Names', 'Instances', 'Security Groups']
    rows = []
    ec2 = get_ec2_connection()
    instances = ec2.instances.all()
    vpcs = ec2.vpcs.all()
    subnets = ec2.subnets.all()

    def subnet_id_to_subnet_name(subnet_id):
        for s in subnets:
            if s.subnet_id != subnet_id: continue
            name = extract_name_from_tags(s.tags)
            if name != 'NO NAME': return name
            break
        return subnet_id
    sgs = ec2.security_groups.all()
    if verbose:
        internet_gateways = ec2.internet_gateways.all()
    try:
        for inst in vpcs:
            row = [f(getattr(inst, i)) for _, i, _, f in list_columns]
            if verbose:
                row.append([i.internet_gateway_id for i in internet_gateways if any(map(lambda x: x['VpcId'] == inst.vpc_id, i.attachments))])
            row.append([subnet_id_to_subnet_name(i.subnet_id) for i in subnets if i.vpc_id == inst.vpc_id])
            row.append([extract_name_from_tags(i.tags) for i in instances if i.vpc_id == inst.vpc_id])
            row.append([i.group_name for i in sgs if i.vpc_id == inst.vpc_id])
            rows.append(row)
    except AttributeError as e:
        error_exit(str(e) + "\nNo such attribute.\nTry 'taw list --argdoc' to see all attributes.")
    output_table(params, header, rows)
