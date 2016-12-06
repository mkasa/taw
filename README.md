# taw
taw is a command line interface for Amazon EC2.
taw stands for Tiny Amazon ec2 Wrapper.
taw is designed to provide a limited number of operations
so that new users can easily understand what they can do with Amazon
EC2, S3, and Route 53.

taw is designed for researchers who try to use the computing resources of
Amazon EC2 but are not familier with cloud computing environments such
as Amazon EC2, Microsoft Azure, or Google Compute Platform,
but maybe it is also useful for other people.

Amazon EC2 is a great cloud environment that provides us with easy-to-use
on-demand computing resources. The web interface of Amazon EC2 is
sophisticated so that new users can easily use cloud resources.
However, the command line interface for Amazon EC2 (CLI, hereafter) is too complex and
hard to understand. This design was chosen presumably because the users of
the command line interface are professional and more familier with
the system of Amazon EC2. First, CLI provides only a low-level interface
although the web interface provides higher-level operations for common
operations. Second, CLI exposes all APIs with all parameters equally.
In other words, new users have no way to guess which API is more common
than others. Deprecated parameters for compatibility are hidden as
optional parameters with a reasonable default value in the web
interface but the document for CLI does not explain it at all.

In academia, a small group of researchers such as a lab in a university
is the one who greatly benefits from cloud computing environments
because they unload the burden of maintaining computing resources internally.
The pay-as-you-go nature of cloud computing allows us to same a
significant amount of money because the small lab usually needs
a huge computing resource only occasionally, and for the rest of
the time computers would be almost all idle, which is wasteful.
However, unlike other core computing facilities where computer geeks
are familier with the local computing facility and ready to ask anything,
a small lab usually does not afford to hire a person who dedicates to
maintain the lab computing infrastructure.

taw is designed specifically for such use cases where no one is
familiar with cloud computing nor interested in system maintanace
matters. taw is also designed for a small use of cloud computing.
If you are going to use thousands of CPU cores on Amazon EC2 or
use hundreads of terabytes of storage in Amazon S3,
I recommend you to learn how Amazon EC2 works; you would be
able to use the Amazon Command Line interface and maybe
you would not need taw.

The design goal of taw is to make a small group of people who
use only a handful of resources (up to 100 instances, up to thousands
objects in a S3 bucket, a few zones, etc.) feel more comfortable
with the command line interface.

# Quick Start
Set up your AWS credential.
```bash
$ aws configure
```

List instances.

```bash
$ taw list                       # this is a shorthand for 'taw instance list'
$ taw instance list
```

List all instances in all regions.
```bash
$ taw instance list --allregions
```

Start an instance with `NAME` tag with a value `webserver01`.

```bash
$ taw instance start webserver01
```

Stop an instance with `NAME` tag with a value `webserver01`.

```bash
$ taw instance stop webserver01
```

Terminate an instance with `NAME` tag with a valie `webserver01`.

```bash
$ taw instance terminate webserver01
```

# Installation
`python setup.py install` will install `taw` command.
It is not (yet) available in PyPI, but it will appear soon.

First you need to setup your credential (ID/password).
You can set it up in [the same way as AWS Command Line
Interface](http://docs.aws.amazon.com/cli/latest/userguide/cli-chap-getting-started.html).
Briefly, you need to execute `aws configure` and answer the questions
(the example below is taken from the mentioned web page).

```bash
$ aws configure
AWS Access Key ID [None]: AKIAIOSFODNN7EXAMPLE
AWS Secret Access Key [None]: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
Default region name [None]: us-west-2
Default output format [None]: ENTER
```

Those configs are written in plain text files, `~/.aws/credentials` and
`~/.aws/config` so you can edit them if needed.

If you have multiple AWS accounts and wish to switch over them, you can
specify `--profile` option to save another credential (again, the
example is taken from the official document).

```bash
$ aws configure --profile user2
AWS Access Key ID [None]: AKIAI44QH8DHBEXAMPLE
AWS Secret Access Key [None]: je7MtGbClwBF/2Zp9Utk/h3yCo8nvbEXAMPLEKEY
Default region name [None]: us-east-1
Default output format [None]: text
```

You can give `--profile=user2` to taw when you use profile `user2`.
Setting an environment variable `AWS_DEFAULT_PROFILE` changes the
default profile used.

# Subcommands
taw has subcommands like git has subcommands.
Each subcommand has a document in `doc/` directory.

# License
MIT

# Author
Masahiro Kasahara
