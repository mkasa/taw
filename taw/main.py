#!/usr/bin/env python3

from __future__ import print_function
from __future__ import absolute_import
import sys
import re, botocore
from taw.util import *
import taw.sshlike
import taw.instance
import taw.zone
import taw.bucket
import taw.vpc
import taw.subnet
import taw.list
import taw.sg
import taw.keypair
import taw.ip
import taw.image
import taw.completion
from taw.taw import *  # This must be the end of imports

# commands/subcommands


# Main runner
def main():
    try:
        taw()
    except botocore.exceptions.EndpointConnectionError as e:
        error_exit("Cannot connect to AWS. Check the network connection.\n" + str(e))
    except botocore.exceptions.ClientError as e:
        error_msg = str(e)
        if re.search('but DryRun flag is set.', error_msg):
            print("Request would have succeeded, but DryRun flag is set.")
            sys.exit(0)
        error_exit(str(e))


if __name__ == '__main__':
    main()
