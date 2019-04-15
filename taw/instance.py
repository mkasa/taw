#!/usr/bin/env python3

from __future__ import print_function
from __future__ import absolute_import
import os, click
from taw.list import *
from taw.util import *
from taw.taw import *  # This must be the end of imports
from six.moves import input
import shlex
import six


# ==================
#  INSTANCE COMMAND
# ==================
@taw.group("instance")
@pass_global_parameters
def instance_group(params):
    """ manage Amazon EC2 instances """


@instance_group.command("stop")
@click.argument('hostnames', nargs=-1, metavar='<host names>')
@click.option('--force', is_flag=True)
@pass_global_parameters
def stop_cmd(params, hostnames, force):
    """ stop an instance """
    for hostname in hostnames:
        instance = convert_host_name_to_instance(hostname)
        print("ID %s (%s) type=%s" % (instance.id, extract_name_from_tags(instance.tags), instance.instance_type))
        if force:
            instance.stop(DryRun=params.aws_dryrun)
    if force:
        print_info("%d hosts processed" % len(hostnames))
    else:
        print("Please add --force to actually stop the instances")


@instance_group.command("start")
@click.argument('hostnames', nargs=-1, metavar='<host names>')
@pass_global_parameters
def start_cmd(params, hostnames):
    """ start an instance """
    for hostname in hostnames:
        instance = convert_host_name_to_instance(hostname)
        instance.start(DryRun=params.aws_dryrun)
    print_info("%d hosts processed" % len(hostnames))


@instance_group.command("terminate")
@click.argument('hostnames', nargs=-1, metavar='<host names>')
@click.option('--force', is_flag=True)
@pass_global_parameters
def terminate_cmd(params, hostnames, force):
    """ start an instance """
    for hostname in hostnames:
        instance = convert_host_name_to_instance(hostname)
        print("ID %s (%s) type=%s" % (instance.id, extract_name_from_tags(instance.tags), instance.instance_type))
        if force:
            instance.terminate(DryRun=params.aws_dryrun)
    if force:
        print_info("%d hosts processed" % len(hostnames))
    else:
        print_warning("Please add --force to actually TERMINATE the instance(s).\nOnce you terminate them, they will be LOST.")


@instance_group.command("ip")
@click.argument('hostnames', nargs=-1, metavar='<host names>')
@click.option('-v', is_flag=True, help='show instance IDs as well')
@pass_global_parameters
def ip_cmd(params, hostnames, v):
    """ show a global IP address of a given instance """
    for hostname in hostnames:
        instance = convert_host_name_to_instance(hostname)
        if v:
            print("%s\t%s" % (instance.public_ip_address, instance.id))
        else:
            print(instance.public_ip_address)


@instance_group.command("register_market_ami", short_help='get machine image IDs of popular OS')
@click.option('-n', is_flag=True)
@pass_global_parameters
def register_market_ami_instancecmd(params, n):
    """ Get Amazon Machine Image ID (AMI ID) from the AWS web site
    """
    register_AMI_ID_to_local_database(n)


@instance_group.command("set_instance_type", short_help='set instance type')
@click.argument('new_instance_name', metavar='<new instance name>')
@click.argument('hostname', metavar='<host name>')
@pass_global_parameters
def change_instance_type_instancecmd(params, hostname, new_instance_name):
    """ change the instance type of a specified instance to a new one """
    instance = convert_host_name_to_instance(hostname)
    instance.modify_attribute(DryRun=params.aws_dryrun,
                              Attribute='instanceType',
                              Value=new_instance_name)


