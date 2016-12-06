#!/usr/bin/env python3

from __future__ import print_function
from __future__ import absolute_import
import os, sys, click
import fnmatch, re, glob
from taw.util import *
from taw.taw import * # This must be the end of imports

# ================
#  BUCKET COMMAND
# ================
@taw.group("bucket")
@pass_global_parameters
def bucket_group(params):
    """ manage S3 buckets """

@bucket_group.command("rm")
@click.argument('files', nargs=-1)
@click.option('--force', is_flag=True)
@pass_global_parameters
def rm_bucketcmd(params, files, force):
    """ remove files in a specified bucket """
    num_affected_files = 0
    num_affected_bytes = 0
    for fn in files:
        _, dest_bucket, dest_path = decompose_rpath(fn)
        s3 = get_s3_connection()
        if dest_bucket == None: error_exit("file names must be in the form of 'bucket_name:key_name'")
        bucket = s3.Bucket(dest_bucket)
        for obj in bucket.objects.all():
            if dest_path != '' and not fnmatch.fnmatch(obj.key, dest_path): continue
            if force:
                obj.delete()
            else:
                print("'%s' (size=%d)" % (obj.key, obj.size))
                num_affected_files += 1
                num_affected_bytes += obj.size
    if not force:
        print("Please add --force to actually remove those %d files (%d bytes in total)" % (num_affected_files, num_affected_bytes))

@bucket_group.command("chmod")
@click.argument('mode', nargs=1)
@click.argument('files', nargs=-1)
@click.option('--force', is_flag=True)
@pass_global_parameters
def chmod_bucketcmd(params, mode, files, force):
    """ change the permission of a given bucket or given files.
        eg1) Make a bucket private.
             taw bucket chmod private bucket-name
        eg2) Make a key (file) public (still you need to make the belonging bucket public to actually allow public to read it)
             taw bucket chmod public-read bucket-name:key-name """
    allowed_perms = [
            'private',
            'public-read',
            'public-read-write',
            'aws-exec-read',
            'authenticated-read',
            'bucket-owner-read',
            'bucket-owner-full-control',
            'log-delivery-write',
        ]
    if not mode in allowed_perms:
        error_exit("Mode must be one of the followings:\n\t" + "\n\t".join(allowed_perms) + "\n\nSee http://docs.aws.amazon.com/AmazonS3/latest/dev/acl-overview.html#canned-acl for details\n")
    if mode == 'public-read-write' and not force:
        error_exit("Setting 'public-read-write' to a bucket or files might make you bankrupt.\nIf you are sure you understand what you do, add --force.")
    s3 = get_s3_connection()
    for full_path in files:
        _, bucket, path = decompose_rpath(full_path)
        if bucket == None:
            error_exit("Use bucket-name: for specifying a bucket\nUse bucket-name:key-name for specifying files")
        if path == '': # for bucket
            s3.Bucket(bucket).Acl().put(ACL=mode)
        else: # for file
            if path.find("*") != -1 or path.find("?") != -1:
                if is_debugging: print("Glob expression '%s'" % path)
                for obj in s3.Bucket(bucket).objects.all():
                    if not fnmatch.fnmatch(obj.key, path):
                        if is_debugging: print("skipped %s:%s" % (bucket, obj.key))
                        continue
                    if is_debugging: print("chmod %s %s:%s" % (mode, bucket, obj.key))
                    obj.Acl().put(ACL=mode)
            else:
                s3.Bucket(bucket).Object(path).Acl().put(ACL=mode)

@bucket_group.command("cp")
@click.argument('src', nargs=-1)
@click.argument('dst', nargs=1)
@pass_global_parameters
def cp_bucketcmd(params, src, dst):
    """ copy to/from a specified bucket """
    for src_file in src:
        _, src_bucket , src_path  = decompose_rpath(src_file)
        _, dest_bucket, dest_path = decompose_rpath(dst)
        if src_bucket == None and dest_bucket == None: error_exit("We do not support local-to-local copy")
        if src_bucket != None and dest_bucket != None: error_exit("We do not support remote-to-remote copy")
        s3 = get_s3_connection()
        any_file_is_copied = False
        if src_bucket == None:
            # Local to remote
            bucket = s3.Bucket(dest_bucket)
            for fn in glob.glob(os.path.expanduser(src_path)):
                # TODO: we need to use multipart upload if the size of file fn is large.
                if dest_path.endswith('/'):
                    dest_key_name = dest_path + os.path.basename(fn)
                else:
                    if dest_path == '':
                        dest_key_name = os.path.basename(fn)
                    else:
                        dest_key_name = dest_path
                any_file_is_copied = True
                if is_debugging: print("%s to [%s]:%s" % (fn, dest_bucket, dest_key_name), file=sys.stderr)
                bucket.Object(dest_key_name).put(Body=open(fn, 'rb').read())
        else:
            # Remote to local
            bucket = s3.Bucket(src_bucket)
            is_local_path_directory = os.path.isdir(dest_path)
            for obj in bucket.objects.all():
                if src_path != '' and not fnmatch.fnmatch(obj.key, src_path): continue
                any_file_is_copied = True
                # TODO: we need to download partially for large files
                if is_local_path_directory:
                    if is_debugging: print("LOCAL FILE=%s" % os.path.basename(obj.key), file=sys.stderr)
                    with open(os.path.basename(obj.key), "wb") as f:
                        f.write(obj.get()['Body'].read())
                else:
                    if is_debugging: print("LOCAL FILE=%s" % dest_path, file=sys.stderr)
                    with open(dest_path, "wb") as f:
                        f.write(obj.get()['Body'].read())
        if not any_file_is_copied:
            error_exit("No file matched")

@bucket_group.command("list", add_help_option=False, context_settings=dict(ignore_unknown_options=True))
@click.argument('args', nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def list_bucketcmd(ctx, args):
    """ list buckets """
    with taw.make_context('taw', ctx.obj.global_opt_str + ['list', 'bucket'] + list(args)) as ncon: _ = taw.invoke(ncon)

@bucket_group.command("ls", add_help_option=False, context_settings=dict(ignore_unknown_options=True))
@click.argument('args', nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def ls_bucketcmd(ctx, args):
    """ list buckets (same as 'taw bucket list') """
    with taw.make_context('taw', ctx.obj.global_opt_str + ['list', 'bucket'] + list(args)) as ncon: _ = taw.invoke(ncon)

