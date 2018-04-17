#!/usr/bin/env python3

from __future__ import print_function
from __future__ import absolute_import
import click
from taw.util import *
from taw.taw import *  # This must be the end of imports


# ==============
#  ZONE COMMAND
# ==============
@taw.group("zone")
@pass_global_parameters
def zone_group(params):
    """ manage zones """


def complete_subdomain_name(possibly_subdomain, domain_name):
    """ Complete a full domain name from a possibly subdomain name.
        eg)
            complete_subdomain_name("abc", "example.com.") => "abc.example.com."
            complete_subdomain_name("abc.ab.", "example.com.") => "abc.ab."
            complete_subdomain_name("abc.ab.example.com", "example.com.") => "abc.ab.example.com."
    """
    if not domain_name.endswith('.'): domain_name += '.'
    if possibly_subdomain.endswith('.' + domain_name): return possibly_subdomain
    if possibly_subdomain.endswith('.' + domain_name[:-1]): return possibly_subdomain + '.'
    if possibly_subdomain.endswith('.'): return possibly_subdomain
    return possibly_subdomain + '.' + domain_name


@zone_group.command("add")
@click.argument('zonename', metavar='<zone name)>')
@click.argument('name', metavar='<subdomain name>')
@click.argument('type_str', metavar='<A|NS|TXT|...>')
@click.argument('values', nargs=-1, required=True, metavar='<value (eg: 123.45.67.89)>')
@click.option('--ttl', metavar='TTL', type=int, default=3600)
@click.option('--weight', type=int, default=100)
@pass_global_parameters
def add_zonecmd(params, zonename, name, type_str, values, ttl, weight):
    """ add a record to zone """
    r53 = get_r53_connection()
    zone_id = convert_zone_name_to_zone_id(zonename)
    name = complete_subdomain_name(name, zonename)
    resource_record_set = {
        'Name': name,
        'Type': type_str,
        'TTL': ttl,
        'ResourceRecords': [{'Value': v} for v in list(values)],
    }
    result = r53.change_resource_record_sets(
        HostedZoneId=zone_id,
        ChangeBatch={
            'Comment': 'taw.py',
            'Changes': [{
                    'Action': 'UPSERT',
                    'ResourceRecordSet': resource_record_set,
            }]
        }
    )
    change_info = result['ChangeInfo']
    print("ID: %s, Status: %s" % (change_info['Id'], change_info['Status']))


@zone_group.command("name")
@click.argument('zonename', metavar='<zone name)>')
@click.argument('name', metavar='<subdomain name>')
@click.argument('targetname', metavar='<instance name|instance ID|bucket name:>')
@click.option('--ttl', metavar='TTL', type=int, default=3600)
@click.option('--weight', type=int, default=100)
@pass_global_parameters
def name_zonecmd(params, zonename, name, targetname, ttl, weight):
    """ add an A record to the specified zone for a given EC2 instance or a given bucket.

        \b
        eg) Give an A record of 'db.example.com' for an instance with name 'db003'.
            taw name example.com db db003
        eg) Give a CNAME record of S3 Bucket 'static.example.com' for an S3 Bucket 'static.example.com'
            taw name example.com static static.example.com:
        """
    r53 = get_r53_connection()
    zone_id = convert_zone_name_to_zone_id(zonename)
    name = complete_subdomain_name(name, zonename)
    if targetname.endswith(":"):
        s3 = get_s3_connection()
        bucket_name = targetname[:-1]
        region_name_of_the_bucket = s3.meta.client.get_bucket_location(Bucket=bucket_name)["LocationConstraint"]
        # see http://docs.aws.amazon.com/AmazonS3/latest/dev/WebsiteEndpoints.html
        endpoint_url_domain = bucket_name + ".s3-website-" + region_name_of_the_bucket + ".amazonaws.com"
        if bucket_name != name[:-1]:
            error_exit("The bucket name (%s) must be the same as the (sub)domain name (%s).\nThis is a requirement by Amazon S3." % (bucket_name, name[:-1]))
        resource_record_set = {
            'Name': name,
            'Type': 'CNAME',
            'TTL': ttl,
            'ResourceRecords': [{'Value': endpoint_url_domain}],
        }
    else:
        instance = convert_host_name_to_instance(targetname)
        if instance.public_ip_address is None:
            error_exit("The instance '%s' (%s) has no public IP address" % (extract_name_from_tags(instance.tags), instance.id))
        values = [instance.public_ip_address]
        resource_record_set = {
            'Name': name,
            'Type': 'A',
            'TTL': ttl,
            'ResourceRecords': [{'Value': v} for v in list(values)],
        }
    result = r53.change_resource_record_sets(
        HostedZoneId=zone_id,
        ChangeBatch={
            'Comment': 'taw.py',
            'Changes': [{
                    'Action': 'UPSERT',
                    'ResourceRecordSet': resource_record_set,
            }]
        }
    )
    change_info = result['ChangeInfo']
    print("ID: %s, Status: %s" % (change_info['Id'], change_info['Status']))


@zone_group.command("rm")
@click.argument('zonename', metavar='<zone name)>')
@click.argument('name', metavar='<subdomain name>')
@click.argument('type_str', default='A', metavar='[A(default)|NS|TXT|...]')
@click.option('--force', is_flag=True, help='actually delete a record')
@pass_global_parameters
def rm_zonecmd(params, zonename, name, type_str, force):
    """ delete a record from zone """
    r53 = get_r53_connection()
    zone_id = convert_zone_name_to_zone_id(zonename)
    name = complete_subdomain_name(name, zonename)
    zone_to_delete = None
    for zone in r53.list_resource_record_sets(HostedZoneId=zone_id)['ResourceRecordSets']:
        if zone['Name'] == name and zone['Type'] == type_str:
            zone_to_delete = zone
            break
    else:
        error_exit("No such record (name='%s', type='%s')" % (name, type_str))
    if force:
        result = r53.change_resource_record_sets(
            HostedZoneId=zone_id,
            ChangeBatch={
                'Comment': 'taw.py',
                'Changes': [{
                        'Action': 'DELETE',
                        'ResourceRecordSet': zone_to_delete,
                }]
            }
        )
        change_info = result['ChangeInfo']
        print("ID: %s, Status: %s" % (change_info['Id'], change_info['Status']))
    else:
        print_info("The following record will be deleted from zone '%s' if run with '--force'" % zonename)
        output_table(params, ['Name', 'Type', 'TTL', 'Value'],
            [[zone_to_delete['Name'],
              zone_to_delete['Type'],
              zone_to_delete['TTL'],
              [x['Value'] for x in zone_to_delete['ResourceRecords']]
            ]])


@zone_group.command("list", add_help_option=False, context_settings=dict(ignore_unknown_options=True))
@click.argument('args', nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def list_instancecmd(ctx, args):
    """ list zones """
    with taw.make_context('taw', ctx.obj.global_opt_str + ['list', 'zone'] + list(args)) as ncon: _ = taw.invoke(ncon)