@instance_group.command("set_host_name", short_help='set/fix host name')
@click.argument('hostname', metavar='<host name>')
@pass_global_parameters
def set_host_name(params, hostname):
    """ set or fix the host name of a specified host """
    instance = convert_host_name_to_instance(hostname)
    import __main__
    cmdline = [__main__.__file__] + params.global_opt_str
    cmdline += ['ssh', hostname, '--', 'sudo', 'sh', '-c', shlex.quote("echo %s > /etc/hostname" % hostname)]
    subprocess.check_call(cmdline)
    cmdline = [__main__.__file__] + params.global_opt_str
    cmdline += ['ssh', hostname, '--', 'sudo', 'hostname', hostname]
    subprocess.check_call(cmdline)
    cmdline = [__main__.__file__] + params.global_opt_str
    cmdline += ['ssh', hostname, '--', 'cat', '/etc/hosts']
    etc_hosts = subprocess.check_output(cmdline)
    if len(list(filter(lambda x: re.search(hostname, x), six.text_type(etc_hosts).split("\\n")))) <= 0: # TODO: this needs to be more sophisticated ...
        print_info("/etc/hosts does not contain the host '%s'" % hostname)
        print_info("Try to add IP for the host...")
        cmdline = [__main__.__file__] + params.global_opt_str
        cmdline += ['ssh', hostname, '--', 'sudo', 'sh', '-c', shlex.quote("echo 127.0.0.1 %s >> /etc/hosts" % hostname)]
        subprocess.check_call(cmdline)


@instance_group.command("set_api_termination", short_help='allow/disallow API termination')
@click.argument('hostname', metavar='<host name>')
@click.option('--allow', is_flag=True, help="allow API termination")
@click.option('--disallow', is_flag=True, help="disallow API termination")
@pass_global_parameters
def set_api_termination_instancecmd(params, hostname, allow, disallow):
    """ change the permission for API termination.
        Either --allow or --disallow must be given.
    """
    if allow and disallow: error_exit("You can't give both --allow and --disallow")
    if not allow and not disallow: error_exit("You must give either --allow or --disallow")
    instance = convert_host_name_to_instance(hostname)
    instance.modify_attribute(DryRun=params.aws_dryrun,
                              Attribute='disableApiTermination',
                              Value='False' if allow else 'True')


@instance_group.command("set_ebs_optimization", short_help='enable/disable EBS optimization')
@click.option('--on', is_flag=True, help="turn on EBS optimization")
@click.option('--off', is_flag=True, help="turn off EBS optimization")
@click.argument('hostname', metavar='<host name>')
@pass_global_parameters
def set_ebs_optimization_instancecmd(params, hostname, on, off):
    """ enable/disable the EBS optimization for a given instance
        Either --on or --off must be given
        """
    if on and off: error_exit("You can't give both --on and --off")
    if not on and not off: error_exit("You must give either --on or --off")
    instance = convert_host_name_to_instance(hostname)
    instance.modify_attribute(DryRun=params.aws_dryrun,
                              Attribute='ebsOptimized',
                              Value='False' if off else 'True')


@instance_group.command("createimage", short_help='create a machine image (AMI)')
@click.argument('hostname', metavar='<host name>')
@click.argument('name')
@click.argument('description')
@click.argument('options', nargs=-1)
@pass_global_parameters
def createimage_instancecmd(params, hostname, name, description, options):
    """ create a machine image (AMI) from an instance (running or stopped)
        """
    instance = convert_host_name_to_instance(hostname)
    block_mapping = []
    noreboot = False
    for opt in options:
        r = re.match(r'(ephemeral\d+):(.*)', opt)
        if r:
            vname = r.group(1)
            devname = r.group(2)
            block_mapping += [{'VirtualName': vname, 'DeviceName': devname}]
            continue
        if opt == 'noreboot':
            noreboot = True
            continue

    image = instance.create_image(
            Name=name,
            Description=description,
            BlockDeviceMappings=block_mapping,
            NoReboot=noreboot
        )


def ask_instance_name_interactively(ctx, params, name):
    if name is None:
        print("")
        print("Name a new instance. Type '?' for listing current instances. CTRL+C to quit.")
    ec2 = get_ec2_connection()
    while True:
        while name is None:
            print("")
            new_name = input("  Name: ")
            if new_name.startswith('?'):
                with taw.make_context('taw', ctx.obj.global_opt_str + ['instance', 'list']) as ncon: _ = taw.invoke(ncon)
                continue
            if name == '': continue
            name = new_name
        if not re.match("^[\w\d]+$", name):
            print_warning("Name '%s' is invalid (contains illegal character(s))" % name)
            name = None
            continue
        instances = list(ec2.instances.filter(Filters=[{'Name': 'tag:Name', 'Values': [name]}]))
        if 0 < len(instances):
            print_warning("An instance with name '%s' already exists (ID=%s).\nTry with another name." % (name, instances[0].id))
            name = None
            continue
        break
    return name


