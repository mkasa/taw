#!/usr/bin/env python3

from __future__ import print_function
from __future__ import absolute_import
import os, sys, click
from taw.util import *
from taw.taw import * # This must be the end of imports

# =============================
#  SG (Security Group) COMMAND
# =============================
@taw.group("sg")
@pass_global_parameters
def sg_group(params):
    """ manage security group """

@sg_group.command("rm")
@click.argument('sg', nargs=-1)
@click.option('--force', is_flag=True)
@pass_global_parameters
def rm_sgcmd(params, sg, force):
    """ remove security group(s) with specified name(s)  """
    ec2 = get_ec2_connection()
    sg = convert_sg_name_to_sg(sg[0])
    print("Security group %s (%s)" % (sg.id, extract_name_from_tags(sg.tags)))
    if force:
        sg.delete()
    else:
        print("Please add --force to actually remove those security group")

@sg_group.command("allow")
@click.argument('sg', metavar='<security group (ID or name)>')
@click.argument('protocol_str', metavar='<protocol strings>')
@click.argument('cidr')
@click.option('--egress', is_flag=True)
@click.option('--force', is_flag=True)
@pass_global_parameters
def allow_sgcmd(params, sg, protocol_str, cidr, egress, force):
    """ add another rule to pass a specified firewall """
    ec2 = get_ec2_connection()
    sg_obj = convert_sg_name_to_sg(sg)
    protocol, target_port_low, target_port_high = parse_protocol_port_string(protocol_str)
    if is_debugging:
        print("Protocol %s" % protocol)
        print("Target port %s to %s" % (target_port_low, target_port_high))
        print("Source ID %s" % cidr)
    cidr = expand_cidr_string(cidr)
    if egress:
        sg_obj.authorize_egress(
                IpProtocol=protocol,
                FromPort=target_port_low,
                ToPort=target_port_high,
                CidrIp=cidr
            )
    else:
        sg_obj.authorize_ingress(
                IpProtocol=protocol,
                FromPort=target_port_low,
                ToPort=target_port_high,
                CidrIp=cidr
            )

@sg_group.command("revoke")
@click.argument('sg', metavar='<security group (ID or name)>')
@click.argument('protocol_str', metavar='<protocol strings>')
@click.argument('cidr')
@click.option('--egress', is_flag=True)
@click.option('--force', is_flag=True)
@pass_global_parameters
def revoke_sgcmd(params, sg, protocol_str, cidr, egress, force):
    """ revoke a rule to pass a specified firewall """
    ec2 = get_ec2_connection()
    sg_obj = convert_sg_name_to_sg(sg)
    protocol, target_port_low, target_port_high = parse_protocol_port_string(protocol_str)
    if is_debugging:
        print("Protocol %s" % protocol)
        print("Target port %s to %s" % (target_port_low, target_port_high))
        print("Source ID %s" % cidr)
    cidr = expand_cidr_string(cidr)
    if egress:
        sg_obj.revoke_egress(
                IpProtocol=protocol,
                FromPort=target_port_low,
                ToPort=target_port_high,
                CidrIp=cidr
            )
    else:
        sg_obj.revoke_ingress(
                IpProtocol=protocol,
                FromPort=target_port_low,
                ToPort=target_port_high,
                CidrIp=cidr
            )

@sg_group.command("list", add_help_option=False, context_settings=dict(ignore_unknown_options=True))
@click.argument('args', nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def list_sgcmd(ctx, args):
    """ list security groups """
    with taw.make_context('taw', ctx.obj.global_opt_str + ['list', 'sg'] + list(args)) as ncon: _ = taw.invoke(ncon)

