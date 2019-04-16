#!/usr/bin/env python3

from __future__ import print_function
from __future__ import absolute_import
import click
import re
from taw.util import *
from taw.taw import *  # This must be the end of imports

# ==================
#  Completion
# ==================
@taw.command("completion")
@pass_global_parameters
def show_completion_command(params):
    """ Show a bash/zsh command for enabling bash/zsh command line completion """
    shell_env_string = os.environ['SHELL']
    r = re.match(r'^.*/(.*)', shell_env_string)
    if r:
        shell_name = r.group(1)
    else:
        shell_name = shell_env_string
    if shell_name == 'bash':
        print("Please execute the following command on the zsh prompt:")
        print()
        print('eval "$(_TAW_COMPLETE=source taw)"')
        print()
    elif shell_name == 'zsh':
        print("Please execute the following command on the zsh prompt:")
        print()
        print('eval "$(_TAW_COMPLETE=source_zsh taw)"')
        print()
    else:
        error_exit("'%s' is not supported (for completion)." % shell_name)