def ask_instance_type_interactively(ctx, params, instancetype):
    if instancetype is None:
        print("")
        print("Choose an instance type. Type '?' for listing instance types. CTRL+C to quit.")
        print("To list specific types of instances, type '?prefix' (eg: ?t2)")
    completer = PrefixCompleter(instance_type_name_to_instance_type.keys()); readline.set_completer(completer.completer)
    while True:
        while instancetype is None:
            print("")
            new_inst = input("  Instance type: ")
            if new_inst.startswith('?'):
                prefix_str = new_inst[1:]
                header = ['type', '#vcpu', 'mem (GB)', 'desc']
                rows = []
                for t in sorted(instance_type_name_to_instance_type.keys()):
                    if not t.startswith(prefix_str): continue
                    v = instance_type_name_to_instance_type[t]
                    rows.append([t, v['vcpu'], v['mem'], v['desc']])
                output_table(params, header, rows)
                continue
            if new_inst == '': continue
            instancetype = new_inst
        if instancetype not in instance_type_name_to_instance_type:
            print_warning("%s is not a valid instance type" % instancetype)
            instancetype = None
            continue
        break
    return instancetype


def ask_ami_id_interactively(ctx, params, ami_id):
    ami_name = '(unknown)'
    db_path = get_AMI_DB_file_path()
    conn = sqlite3.connect(db_path)
    completion_candidates = [sql_row[0] for sql_row in conn.execute("SELECT * FROM ami_ids;")]
    # IMAGES
    ec2 = get_ec2_connection()
    images = ec2.images.filter(Filters=[{'Name': 'is-public', 'Values': ['false']}])
    image_id = map(lambda x: x.id, images)
    image_names = map(lambda x: x.name, images)
    completion_candidates += image_id
    completion_candidates += image_names
    if ami_id is None and len(completion_candidates) <= 0:
        error_exit("You have to register AMI ID first. Type 'taw instance register_market_ami'.\nAlternatively you can directly specify an AMI ID if you know one.")
    completer = PrefixCompleter(completion_candidates); readline.set_completer(completer.completer)
    if ami_id is None:
        print("")
        print("Enter an AMI ID you want to launch from. Alternatively you can type a part of the name of AMI.")
        print("Type '?' for listing registered AMIs, '??' for your AMIs. You can search abc for typing '?abc'. CTRL+C to quit.")
    while True:
        while ami_id is None:
            print("")
            new_ami_id = input("  AMI ID (or keyword): ")
            if new_ami_id.startswith('??'):
                search_str = new_ami_id[1:]
                with taw.make_context('taw', ctx.obj.global_opt_str + ['image', 'list', search_str]) as ncon: _ = taw.invoke(ncon)
                continue
            if new_ami_id.startswith('?'):
                search_str = new_ami_id[1:]
                with taw.make_context('taw', ctx.obj.global_opt_str + ['list', 'market', search_str]) as ncon: _ = taw.invoke(ncon)
                continue
            if new_ami_id == '': continue
            ami_id = new_ami_id
        # conver name to ami
        if not re.match('^ami-([\d\w]+)$', ami_id):
            my_region = get_aws_region()
            candidate_ami = []
            for sql_row in conn.execute("SELECT * FROM ami_ids;"):
                image_name = sql_row[0]
                if not image_name.startswith(ami_id): continue
                region_to_ami = pickle.loads(sql_row[1])
                if my_region in region_to_ami:
                    candidate_ami.append((image_name, region_to_ami[my_region]))
            for image in images:
                name = image.name
                if not name.startswith(ami_id): continue
                candidate_ami.append((name, image.id))
            if len(candidate_ami) <= 0:
                print_warning("No such AMIs. Try different AMI (or name query).")
                ami_id = None
                continue
            if 1 < len(candidate_ami):
                print_warning("Multiple hits for that query '%s'. Candidates are" % ami_name)
                for n, ami in candidate_ami:
                    print("\t%s\t(%s)" % (n, ami))
                ami_id = None
                continue
            ami_name, ami_id = candidate_ami[0]
        if not re.match('^ami-([\d\w]+)$', ami_id):
            print_warning("AMI ID '%s' does not look like an AMI ID" % ami_id)
            continue
        break
    return ami_id, ami_name


