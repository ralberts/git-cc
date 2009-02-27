"""Checkin new git changesets to Clearcase"""

from common import *
from daemon import *
from clearcase import cc
from status import Modify, Add, Delete, Rename
import filecmp
from os import listdir
from os.path import isdir

IGNORE_CONFLICTS=False
SEND_MAIL=False
ARGS = {
    'force': 'ignore conflicts and check-in anyway',
    'sendmail':'send mail to commiter after the checkin is complete'
}

def main(force=False,sendmail=False):
    global IGNORE_CONFLICTS, SEND_MAIL
    if force:
        IGNORE_CONFLICTS=True
    if sendmail:
        SEND_MAIL=True
    cc_exec(['update', '.'])
    log = git_exec(['log', '--first-parent', '--reverse', '--pretty=format:%H%n%ce%n%s%n%b', CI_TAG + '..'])
    comment = []
    id = None
    email = None
    def _commit():
        if not id:
            return
        statuses = getStatuses(id)
        checkout(statuses, '\n'.join(comment))
        if SEND_MAIL:
            sendSummaryMessage(email,id)
        tag(CI_TAG, id)
    for line in log.splitlines():
        if line == "":
            _commit()
            comment = []
            id = None
            email = None
        if not id:
            id = line
        elif not email:
            email = line
        else:
            comment.append(line)
    _commit()

def getStatuses(id):
    status = git_exec(['diff','--name-status', '-M', '-z', '%s..%s' % (cfg.get('last_commit_id',CI_TAG), id)])
    types = {'M':Modify, 'R':Rename, 'D':Delete, 'A':Add, 'C':Add}
    list = []
    split = status.split('\x00')
    while len(split) > 1:
        char = split.pop(0)[0] # first char
        args = [split.pop(0)]
        if char == 'R':
            args.append(split.pop(0))
        elif char == 'C':
            args = [split.pop(0)]
        type = types[char](args)
        type.id = id
        list.append(type)
    return list

def checkout(stats, comment):
    """Poor mans two-phase commit"""
    transaction = Transaction(comment)
    for stat in stats:
        try:
            stat.stage(transaction)
        except Exception as e:
            transaction.rollback()
            raise e
    for stat in stats:
         stat.commit(transaction)
    transaction.commit(comment);

class Transaction:
    def __init__(self, comment):
        self.checkedout = []
        cc.mkact(comment)
    def add(self, file):
        self.checkedout.append(file)
    def co(self, file):
        cc_exec(['co', '-reserved', '-nc', file])
        self.add(file)
    def stageDir(self, file):
        file = file if file else '.'
        if file not in self.checkedout:
            self.co(file)
    def stage(self, file):
        self.co(file)
        global IGNORE_CONFLICTS    
        ccid = git.getFileHash(join(CC_DIR, file))
        gitid = getGitHash(file)
        print("object hash of object in clearcase = ",ccid);
        print("object hash of parent object in git = ",gitid);
        if ccid != gitid:
            if not IGNORE_CONFLICTS:
                raise Exception('File has been modified: %s. Try rebasing.' % file)
            else:
                print ('WARNING: Detected possible confilct with',file,'...ignoring...')
    def rollback(self):
        for file in self.checkedout:
            cc_exec(['unco', '-rm', file])
        cc.rmactivity()
    def commit(self, comment):
        for file in self.checkedout:
            storeGitHash(file,git.getFileHash(join(CC_DIR, file)))
            cc_exec(['ci', '-identical', '-c', comment, file])
            
        cc.commit()

# Retrieves the has of a file currently in clearcase
# We cache here for two reason, the first is speed, 
# but the second is that we need the has for the file as 
# it was *before* we started checking in over it.
# This prevents errors when we are checkin in the same file, over and over.
# Otherwise, the check to see if the clearcase parent had changed would barf....
# This is somewhat dangerous, but only if someone ch
HASH_CACHE=dict()

def storeGitHash(file,hash):
    print("storing hash ",hash,"for file",file)
    HASH_CACHE[file] = hash

def getGitHash(file):
    if file in HASH_CACHE:
        return HASH_CACHE[file]
    else:
        cmd = ['merge-base']
        cmd.extend([CC_TAG,'HEAD'])
        HASH_CACHE[file] = getBlob(git._exec(cmd).strip(), file)
    print("returning hash",HASH_CACHE[file],"for file",file)
    return HASH_CACHE[file]
        
    