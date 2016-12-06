#!/usr/bin/env python3

from __future__ import print_function
from __future__ import absolute_import
import os, sys, click
from taw.util import *
from taw.taw import * # This must be the end of imports

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
@pass_global_parameters
def create_vpccmd(params, name, cidr, nosubnet):
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
        gateway = ec2.create_internet_gateway()
        gateway.attach_to_vpc(VpcId=vpc.vpc_id)

@vpc_group.command("list", add_help_option=False, context_settings=dict(ignore_unknown_options=True))
@click.argument('args', nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def list_vpccmd(ctx, args):
    """ list VPC """
    with taw.make_context('taw', ctx.obj.global_opt_str + ['list', 'vpc'] + list(args)) as ncon: _ = taw.invoke(ncon)

