"""Copy files from Clearcase to Git manually"""

from common import *
import os, shutil, stat
from os.path import join, abspath
from fnmatch import fnmatch

ARGS= {
       'ignore_whitespace' : 'Ignore whitespace and line feeds when choosing files to sync'
}

def main(glob,ignore_whitespace=False):
    quest = "This will copy all files matching " + glob + " in the clearcase view to the git repository.\n"
    quest += "Are you sure you want to do this?"

    if ask(quest,["Yes","No"]) == 'y':
        base = abspath(CC_DIR)
        for i in cfg.getList('include', '.'):
            for (dirpath, dirnames, filenames) in os.walk(buildPath([CC_DIR, i])):
                reldir = dirpath[len(base):]
                for file in filenames:
                    if fnmatch(file, glob):
                        newFile = buildPath([GIT_DIR, reldir, file])
                        fromFile = buildPath([dirpath,file])
                        if (not ignore_whitespace) or doDiff(newFile,fromFile):
                            if DEBUG: 
                                print('Copying',fromFile,"to",newFile)
                            mkdirs(newFile)
                            shutil.copy(fromFile, newFile)
                            os.chmod(newFile, stat.S_IWRITE)

def doDiff(file1,file2):
    cmd = ['--ignore-all-space', file1, file2]
    output = popen('diff', cmd, cwd=os.getcwd())
    debug("Output from diff is: " + output)
    if output:
        return True
    return False
    