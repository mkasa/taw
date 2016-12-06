#!/usr/bin/env python3

from __future__ import print_function
from __future__ import absolute_import
import os, sys, click
import subprocess
from taw.util import *
from taw.taw import *

# commands/subcommands

# ==============
#  SSH COMMAND
# ==============
@taw.command("ssh")
@click.argument('hostname', metavar='<host name>')
@click.argument('sshargs', nargs=-1)
@pass_global_parameters
def ssh_cmd(params, hostname, sshargs):
    """ do SSH to a specified host """
    ssh_like_call(params, 'ssh', hostname, sshargs)

# ==============
#  MOSH COMMAND
# ==============
@taw.command("mosh")
@click.argument('hostname', metavar='<host name>')
@click.argument('moshargs', nargs=-1)
@pass_global_parameters
def mosh_cmd(params, hostname, moshargs):
    """ do MOSH to a specified host """
    ssh_like_call(params, 'mosh', hostname, moshargs)

# ==============
#  RSSH COMMAND
# ==============
@taw.command("rssh")
@click.argument('hostname', metavar='<host name>')
@click.argument('rsshargs', nargs=-1)
@pass_global_parameters
def rssh_cmd(params, hostname, rsshargs):
    """ do rSSH to a specified host """
    ssh_like_call(params, 'rssh', hostname, rsshargs)

# ==============
#  SCP COMMAND
# ==============
@taw.command("scp")
@click.argument('src', nargs=-1)
@click.argument('dst', nargs=1)
@click.option('-i', 'key_file_path', help='SSH key file')
@click.option('-p', 'preserve_flag', is_flag=True, help='preserve attrs')
@click.option('-B', 'batch_flag', is_flag=True, help='batch mode')
@click.option('-C', 'compression_flag', is_flag=True, help='enable compression')
@click.option('-c', 'cypher', help='cypher type')
@click.option('-l', 'limit_bandwidth', help='bandwidth limit in Kb/s')
@click.option('-P', 'port', default=None, type=int, help='port number')
@click.option('-r', 'recursive_flag', is_flag=True, help='recursive copy')
@click.option('-q', 'quiet_flag', is_flag=True, help='quiet mode')
# TODO: support -v/-vv/-vvv, -o, -F (, -1, -2, -3, -4, -6 at lower priority)
@pass_global_parameters
def scp_cmd(params, src, dst, key_file_path, preserve_flag, batch_flag, compression_flag, cypher, limit_bandwidth, port, recursive_flag, quiet_flag):
    """ do scp to/from a specified host """
    args = ['scp']
    if preserve_flag: args.append('-p')
    if batch_flag: args.append('-B')
    if compression_flag: args.append('-C')
    if cypher: args += ['-c', cypher]
    if limit_bandwidth: args += ['-l', limit_bandwidth]
    if port: args += ['-P', port]
    if recursive_flag: args.append('-r')
    if quiet_flag: args.append('-q')
    (dest_user, dest_host, dest_path) = decompose_rpath(dst)
    copying_local_to_remote = dest_host != None
    if copying_local_to_remote:
        instance = convert_host_name_to_instance(dest_host)
        if instance.public_ip_address == None: error_exit("The instance has no public IP address")
        dest_host = instance.public_ip_address
        if dest_user == '_': dest_user = os.environ['USER']
        if dest_user == None: dest_user = get_root_like_user_from_instance(instance)
        if key_file_path == None: key_file_path = os.path.join(os.path.expanduser("~/.ssh"), instance.key_name + ".pem")
        if os.path.exists(key_file_path):
            args += ['-i', key_file_path]
        else:
            print_info("Key file '%s' does not exist.\nThe default keys might be used" % key_file_path)
        args += list(src) + ["%s@%s:%s" % (dest_user, dest_host, dest_path)]
    else:
        # copying remote to local
        sources_arr = [decompose_rpath(i) for i in src]
        for host in sources_arr[1:]:
            if host[1] != sources_arr[0][1]: error_exit("Multiple source hosts are not supported.")
            if host[0] != sources_arr[0][0]: error_exit("Multiple source users are not supported.")
        instance = convert_host_name_to_instance(sources_arr[0][1])
        if instance.public_ip_address == None: error_exit("The instance has no public IP address")
        src_host = instance.public_ip_address
        src_user = sources_arr[0][0]
        if src_user == '_': src_user = os.environ['USER']
        if src_user == None: src_user = get_root_like_user_from_instance(instance)
        if key_file_path == None: key_file_path = os.path.join(os.path.expanduser("~/.ssh"), instance.key_name + ".pem")
        if os.path.exists(key_file_path):
            args += ['-i', key_file_path]
        else:
            print_info("Key file '%s' does not exist.\nThe default keys might be used" % key_file_path)
        args += ["%s@%s:%s" % (src_user, src_host, x[2]) for x in sources_arr]
        args.append(dst)
    if params.aws_dryrun:
        print(" ".join(args))
        return
    try:
        subprocess.check_call(args)
    except:
        pass

