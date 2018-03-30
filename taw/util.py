#!/usr/bin/env python3

from __future__ import print_function
import os, sys, click
import subprocess, re, datetime, mimetypes
import boto3, botocore
import tabulate, json, colorama
import pyperclip, time, sqlite3, pickle, readline
from termcolor import colored

# Global variables
home_dir = os.environ['HOME']
param_region = None
param_profile = None
is_debugging = False

# Debugging
def set_debugging_status(s):
    global is_debugging
    is_debugging = s

# EC2 client
global_ec2_client = None
def get_ec2_client():
    global global_ec2_client
    if global_ec2_client != None: return global_ec2_client
    global_ec2_client = boto3.client('ec2', region_name=param_region)
    return global_ec2_client

# EC2 connection
global_ec2_connection = None
def get_ec2_connection():
    global global_ec2_connection
    if global_ec2_connection != None: return global_ec2_connection
    global_ec2_connection = boto3.resource('ec2', region_name=param_region)
    return global_ec2_connection

# Route53 connection
global_r53_connection = None
def get_r53_connection():
    global global_r53_connection
    if global_r53_connection != None: return global_r53_connection
    global_r53_connection = boto3.client('route53', region_name=param_region)
    return global_r53_connection

# S3 connection
global_s3_connection = None
def get_s3_connection():
    global global_s3_connection
    if global_s3_connection != None: return global_s3_connection
    global_s3_connection = boto3.resource('s3', region_name=param_region)
    return global_s3_connection

# S3 client
global_s3_client = None
def get_s3_client():
    global global_s3_client
    if global_s3_client != None: return global_s3_client
    global_s3_client = boto3.client('s3', region_name=param_region)
    return global_s3_client

# IAM client
global_iam_client = None
def get_iam_client():
    global global_iam_client
    if global_iam_client != None: return global_iam_client
    global_iam_client = boto3.client('iam', region_name=param_region)
    return global_iam_client

# Set region
def set_aws_region(region_name):
    """ set the AWS region.
        The argument must be for example 'us-east-1'. Nicknames for regions (eg, 'tokyo) is not accepted.
        Calling this function will clear any existing connections """
    global param_region
    global global_ec2_client
    global global_ec2_connection
    global global_r53_connection
    global global_s3_connection
    global global_s3_client
    if param_region != region_name:
        param_region = region_name
        if is_debugging: print("AWS DEFAULT REGION WAS SET TO " + region_name, file=sys.stderr)
        global_ec2_client     = None
        global_ec2_connection = None
        global_r53_connection = None
        global_s3_connection  = None
        global_s3_client      = None

def get_aws_region():
    return param_region

# Set profile
def set_aws_profile(profile_name):
    """ set the AWS credential profile.
        See http://boto3.readthedocs.io/en/latest/guide/configuration.html for details.
    """
    global param_profile
    global global_ec2_client
    global global_ec2_connection
    global global_r53_connection
    global global_s3_connection
    if param_profile != profile_name:
        param_profile = profile_name
        boto3.setup_default_session(profile_name=param_profile)
        if is_debugging: print("AWS DEFAULT PROFILE WAS SET TO " + profile_name, file=sys.stderr)
        global_ec2_client     = None
        global_ec2_connection = None
        global_r53_connection = None
        global_s3_connection  = None

# utility functions
def ident(x):
    """ Identity function """
    return x

def dc(di, element_name):
    """ returns the child element `element_name' if any.
        returns None otherwise (when di is null or there is no such child element
    """
    if di == None: return None
    if element_name in di: return di[element_name]
    return None

def error_exit(msg):
    """ print an error message and exit with error code 2
        msg can contain newlines if needed.
    """
    lines = msg.split("\n")
    click.secho("ERROR: " + ("\n       ".join(lines)), fg='red')
    sys.exit(2)

def print_warning(msg):
    """ print a warning message
        msg can contain newlines if needed.
    """
    lines = msg.split("\n")
    click.secho("WARNING: " + ("\n         ".join(lines)), fg='yellow')

def print_info(msg):
    """ print an informational message
        msg can contain newlines if needed.
    """
    lines = msg.split("\n")
    click.secho("INFO: " + ("\n      ".join(lines)), fg='white')