def ask_vpc_interactively(ctx, params, vpc_id):
    if vpc_id is None:
        print("")
        print("Choose a VPC. Type '?' for listing VPC. CTRL+C to quit. Type '+name' to create a new VPC 'name'.")
    ec2 = get_ec2_connection()
    completion_candidates = [extract_name_from_tags(i.tags) for i in ec2.vpcs.all()]
    completion_candidates += [i.id for i in ec2.vpcs.all()]
    completer = PrefixCompleter(completion_candidates); readline.set_completer(completer.completer)
    while True:
        while vpc_id is None:
            print("")
            input_str = input("  VPC ID or name: ")
            if input_str.startswith('?'):
                with taw.make_context('taw', ctx.obj.global_opt_str + ['vpc', 'list']) as ncon: _ = taw.invoke(ncon)
                continue
            if input_str.startswith('+'):
                new_vpc_name = input_str[1:]
                with taw.make_context('taw', ctx.obj.global_opt_str + ['vpc', 'create', new_vpc_name]) as ncon: _ = taw.invoke(ncon)
                vpc_id = new_vpc_name
                break
            if input_str.startswith('/'):
                pass
                # TODO: it might be useful if we can search here
            if input_str == '': continue
            vpc_id = input_str
        vpc = convert_vpc_name_to_vpc(vpc_id)
        if vpc is None:
            print_warning("No such VPC. Try with another name or ID.")
            vpc_id = None
            continue
        vpc_id = vpc.vpc_id
        break
    return vpc_id


def ask_subnet_interactively(ctx, params, vpc_id, subnet):
    if subnet is None:
        print("")
        print("Choose a subnet. Type '?' for listing subnet. CTRL+C to quit.\nType '+name 192.168.14.0/24' to create a new subnet 'name' with the specified CIDR.")
    ec2 = get_ec2_connection()
    completion_candidates = [extract_name_from_tags(i.tags) for i in ec2.subnets.filter(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])]
    completion_candidates += [i.id for i in ec2.subnets.filter(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])]
    completer = PrefixCompleter(completion_candidates); readline.set_completer(completer.completer)
    while True:
        while subnet is None:
            print("")
            input_str = input("  Subnet ID or name: ")
            if input_str.startswith('?'):
                with taw.make_context('taw', ctx.obj.global_opt_str + ['subnet', 'list', vpc_id]) as ncon: _ = taw.invoke(ncon)
                continue
            if input_str.startswith('+'):
                args_str = input_str[1:].strip()
                with taw.make_context('taw', ctx.obj.global_opt_str + ['subnet', 'create'] + re.split(r'\s+', args_str)) as ncon: _ = taw.invoke(ncon)
                continue
            if input_str.startswith('/'):
                pass
                # TODO: it might be useful if we can search here
            if input_str == '': continue
            subnet = input_str
        subnet = convert_subnet_name_to_subnet(subnet, False, vpc_id)
        if subnet is None:
            print_warning("No such subnet.")
            subnet = None
            continue
        subnet = subnet.subnet_id
        break
    return subnet


