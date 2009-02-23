"""Copy files from Clearcase to Git manually"""

from common import *
import os, shutil, stat
from os.path import join, abspath
from fnmatch import fnmatch

def main(glob):
    base = abspath(CC_DIR)
    for i in cfg.getList('include', '.'):
        for (dirpath, dirnames, filenames) in os.walk(join(CC_DIR, i)):
            reldir = dirpath[len(base):]
            for file in filenames:
                if fnmatch(file, glob):
                    newFile = join(GIT_DIR, reldir, file)
                    debug('Copying %s' % newFile)
                    mkdirs(newFile)
                    shutil.copy(join(dirpath, file), newFile)
                    os.chmod(newFile, stat.S_IWRITE)
