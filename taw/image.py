#!/usr/bin/env python3

from __future__ import print_function
from __future__ import absolute_import
import click
from taw.util import *
from taw.taw import *  # This must be the end of imports


# ==============
#  AMI COMMAND
# ==============
@taw.group("image")
@pass_global_parameters
def image_group(params):
    """ manage Amazon Machine Images (AMIs) """


@image_group.command("rm")
@click.argument('ami_id')
@click.option('--force', is_flag=True)
@pass_global_parameters
def rm_amicmd(params, ami_id, force):
    """ remove the AMI with a specified name """
    ec2 = get_ec2_connection()
    images = list(ec2.images.filter(Filters=[{'Name': 'image-id', 'Values': [ami_id]}]))
    if len(images) <= 0: error_exit("No such image ID ('%s')" % ami_id)
    image = images[0]
    if force:
        image.deregister()
        print("Removed %s (%s): %s" % (image.image_id, image.name, image.descriptino))
    else:
        print("Following resources will be removed:")
        print("\t%s (%s): %s" % (image.image_id, image.name, image.descriptino))
        print("Please add --force to actually remove this AMI")


@image_group.command("chmod")
@click.argument('ami_id')
@click.argument('user')
@pass_global_parameters
def chmod_amicmd(params, ami_id, user):
    """ change the permission of a specified AMI """
    if not (user.startswith('+') or user.startswith('-')):
        print("User must start with either + or -")
        return
    ec2 = get_ec2_connection()
    image_id = convert_ami_name_to_ami(ami_id)
    image = list(ec2.images.filter(Filters=[{'Name': 'image-id', 'Values': [image_id]}]))
    if user.startswith('+'):
        image[0].modify_attribute(Attribute='launchPermission', OperationType='add', UserIds=[user[1:]])
    else:
        image[0].modify_attribute(Attribute='launchPermission', OperationType='remove', UserIds=[user[1:]])


@image_group.command("name")
@click.argument('ami_id')
@click.argument('name')
@pass_global_parameters
def name_amicmd(param, ami_id, name):
    """ name a specified AMI """
    ec2 = get_ec2_connection()
    eips = list(ec2.images.filter(Filters=[{'Name': 'image-id', 'Values': [ami_id]}]))
    if len(eips) <= 0: error_exit("No such association ID ('%s')" % ami_id)
    for eip in eips:
        ec2.create_tags(Resources=[ami_id], Tags=[{'Key': 'Name', 'Value': name}])


@image_group.command("list", add_help_option=False, context_settings=dict(ignore_unknown_options=True))
@click.argument('args', nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def list_amicmd(ctx, args):
    """ list AMIs """
    with taw.make_context('taw', ctx.obj.global_opt_str + ['list', 'image'] + list(args)) as ncon: _ = taw.invoke(ncon)