def ask_key_interactively(ctx, params, keyname):
    if keyname is None:
        print("")
        print("Choose a private key. Type '?' for listing keys. CTRL+C to quit.")
    ec2 = get_ec2_connection()
    completion_candidates = [k.key_name for k in ec2.key_pairs.all()]
    completer = PrefixCompleter(completion_candidates); readline.set_completer(completer.completer)
    while True:
        while keyname is None:
            print("")
            input_str = input("  Key name: ")
            if input_str.startswith('?'):
                with taw.make_context('taw', ctx.obj.global_opt_str + ['list', 'key']) as ncon: _ = taw.invoke(ncon)
                print("")
                print("You can import an existing key from your local storage,")
                print("or alternatively you can create a new one by typing '/'.")
                continue
            if input_str.startswith('/'):
                print("")
                print("Creating a new key pair...")
                print("")
                keyname = input("  New key name (hit return to go back): ")
                if keyname == '': continue
                with taw.make_context('taw', ctx.obj.global_opt_str + ['keypair', 'create', keyname]) as ncon: _ = taw.invoke(ncon)
                print("Created a new key '%s'" % keyname)
                break
            if input_str == '': continue
            keyname = input_str
        key_candidates = [k for k in ec2.key_pairs.all() if k.key_name == keyname]
        if len(key_candidates) <= 0:
            print_warning("No such key.")
            if os.path.exists(os.path.join(os.path.expanduser("~/.ssh"), keyname + ".pub")):
                print_warning("You forgot to import the key into AWS? Then, try 'taw keypair import'")
            elif os.path.exists(os.path.join(os.path.expanduser("~/.ssh"), keyname + ".pem")):
                print_warning("You forgot to import the key into AWS?\nI found something in ~/.ssh\nSee http://stackoverflow.com/questions/1011572/convert-pem-key-to-ssh-rsa-format for conversion.")
            keyname = None
            continue
        break
    return keyname


def ask_security_group_interactively(ctx, params, vpc_id, subnet_id, securitygroup):
    if len(securitygroup) <= 0:
        print("")
        print("Choose a security group(s). Type '?' for listing security groups. CTRL+C to quit.")
        print("Input a security group name or ID. You can enter multiple security groups; if done, type '-'.")
    ec2 = get_ec2_connection()
    candidates = [i.group_name for i in ec2.security_groups.filter(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])]
    candidates += [i.id for i in ec2.security_groups.filter(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])]
    completer = PrefixCompleter(candidates); readline.set_completer(completer.completer)
    while True:
        security_group_candidates = []
        while len(securitygroup) <= 0:
            print("")
            input_str = input("  Name or ID: ")
            if input_str.startswith('?'):
                with taw.make_context('taw', ctx.obj.global_opt_str + ['sg', 'list', vpc_id]) as ncon: _ = taw.invoke(ncon)
                continue
            if input_str == '': continue
            if input_str == '-':
                if 0 < len(security_group_candidates):
                    securitygroup = security_group_candidates
                    break
                print_warning("Not yet entered a single name or ID")
                continue
            if input_str in security_group_candidates:
                print_warning("Duplicated!")
                continue
            sg_by_ids = ec2.security_groups.filter(Filters=[{'Name': 'group-id', 'Values': [input_str]}])
            sg_by_names = ec2.security_groups.filter(Filters=[{'Name': 'group-name', 'Values': [input_str]},
                                                              {'Name': 'vpc-id', 'Values': [vpc_id]}])
            sgs = list(sg_by_ids) + list(sg_by_names)
            if len(sgs) != 1:
                if 1 < len(sgs):
                    print_warning("Multiple candidates")
                    for i in sgs:
                        print("\t%s (%s)" % (i.group_name, i.group_id))
                    continue
                print_warning("No such security group")
                continue
            security_group_candidates.append(sgs[0].group_id)
            print("")
            print("Type '-' if done. Current selection(s) are:")
            print("\t" + ", ".join(security_group_candidates))
        # check if they exist
        for sg_id in securitygroup:
            sg_by_ids = list(ec2.security_groups.filter(Filters=[{'Name': 'group-id', 'Values': [sg_id]}]))
            if len(sg_by_ids) <= 0:
                print_warning("Security group '%s' does not exist. Try again from the start." % sg_id)
                securitygroup = []
                break
        if 0 < len(securitygroup):
            break
    return securitygroup


def ask_shutdownbehavior_interactively(shutdownbehavior):
    if shutdownbehavior != 'stop' and shutdownbehavior != 'terminate':
        print("")
        print("When the new instance shuts down, you can choose from the following:")
        print("\tstop: the instance stops, you can start it again by 'taw instance start'")
        print("\tterminate: the instance terminates, it will be destroyed and deleted.")
    while shutdownbehavior != 'stop' and shutdownbehavior != 'terminate':
        candidates = ['stop', 'terminate']
        completer = PrefixCompleter(candidates); readline.set_completer(completer.completer)
        print("")
        shutdownbehavior = input("  When shutdown, should it [stop/terminate]? ")
    return shutdownbehavior


