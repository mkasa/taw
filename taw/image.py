#!/usr/bin/env python3

from __future__ import print_function
from __future__ import absolute_import
import click, six
from taw.util import *
from taw.taw import *  # This must be the end of imports


# ========
#  HELPER
# ========
def device_mappings_to_device_mapping_strs(xs):
    rows = []
    for d in xs:
        devs = []
        for k, v in six.iteritems(d):
            if k == 'Ebs':
                dev = "%s[%s](%sGB, %s, %s%s)" % (k.upper(), v['SnapshotId'], v['VolumeSize'], v['VolumeType'],
                                                       'Encrypted' if v['Encrypted'] == 'True' else 'Unencrypted',
                                                       ',DeleteOnTermination' if v['DeleteOnTermination'] == 'True' else ''
                                                 )
                devs.append(dev)
            else:
                key_str = str(k)
                devs.append(('  ' if key_str == 'DeviceName' else '') + key_str + ":" + str(v))
        rows.append("\n".join(devs))
    return rows

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
    image_id = convert_ami_name_to_ami(ami_id)
    images = list(ec2.images.filter(Filters=[{'Name': 'image-id', 'Values': [image_id]}]))
    if len(images) <= 0: error_exit("No such image ID ('%s')" % ami_id)
    image = images[0]
    if force:
        image.deregister()
        print("Removed %s (%s): %s" % (image.image_id, image.name, image.description))
    else:
        print("Following resources will be removed:")
        print("\t%s (%s): %s" % (image.image_id, image.name, image.description))
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
@click.argument('keywords', nargs=-1)
@click.option('--argdoc', is_flag=True)
@click.option('--verbose', is_flag=True)
@click.option('--attr', '-a', multiple=True, help='Attribute name(s).')
@click.option('--allregions', is_flag=True, help='List for all regions.')
@pass_global_parameters
def list_image(params, keywords, argdoc, verbose, attr, allregions):
    """ list images (of mine or trusted parties) """
    dummy_argument = keywords # renaming
    if argdoc:
        click.launch('https://boto3.readthedocs.io/en/latest/reference/services/ec2.html#image')
        return
    sts_client = get_sts_client()
    sts_result = sts_client.get_caller_identity()
    user_id = sts_result['Account']

    def self_if_mine(account_str):
        if account_str == user_id:
            return 'self'
        return account_str

    all_list_columns = [
            (True , "name"                 , "Name"            , ident)                       ,
            (True , "image_id"             , "Image ID"        , ident)                       ,
            (True , "state"                , "State"           , ident)                       ,
            (True , "architecture"         , "Arch"            , ident)                       ,
            (True , "creation_date"        , "Created"         , convert_amazon_time_to_local),
            (True , "public"               , "Public"          , ident)                       ,
            (True , "owner_id"             , "Owner"           , self_if_mine)                ,
            (True , "description"          , "Description"     , ident)                       ,
            (False, "virtualization_type"  , "Virt. Type"      , ident)                       ,
            (False, "hypervisor"           , "Hypervisor"      , ident)                       ,
            (False, "block_device_mappings", "Block Device Map", device_mappings_to_device_mapping_strs)        ,
        ]
    list_columns = [x for x in all_list_columns if verbose or x[0]]
    for v in attr: list_columns.append((True, v, v, ident))
    header = [x[2] for x in list_columns]; rows = []
    ec2 = get_ec2_connection()
    if 0 < len(dummy_argument):
        images = ec2.images.filter(Owners=['self', '099720109477'],
                                   Filters=[{'Name': 'is-public', 'Values': ['true']},
                                            {'Name': 'virtualization-type', 'Values': ['hvm']}])
    else:
        images = ec2.images.filter(Owners=['self'],
                                   Filters=[{'Name': 'is-public', 'Values': ['false']},
                                            {'Name': 'virtualization-type', 'Values': ['hvm']}])
    header.append('Permissions')
    try:
        for image in images:
            row = [f(getattr(image, i)) for _, i, _, f in list_columns]
            if image.owner_id == user_id:
                try:
                    perms = image.describe_attribute(Attribute='launchPermission')['LaunchPermissions']
                    # print(perms)
                    # print(list(map(lambda x: x['UserId'], perms)))
                    row.append(", ".join(['self'] + list(map(lambda x: x['UserId'], perms))))
                except:
                    row.append('ERROR')
            else:
                row.append('Not mine')
            has_to_exclude = False
            desc = row[7]
            if desc is None and len(dummy_argument) > 0:
                has_to_exclude = True
            if len(dummy_argument) > 0 and desc is not None:
                all_found = True
                any_pos_keyword = False
                for i in dummy_argument:
                    if i.startswith('/'):
                        if desc.find(i[1:]) >= 0:
                            has_to_exclude = True
                            break
                    else:
                        any_pos_keyword = True
                        if desc.find(i) < 0:
                            all_found = False
                if any_pos_keyword and not all_found:
                    has_to_exclude = True
            if not has_to_exclude:
                rows.append(row)
    except AttributeError as e:
        error_exit(str(e) + "\nNo such attribute.\nTry 'taw list --argdoc' to see all attributes.")

    def coloring(r):
        if verbose: return None
        if r[2] == 'pending': return {-1: 'cyan'}
        return None

    output_table(params, header, rows, [coloring])

