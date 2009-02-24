"""Initialise gitcc with a clearcase directory"""

from common import *
from git import *
from os import open
from os.path import join, exists

def main(ccdir):
    if not exists(join(GIT_DIR, '.git')):
        git_exec(['init'])
        git_exec(['config', 'core.autocrlf', 'false'])
        excludes = """*.class
*.jar
"""
        write(join(GIT_DIR, '.git', 'info', 'exclude'), excludes.encode())
    cfg.set(CFG_CC, ccdir)
    cfg.write()
    
    # Create clearcase branch
    if not git.branchExists('clearcase'):
        git.createBranch('clearcase')
        
    
       
