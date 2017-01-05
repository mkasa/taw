#!/usr/bin/env python3

from __future__ import print_function
from __future__ import absolute_import
import os, sys, subprocess, re, datetime, glob
import click, boto3, colorama, botocore, fnmatch
import tabulate, json
import sqlite3
from termcolor import colored
from taw.util import *
from taw.taw import * # This must be the end of imports

# ==============
#  LIST COMMAND
# ==============
@taw.command("list", short_help="list various types of resources")
@click.argument('restype', default='instance', metavar='[resource type (default: instance)]')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output.')
@click.option('--argdoc', is_flag=True, help='Show available attributes in a web browser')
@click.option('--attr', '-a', multiple=True, help='Attribute name(s).')
@click.option('--allregions', is_flag=True, help='List for all regions.')
@click.argument('subargs', nargs=-1)
@pass_global_parameters
def list_cmd(params, restype, verbose, argdoc, attr, subargs, allregions):
    """ list various types of resources such as instances """

    def security_group_list_to_strs(cs):
        def sg_to_str(s):
            return dc(s, 'GroupName')
        return [sg_to_str(s) for s in cs]
    def get_block_device_map(xs):
        rows = []
        for d in xs:
            devs = []
            for k, v in d.items():
                if k == 'Ebs':
                    dev = "%s[%s](%sGB, %s, %s%s)" % (k.upper(), v['SnapshotId'], v['VolumeSize'], v['VolumeType'],
                                                           'Encrypted' if v['Encrypted'] == 'True' else 'Unencrypted',
                                                           ',DeleteOnTermination' if v['DeleteOnTermination'] == 'True' else ''
                                                       )
                    devs.append(dev)
            rows.append("\n".join(devs))
        return rows

    def list_instance(dummy_argument):
        """ list instances """
        if argdoc:
            click.launch('https://boto3.readthedocs.io/en/latest/reference/services/ec2.html#instance')
            return
        all_list_columns = [
                (True , "tags"             , "Name"           , extract_name_from_tags)                                  ,
                (True , "instance_id"      , "ID"             , ident)                                                        ,
                (True , "instance_type"    , "Instance Type"  , ident)                                                        ,
                (False, "key_name"         , "Key"            , ident)                                                        ,
                (True , "public_ip_address", "Public IP"      , ident)                                                        ,
                (True , "security_groups"  , "Security Groups", lambda l: ", ".join(security_group_list_to_strs(l)))          ,
                (True , "state"            , "State"          , lambda d: dc(d, 'Name'))                                      ,
                (False, "state_reason"     , "Reason"         , lambda d: dc(d, 'Message'))                                   ,
                (False, "tags"             , "Tag"            , lambda a: list(map(lambda x: x['Key'] + "=" + x['Value'], a or []))),
                (False, "subnet_id"        , "Subnet ID"      , ident)                                                        ,
                (False, "vpc_id"           , "VPC ID"         , ident)                                                        ,
            ]
        list_columns = [x for x in all_list_columns if verbose or x[0]]
        for v in attr: list_columns.append((True, v, v, ident))
        header = [x[2] for x in list_columns]; rows = []
        header += ['Subnet Name', 'VPC Name']
        ec2 = get_ec2_connection()
        instances = ec2.instances.all()
        subnets = list(ec2.subnets.all())
        vpcs = list(ec2.vpcs.all())
        try:
            for inst in instances:
                row = [f(getattr(inst, i)) for _, i, _, f in list_columns]
                row.append([extract_name_from_tags(i.tags, inst.subnet_id) for i in subnets if i.id == inst.subnet_id])
                row.append([extract_name_from_tags(i.tags, inst.vpc_id) for i in vpcs if i.id == inst.vpc_id])
                rows.append(row)
        except AttributeError as e:
            error_exit(str(e) + "\nNo such attribute.\nTry 'taw list --argdoc' to see all attributes.")
        def coloring(r):
            if verbose: return None
            if r[5] == 'stopped': return {-1: 'red'}
            if r[5] == 'stopping': return {-1: 'green'}
            if r[5] == 'pending': return {-1: 'yellow'}
            if r[5] == 'stopped': return {-1: 'red'}
            if r[5] == 'terminated': return {-1: 'grey'}
            if r[5] == 'shutting-down': return {-1: 'cyan'}
            return None
        output_table(params, header, rows, [coloring])

    def list_vpc(dummy_argument):
        """ list VPCs """
        if argdoc:
            click.launch('https://boto3.readthedocs.io/en/latest/reference/services/ec2.html#vpc')
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

    def list_subnet(dummy_argument):
        """ list subnets """
        if argdoc:
            click.launch('https://boto3.readthedocs.io/en/latest/reference/services/ec2.html#subnet')
            return
        all_list_columns = [
                (True , "tags"                      , "Name"          , extract_name_from_tags),
                (True , "subnet_id"                 , "Subnet ID"     , ident)                      ,
                (False, "vpc_id"                    , "VPC ID"        , ident)                      ,
                (True , "cidr_block"                , "CIDR Block"    , ident)                      ,
                (True , "state"                     , "State"         , ident)                      ,
                (False, "default_for_az"            , "Default for AZ", ident)                      ,
                (False, "available_ip_address_count", "# IP"          , ident)                      ,
                (False, "availability_zone"         , "AZ"            , ident)                      ,
            ]
        list_columns = [x for x in all_list_columns if verbose or x[0]]
        for v in attr: list_columns.append((True, v, v, ident))
        header = [x[2] for x in list_columns] + ['VPC Names', 'Instances']; rows = []
        ec2 = get_ec2_connection()
        subnets = ec2.subnets.all()
        instances = ec2.instances.all()
        vpcs = ec2.vpcs.all()
        try:
            for subnet in subnets:
                row = [f(getattr(subnet, i)) for _, i, _, f in list_columns]
                row.append([extract_name_from_tags(i.tags) for i in vpcs if i.vpc_id == subnet.vpc_id])
                row.append([extract_name_from_tags(i.tags) for i in instances if i.subnet_id == subnet.subnet_id])
                rows.append(row)
        except AttributeError as e:
            error_exit(str(e) + "\nNo such attribute.\nTry 'taw list --argdoc' to see all attributes.")
        output_table(params, header, rows)

    def list_image(dummy_argument):
        """ list images (of mine) """
        if argdoc:
            click.launch('https://boto3.readthedocs.io/en/latest/reference/services/ec2.html#image')
            return
        all_list_columns = [
                (True , "name"                 , "Name"            , ident)                       ,
                (True , "image_id"             , "Image ID"        , ident)                       ,
                (True , "state"                , "State"           , ident)                       ,
                (True , "architecture"         , "Arch"            , ident)                       ,
                (True , "creation_date"        , "Created"         , convert_amazon_time_to_local),
                (True , "public"               , "Public"          , ident)                       ,
                (True , "description"          , "Description"     , ident)                       ,
                (False, "virtualization_type"  , "Virt. Type"      , ident)                       ,
                (False, "hypervisor"           , "Hypervisor"      , ident)                       ,
                (False, "block_device_mappings", "Block Device Map", get_block_device_map)        ,
            ]
        list_columns = [x for x in all_list_columns if verbose or x[0]]
        for v in attr: list_columns.append((True, v, v, ident))
        header = [x[2] for x in list_columns]; rows = []
        ec2 = get_ec2_connection()
        images = ec2.images.filter(Owners=['self'])
        try:
            for image in images:
                row = [f(getattr(image, i)) for _, i, _, f in list_columns]
                rows.append(row)
        except AttributeError as e:
            error_exit(str(e) + "\nNo such attribute.\nTry 'taw list --argdoc' to see all attributes.")
        output_table(params, header, rows)

    def list_key_pairs(dummy_argument):
        """ list key pairs (only info) """
        if argdoc:
            click.launch('https://boto3.readthedocs.io/en/latest/reference/services/ec2.html#keypairinfo')
            return
        all_list_columns = [
                (True, "key_name"       , "Name"       , ident),
                (True, "key_fingerprint", "FingerPrint", ident),
            ]
        list_columns = [x for x in all_list_columns if verbose or x[0]]
        for v in attr: list_columns.append((True, v, v, ident))
        header = [x[2] for x in list_columns]; rows = []
        ec2 = get_ec2_connection()
        keys = ec2.key_pairs.all()
        try:
            for key in keys:
                row = [f(getattr(key, i)) for _, i, _, f in list_columns]
                rows.append(row)
        except AttributeError as e:
            error_exit(str(e) + "\nNo such attribute.\nTry 'taw list --argdoc' to see all attributes.")
        output_table(params, header, rows)

    def list_local_key_pairs(dummy_argument):
        """ list local key pairs (in ~/.ssh/*.pem) """
        if allregions: error_exit("--allregions option is pointless for local key pairs (local files).")
        header = ['Name', 'Finger Print']; rows = []
        for fn in glob.glob(os.path.expanduser("~/.ssh/*.pem")):
            # See http://serverfault.com/questions/549075/fingerprint-of-pem-ssh-key
            fp = subprocess.check_output("openssl pkcs8 -in " + fn + " -inform PEM -outform DER -topk8 -nocrypt | openssl sha1 -c | tail -c +10", shell=True)
            rows.append([os.path.basename(fn)[:-4], fp.strip().decode('utf-8')])
        output_table(params, header, rows)

    def list_snapshots(dummy_argument):
        """ list snapshots (of mine) """
        if argdoc:
            click.launch('https://boto3.readthedocs.io/en/latest/reference/services/ec2.html#snapshot')
            return
        all_list_columns = [
                (True , "tags"         , "Name"       , extract_name_from_tags)          ,
                (True , "snapshot_id"  , "Snapshot ID", ident)                                ,
                (True , "state"        , "State"      , ident)                                ,
                (True , "progress"     , "Progress"   , ident)                                ,
                (True , "start_time"   , "Started"    , lambda x: datetime.datetime.strftime(x, '%c')),
                (True , "volume_id"    , "Volume ID"  , ident)                                ,
                (True , "volume_size"  , "Size (GB)"  , ident)                                ,
                (False, "encrypted"    , "Encrypted"  , ident)                                ,
                (False, "state_message", "Message"    , ident)                                ,
            ]
        list_columns = [x for x in all_list_columns if verbose or x[0]]
        for v in attr: list_columns.append((True, v, v, ident))
        header = [x[2] for x in list_columns]; rows = []
        ec2 = get_ec2_connection()
        snapshots = ec2.snapshots.filter(OwnerIds=['self'])
        try:
            for snapshot in snapshots:
                row = [f(getattr(snapshot, i)) for _, i, _, f in list_columns]
                rows.append(row)
        except AttributeError as e:
            error_exit(str(e) + "\nNo such attribute.\nTry 'taw list --argdoc' to see all attributes.")
        output_table(params, header, rows)

    def list_security_groups(sg_if_any):
        """ list security groups """
        if argdoc:
            click.launch('https://boto3.readthedocs.io/en/latest/reference/services/ec2.html#securitygroup')
            return
        def str_sg_permission(arr):
            """ convert the array into the list of strings that describe the firewall rules """
            def conv(d):
                """ convert an element of the array into a human readable firewall rule """
                def fs(ip_ranges):
                    """ convert IP ranges (an array of IP range) into a human readable string of the range """
                    if len(ip_ranges) <= 0: return ["any"]
                    iss = [x['CidrIp'] for x in ip_ranges]
                    if len(iss) == 1 and iss[0] == '0.0.0.0/0': return ["any"]
                    return iss
                if not 'FromPort' in d:
                    return ["N/A"]
                if d['FromPort'] == -1:
                    prot  = d['IpProtocol']
                    ranges = d['IpRanges']
                    return ["%s:%s" % (prot, i) for i in fs(ranges)]
                else:
                    prot  = d['IpProtocol']
                    froms = d['FromPort']
                    tos   = d['ToPort']
                    if froms == tos:
                        port_range_str = "%d" % froms
                    else:
                        if froms == 0 and tos == 65535:
                            port_range_str = "all"
                        else:
                            if froms == -1 or tos == -1:
                                port_range_str = ""
                            else:
                                port_range_str = "%d-%d" % (froms, tos)
                    ranges = d['IpRanges']
                    return ["%s:%s(%s)" % (prot, port_range_str, i) for i in fs(ranges)]
            return [i for x in arr for i in conv(x)]
        all_list_columns = [
                (True , "group_name"           , "Name"  , ident)            ,
                (True , "group_id"             , "ID"    , ident)            ,
                (True , "ip_permissions"       , "Perm"  , str_sg_permission),
                (True , "ip_permissions_egress", "Egress", str_sg_permission),
                (False, "vpc_id"               , "VPC"   , ident)            ,
            ]
        list_columns = [x for x in all_list_columns if verbose or x[0]]
        for v in attr: list_columns.append((True, v, v, ident))
        header = [x[2] for x in list_columns]; rows = []
        if verbose: header += ['Instances']
        header += ['VPC Names']
        ec2 = get_ec2_connection()
        vpcs = ec2.vpcs.all()
        if sg_if_any:
            sg_id_likes = [i for i in sg_if_any if i.startswith("sg-")]
            sg_name_likes = [i for i in sg_if_any if not i.startswith("sg-")]
            sg_ids = ec2.security_groups.filter(Filters=[{'Name': 'group-id', 'Values': list(sg_if_any)}])
            sg_names = ec2.security_groups.filter(Filters=[{'Name': 'group-name', 'Values': list(sg_if_any)}])
            sg_byvpc = ec2.security_groups.filter(Filters=[{'Name': 'vpc-id', 'Values': list(sg_if_any)}])
            security_groups = list(sg_ids) + list(sg_names) + list(sg_byvpc)
        else:
            security_groups = ec2.security_groups.all()
        instances = ec2.instances.all()
        try:
            for security_group in security_groups:
                row = [f(getattr(security_group, i)) for _, i, _, f in list_columns]
                if verbose:
                    insts = [extract_name_from_tags(inst.tags) for inst in instances if
                            security_group.group_id in [x['GroupId'] for x in inst.security_groups]]
                    row.append(insts)
                vpc_names = [extract_name_from_tags(vpc.tags) for vpc in vpcs if vpc.vpc_id == security_group.vpc_id]
                row.append(vpc_names)
                rows.append(row)
        except AttributeError as e:
            error_exit(str(e) + "\nNo such attribute.\nTry 'taw list --argdoc' to see all attributes.")
        output_table(params, header, rows)

    def list_zones(zone_name_if_any):
        """ list all zones hosted by Route53 """
        if argdoc:
            click.launch('http://boto3.readthedocs.io/en/latest/reference/services/route53.html#Route53.Client.list_hosted_zones')
            return
        if allregions: error_exit("Route53 zones are all global, so --allregions option is pointless.")
        if 0 < len(zone_name_if_any):
            if 1 < len(zone_name_if_any): error_exit("Only single zone name is accepted.")
            zone_name = zone_name_if_any[0]
            zone_id = convert_zone_name_to_zone_id(zone_name)
            def remove_trailing_domain_name(d):
                if d.endswith('.' + zone_name): return d[:-len(zone_name) - 1]
                if d.endswith('.' + zone_name + '.'): return d[:-len(zone_name) - 2]
                return d
            all_list_columns = [
                    (True, "Name"           , "Name" , remove_trailing_domain_name)      ,
                    (True, "TTL"            , "TTL"  , ident)                            ,
                    (True, "Type"           , "Type" , ident)                            ,
                    (True, "ResourceRecords", "Value", lambda x: [y['Value'] for y in x]),
                ]
            list_columns = [x for x in all_list_columns if verbose or x[0]]
            for v in attr: list_columns.append((True, v, v, ident))
            header = [x[2] for x in list_columns]; rows = []
            r53 = get_r53_connection()
            for zone in r53.list_resource_record_sets(HostedZoneId=zone_id)['ResourceRecordSets']:
                row = [f(zone[i]) for _, i, _, f in list_columns]
                rows.append(row)
        else:
            r53 = get_r53_connection()
            header = ['Name', 'Comment', 'IsPrivate', 'RecordSetCount']; rows = []
            for zone in r53.list_hosted_zones()['HostedZones']:
                row = [zone['Name'], zone['Config']['Comment'], zone['Config']['PrivateZone'], zone['ResourceRecordSetCount']]
                rows.append(row)
        output_table(params, header, rows)

    def list_s3_buckets(bucket_name_if_any):
        """ list all buckets (or a specified one) in S3 """
        def pstr_to_octal_bits(permission_str):
            """ convert a permission string such as 'READ'/'WRITE'/'READ_ACP'/'WRITE_ACP'/'FULL_CONTROL' to octal bits used in UNIX """
            if permission_str == 'READ': return 4
            if permission_str == 'WRITE': return 2
            if permission_str == 'WRITE_ACP': return 8
            if permission_str == 'READ_ACP': return 16
            if permission_str == 'FULL_CONTROL': return 30
            error_exit("Ask the author. Unknown permission string '%s'.\nThis might be probably caused by a change in Amazon S3 specs." % permission_str)
        def perm_bit_to_str(pb):
            if pb == 30: return 'all'
            retvals = []
            retvals.append('A' if pb & 16 else '-')
            retvals.append('a' if pb & 8 else '-')
            retvals.append('r' if pb & 4 else '-')
            retvals.append('w' if pb & 2 else '-')
            return "".join(retvals)
        def grants_to_id_to_perm_bits(grants):
            id_to_perm_bits = {}
            print("grants", grants)
            for gpar in grants:
                grant = gpar['Grantee']
                gtype = grant['Type']; perm = gpar['Permission']
                if gtype == 'CanonicalUser':
                    name = grant['DisplayName']
                elif gtype == 'Group':
                    uri = grant['URI']
                    if uri == 'http://acs.amazonaws.com/groups/global/AllUsers':
                        name = 'public'
                    elif uri == 'http://acs.amazonaws.com/groups/global/AuthenticatedUsers':
                        name = 'others'
                if not (name in id_to_perm_bits): id_to_perm_bits[name] = 0
                id_to_perm_bits[name] |= pstr_to_octal_bits(perm)
            return id_to_perm_bits
        if argdoc:
            click.launch('http://boto3.readthedocs.io/en/latest/reference/services/s3.html#S3.Client.list_buckets')
            return
        if allregions: error_exit("S3 buckets are all global, so --allregions option is pointless.")
        rows = []
        s3 = get_s3_connection()
        page_size = 2048
        if 0 < len(bucket_name_if_any):
            """ list a specified bucket """
            bucket_name = bucket_name_if_any[0]
            key_search_regex_if_any = bucket_name_if_any[1] if 1 < len(bucket_name_if_any) else None
            if is_debugging: print("Key pattern = '%s'" % key_search_regex_if_any, file=sys.stderr)
            all_list_columns = [
                    (True , "key"          , "Name"         , ident)                     ,
                    (True , "size"         , "Size"         , ident)                     ,
                    (True , "last_modified", "Modified"     , ident)                     ,
                    (True , "owner"        , "Owner"        , lambda x: x['DisplayName']),
                    (False, "owner"        , "Owner ID"     , lambda x: x['ID'])         ,
                    (False, "storage_class", "Storage Class", ident)                     ,
                ]
            list_columns = [x for x in all_list_columns if verbose or x[0]]
            for v in attr: list_columns.append((True, v, v, ident))
            header = [x[2] for x in list_columns]; rows = []
            if verbose: header.append('Permission')
            if key_search_regex_if_any and re.match(r'[^\*]+\*$', key_search_regex_if_any):
                if is_debugging: print("Prefix='%s'" % key_search_regex_if_any[:-1], file=sys.stderr)
                query_object = s3.Bucket(bucket_name).objects.filter(Prefix=key_search_regex_if_any[:-1]).page_size(page_size)
            else:
                query_object = s3.Bucket(bucket_name).objects.page_size(page_size)
            try:
                for obj in query_object:
                    if key_search_regex_if_any and not fnmatch.fnmatch(obj.key, key_search_regex_if_any): continue
                    row = [f(getattr(obj, i)) for _, i, _, f in list_columns]
                    if verbose:
                        id_to_perm_bits = grants_to_id_to_perm_bits(obj.Acl().grants)
                        row.append(", ".join([k+"("+perm_bit_to_str(v)+")" for k, v in id_to_perm_bits.items()]))
                    rows.append(row)
            except AttributeError as e:
                error_exit(str(e) + "\nNo such attribute.\nTry 'taw list --argdoc' to see all attributes.")
        else:
            all_list_columns = [
                    (True, "name"         , "Name"         , ident),
                    (True, "creation_date", "Creation Date", ident),
                ]
            list_columns = [x for x in all_list_columns if verbose or x[0]]
            for v in attr: list_columns.append((True, v, v, ident))
            header = [x[2] for x in list_columns]; rows = []; header.append("Permission")
            try:
                for b in s3.buckets.page_size(page_size):
                    row = [f(getattr(b, i)) for _, i, _, f in list_columns]
                    id_to_perm_bits = grants_to_id_to_perm_bits(b.Acl().grants)
                    row.append(", ".join([k+"("+perm_bit_to_str(v)+")" for k, v in id_to_perm_bits.items()]))
                    rows.append(row)
            except AttributeError as e:
                error_exit(str(e) + "\nNo such attribute.\nTry 'taw list --argdoc' to see all attributes.")
        output_table(params, header, rows)

    def list_availability_zones(dummy_arg):
        """ list all availability zones """
        ec2 = get_ec2_client()
        header = ['Name', 'State', 'Message', 'Region']; rows = []
        for az in ec2.describe_availability_zones()['AvailabilityZones']:
            row = [az['ZoneName'], az['State'], az['Messages'], az['RegionName']]
            rows.append(row)
        output_table(params, header, rows)

    def list_elastic_ip(dummy_arg):
        """ list all elastic IPs """

    def list_market_ami(option_strs):
        """ list recommended AMIs in AMI Marketplace """
        multiplier = 1
        add_unit = ''
        search_terms = []
        for opt_str in option_strs:
            if opt_str == 'day':
                multiplier = 24
            elif opt_str == 'week':
                multiplier = 24 * 7
            elif opt_str == 'month':
                multiplier = 24 * 31
            elif opt_str == 'year':
                multiplier = 365
            else:
                search_terms.append(opt_str)
            add_unit = '/' + opt_str
        db_path = get_AMI_DB_file_path()
        conn = sqlite3.connect(db_path)
        header = ['Name', 'AMI']
        if verbose:
            header += ['Instance Type', 'Total' + add_unit]
        rows = []
        my_region = get_aws_region()
        for sql_row in conn.execute("SELECT * FROM ami_ids;"):
            image_name = sql_row[0]
            if 0 < len(search_terms) and all(map(lambda x: re.search(x, image_name, re.I) == None, search_terms)): continue
            row = [image_name]
            region_to_ami = pickle.loads(sql_row[1])
            if my_region in region_to_ami:
                row.append(region_to_ami[my_region])
            else:
                row.append("N/A")
            if verbose:
                type_to_cost = pickle.loads(sql_row[2])
                its, tcs = [], []
                for type_str in sorted(type_to_cost.keys()):
                    d = type_to_cost[type_str]
                    its.append(d['InstanceType'])
                    if multiplier == 1:
                        tcs.append(d['CostTotal'])
                    else:
                        tcs.append("%9.2f" % (float(d['CostTotal']) * multiplier))
                row += [its, tcs]
            rows.append(row)
        output_table(params, header, rows)
        conn.close()

    def list_test():
        """ test function. (can be eliminated) """
        output_table(params, ["c1", "c2", "c3", "l"*100], [
            [1, 1, 3, "boo\nmoo\nnon\n"],
            [4, 5, 6, "bar"]], [lambda x: ({-1: 'red'} if int(x[1]) % 2 == 1 else None)])

    subcommand_table = {
        'instances'      : list_instance,
        'vpcs'           : list_vpc,
        'test'           : list_test,
        'subnets'        : list_subnet,
        'images'         : list_image,
        'keypairs'       : list_key_pairs,
        'localkeypairs'  : list_local_key_pairs,
        'snapshots'      : list_snapshots,
        'securitygroups' : list_security_groups,
        'sg'             : list_security_groups,
        'zone'           : list_zones,
        'buckets'        : list_s3_buckets,
        'az'             : list_availability_zones,
        'ip'             : list_elastic_ip,
        'market'         : list_market_ami,
        }
    if allregions:
        s = boto3.session.Session()
        params.output_noless = True
        is_first_region = True
        for region in s.get_available_regions('ec2'):
            set_aws_region(region)
            try:
                nick_name = region_name_to_region_nickname[region]
            except:
                nick_name = 'ask the author'
            if is_first_region:
                is_first_region = False
            else:
                print("")
            print(("=[%s (%s)]" % (region, nick_name)) + "=" * (70 - len(region) - len(nick_name)))
            call_function_by_unambiguous_prefix(subcommand_table, restype, subargs)
    else:
        call_function_by_unambiguous_prefix(subcommand_table, restype, subargs)

