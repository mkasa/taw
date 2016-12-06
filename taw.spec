# -*- mode: python -*-
# vim: set ft=python :

from __future__ import print_function

import sys, os
import pkg_resources

WORKPATH='./taw'
block_cipher = None

# See the site below for details
# https://github.com/pyinstaller/pyinstaller/wiki/Recipe-Setuptools-Entry-Point
def Entrypoint(dist, group, name,
               scripts=None, pathex=None, hiddenimports=None, fakeimports=None,
               hookspath=None, excludes=None, runtime_hooks=None):
    import pkg_resources

    # get toplevel packages of distribution from metadata
    def get_toplevel(dist):
        distribution = pkg_resources.get_distribution(dist)
        if distribution.has_metadata('top_level.txt'):
            return list(distribution.get_metadata('top_level.txt').split())
        else:
            return []

    packages = hiddenimports or []
    for distribution in hiddenimports:
        packages += get_toplevel(distribution)

    scripts = scripts or []
    pathex = pathex or []
    fakeimports = fakeimports or []
    # get the entry point
    ep = pkg_resources.get_entry_info(dist, group, name)
    print(ep)
    print("dist location:", ep.dist.location)
    # insert path of the egg at the verify front of the search path
    pathex = [ep.dist.location] + pathex
    # script name must not be a valid module name to avoid name clashes on import
    script_path = os.path.join(WORKPATH, name + '-script.py')
    print("creating script for entry point", dist, group, name)
    with open(script_path, 'w') as fh:
        fh.write("import {0}\n".format(ep.module_name))
        fh.write("{0}.{1}()\n".format(ep.module_name, '.'.join(ep.attrs)))
        for package in packages:
            fh.write("import {0}\n".format(package))
        for package in fakeimports:
            fh.write("import {0}\n".format(package))

    print("Script path:", script_path)
    print("pathex:", pathex)
    print("hiddenimports:", hiddenimports)
    print("hookspath:", hookspath)
    print("excludes:", excludes)
    print("runtime_hooks:", runtime_hooks)
    return Analysis([script_path] + scripts, pathex, hiddenimports, hookspath, excludes, runtime_hooks)

fake_import_modules = []
if sys.version_info < (3, 0):
    fake_import_modules.append('HTMLParser')
else:
    fake_import_modules.append('html.parser')

a = Entrypoint('tiny-amazon-wrapper', 'console_scripts', 'taw',
             pathex=[],
             hiddenimports=[],
             fakeimports=fake_import_modules,
             hookspath=[],
             runtime_hooks=[],
             excludes=[])
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='taw',
          debug=False,
          strip=False,
          upx=True,
          console=True )
