#!/usr/bin/env python
from setuptools import setup, find_packages

import sys

depending_libraries = \
    [
        'click>=6.6',
        'boto3>=1.7.7',
        'tabulate>=0.7.7',
        'colorama==0.2.5',
        'termcolor',
        'future',
        'six',
        'pyperclip',
        'awscli>=1.11.35',
        'dnspython',
    ]
if sys.version_info < (3, 0):
    depending_libraries.append('pysqlite')  # this is only needed by Python 2.x
else:
    pass

setup(
        name='tiny-amazon-wrapper',
        version='0.1.1',
        packages=find_packages(),
        include_package_data=True,
        install_requires=depending_libraries,
        entry_points={
            'console_scripts':
                [
                    'taw=taw.main:main'
                ]
        },
     )