def convert_amazon_time_to_local(s):
    """ parse a date-time string given by Amazon and outputs the string of the local time"""
    return datetime.datetime.strftime(datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%fZ"), '%c')

def ensure_credential(p):
    """ ensure that the target AWS region and the credentials are
        properly given
    """
    config_file_path = os.path.join(home_dir, ".aws", "config")
    have_config_file = os.path.exists(config_file_path)
    have_cred_file = os.path.exists(os.path.join(home_dir, ".aws", "credentials"))
    if param_region == None:
        if have_config_file:
            if (3, 0) <= sys.version_info:
                import configparser
                configp = configparser.SafeConfigParser()
            else:
                import ConfigParser
                configp = ConfigParser.SafeConfigParser()
            configp.read(config_file_path)
            section_name = 'default'
            if param_profile: section_name = 'profile ' + param_profile
            region_name_in_config = configp.get(section_name, 'region')
            set_aws_region(region_name_in_config)
        else:
            error_exit("""You must specify an AWS region by --region or
by AWS_DEFAULT_REGION environment variable, or
by ~/.aws/config
""")
    if not have_cred_file and not ('AWS_SECRET_ACCESS_KEY' in os.environ) and not have_config_file:
        error_exit("""You must give a credential for EC2 by
AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY,
or by ~/.aws/credentials, or by ~/.aws/config.
See http://docs.aws.amazon.com/cli/latest/userguide/cli-chap-getting-started.html for details.
""")

region_name_to_region_nickname = {
    "us-east-1"      : "virginia",
    "us-east-2"      : "ohio",
    "us-west-1"      : "california",
    "us-west-2"      : "oregon",
    "ca-central-1"   : "canada",
    "sa-east-1"      : "sanpaulo",
    "eu-west-1"      : "ireland",
    "eu-west-2"      : "london",
    "eu-central-1"   : "frankfurt",
    "ap-southeast-1" : "singapore",
    "ap-southeast-2" : "sydney",
    "ap-northeast-1" : "tokyo",
    "ap-northeast-2" : "seoul",
    "ap-south-1"     : "mumbai"
    }
region_nickname_to_region_name = dict([(v, k) for k, v in region_name_to_region_nickname.items()])

def normalize_region_name(region_name, error_on_exit=True):
    """ normalize a given region name.
        If the given region name is a nickname (eg, oregon), it will be converted to the corresponding region name (eg, us-west-2).
        If the given region name is an official AWS region name (eg, us-west-2), it will return the name as it is.
    """
    if region_name in region_name_to_region_nickname: return region_name
    if region_name in region_nickname_to_region_name: return region_nickname_to_region_name[region_name]
    if error_on_exit:
        error_exit("Region name '%s' is not a region name nor a region nickname" % region_name)
    return None

instance_type_name_to_instance_type = {
    "t2.nano"        : {"vcpu" :   1, "mem" :  0.5, "desc" :  "3 credit minutes/hour, EBS backend"},
    "t2.micro"       : {"vcpu" :   1, "mem" :    1, "desc" :  "6 credit minutes/hour, EBS backend"},
    "t2.small"       : {"vcpu" :   1, "mem" :    2, "desc" :  "12 credit minutes/hour, EBS backend"},
    "t2.medium"      : {"vcpu" :   2, "mem" :    4, "desc" :  "24 credit minutes/hour, EBS backend"},
    "t2.large"       : {"vcpu" :   2, "mem" :    8, "desc" :  "36 credit minutes/hour, EBS backend"},
    "m4.large"       : {"vcpu" :   2, "mem" :    8, "desc" :  "450Mbps EBS, EBS backend"},
    "m4.xlarge"      : {"vcpu" :   4, "mem" :   16, "desc" :  "750Mbps EBS, EBS backend"},
    "m4.2xlarge"     : {"vcpu" :   8, "mem" :   32, "desc" :  "1Gbps EBS, EBS backend"},
    "m4.4xlarge"     : {"vcpu" :  16, "mem" :   64, "desc" :  "2Gbps EBS, EBS backend"},
    "m4.10xlarge"    : {"vcpu" :  40, "mem" :  160, "desc" :  "4Gbps EBS, EBS backend"},
    "m3.medium"      : {"vcpu" :   1, "mem" : 3.75, "desc" :  "1x4GB SSD"},
    "m3.large"       : {"vcpu" :   2, "mem" :  7.5, "desc" :  "1x32GB SSD"},
    "m3.xlarge"      : {"vcpu" :   4, "mem" :   15, "desc" :  "2x40GB SSD"},
    "m3.2xlarge"     : {"vcpu" :   8, "mem" :   30, "desc" :  "2x80GB SSD"},
    "c4.large"       : {"vcpu" :   2, "mem" : 3.75, "desc" :  "500Mbps EBS, EBS backend"},
    "c4.xlarge"      : {"vcpu" :   4, "mem" :  7.5, "desc" :  "750Mbps EBS, EBS backend"},
    "c4.2xlarge"     : {"vcpu" :   8, "mem" :   15, "desc" :  "1Gbps EBS, EBS backend"},
    "c4.4xlarge"     : {"vcpu" :  16, "mem" :   30, "desc" :  "2Gbps EBS, EBS backend"},
    "c4.8xlarge"     : {"vcpu" :  32, "mem" :   60, "desc" :  "4Gbps EBS, EBS backend"},
    "c3.large"       : {"vcpu" :   2, "mem" : 3.75, "desc" :  "2x16GB SSD"},
    "c3.xlarge"      : {"vcpu" :   4, "mem" :  7.5, "desc" :  "2x40GB SSD"},
    "c3.2xlarge"     : {"vcpu" :   8, "mem" :   15, "desc" :  "2x80GB SSD"},
    "c3.4xlarge"     : {"vcpu" :  16, "mem" :   30, "desc" :  "2x160GB SSD"},
    "c3.8xlarge"     : {"vcpu" :  32, "mem" :   60, "desc" :  "2x320GB SSD"},
    "x1.32xlarge"    : {"vcpu" : 128, "mem" : 1952, "desc" :  "2x1920GB SSD, 10Gbps EBS"},
    "r3.large"       : {"vcpu" :   2, "mem" : 15.25, "desc" :  "1x32GB SSD"},
    "r3.xlarge"      : {"vcpu" :   4, "mem" : 30.5, "desc" :  "1x80GB SSD"},
    "r3.2xlarge"     : {"vcpu" :   8, "mem" :   61, "desc" :  "1x160GB SSD"},
    "r3.4xlarge"     : {"vcpu" :  16, "mem" :  122, "desc" :  "1x320GB SSD"},
    "r3.8xlarge"     : {"vcpu" :  32, "mem" :  244, "desc" :  "2x320GB SSD"},
    "g2.2xlarge"     : {"vcpu" :   8, "mem" :   15, "desc" :  "1 GPU (Kepler, GK104), 1x60GB SSD"},
    "g2.8xlarge"     : {"vcpu" :  32, "mem" :   60, "desc" :  "4 GPUs (Kepler, GK104), 2x120GB SSD"},
    "i2.xlarge"      : {"vcpu" :   4, "mem" : 30.5, "desc" :  "1x800GB SSD"},
    "i2.2xlarge"     : {"vcpu" :   8, "mem" :   61, "desc" :  "2x800GB SSD"},
    "i2.4xlarge"     : {"vcpu" :  16, "mem" :  122, "desc" :  "4x800GB SSD"},
    "i2.8xlarge"     : {"vcpu" :  32, "mem" :  244, "desc" :  "8x800GB SSD"},
    "d2.xlarge"      : {"vcpu" :   4, "mem" : 30.5, "desc" :  "3x2TB HDD"},
    "d2.2xlarge"     : {"vcpu" :   8, "mem" :   61, "desc" :  "6x2TB HDD"},
    "d2.4xlarge"     : {"vcpu" :  16, "mem" :  122, "desc" :  "12x2TB HDD"},
    "d2.8xlarge"     : {"vcpu" :  36, "mem" :  244, "desc" :  "24x2TB HDD"},
    "p2.xlarge"      : {"vcpu" :   4, "mem" :   61, "desc" :  "1 GPU (K80)"},
    "p2.8xlarge"     : {"vcpu" :  32, "mem" :  488, "desc" :  "4 GPUs (K80)"},
    "p2.16xlarge"    : {"vcpu" :  64, "mem" :  732, "desc" :  "16 GPUs (K80)"},
}

trusted_ami_owners = [
    'amazon',         # Amazon, of course
    '309956199498',   # RedHat
    '099720109477',   # Ubuntu
]

def read_from_aws_profile(profile_name):
    profile_file_path = profile_name
    if not profile_file_path.startswith('/'):
        profile_file_path = os.path.join(os.environ['HOME'], '.aws', profile_file_path + '.sh')
    try:
        o = subprocess.check_output([os.environ['SHELL'], '-c',
                                     'source ' + profile_file_path + '; ' +
                                     'echo $AWS_ACCESS_KEY_ID; ' +
                                     'echo $AWS_SECRET_ACCESS_KEY; ' +
                                     'echo $AWS_DEFAULT_REGION'])
    except:
        error_exit("Cannot find or had an error with profile '%s'\nThe searched file was '%s'" % (profile_name, profile_file_path))
    xs = o.decode('utf-8').split("\n")
    os.environ['AWS_DEFAULT_REGION']    = xs[-2]
    os.environ['AWS_SECRET_ACCESS_KEY'] = xs[-3]
    os.environ['AWS_ACCESS_KEY_ID']     = xs[-4]

def multicolumn_tabulate(rows, header, coloring):
    """ create the string of a textual table defined by header and rows with coloring
        header is the list of header strings.
        rows is the list or rows. Each row contains the list of columns.
        coloring is the list of functions that takes a row and returns
             color (such as 'red' or None) if needed. If None, no color is used.
    """
    # check the types to determine if we have to right-justify
    is_rightjustify = [False for _ in range(len(header))]
    for i in range(len(header)):
        for row in rows:
            if i < len(row) and row[i] != None:
                v = row[i]
                if isinstance(v, list) and 0 < len(v): v = v[0]
                if isinstance(v, bool) or isinstance(v, str):
                    break
                elif isinstance(v, int) or isinstance(v, float):
                    is_rightjustify[i] = True
                    break
                else:
                    break
    # str'fy
    header = [str(x) for x in header]
    rows = [[("\n".join([str(i).rstrip() for i in x]) if isinstance(x, list) else str(x).rstrip()) if x != None else '' for x in row] for row in rows]
    # calculate the column width and the row heights
    column_index_to_max_width = [0 for _ in range(len(header))]
    for i, x in enumerate(header):
        column_index_to_max_width[i] = max(column_index_to_max_width[i], len(x))
    row_index_to_max_height = []
    def str_to_height(s):
        return len(s.split("\n"))
    def str_to_width(str_w_newlines):
        return max([len(x) for x in str_w_newlines.split("\n")])
    for row in rows:
        for i, x in enumerate(row):
            column_index_to_max_width[i] = max(column_index_to_max_width[i], str_to_width(x))
        row_index_to_max_height.append(max(map(str_to_height, row)))
    # let's generate the output string
    lines = []
    # draw the header
    lines.append(" ".join(["%-*s" % (column_index_to_max_width[i], x) for i, x in enumerate(header)]))
    lines.append(" ".join(["-"*column_index_to_max_width[i] for i, _ in enumerate(header)]))
    # draw each row
    for row_index, row in enumerate(rows):
        # determine colors
        color = [None for _ in range(len(header))]
        if coloring != None:
            def check_color():
                for func in coloring:
                    result = func(row)
                    if result != None:
                        for k, v in result.items():
                            if k != -1:
                                color[k] = v
                            else:
                                for i in range(len(color)): color[i] = v
                            return
            check_color()
        height_of_the_row = row_index_to_max_height[row_index]
        # draw local rows
        local_rows = [[] for i in range(height_of_the_row)]
        for ci, column in enumerate(row):
            xs = column.split("\n")
            for i in range(height_of_the_row):
                if i < len(xs):
                    if is_rightjustify[ci]:
                        v = "%*.*s" % (column_index_to_max_width[ci], column_index_to_max_width[ci], xs[i])
                    else:
                        v = "%-*.*s" % (column_index_to_max_width[ci], column_index_to_max_width[ci], xs[i])
                    local_rows[i].append(v if color[ci] == None else colored(v, color[ci]))
                else:
                    local_rows[i].append(' '*column_index_to_max_width[ci])
        for local_row in local_rows:
            lines.append(" ".join(local_row))
    # finished
    lines.append("") # to add the last new line
    return "\n".join(lines)

def output_table(params, header, data, coloring=None):
    """ output data in a table format.

        The acceptable format (which is given by params.output_format) is one of these:

            csv, tsv, json, plain, simple, simple_with_color, grid, fancy_grid, pipe,
            orgtbl, jira, psql, rst, mediawiki, moinmoin,
            html, latex, latex_booktabs, textile

        header is the list of header columns given by strings.
        data is the list of rows, each of which is the list of columns of type string.
        coloring is None if coloring is not needed.
            Otherwise it is the list of functions. Each function in the list takes
            one row (the list of columns) as an argument and returns either None or
            a dictionary in which column index number maps to the name of the color
            (such as 'red' or 'yellow'). If the return value of a function is None,
            it is ignored and we proceed to the next function in coloring. If the
            column index number is -1, it means the returned color string applies
            to all of the columns. For example, the following coloring means
            "if the 2nd column is even, it makes the 3rd column green, and
             if the 2nd column is 3, it makes all columns red".
            
            def coloring_function(row):
                if row[1] % 2 == 0: # the 2nd column (1st column in 0-origin) is even
                    return {3: 'green'}
                if row[1] == 3:
                    return {-1: 'red'}
                return None
    """
    format = params.output_format
    if format == 'csv' or format == 'tsv':
        import csv
        writer = csv.writer(os.sys.stdout, dialect = 'excel' if format == 'csv' else 'excel-tab')
        if params.output_header: writer.writerow(header)
        writer.writerows(data)
    elif format == 'json':
        for row in data:
            d = {}
            for k, v in zip(header, row): d[k] = v
            print(json.dumps(d))
    else:
        def need_to_use_less(output_text):
            """ returns True if the second line of output_text does not fit to the terminal width """
            lines = output_text.split("\n")
            # See http://stackoverflow.com/questions/566746/how-to-get-console-window-width-in-python
            rowstr, columnstr = os.popen('stty size', 'r').read().split()
            rows, columns = int(rowstr), int(columnstr)
            if is_debugging: print_info("ROW=%d, COL=%d, LINES=%d" % (rows, columns, len(lines)+2))
            if rows < len(lines) + 2: return True
            ansi_escape = re.compile(r'\x1b[^m]*m')
            for rawl in lines:
                l = ansi_escape.sub('', rawl)
                if is_debugging and columns < len(l) + 1: print_info("COL=%d, LINE=%d" % (columns, len(l)))
                if columns < len(l) + 1: return True
            return False

        if format == 'simple_with_color':
            output_string = multicolumn_tabulate(data, header, coloring)
        else:
            output_string = tabulate.tabulate(data, header, format)
        if not params.output_noless and need_to_use_less(output_string):
            less_proc = subprocess.Popen(["less", "-SRc" if format == 'simple_with_color' else "-Sc"], stdin=subprocess.PIPE, universal_newlines=True)
            less_proc.stdin.write(output_string)
            less_proc.stdin.close()
            less_proc.wait()
        else:
            sys.stdout.write(output_string)

def call_function_by_unambiguous_prefix(call_table, prefix_string, subargs):
    """ call a function by a given prefix string.
        call_table is a dictionary that maps a full string to a function.
        subargs is an argument to the callee
    """
    candidates = []
    for k, v in call_table.items():
        if k.startswith(prefix_string):
            candidates.append((k, v))
    if len(candidates) == 0:
        error_exit("No such target '%s'" % prefix_string)
    if 1 < len(candidates):
        error_exit("There are more than one possible candidates:\n  " +
                   " ".join([k for k, v in candidates]))
    (_, func) = candidates[0]
    return func(subargs)

def extract_name_from_tags(cs, default_no_name = "NO NAME"):
    """ extract the host name from tags associated with an instance or vpc or subnet on Amazon EC2 """
    if cs == None: return default_no_name
    for d in cs:
        if 'Key' in d and d['Key'] == 'Name' and 'Value' in d: return d['Value']
    return default_no_name

class NoneInstanceID:
    """ This exception is raised when a given instance ID is None. """

def convert_host_name_to_instance(possible_instance_id, error_on_exit=True):
    """ Convert a given host name into the instance ID.
        If the input host name looks like an existing instance ID, then return the instance immediately.
        If the instance with the given host name exists, then return the instance.
        If there is no such instance, it prints an error and exits.
    """
    if possible_instance_id == None: raise NoneInstanceID()
    ec2 = get_ec2_connection()
    if re.match(r'^i-[0-9a-f]+$', possible_instance_id):
        instances = list(ec2.instances.filter(Filters=[{'Name': 'instance-id', 'Values': [possible_instance_id]}]))
        if len(instances) <= 0:
            if error_on_exit: error_exit("Cannot find a instance ID '%s'" % possible_instance_id)
            return None
        return instances[0]
    instances = list(ec2.instances.filter(Filters=[{'Name':'tag:Name', 'Values': [possible_instance_id]}]))
    if len(instances) <= 0:
        if error_on_exit: error_exit("Cannot find a host '%s'" % possible_instance_id)
        return None
    instance_ids = [i.instance_id for i in instances]
    if 1 < len(instance_ids):
        if error_on_exit: error_exit("There are multiple instances with name='%s'.\nCandidates are:\n\t%s" % (possible_instance_id, "\n\t".join(instance_ids)))
        return None
    return instances[0]

class NoneVPCID:
    """ This exception is raised when a given VPC is None. """

def convert_vpc_name_to_vpc(possible_vpc_id, error_on_exit=True):
    """ Convert a given VPC name into the VPC
        If the input VPC name looks like an existing VPC ID, then return the VPC immediately.
        If the VPC with the given VPC name exists, then return the VPC.
        If there is no such VPC, it prints an error and exits.
    """
    if possible_vpc_id == None: raise NoneVPCID()
    ec2 = get_ec2_connection()
    if re.match(r'^vpc-[0-9a-f]+$', possible_vpc_id):
        vpcs = list(ec2.vpcs.filter(Filters=[{'Name': 'vpc-id', 'Values': [possible_vpc_id]}]))
        if len(vpcs) <= 0:
            if error_on_exit: error_exit("Cannot find a VPC ID name '%s'" % possible_vpc_id)
            return None
        return vpcs[0]
    vpcs = list(ec2.vpcs.filter(Filters=[{'Name': 'tag:Name', 'Values': [possible_vpc_id]}]))
    if len(vpcs) <= 0:
        if error_on_exit: error_exit("Cannot find a VPC '%s'" % possible_vpc_id)
        return None
    vpc_ids = [i.id for i in vpcs]
    if 1 < len(vpc_ids):
        if error_on_exit: error_exit("There are multiple VPCs with name='%s'.\nCandidates are:\n\t%s" % (possible_vpc_id, "\n\t".join(vpc_ids)))
        return None
    return vpcs[0]

class NoneSubnetID:
    """ This exception is raised when a given subnet is None. """

def convert_subnet_name_to_subnet(possible_subnet_id, error_on_exit=True):
    """ Convert a given subnet name into the subnet
        If the input subnet name looks like an existing subnet ID, then return the subnet immediately.
        If the subnet with the given subnet name exists, then return the subnet.
        If there is not such subnet, it prints an error and exits.
    """
    if possible_subnet_id == None: raise NoneSubnetID()
    ec2 = get_ec2_connection()
    if re.match(r'^subnet-[0-9a-f]+$', possible_subnet_id):
        subnets = list(ec2.subnets.filter(Filters=[{'Name': 'subnet-id', 'Values': [possible_subnet_id]}]))
        if len(subnets) <= 0:
            if error_on_exit: error_exit("Cannot find a subnet with subnet ID '%s'" % possible_subnet_id)
            return None
        return subnets[0]
    subnets = list(ec2.subnets.filter(Filters=[{'Name': 'tag:Name', 'Values': [possible_subnet_id]}]))
    if len(subnets) <= 0:
        if error_on_exit: error_exit("Cannot find a subnet '%s'" % possible_subnet_id)
        return None
    subnet_ids = [i.id for i in subnets]
    if 1 < len(subnet_ids):
        if error_on_exit: error_exit("There are multiple subnets with name='%s'.\nCandidates are:\n\t%s" % (possible_subnet_id, "\n\t".join(subnet_ids)))
        return None
    return subnets[0]

class NoneSecurityGroupID:
    """ This exception is raised when a given security group is None. """

def convert_sg_name_to_sg(possible_sg_id, error_on_exit=True):
    """ Convert a given security group name into the security group.
        If the input security group name look like an existing security group ID, then return the security group immediately.
        If the security group with the given security group name exists, then return the security group.
        If there is no such security group, it prints an error and exits.
    """
    if possible_sg_id == None: raise NoneSecurityGroupID()
    ec2 = get_ec2_connection()
    if re.match(r'sg-[0-9a-f]+$', possible_sg_id):
        sgs = list(ec2.security_groups.filter(Filters=[{'Name': 'group-id', 'Values': [possible_sg_id]}]))
        if len(sgs) <= 0:
            if error_on_exit: error_exit("Cannot find a security group ID '%s'" % possible_sg_id)
            return None
        return sgs[0]
    sgs = list(ec2.security_groups.filter(Filters=[{'Name': 'group-name', 'Values': [possible_sg_id]}]))
    if len(sgs) <= 0:
        if error_on_exit: error_exit("Cannot find a security group '%s'" % possible_sg_id)
        return None
    sg_ids = [i.id for i in sgs]
    if 1 < len(sg_ids):
        if error_on_exit: error_exit("There are multiple security groups with name='%s'.\nCandidates are:\n\t%s" % (possible_sg_id, "\n\t".join(sg_ids)))
        return None
    return sgs[0]

def get_root_like_user_from_instance(instance):
    """ get a root-like user (eg, ec2-user) from an instance """
    for t in instance.tags:
        if t['Key'] == 'root':
            return t['Value']
    print_info("'root' tag does not exist for this instance.\nThe user name is 'ec2-user' unless you specify it by option")
    return 'ec2-user' # default

def ssh_like_call(params, command_name, hostname_or_instance_id, command_args):
    """ call an SSH-like command to login into a specified host with specified arguments
        params is a parameter object of click,
        command_name is a string such as 'ssh' or 'mosh',
        hostname_or_instance_id is a hostname (Name tag) or an instance ID,
        command_args is a list of arguments passed to command_name.
    """
    instance = convert_host_name_to_instance(hostname_or_instance_id)
    if instance.public_ip_address == None:
        error_exit("The instance has no public IP address")
    # root user
    root_user = get_root_like_user_from_instance(instance)
    args = ['ssh', '-l', root_user]
    key_file_path = os.path.join(os.path.expanduser("~/.ssh"), instance.key_name + ".pem")
    if os.path.exists(key_file_path):
        args += ['-i', key_file_path]
    else:
        print_info("Key file '%s' does not exist.\nThe default keys might be used" % key_file_path)
    args += [instance.public_ip_address]
    args += list(command_args)
    if params.aws_dryrun:
        print(" ".join(args))
        return
    try:
        subprocess.check_call(args)
    except:
        pass

def convert_zone_name_to_zone_id(zone_name, error_on_exit=True):
    """ convert an Route53 zone name to the corresponding zone ID """
    if zone_name != None and not zone_name.endswith('.'): zone_name += '.'
    r53 = get_r53_connection()
    possible_zone_ids = [i['Id'] for i in r53.list_hosted_zones()['HostedZones'] if i['Name'] == zone_name]
    if 0 >= len(possible_zone_ids):
        if error_on_exit: error_exit("No such zone '%s'" % zone_name)
        return None
    return possible_zone_ids[0]

def decompose_rpath(rpath):
    """ decompose an SCP-style path into components.
        eg) decompose_rpath("user@host.example.com:/path/foo") -> ('user', 'host.example.com', '/path/foo')
            decompose_rpath("/abc/def") -> (None, None, '/abc/def')
        Note that the first and the second return values might be None
        but the the third argument will never be None (could be '', though).
    """
    r = re.match(r'^(((.*?)@)?(.*?):)?(.*)$', rpath)
    return (r.group(3), r.group(4), r.group(5))

def parse_port_string(port_str):
    if port_str == 'any' or port_str == 'all': return -1, -1
    sarr = port_str.split("-")
    if len(sarr) <= 0: return None
    if len(sarr) <= 1:
        try:
            v = int(sarr[0])
        except:
            error_exit("'%s' is not an integer" % sarr[0])
        return v, v
    try:
        v1 = int(sarr[0])
        v2 = int(sarr[1])
    except:
        error_exit("'%s' or '%s' is not an integer" % (sarr[0], sarr[1]))
    return v1, v2

def parse_protocol_port_string(prot_port_str):
    port_arr = prot_port_str.split("/")
    if len(port_arr) <= 0: error_exit("protocol must be one of 'icmp', 'tcp/<port nums>', 'udp/<port nums>', where <port nums> is a number or a range (eg. 100-120)")
    if port_arr[0] == 'icmp':
        protocol = 'icmp'
        target_port_low, target_port_high = -1, -1
    elif port_arr[0] == 'tcp':
        protocol = 'tcp'
        if len(port_arr) < 2: error_exit("specify port range (e.g., tcp/all, tcp/22, tcp/10000-20000)")
        target_port_low, target_port_high = parse_port_string(port_arr[1])
    elif port_arr[0] == 'udp':
        protocol = 'udp'
        if len(port_arr) < 2: error_exit("specify port range (e.g., udp/all, udp/22, udp/10000-20000)")
        target_port_low, target_port_high = parse_port_string(port_arr[1])
    elif port_arr[0] == 'any':
        protocol = '-1'
        target_port_low, target_port_high = -1, -1
    else:
        error_exit("unknown protocol '%s'" % port_arr[0])
    return protocol, target_port_low, target_port_high

def expand_cidr_string(unexpanded_cidr_string):
    """ expand a given CIDR string.
        1) Normal CIDR strings are returned as is.
           '123.45.67.89/24' => '123.45.67.89/24'
        2) 'any'/'all' is expanded.
           'any' => '0.0.0.0/0'
        3) 'self' is expanded to my IP. This requires pystun library (that works only on Python 2.x for now)
           'self' => '123.45.67.89/32'
    """
    if unexpanded_cidr_string == 'any' or unexpanded_cidr_string == 'all': return '0.0.0.0/0'
    if unexpanded_cidr_string == 'self':
        if sys.version_info < (3, 0):
            # NOTE: not tested
            import pystun
            nat_type, external_ip, external_port = stun.get_ip_info()
            if nat_type == pystun.Blocked:
                error_exit("Cannot reach to a STUN server so cannot find my external IP")
            return external_ip
        else:
            error_exit("'self' can be used only with Python 2.x because a dependent library is not compatible with Python 3.x")
    return unexpanded_cidr_string

def is_private_cidr(cidr_str):
    """ return a pentuple (eg. (1, 2, 3, 4, 5) for '1.2.3.4/5') if a given string is a private CIDR (eg. 192.168.1.0/24).
        returns None if the input is invalid.
        returns False if it is not a private CIDR
    """
    arr = cidr_str.split("/")
    if len(arr) != 2: return None
    try:
        mask_bits = int(arr[1])
    except:
        return None
    if not (0 <= mask_bits <= 32): return None
    addr = is_private_ip(arr[0])
    if addr == None or addr == False: return None
    b1, b2, b3, b4 = addr
    if b1 == 10 and 8 <= mask_bits: return (b1, b2, b3, b4, mask_bits)
    if b1 == 172 and 16 <= b2 <= 31 and 11 <= mask_bits: return (b1, b2, b3, b4, mask_bits)
    if b1 == 192 and b2 == 168 and 16 <= mask_bits: return (b1, b2, b3, b4, mask_bits)
    return False

def is_private_ip(ip_str):
    """ return a quadruple if a given string is a private IP.
        returns None if the input is invalid.
        returns False if it is not private.
    """
    arr = ip_str.split(".")
    if len(arr) != 4: return None
    try:
        b1, b2, b3, b4 = int(arr[0]), int(arr[1]), int(arr[2]), int(arr[3])
    except:
        return None
    if not (0 <= b1 <= 255): return False
    if not (0 <= b2 <= 255): return False
    if not (0 <= b3 <= 255): return False
    if not (0 <= b4 <= 255): return False
    if b1 == 10: return (b1, b2, b3, b4)
    if b1 == 172 and 16 <= b2 <= 31: return (b1, b2, b3, b4)
    if b1 == 192 and b2 == 168: return (b1, b2, b3, b4)
    return False

def get_AMI_DB_file_path():
    return os.path.join(os.path.expanduser("~/.aws"), "ami_db.sqlite3")

def ensure_AMI_DB_exist():
    """ ensure that the AMI database exists.
        If there is not an existing one, create a new one
    """
    db_path = get_AMI_DB_file_path()
    if os.path.exists(db_path): return
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE ami_ids (name text primary key, id text, cost text);")
    conn.commit()
    conn.close()

def register_AMI_ID_to_local_database(do_not_open_browser):
    """ Register AMIs to the AMI database that is located on local disk """
    ensure_AMI_DB_exist()
    if not do_not_open_browser:
        basic_url =('https://aws.amazon.com/marketplace/search/results?page=1&' +
                    'filters=operating_system%2Cfulfillment_options%2Carchitectures%2Cregions&' +
                    'operating_system=AMAZONLINUX%2CDEBIAN%2CCENTOS%2CRHEL%2CUBUNTU&' +
                    'fulfillment_options=AMI&architectures=64-bit&' +
                    'regions=' + param_region)
        print_info("Launching a web browser.\nPlease select one and click on 'Continue',\nand then select 'Manual Launch' tab.\n" +
                   "You need to agree with Terms and Conditions,\nafter which you expand a 'launch'.\n" +
                   "You see a bunch of AMI IDs there.\n" +
                   "Then you copy everything (press CMD+A, CMD+C for macOS, CTRL+A, CTRL+C for Windows) to the clipboard\n" +
                   "We analyze the copied text and bring you to the next step.")
        click.launch(basic_url)
    while True:
        txt = wait_for_clipboard_to_update(512)
        print_info("Detected an update in the clipboard.")
        lines = txt.split("\n")
        image_name = None
        ami_ids = []
        cost_table = []
        line_index = 0
        while line_index < len(lines):
            l = lines[line_index]
            if re.match('Launch on EC2:', l, re.I):
                image_name = lines[line_index + 1]; line_index += 1
            elif re.match(r'Region\s+ID', l, re.I):
                line_index += 1
                while line_index < len(lines):
                    m = lines[line_index]
                    if re.match('Security Group', m, re.I): break
                    res = re.match(r'(.*?)\s+(ami-[0-9a-f]+)\s+Launch', m, re.I)
                    if res:
                        region_nickname = res.group(1)
                        ami_id = res.group(2)
                        region_id = None
                        for k, v in region_name_to_region_nickname.items():
                            if re.search(v, region_nickname, re.I):
                                region_id = k
                                break
                        if region_id == None: region_id = region_nickname
                        ami_ids.append({'Region': region_id, 'AMI': ami_id})
                    line_index += 1
            elif re.match('EC2 Instance Type', l, re.I):
                line_index += 1
                while line_index < len(lines):
                    m = lines[line_index]
                    if re.match('EBS Magnetic volumes', m, re.I): break
                    res = re.match(r'(.*?)\s+\$(\d+\.\d+)/hr\s+\$(\d+\.\d+)/hr\s+\$(\d+\.\d+)/hr', m, re.I)
                    if res:
                        cost_table.append({'InstanceType': res.group(1), 'CostForLicense': res.group(2), 'CostForInstance': res.group(3), 'CostTotal': res.group(4)})
                    res = re.match(r'(.*?)\s+\$(\d+\.\d+)/hr', m, re.I)
                    if res:
                        cost_table.append({'InstanceType': res.group(1), 'CostTotal': res.group(2)})
                    line_index += 1
            line_index += 1
        if is_debugging:
            print("Image name:")
            print("\t" + image_name)
            print(type(image_name))
        if image_name == None or image_name == '':
            print_warning("Image name is missing. Retry.")
            continue
        if is_debugging: print("AMI IDs:", ami_ids)
        if len(ami_ids) <= 0:
            print_warning("AMI IDs are not detected. Retry.")
            continue
        if is_debugging: print("Cost table:", cost_table)
        if len(cost_table) <= 0:
            print_warning("Cost table is not detected. Retry.")
            continue
        break
    region_name_to_ami_id = {}
    for d in ami_ids: region_name_to_ami_id[d['Region']] = d['AMI']
    instance_type_to_cost = {}
    for d in cost_table: instance_type_to_cost[d['InstanceType']] = d

    db_path = get_AMI_DB_file_path()
    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM ami_ids WHERE name = ?", (image_name,) )
    conn.execute("INSERT INTO ami_ids VALUES(?, ?, ?)", (image_name,
            pickle.dumps(region_name_to_ami_id), pickle.dumps(instance_type_to_cost)))
    conn.commit()
    conn.close()
    print_info("Successfully registered the AMI info for '%s'" % image_name)
    if not do_not_open_browser:
        print_info("If you wish to continue registering more AMI, please execute the same command with '-n' option")

def wait_for_clipboard_to_update(minimum_size = 0):
    """ Wait for something of more than or equal to minimum_size bytes to be copied to the clipboard.
        The return value is the content of the clipboard (in plain text).
    """
    if minimum_size == 0 or minimum_size <= len(pyperclip.paste()):
        pyperclip.copy('') # clear the clipboard
    while True:
        t = pyperclip.paste()
        if t != None and t != '' and minimum_size <= len(t):
            return t
        time.sleep(1)

def update_recommended_image_cache():
    """ Update the file that contains recommended AWS EC2 images (eg., RetHat Enterprise Linux, Amazon Linux, Cent OS, Ubuntu, etc.) """
    # NOTE: this is not (yet?) implemented.
    ec2 = get_ec2_connection()
    images = ec2.images.filter(Owners=['self'])

class PrefixCompleter:
    not_yet_initialized = True
    def __init__(self, candidate_strings):
        self.candidate_strings = sorted(candidate_strings)
        if PrefixCompleter.not_yet_initialized:
            readline.parse_and_bind("tab: complete")
            readline.set_completer_delims('')
            PrefixCompleter.not_yet_initialized = False

    def completer(self, text, index):
        fl = [i for i in self.candidate_strings if i.startswith(text)]
        if index < len(fl): return fl[index]
        return None

def get_default_content_type(file_name):
    """ get the default content type from a given file name """
    mime_type, compress_type = mimetypes.guess_type(file_name)
    if mime_type != None: return mime_type
    return "application/octet-stream"