def ask_if_not_set(explanation_string, current_flag):
    if current_flag: return current_flag
    print("")
    print(explanation_string)
    readline.set_completer(None)
    while True:
        print("")
        a = input("  (y/[N])? ")
        if a == '': return False
        if re.match("y(e(s)?)?", a, re.I): return True
        if re.match("no?", a, re.I): return False
        print("yes or no.")


def ask_if_need_change(property_name, explanation_string, current_choice):
    print("")
    print("Current " + property_name + " is " + current_choice)
    print(explanation_string)
    readline.set_completer(None)
    while True:
        print("")
        a = input("  Change (y/[N])? ")
        if a == '': return current_choice
        if re.match("y(e(s)?)?", a, re.I):
            print("")
            input_str = input("  new " + property_name + "> ")
            if input_str == '': continue
            print(property_name + " is now " + current_choice)
            print("")
            continue
        if re.match("no?", a, re.I): return False
        print("yes or no.")


def estimate_root_accout_name_from_ami_name(ami_name):
    # https://alestic.com/2014/01/ec2-ssh-username/
    if re.search("ubuntu", ami_name, re.I): return 'ubuntu'
    if re.search("debian", ami_name, re.I): return 'admnin'
    if re.search("bitnami", ami_name, re.I): return 'bitnami'
    if re.search("cent ?os", ami_name, re.I): return 'centos'
    if re.search("suse", ami_name, re.I): return 'root'
    if re.search("turnkey", ami_name, re.I): return 'root'
    if re.search("nanostack", ami_name, re.I): return 'ubuntu'
    if re.search("omnios", ami_name, re.I): return 'ubuntu'
    return 'ec2-user'


