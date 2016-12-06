#!/usr/bin/env python3

from __future__ import print_function
from __future__ import absolute_import
import os, sys, click
from taw.util import *
from taw.taw import * # This must be the end of imports

# ==============
#  KEYPAIR COMMAND
# ==============
@taw.group("keypair")
@pass_global_parameters
def keypair_group(params):
    """ manage key pairs """

@keypair_group.command("create")
@click.argument('key_name')
@pass_global_parameters
def create_keypaircmd(params, key_name):
    """ create a key pair with a specified name """
    ec2 = get_ec2_connection()
    pem_file_path = os.path.join(os.path.expanduser("~/.ssh"), key_name + ".pem")
    if os.path.exists(pem_file_path):
        error_exit("There already exists a key file '%s'" % pem_file_path)
    with os.fdopen(os.open(pem_file_path, os.O_WRONLY | os.O_CREAT, 0o600), 'w') as f:
        kp = ec2.create_key_pair(KeyName=key_name)
        f.write(kp.key_material)
    print("Saved a private key as '%s'" % pem_file_path)
    print("The fingerprint is " + kp.key_fingerprint)

@keypair_group.command("rm")
@click.argument('key_name')
@click.option('--force', is_flag=True)
@pass_global_parameters
def rm_keypaircmd(params, key_name, force):
    """ remove a key pair with a specified name """
    ec2 = get_ec2_connection()
    kps = list(ec2.key_pairs.filter(Filters=[{'Name': 'key-name', 'Values': [key_name]}]))
    if len(kps) <= 0: error_exit("Cannot find a key pair '%s'" % key_name)
    for k in kps:
        print("%s (fp=%s)" % (k.key_name, k.key_fingerprint))
    if 1 < len(kps): error_exit("There are multiple key pairs with name '%s'. Abort for safety." % key_name)
    if force:
        kps[0].delete()
    else:
        print("Please add --force to actually remove this key pair\nNote that the local key file will not be removed. Only the key in AWS will be removed.")

@keypair_group.command("import")
@click.argument('key_name')
@click.argument('file_path', required=False)
@pass_global_parameters
def import_keypair(params, key_name, file_path):
    """ import a public key from a specified OpenSSH public key file """
    ec2 = get_ec2_connection()
    if file_path == None:
        file_path = os.path.join(os.path.expanduser("~/.ssh"), key_name + ".pub")
    if not os.path.exists(file_path): error_exit("Key file '%s' does not exist" % file_path)
    with open(file_path, "rb") as f:
        public_key = f.readline().strip().decode('ascii')
    ec2.import_key_pair(KeyName=key_name, PublicKeyMaterial=public_key)

@keypair_group.command("list", add_help_option=False, context_settings=dict(ignore_unknown_options=True))
@click.argument('args', nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def list_keypaircmd(ctx, args):
    """ list key pairs """
    with taw.make_context('taw', ctx.obj.global_opt_str + ['list', 'keypair'] + list(args)) as ncon: _ = taw.invoke(ncon)

