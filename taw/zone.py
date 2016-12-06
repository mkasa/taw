#!/usr/bin/env python3

from __future__ import print_function
from __future__ import absolute_import
import os, sys, click
from taw.util import *
from taw.taw import * # This must be the end of imports

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
        'ResourceRecords': [ {'Value': v } for v in list(values)],
    }
    result = r53.change_resource_record_sets(
        HostedZoneId=zone_id,
        ChangeBatch={
            'Comment': 'taw.py',
            'Changes': [ {
                    'Action': 'UPSERT',
                    'ResourceRecordSet': resource_record_set,
            } ]
        }
    )
    change_info = result['ChangeInfo']
    print("ID: %s, Status: %s" % (change_info['Id'], change_info['Status']))

@zone_group.command("delete")
@click.argument('zonename', metavar='<zone name)>')
@click.argument('name', metavar='<subdomain name>')
@click.argument('type_str', metavar='<A|NS|TXT|...>')
@click.option('--force', is_flag=True, help='actually delete a record')
@pass_global_parameters
def delete_zonecmd(params, zonename, name, type_str, force):
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
                'Changes': [ {
                        'Action': 'DELETE',
                        'ResourceRecordSet': zone_to_delete,
                } ]
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
