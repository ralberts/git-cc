"""Rebase from Clearcase"""

from os.path import join, dirname, exists, isdir
import os, stat, shutil, time

import acquire

from common import *
from datetime import datetime, timedelta
from users import users, mailSuffix
from fnmatch import fnmatch
from git import *

"""
Things remaining:
1. Renames with no content change. Tricky.
"""

ARGS = {
    'stash': 'Wraps the rebase in a stash to avoid file changes being lost',
    'dry_run': 'Prints a list of changesets to be imported',
    'lshistory': 'Prints the raw output of lshistory to be cached for load',
    'load': 'Loads the contents of a previously saved lshistory file',
    'since': 'Override the date used to rebase from (use with caution)'
}


def main(stash=False, dry_run=False, lshistory=False, load=None, since=None):
    if git.getCurrentBranch() == CC_TAG:
        print("Cannot rebase",CC_TAG,"""onto itself (well, I could, but what is the point?).\n  
            Please choose another branch and try again.""")
    branch = git.getCurrentBranch()
    if not (stash or dry_run or lshistory):
        git.checkPristine()
    acquire.main(since=since,load=load,lshistory=lshistory,dry_run=dry_run)
    if not dry_run:
        print('Performing rebase...')
        if len(branch):
            git._exec(['rebase', '--onto', CC_TAG, CI_TAG, branch])
            git._exec(['tag','-f', CI_TAG, CC_TAG])
        else:
            git._exec(['checkout', '-b', CC_TAG])
        