@instance_group.command("launch", short_help='launch(run) a new instance interactively')
@click.option('--name')
@click.option('--instancetype')
@click.option('--amiid', help="Amazon Machine Image (AMI) ID")
@click.option('--vpc')
@click.option('--ami_name')
@click.option('--shutdownbehavior')
@click.option('--subnet')
@click.option('--rootaccount')
@click.option('--keyname', help="Name of SSH private key you use")
@click.option('--count', default=1, type=int, help="Number of instances you need to launch")
@click.option('--ebsoptimized', is_flag=True, help="Use optimized EBS backend")
@click.option('--noebsoptimized', is_flag=True, help="Do not use optimized EBS backend")
@click.option('--securitygroup', multiple=True)
@click.option('--disableapitermination', is_flag=True, help="Prevent a new instance from being terminated by API")
@click.option('--enableapitermination', is_flag=True, help="Allow termination by API")
@pass_global_parameters
@click.pass_context
def launch_instancecmd(ctx, params, name, instancetype, amiid, keyname, vpc, subnet, count, ebsoptimized, noebsoptimized, disableapitermination, enableapitermination, securitygroup, shutdownbehavior, rootaccount, ami_name):
    """ Launch a new instance interactively """

    try:
        count = int(count)
    except:
        error_exit(count + " is not an integer")
    (amiid, new_ami_name) = ask_ami_id_interactively(ctx, params, amiid)
    ami_name = ami_name or new_ami_name
    name = ask_instance_name_interactively(ctx, params, name)
    instancetype = ask_instance_type_interactively(ctx, params, instancetype)
    keyname = ask_key_interactively(ctx, params, keyname)
    vpc = ask_vpc_interactively(ctx, params, vpc)
    subnet = ask_subnet_interactively(ctx, params, vpc, subnet)
    securitygroup = ask_security_group_interactively(ctx, params, vpc, subnet, list(securitygroup))
    if enableapitermination:
        disableApiTermination = False
    else:
        disableapitermination = ask_if_not_set("Disable API termination? If set, you cannot DIRECTLY terminate the instance from taw.", disableapitermination)
    if noebsoptimized:
        ebsoptimized = False
    else:
        ebsoptimized = ask_if_not_set("Need EBS optimization? If set, you get faster storage but pay more. Not available for all instance types.", ebsoptimized)
    shutdownbehavior = ask_shutdownbehavior_interactively(shutdownbehavior)
    if rootaccount:
        root_account_name = rootaccount
    else:
        root_account_name = estimate_root_accout_name_from_ami_name(ami_name)
        root_account_name = ask_if_need_change("root (sudo) account", "The root account we guessed is right?", root_account_name)

    print("")
    print("=" * 70)
    print("EBS optimiation        :", ebsoptimized)
    print("root (sudo) account    :", root_account_name)
    print("=" * 70)
    print("You can retry this with the following command:")
    print("")
    cmd_line = "taw instance launch --count %d --name %s --instancetype %s --amiid %s --vpc %s --subnet %s --shutdownbehavior %s --keyname %s" % (
                    count, name, instancetype, amiid, vpc, subnet, shutdownbehavior, keyname)
    cmd_line += ''.join(map(lambda x: " --securitygroup " + x, securitygroup))
    cmd_line += " --rootaccount " + root_account_name
    cmd_line += " --ami_name '" + ami_name + "'"
    if disableapitermination:
        cmd_line += ' --disableapitermination'
    else:
        cmd_line += ' --enableapitermination'
    if ebsoptimized:
        cmd_line += ' --ebsoptimized'
    else:
        cmd_line += ' --noebsoptimized'
    print(cmd_line)
    print("=" * 70)
    ec2 = get_ec2_connection()
    print("")
    print("Creating new instance(s) ...")
    result_instances = ec2.create_instances(
        ImageId=amiid,
        MinCount=count,
        MaxCount=count,
        KeyName=keyname,
        InstanceType=instancetype,
        # Placement={
        #     'AvailabilityZone': 'string',
        #     'GroupName': 'string',
        #     'Tenancy': 'default',
        #     'HostId': 'string',
        #     'Affinity': 'string'
        # },
        # BlockDeviceMappings=[
        #     ],
        DisableApiTermination=disableapitermination,
        InstanceInitiatedShutdownBehavior='stop',
        EbsOptimized=ebsoptimized,
        NetworkInterfaces=[
            {
                'DeviceIndex': 0,
                'SubnetId': subnet,
                'Groups': securitygroup,
                'AssociatePublicIpAddress': True},
            ],  # noqa: E123
    )
    result_instances = list(result_instances)
    if len(result_instances) <= 0: error_exit("Could not create any instance(s)")
    wait_interval_in_sec = 3
    for inst in result_instances:
        while True:
            try:
                inst.create_tags(Tags=[
                    {'Key': 'Name', 'Value': name}             ,  # noqa: E203
                    {'Key': 'root', 'Value': root_account_name},
                    ])  # noqa: E123
                break
            except Exception as e:
                print(e)
                print("\nWait for %d seconds..." % wait_interval_in_sec)
                time.sleep(wait_interval_in_sec)  # interval
                wait_interval_in_sec += 3
        print("Successfully created an instance with ID = %s" % inst.id)
    print("Done.")


@instance_group.command("settag")
@click.argument('hostname')
@click.argument('tagname')
@click.argument('tagvalue')
@pass_global_parameters
def settag_instancecmd(params, hostname, tagname, tagvalue):
    """ set a value to a tag for a specified instance """
    instance = convert_host_name_to_instance(hostname)
    instance.create_tags(DryRun=params.aws_dryrun,
                         Tags=[{'Key': tagname,
                                'Value': tagvalue}])


@instance_group.command("rmtag")
@click.argument('hostname')
@click.argument('tagname')
@click.argument('tagvalue', required=False)
@pass_global_parameters
def removetag_instancecmd(params, hostname, tagname, tagvalue):
    """ remove a tag (w/a specified value, if anyh) for a specified instance """
    instance = convert_host_name_to_instance(hostname)
    if tagvalue is None:
        instance.delete_tags(DryRun=params.aws_dryrun,
                             Tags=[{'Key': tagname}])
    else:
        instance.delete_tags(DryRun=params.aws_dryrun,
                             Tags=[{'Key': tagname,
                                    'Value': tagvalue}])


