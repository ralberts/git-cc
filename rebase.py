"""Rebase from Clearcase"""

from os.path import join, dirname, exists, isdir
import os, stat, shutil, time
from common import *
from datetime import datetime, timedelta
from users import users, mailSuffix
from fnmatch import fnmatch
from clearcase import cc

"""
Things remaining:
1. Renames with no content change. Tricky.
"""

CC_LSH = ['lsh', '-fmt', '%o%m|%d|%u|%En|%Vn|'+cc.getCommentFmt()+'\\n', '-recurse']
DELIM = '|'

ARGS = {
    'stash': 'Wraps the rebase in a stash to avoid file changes being lost',
    'dry_run': 'Prints a list of changesets to be imported',
    'lshistory': 'Prints the raw output of lshistory to be cached for load',
    'load': 'Loads the contents of a previously saved lshistory file',
}

def main(stash=False, dry_run=False, lshistory=False, load=None):
    if not (stash or dry_run or lshistory):
        checkPristine()
    since = getSince()
    if load:
        history = open(load, 'r').read()
    else:
        cc.rebase()
        history = getHistory(since)
    if lshistory:
        print(history)
    else:
        cs = parseHistory(history,getCurrentVersions())
        cs.sort(key = lambda x: x.date)
        cs = mergeHistory(cs)
        if dry_run:
            return printGroups(cs)
        if not len(cs):
            return
        doStash(lambda: doCommit(cs), stash)

def doCommit(cs):
    branch = getCurrentBranch()
    git_exec(['checkout', CC_TAG])
    commit(cs)
    if len(branch):
        git_exec(['rebase', '--onto', CC_TAG, CI_TAG, branch])
    else:
        git_exec(['checkout', '-b', CC_TAG])
    tag(CI_TAG, CC_TAG)

def getCurrentBranch():
    for branch in git_exec(['branch']).split('\n'):
        if branch.startswith('*'):
            branch = branch[2:]
            if branch == '(no branch)':
                fail("Why aren't you on a branch?")
            return branch
    return ""

def getSince():
    date = git_exec(['log', '-n', '1', '--pretty=format:%ai', '%s' % CC_TAG])
    if len(date) == 0:
        return cfg.get('since')
    date = date[:19]
    date = datetime.strptime(date, '%Y-%m-%d %H:%M:%S')
    date = date + timedelta(seconds=1)
    return datetime.strftime(date, '%d-%b-%Y.%H:%M:%S')

def getHistory(since):
    lsh = CC_LSH[:]
    if since:
        lsh.extend(['-since', since])
    lsh.extend(cfg.getList('include', '.'))
    return cc_exec(lsh)

def getCurrentVersions():
    lsc = ['ls','-recurse','-short'][:]
    lsc.extend(cfg.getList('include','.'))
    ls = cc_exec(lsc).splitlines()
    versions = dict()
    for line in ls:
        if line.count('@@') > 0:
            versions[line.split('@@')[0]] = Version(line)
    return versions

def filterBranches(version):
    version = version.split('\\')
    version.pop()
    version = version[-1]
    for branch in cfg.getList('branches', 'main'):
        if fnmatch(version, branch):
            return True
    return False

def parseHistory(lines,versions):
    changesets = []
    def add(split, comment):
        if not split:
            return
        cstype = split[0]
        if cstype in TYPES:
            cs = TYPES[cstype](split, comment)
            if filterBranches(cs.version):
                if versions[cs.file].branch != cs.version.split('\\')[-2]:
                    if datetime.fromtimestamp(os.path.getmtime(buildPath([CC_DIR,versions[cs.file].file]))) < datetime.strptime(cs.date[:-3], '%Y-%m-%dT%H:%M:%S'): 
                        return
                changesets.append(cs)
    last = None
    comment = None
    for line in lines.splitlines():
        split = line.split(DELIM)
        if len(split) == 1 and last:
            comment += "\n" + split[0]
        else:
            add(last, comment)
            comment = split[5]
            last = split
    add(last, comment)
    return changesets

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

def commit(list):
    for cs in list:
        cs.commit()

def printGroups(groups):
    for cs in groups:
        print('%s "%s"' % (cs.user, cs.subject))
        for file in cs.files:
            print("  %s" % file.file)

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
    def commit(self):
        def getUserEmail(user):
            return '<%s@%s>' % (user.lower().replace(' ','.').replace("'", ''), mailSuffix)
        files = []
        for file in self.files:
            files.append(file.file)
        for file in self.files:
            file.add(files)
        env = {}
        user = users.get(self.user, self.user)
        user = str(user)
        env['GIT_AUTHOR_DATE'] = env['GIT_COMMITTER_DATE'] = str(self.date)
        env['GIT_AUTHOR_NAME'] = env['GIT_COMMITTER_NAME'] = user
        env['GIT_AUTHOR_EMAIL'] = env['GIT_COMMITTER_EMAIL'] = getUserEmail(user)
        comment = self.comment if self.comment.strip() != "" else "<empty message>"
        git_exec(['commit', '-m', comment], env=env)

def cc_file(file, version):
    return '%s@@%s' % (file, version)

class Changeset(object):
    def __init__(self, split, comment):
        self.date = split[1]
        self.user = split[2]
        self.file = split[3]
        self.version = split[4]
        self.comment = comment
        self.subject = comment.split('\n')[0]
    def add(self, files):
        self._add(self.file, self.version)
    def _add(self, file, version):
        toFile = join(GIT_DIR, file)
        mkdirs(toFile)
        removeFile(toFile)
        cc_exec(['get','-to', toFile, cc_file(file, version)])
        if not exists(toFile):
            git_exec(['checkout', 'HEAD', toFile])
        else:
            os.chmod(toFile, stat.S_IWRITE)
        git_exec(['add', file])

class Uncataloged(Changeset):
    def add(self, files):
        dir = cc_file(self.file, self.version)
        diff = cc_exec(['diff', '-diff_format', '-pred', dir])
        def getFile(line):
            return join(self.file, line[2:line.find(' --') - 1])
        for line in diff.split('\n'):
            if line.startswith('<'):
                git_exec(['rm', '-r', getFile(line)])
            elif line.startswith('>'):
                added = getFile(line)
                cc_added = join(CC_DIR, added)
                if not exists(cc_added) or isdir(cc_added) or added in files:
                    continue
                history = cc_exec(['lshistory', '-fmt', '%o%m|%d|%Vn\\n', added])
                date = cc_exec(['describe', '-fmt', '%d', dir])
                def f(s):
                    return s[0] == 'checkinversion' and s[1] < date and filterBranches(s[2])
                versions = list(filter(f, list(map(lambda x: x.split('|'), history.split('\n')))))
                if len(versions) == 0:
                    raise Exception("It appears that you may be missing a branch (or have a mis-spelling) in the includes section of your gitcc config file.")  
                self._add(added, version.strip())

class Version(object):
    def __init__(self,lsline):
        split = lsline.split('@@')
        self.file = split[0]
        versionSplit = split[1].split('\\')
        self.branch = versionSplit[-2]
        self.version = versionSplit[-1]

TYPES = {\
    'checkinversion': Changeset,\
    'checkindirectory version': Uncataloged,\
}