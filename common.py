import smtplib
from datetime import datetime, timedelta
from distutils import __version__
v30 = __version__.find("3.") == 0

from subprocess import Popen, PIPE
import os, sys
from os.path import join, exists, abspath, dirname
if v30:
    from configparser import SafeConfigParser
else:
    from ConfigParser import SafeConfigParser

CC_TAG = 'clearcase'
CI_TAG = 'clearcase_ci'
CFG_CC = 'clearcase'
CC_DIR = None
ENCODING = sys.stdin.encoding

def fail(string):
    print(string)
    sys.exit(2)

def debug(string):
    if DEBUG:
        print(string)

def git_exec(cmd, **args):
    return popen('git', cmd, GIT_DIR, **args)

def cc_exec(cmd):
    return popen('cleartool', cmd, CC_DIR)

def popen(exe, cmd, cwd, env=None, decode=True):
    cmd.insert(0, exe)
    if DEBUG:
        debug('> ' + ' '.join(cmd))
    input = Popen(cmd, cwd=cwd, stdout=PIPE, env=env).stdout.read()
    return input if not decode else input.decode(ENCODING)

def tag(tag, id="HEAD"):
    git_exec(['tag', '-f', tag, id])

def reset(tag=CC_TAG):
    git_exec(['reset', '--hard', tag])

def getBlob(sha, file):
    return git_exec(['ls-tree', '-z', sha, file]).split(' ')[2].split('\t')[0]

def gitDir():
    def findGitDir(dir):
        if exists(join(dir, '.git')):
            return dir
        if not exists(dir) or dirname(dir) == dir:
            return '.'
        return findGitDir(dirname(dir))
    return findGitDir(abspath('.'))

class GitConfigParser():
    section = 'gitcc'
    def __init__(self):
        self.file = join(GIT_DIR, '.git', 'gitcc')
        self.parser = SafeConfigParser();
        self.parser.add_section(self.section)
    def set(self, name, value):
        self.parser.set(self.section, name, value)
    def read(self):
        self.parser.read(self.file)
    def write(self):
        self.parser.write(open(self.file, 'w'))
    def get(self, name, default=None):
        if not self.parser.has_option(self.section, name):
            return default
        return self.parser.get(self.section, name)
    def getList(self, name, default=None):
        return self.get(name, default).split('|')



def write(file, blob):
    _write(file, blob)

def _write(file, blob):
    f = open(file, 'wb')
    f.write(blob)
    f.close()

def mkdirs(file):
    dir = dirname(file)
    if not exists(dir):
        os.makedirs(dir)

def removeFile(file):
    if exists(file):
        os.remove(file)

def buildPath(seq):
     # If running in a unix-like environment (including cygwin) use '/' as a path separator, otherwise use '\'
     if "TERM" in os.environ.keys():
        return '/'.join(seq).replace("\\","/")
     else:
        return '\\'.join(seq).replace("/","\\")

def getClearcaseDatetime(timestamp):
    # Strip off UTC, as this is not handled well by pythong.
    if len(timestamp) > 22: # UTC offset is -HH:MM (happens on windows 2003 server) 
        time = timestamp[:-6]
    else: # UTC offset is -HH
        time = timestamp[:-3]
    return datetime.strptime(time, '%Y-%m-%dT%H:%M:%S')        


    
GIT_DIR = gitDir()
cfg = GitConfigParser()
if exists(join(GIT_DIR, '.git')):
    cfg.read()
    CC_DIR = cfg.get(CFG_CC)
DEBUG = cfg.get('debug', True)