@instance_group.command("name")
@click.argument('instanceid')
@click.argument('hostname')
@pass_global_parameters
def name_instancecmd(params, instanceid, hostname):
    """ name the specified instance """
    instance = convert_host_name_to_instance(instanceid)
    instance.create_tags(DryRun=params.aws_dryrun,
                         Tags=[{'Key': 'Name',
                                'Value': hostname}])
    if is_debugging: print("public ip = ", instance.public_ip_address)
    res = ssh_like_call(params, 'which', instanceid, ['hostnamectl'], True)
    if is_debugging: print(res)
    if res is not None and res.decode('utf-8').strip().endswith('/hostnamectl'):
        # The system has hostnamectl
        if is_debugging: print("Using hostnamectl")
        res = ssh_like_call(params, 'sudo', instanceid, ['-t', 'hostnamectl', 'set-hostname', hostname], True)
        if is_debugging: print(res)
    else:
        if is_debugging: print("Using an old-fashoned hostname")
        res = ssh_like_call(params, 'sudo', instanceid, ['-t', 'hostname', hostname], True)
        if is_debugging: print(res)
    res = ssh_like_call(params, 'cat', instanceid, ['cat', '/etc/hosts'], True)
    etc_hosts_lines = res.decode('utf-8').split("\n")
    if is_debugging:
        print("/etc/hosts:")
        for i in etc_hosts_lines:
            print("    " + i)
    if instance.public_ip_address is not None and all([i.find(instance.public_ip_address) == -1 for i in etc_hosts_lines]):
        line_to_add = "%s %s" % (instance.public_ip_address, hostname)
        new_etc_hosts = [line_to_add] + etc_hosts_lines
        res = ssh_like_call(params, 'sudo', instanceid, ['-t', 'perl', '-i', '-pe', '\'if($.==1){print"' + line_to_add + '\\n"}\'', '/etc/hosts'])
        print_info("Added an entry '%s' to /etc/hosts" % line_to_add)
    else:
        print_info("/etc/hosts already has an entry with the public IP (%s)." % instance.public_ip_address)


@instance_group.command("list")
@click.option('--verbose', '-v', is_flag=True, help='Verbose output.')
@click.option('--argdoc', is_flag=True, help='Show available attributes in a web browser')
@click.option('--attr', '-a', multiple=True, help='Attribute name(s).')
@click.option('--allregions', is_flag=True, help='List for all regions.')
@click.argument('subargs', nargs=-1)
@pass_global_parameters
def list_instance_instancecmd(params, verbose, argdoc, attr, allregions, subargs):
    """ list instances """
    if argdoc:
        click.launch('https://boto3.readthedocs.io/en/latest/reference/services/ec2.html#instance')
        return
    if allregions:
        list_for_all_regions(params, subargs, 'instance', lambda x: list_instancecmd(params, verbose, argdoc, attr, False))
        return
    all_list_columns = [
            (True , "tags"             , "Name"           , extract_name_from_tags)                                       ,
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
    completion_keywords = []
    try:
        for inst in instances:
            row = [f(getattr(inst, i)) for _, i, _, f in list_columns]
            row.append([extract_name_from_tags(i.tags, inst.subnet_id) for i in subnets if i.id == inst.subnet_id])
            row.append([extract_name_from_tags(i.tags, inst.vpc_id) for i in vpcs if i.id == inst.vpc_id])
            rows.append(row)
            completion_keywords += [{"host": row[0]}, {"instance_id": row[1]}, {"ip": inst.public_ip_address}]
    except AttributeError as e:
        error_exit(str(e) + "\nNo such attribute.\nTry 'taw list --argdoc' to see all attributes.")
    update_completion_keywords(completion_keywords, "instance")

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


@instance_group.command("showprice")
@click.argument('args', nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def showprice_instancecmd(ctx, args):
    """ list the price for each instance type """
    with taw.make_context('taw', ctx.obj.global_opt_str + ['list', 'price'] + list(args)) as ncon: _ = taw.invoke(ncon)
