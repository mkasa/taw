#!/usr/bin/env python3

from __future__ import print_function
from __future__ import absolute_import
import os, sys, click
from taw.util import *
from taw.taw import * # This must be the end of imports

# ================
#  SUBNET COMMAND
# ================
@taw.group("subnet")
@pass_global_parameters
def subnet_group(params):
    """ manage subnets """

@subnet_group.command("create")
@click.argument('name')
@click.argument('vpc')
@click.argument('cidr', required=False, default="172.16.1.0/24")
@click.argument('az', default=None, metavar='[availability zone]', required=False)
@pass_global_parameters
def create_subnetcmd(params, name, vpc, cidr, az):
    """ create a subnet with a specified block of CIDR """
    ec2 = get_ec2_connection()
    vpc = convert_vpc_name_to_vpc(vpc)
    if not is_private_cidr(cidr):
        error_exit("CIDR block %s is not a private address block" % cidr)
    if is_debugging: print(vpc)
    if az:
        subnet = vpc.create_subnet(CidrBlock=cidr, AvailabilityZone=az)
    else:
        subnet = vpc.create_subnet(CidrBlock=cidr)
    if is_debugging: print(subnet)
    subnet.create_tags(Tags=[{'Key': 'Name', 'Value': name}])

@subnet_group.command("rm")
@click.argument('subnet', nargs=-1)
@click.option('--force', is_flag=True)
@pass_global_parameters
def rm_subnetcmd(params, subnet, force):
    """ remove subnet(s) with specified name(s)  """
    ec2 = get_ec2_connection()
    subnet = list(subnet)
    for subnet in ec2.subnets.filter(Filters=[{'Name':'tag:Name', 'Values': subnet}]):
        print("subnet %s (%s)" % (subnet.id, extract_name_from_tags(subnet.tags)))
        if force: subnet.delete()
    if not force:
        print("Please add --force to actually remove those subnets")

@subnet_group.command("name")
@click.argument('subnet_id')
@click.argument('name')
@pass_global_parameters
def name_subnetcmd(params, subnet_id, name):
    """ name a specified subnet """
    ec2 = get_ec2_connection()
    subnet = convert_subnet_name_to_subnet(subnet_id)
    if is_debugging: print(subnet)
    subnet.create_tags(Tags=[{'Key': 'Name', 'Value': name}])

@subnet_group.command("list", add_help_option=False, context_settings=dict(ignore_unknown_options=True))
@click.argument('args', nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def list_subnetcmd(ctx, args):
    """ list subnets """
    with taw.make_context('taw', ctx.obj.global_opt_str + ['list', 'subnets'] + list(args)) as ncon: _ = taw.invoke(ncon)

