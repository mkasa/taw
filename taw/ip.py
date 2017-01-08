#!/usr/bin/env python3

from __future__ import print_function
from __future__ import absolute_import
import os, sys, click
from taw.util import *
from taw.taw import * # This must be the end of imports

# ==============
#  IP COMMAND
# ==============
@taw.group("ip")
@pass_global_parameters
def ip_group(params):
    """ manage Elastic IP addresses """

@ip_group.command("rm")
@click.argument('eip_id')
@click.option('--force', is_flag=True)
@pass_global_parameters
def rm_ipcmd(params, eip_id, force):
    """ remove the IP with a specified name """
    ec2 = get_ec2_connection()
    eips = list(ec2.vpc_addresses.filter(Filters=[{'Name': 'allocation-id', 'Values': [eip_id]}]))
    if len(eips) <= 0: error_exit("No such allocation ID ('%s')" % eip_id)
    eip = eips[0]
    if force:
        ec2_client = get_ec2_client()
        public_ip, allocation_id = eip.public_ip, eip.allocation_id
        ec2_client.release_address(AllocationId=allocation_id)
        print("Removed %s (%s)" % (public_ip, allocation_id))
    else:
        print("Following resources will be removed:")
        print("\t%s (%s)" % (eip.public_ip, eip.allocation_id))
        print("Please add --force to actually remove those elastic IPs")

@ip_group.command("create")
@pass_global_parameters
def create_ipcmd(params):
    """ create an elastic IP """
    ec2_client = get_ec2_client()
    addr = ec2_client.allocate_address(Domain='vpc')
    print("Created an elastic IP")
    print("Public IP:", addr['PublicIp'])
    print("Allocation ID:", addr['AllocationId'])

@ip_group.command("associate")
@click.argument('eip_id')
@click.argument('hostname')
@pass_global_parameters
def associate_ipcmd(params, eip_id, hostname):
    """ associate an elastic IP with the specified instance """
    ec2 = get_ec2_connection()
    eips = list(ec2.vpc_addresses.filter(Filters=[{'Name': 'allocation-id', 'Values': [eip_id]}]))
    if len(eips) <= 0: error_exit("No such allocation ID ('%s')" % eip_id)
    instance = convert_host_name_to_instance(hostname)
    ec2_client = get_ec2_client()
    addr = ec2_client.associate_address(InstanceId=instance.id, AllocationId=eip_id)

@ip_group.command("disassociate")
@click.argument('association_id')
@pass_global_parameters
def associate_ipcmd(params, association_id):
    """ associate an elastic IP with the specified instance """
    ec2 = get_ec2_connection()
    eips = list(ec2.vpc_addresses.filter(Filters=[{'Name': 'association-id', 'Values': [association_id]}]))
    if len(eips) <= 0: error_exit("No such association ID ('%s')" % association_id)
    ec2_client = get_ec2_client()
    addr = ec2_client.disassociate_address(AssociationId=association_id)

@ip_group.command("list", add_help_option=False, context_settings=dict(ignore_unknown_options=True))
@click.argument('args', nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def list_ipcmd(ctx, args):
    """ list elastic IPs """
    with taw.make_context('taw', ctx.obj.global_opt_str + ['list', 'ip'] + list(args)) as ncon: _ = taw.invoke(ncon)

