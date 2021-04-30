#!/usr/bin/env python3

from __future__ import print_function
from __future__ import absolute_import
import click
from taw.util import *
from taw.taw import *  # This must be the end of imports


# ===============
#  SHELL COMMAND
# ===============
@taw.group("shell")
@pass_global_parameters
def shell_group(params):
    """ IPython Shell command """


ec2 = None
client = None
s3 = None


@shell_group.command("py")
@pass_global_parameters
def launch_ipython(params):
    """ Launch IPython shell """
    global ec2
    ec2 = get_ec2_connection()
    global client
    client = get_ec2_client()
    global s3
    s3 = get_s3_connection()
    import IPython
    IPython.embed()
