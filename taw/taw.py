#!/usr/bin/env python3

from __future__ import print_function
from __future__ import absolute_import
import colorama
import click
from taw.util import *

# constants
_VERSION_STRING = "0.0.0"


# click decorator
class GlobalParameters(object):
    def __init__(self):
        pass

    def __repr__(self):
        return '<GlobalParameters>'


pass_global_parameters = click.make_pass_decorator(GlobalParameters)


# commands/subcommands
@click.group(help="Tiny Amazon Wrapper")
@click.version_option(_VERSION_STRING)
@click.option('--region', '-r', envvar='AWS_DEFAULT_REGION', help='AWS region.', type=click.Choice(look_for_completion_region()))
@click.option('--noheader', is_flag=True, help='Do not output the header line.')
@click.option('--format', '-f', 'format_type', default='simple_with_color', help='Output format.', type=click.Choice(['csv', 'json', 'tsv', 'simple', 'simple_with_color']))
@click.option('--noless', '-n', is_flag=True, help='Do not invoke less.')
@click.option('--debug', is_flag=True, help='Turn on debugging.')
@click.option('--profile', '-p', 'aws_profile', help='Choose profile.', type=click.Choice(look_for_completion_profile()))
@click.option('--dryrun', is_flag=True, help='Dry-run. This may not be supported by commands that do not change the state.')
@click.option('--subprocess', help='Used internally')
@click.pass_context
def taw(ctx, region, noheader, format_type, noless, debug, aws_profile, subprocess, dryrun):
    """ main command group """
    ctx.obj = GlobalParameters()
    opt_lists = []   # this is for command redirection such as ('taw instance list' -> 'taw list instance') (*)
    if subprocess == 'color':
        colorama.init(strip=False)
    else:
        colorama.init()
    set_debugging_status(debug)
    if debug: opt_lists.append('--debug')
    if aws_profile:
        if aws_profile == "default":
            del os.environ["AWS_PROFILE"]
        else:
            set_aws_profile(aws_profile)
            opt_lists += ['--profile', aws_profile]
    if region in region_nickname_to_region_name: region = region_nickname_to_region_name[region]
    if region:
        opt_lists += ['--region', region]
        set_aws_region(region)
    else:
        region = read_default_region_from_config(aws_profile)
        set_aws_region(region)
    ensure_credential(ctx.obj)
    ctx.obj.output_header = not noheader
    if noheader:
        opt_lists += ['--noheader']
    ctx.obj.output_format = format_type
    opt_lists += ['--format', format_type]
    ctx.obj.output_noless = noless
    if noless: opt_lists += ['--noless']
    ctx.obj.aws_dryrun = dryrun
    if dryrun: opt_lists += ['--dryrun']
    ctx.obj.global_opt_str = opt_lists  # Again, this is for command redirection.See the above (*)
    if subprocess:
        try:
            nick_name = region_name_to_region_nickname[region]
        except:
            nick_name = 'ask the author (need to add to the table)'
        print("")
        print_fence("[%s (%s)]" % (region, nick_name))
