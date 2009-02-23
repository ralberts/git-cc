"""Imports history from Clearcase and commits it to Git repository"""

from os.path import join, dirname, exists, isdir
import os, stat, shutil, time

from timeutil import *

from common import *
from datetime import datetime, timedelta
from users import users, mailSuffix
from fnmatch import fnmatch
from clearcase import *
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
    'merge': 'Uses \'git merge\' instead of \'git rebase\' to sync the current branch',
    'since': 'Override the date used to rebase from (use with caution)'
}

def main(stash=False, dry_run=False, lshistory=False, load=None, since=None):
    checkRepo()
    if not (stash or dry_run or lshistory):
        git.checkPristine()
    if not since:
        since = getSince()
    if load:
        history = open(load, 'r').read()
    else:
        history = cc.getViewHistory(since,raw=True)
    
    if lshistory:
        print(history)
    else:
        checkins = cc.parseHistory(history,_filter=onlyAncestorsFilter)
        checkins.sort(key = lambda x: x.date)
        groups = mergeHistory(checkins)
        if dry_run:
            return printGroups(checkins)
        if not len(checkins):
            return
        git.doStash(lambda: doCommit(groups), stash)

# Check the repo to ensure that the "clearcase" branch exists
def checkRepo():
    if not git.branchExists(CC_TAG):
        answer = input(CC_TAG + " does not exist.  Do you want me to create it? (Y or N)")
        if answer.upper().find('Y') == 0:
            git.checkout("master")
            git.createBranch(CC_TAG)
            if not git.branchExists(CC_TAG):
                raise Exception("Unable to create branch " + CC_TAG)
        else:
            print("Please create the ",CC_TAG,"branch and try again")
            exit()
            
def doCommit(groups):
    branch = git.getCurrentBranch()
    git.checkout(CC_TAG)
    for group in groups:
        commitGroup(group)
    

def getSince():
    commit = git.getLastCommit(CC_TAG)
    return commit.date + timedelta(seconds=1)

def mergeHistory(changesets):
    last = None
    groups = []
    def same(a, b):
        return a.subject == b.subject and a.user == b.user
    for cs in changesets:
        if last and same(last, cs):
            last.append(cs)
        else:
            last = Group(cs)
            groups.append(last)
    for group in groups:
        group.fixComment()
    return groups

def printGroups(groups):
    for cs in groups:
        print('%s "%s"' % (cs.user, cs.subject))
        for file in cs.files:
            print("  %s" % file.file)

def commitGroup(group):
    def getUserEmail(user):
        return '<%s@%s>' % (user.lower().replace(' ','.').replace("'", ''), mailSuffix)
    files = []
    for file in group.files:
        addElement(file)
    env = {}
    user = users.get(group.user, group.user)
    user = str(user)
    env['GIT_AUTHOR_DATE'] = env['GIT_COMMITTER_DATE'] = str(group.date)
    env['GIT_AUTHOR_NAME'] = env['GIT_COMMITTER_NAME'] = user
    env['GIT_AUTHOR_EMAIL'] = env['GIT_COMMITTER_EMAIL'] = getUserEmail(user)
    comment = group.comment if group.comment.strip() != "" else "<empty message>"
    git.commit(comment, check=True, env=env)

def addElement(elm):
    toFile = buildPath([GIT_DIR, elm.path])
    mkdirs(toFile)
    if elm.type == "FILE":
        removeFile(toFile)
        cc.getFileForElement(elm, toFile)
        if not exists(toFile):
            git.checkoutFile('HEAD', toFile)
        else:
            os.chmod(toFile, stat.S_IWRITE)
        git.add(elm.path)
    elif elm.type == "DIRECTORY":
        elm.getAddedRemoved();
        for added in elm.added:
            fakelm = Element(added,"")
            versions = cc.getElementHistory(fakelm,_filter=chainFilters([branchFilter,dateRangeFilter(toDate=elm.date)]))
            if len(versions) < 1:
                versions = cc.getElementHistory(fakelm,since=elm.date,_filter=branchFilter)
                versions.reverse()
                if len(versions) <1:
                    print("Cannot find a version of the file ",fakelm.path,"to add to directory",elm.path)
                    continue
            addElement(versions.pop())
        for removed in elm.removed:
            git.remove(removed)
            
class Group:
    def __init__(self, cs):
        self.user = cs.user
        self.comment = cs.comment
        self.subject = cs.subject
        self.files = []
        self.append(cs)
    def append(self, cs):
        self.date = cs.date
        self.files.append(cs)
    def fixComment(self):
        self.comment = cc.getRealComment(self.comment)
        self.subject = self.comment.split('\n')[0]
    
    
