#!/usr/bin/env python3

from __future__ import print_function
from __future__ import absolute_import
import os, sys, subprocess, re, datetime, glob
import click, boto3, fnmatch
import sqlite3
from taw.util import *
from taw.taw import *  # This must be the end of imports


# ====================
#  Exported Functions
# ====================
def security_group_list_to_strs(cs):
    def sg_to_str(s):
        return dc(s, 'GroupName')
    return [sg_to_str(s) for s in cs]



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
    """ list various types of resources such as instances

        \b
        vpcs            : list VPCs
        subnets         : list subnets
        images          : list images
        keypairs        : list key pairs
        localkeypairs   : list local key pairs
        snapshots       : list snapshots
        securitygroups  : list security groups
        sg              : list security groups (short hand)
        zone            : list zones
        buckets         : list S3 buckets
        az              : list availability zones
        ip              : list elastic ip
        market          : list market AMIs
        price           : list instance prices
        identity        : show my identity
    """

    def list_subnet(vpc_id_if_any):
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
                vpc_is_found = False
                for i in vpcs:
                    if i.vpc_id == subnet.vpc_id:
                        if len(vpc_id_if_any) == 0 or i.vpc_id in vpc_id_if_any:
                            vpc_is_found = True
                            row.append([extract_name_from_tags(i.tags)])
                row.append([extract_name_from_tags(i.tags) for i in instances if i.subnet_id == subnet.subnet_id])
                if vpc_is_found:
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
                if 'IpProtocol' in d and d['IpProtocol'] == "-1":  # noqa: E221
                    group_ids = list(map(lambda x: x['GroupId'], d['UserIdGroupPairs']))
                    if len(group_ids) <= 0: return ['any']
                    return ['any(' + ", ".join(group_ids) + ')']
                if 'FromPort' not in d:
                    return ["N/A"]
                if d['FromPort'] == -1:
                    prot   = d['IpProtocol']  # noqa: E221
                    ranges = d['IpRanges']
                    return ["%s:%s" % (prot, i) for i in fs(ranges)]
                else:
                    prot  = d['IpProtocol']  # noqa: E221
                    froms = d['FromPort']
                    tos   = d['ToPort']      # noqa: E221
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
                    return ["%s/%s(%s)" % (prot, port_range_str, i) for i in fs(ranges)]
            return [i for x in arr for i in conv(x)]
        all_list_columns = [
                (True , "group_name"           , "Name"  , ident)            ,
                (True , "group_id"             , "ID"    , ident)            ,
                (True , "ip_permissions"       , "Ingress"  , str_sg_permission),
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
                config = zone['Config']
                row = [zone['Name'], config['Comment'] if 'Comment' in config else '',
                       config['PrivateZone'] if 'PrivateZone' in config else '', zone['ResourceRecordSetCount']]
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
            _, bucket_name, bucket_path = decompose_rpath(bucket_name_if_any[0])
            key_search_regex_if_any = bucket_name_if_any[1] if 1 < len(bucket_name_if_any) else None
            if bucket_name is None:
                bucket_name = bucket_path
            else:
                key_search_regex_if_any = bucket_path
            if is_debugging: print("Key pattern = '%s'" % key_search_regex_if_any, file=sys.stderr)
            all_list_columns = [
                    (True , "key"          , "Name"         , ident)                     ,
                    (True , "size"         , "Size"         , ident)                     ,
                    (False, "Object"       , "Content-Type" , lambda x: x().content_type),
                    (True , "last_modified", "Modified"     , ident)                     ,
                    (True , "owner"        , "Owner"        , lambda x: x['DisplayName']),
                    (False, "owner"        , "Owner ID"     , lambda x: x['ID'])         ,
                    (False, "storage_class", "Storage Class", ident)                     ,
                ]
            list_columns = [x for x in all_list_columns if verbose or x[0]]
            for v in attr: list_columns.append((True, v, v, ident))
            header = [x[2] for x in list_columns]; rows = []
            if verbose: header += ['Permission']
            if key_search_regex_if_any and re.match(r'[^\*]+\*$', key_search_regex_if_any):
                if is_debugging: print("Prefix='%s'" % key_search_regex_if_any[:-1], file=sys.stderr)
                query_object = s3.Bucket(bucket_name).objects.filter(Prefix=key_search_regex_if_any[:-1]).page_size(page_size)
            else:
                query_object = s3.Bucket(bucket_name).objects.page_size(page_size)
            try:
                for obj in query_object:
                    if key_search_regex_if_any and not fnmatch.fnmatch(obj.key, key_search_regex_if_any): continue
                    row = [f(getattr(obj, i)) for _, i, _, f in list_columns]  # noqa: F812
                    if verbose:
                        id_to_perm_bits = grants_to_id_to_perm_bits(obj.Acl().grants)
                        row.append(", ".join([k + "(" + perm_bit_to_str(v) + ")" for k, v in id_to_perm_bits.items()]))
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
            if verbose: header += ['Region']
            try:
                for b in s3.buckets.page_size(page_size):
                    bucket_name = b.name
                    row = [f(getattr(b, i)) for _, i, _, f in list_columns]
                    id_to_perm_bits = grants_to_id_to_perm_bits(b.Acl().grants)
                    row.append(", ".join([k + "(" + perm_bit_to_str(v) + ")" for k, v in id_to_perm_bits.items()]))
                    if verbose:
                        # NOTE: should do better in the future.
                        #       see https://github.com/boto/boto3/issues/292
                        region_name_of_the_bucket = s3.meta.client.get_bucket_location(Bucket=bucket_name)["LocationConstraint"]
                        row.append(region_name_of_the_bucket)
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
        if argdoc:
            click.launch('http://boto3.readthedocs.io/en/latest/reference/services/s3.html#S3.Client.list_buckets')
            return
        ec2 = get_ec2_connection()
        instances = ec2.instances.all()
        header = ['Name', 'Allocation ID', 'Association ID', 'Public IP', 'Domain', 'Instance ID', 'Private IP', 'Network Interface ID', 'Instance Name']; rows = []
        for i in ec2.vpc_addresses.all():
            row = [extract_name_from_tags(i.tags)]
            row += [i.allocation_id, i.association_id, i.public_ip, i.domain, i.instance_id, i.private_ip_address, i.network_interface_id]
            row.append([extract_name_from_tags(inst.tags) for inst in instances if inst.instance_id == i.instance_id])
            rows.append(row)
        output_table(params, header, rows)

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
            if 0 < len(search_terms) and all(map(lambda x: re.search(x, image_name, re.I) is None, search_terms)): continue
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

    def list_instance_price(dummy_arg):
        """ list the instance prices.
            How to calculate the instance prices is really complicated so
            I just decided to use the existing web service, ec2pricing.
            It displays the price for each instance. It calculates spot prices, too.
        """
        click.launch('http://ec2pricing.net/')

    def list_identity(dummy_arg):
        """ Show the identity of the user.
            This is useful to find your user ID
        """
        client = get_sts_client()
        r = client.get_caller_identity()
        output_table(params, ["User ID", "Account", "ARN"], [[r['UserId'], r['Account'], r['Arn']]])

    def list_instance(dummy_arg):
        """ List instances.
            This is a shorthand for 'taw instance list' but has fewer options. Use 'taw instance list' where possible.
            """
        s = boto3.session.Session()
        import __main__
        cmdline = [__main__.__file__] + params.global_opt_str + ['instance', 'list'] + list(subargs)
        subprocess.check_call(cmdline)

    def list_image(dummy_argument):
        """ List images.
            """
        s = boto3.session.Session()
        import __main__
        cmdline = [__main__.__file__] + params.global_opt_str + ['image', 'list'] + list(subargs)
        subprocess.check_call(cmdline)

    # def list_test():
        # """ test function. (can be eliminated) """
        # output_table(params, ["c1", "c2", "c3", "l" * 100], [
    #         [1, 1, 3, "boo\nmoo\nnon\n"],
    #         [4, 5, 6, "bar"]], [lambda x: ({-1: 'red'} if int(x[1]) % 2 == 1 else None)])

    subcommand_table = {
            'instances'      : list_instance,
            # 'vpcs'           : list_vpc,
            # 'test'           : list_test,
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
            'price'          : list_instance_price,
            'identity'       : list_identity
        }
    if allregions:
        s = boto3.session.Session()
        if is_gnu_parallel_available():
            cmdlines = []
            import __main__
            for region in s.get_available_regions('ec2'):
                cmdlines.append([__main__.__file__] + params.global_opt_str + ['--region', region, '--subprocess', 'color', 'list', restype] + list(subargs))
            # print("===")
            # for i in cmdlines: print(i)
            # print("===")
            parallel_subprocess_by_gnu_parallel(cmdlines)
        else:
            params.output_noless = True
            is_first_region = True
            for region in s.get_available_regions('ec2'):
                set_aws_region(region)
                try:
                    nick_name = region_name_to_region_nickname[region]
                except:
                    nick_name = 'ask the author (need to add to the table)'
                if is_first_region:
                    is_first_region = False
                else:
                    print("")
                print_fence("[%s (%s)]" % (region, nick_name))
                call_function_by_unambiguous_prefix(subcommand_table, restype, subargs)
    else:
        call_function_by_unambiguous_prefix(subcommand_table, restype, subargs)


def list_for_all_regions(params, subargs, restype, func):
    """ List resources in all AWS regions.
        params is a global parameter object of click
        restype is a resource type such as 'instance' or 'vpc'
        """
    s = boto3.session.Session()
    if is_gnu_parallel_available():
        cmdlines = []
        import __main__
        for region in s.get_available_regions('ec2'):
            cmdlines.append([__main__.__file__] + params.global_opt_str + ['--region', region, '--subprocess', 'color', restype, 'list'] + list(subargs))
        # print("===")
        # for i in cmdlines: print(i)
        # print("===")
        parallel_subprocess_by_gnu_parallel(cmdlines)
    else:
        params.output_noless = True
        is_first_region = True
        for region in s.get_available_regions('ec2'):
            set_aws_region(region)
            try:
                nick_name = region_name_to_region_nickname[region]
            except:
                nick_name = 'ask the author (need to add to the table)'
            if is_first_region:
                is_first_region = False
            else:
                print("")
            print_fence("[%s (%s)]" % (region, nick_name))
            func()
