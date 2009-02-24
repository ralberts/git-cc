"""Copy files from Clearcase to Git manually"""

from common import *
import os, shutil, stat
from os.path import join, abspath
from fnmatch import fnmatch


def main(glob):
    base = abspath(CC_DIR)
    for i in cfg.getList('include', '.'):
        for (dirpath, dirnames, filenames) in os.walk(buildPath([CC_DIR, i])):
            reldir = dirpath[len(base):]
            for file in filenames:
                if fnmatch(file, glob):
                    newFile = buildPath([GIT_DIR, reldir, file])
                    fromFile = buildPath([dirpath,file])
                    print('Copying',fromFile,"to",newFile)
                    mkdirs(newFile)
                    shutil.copy(fromFile, newFile)
                    os.chmod(newFile, stat.S_IWRITE)
