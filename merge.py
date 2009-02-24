"""Imports the latest history from clearcase into the "clearcase" branch,
and merges the clearcase branch to the current branch"""

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
    if not (len(git.getCurrentBranch()) or git.getCurrentBranch() == CC_TAG):
        fail('You must be on a branch other then ' + CC_TAG + 'to use the gitcc merge')
    branch = git.getCurrentBranch()
    if not (stash or dry_run or lshistory):
        git.checkPristine()
    acquire.main(since=since,load=load,lshistory=lshistory,dry_run=dry_run)
    print('Performing merge...')
    git.checkout(branch)
    git.merge(CC_TAG)
    tag(CI_TAG, CC_TAG)    