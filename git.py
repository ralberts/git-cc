from common import *
from datetime import *

def popen(exe, cmd, cwd, env=None, decode=True):
    cmd.insert(0, exe)
    if DEBUG:
        debug('> ' + ' '.join(cmd))
    input = Popen(cmd, cwd=cwd, stdout=PIPE, env=env).stdout.read()
    return input if not decode else input.decode(ENCODING)

class Git(object):
    def getCurrentBranch(self):
        for branch in git_exec(['branch']).split('\n'):
            if branch.startswith('*'):
                branch = branch[2:]
                return branch
        return ""

    def _exec(self, cmd, check=False, env=None):
        output = popen('git', cmd, GIT_DIR, env)
        if check:
            # TODO: Figure out a reliable way to check for errors
            #if output.upper().find('ERROR') > -1 or output.upper().find('FATAL') > -1:
            # Hack, until we can figure out a better way to check for errors.
            if False:
                raise Exception(output)
            
        return output

    def getBranchList(self):
        def trm(branch):
            return branch[2:]
        return list(map(trm,self._exec(['branch']).split('\n')))
    
    def createBranch(self,branchname):
        self._exec(['branch', branchname])
        
    def branchExists(self,branchname):
        if branchname in self.getBranchList():
            return True
        return False
    
    def commit(self,comment="<no comment>",check=False,env=None):
        self._exec(['commit','-m',comment],check,env)
    
    def add(self,path,check=False):
        self._exec(['add',path],check)
        
    def remove(self,path,check=False):
        self._exec(['rm',path],check)
        self._exec(['add',path],check)
        
    def merge(self,branch):
        return self._exec(['merge',branch])
        
    def checkout(self,branchname,force=False):
        if force:
            self._exec(['checkout','-f',branchname],True)
        else:
            self._exec(['checkout',branchname],True)
            
    def checkoutPath(self,ref,path,check=False):
        self._exec(['checkout',ref,path,check])
        
    def getLastCommit(self,branchname):
        line = self._exec(['log', '-n', '1', '--pretty=format:%H?*?%ce?*?%cn?*?%ai?*?%s?*?%b', '%s' % branchname])
        split = line.split("?*?")
        return Commit(split[0],split[3],split[2],split[1],split[4] + '\n' + split[5])

    def checkPristine(self):
        if not exists(".git"):
            fail('No .git directory found')
        if(len(self._exec(['ls-files', '--modified']).splitlines()) > 0):
            fail('There are uncommitted files in your git directory')

    def doStash(self, f, stash=True):
        if(stash):
            self._exec(['stash'])
        f()
        if(stash):
            self._exec(['stash', 'pop'])
            
    def tag(self, tag, id="HEAD"):
        git_exec(['tag', '-f', tag, id])            

git = Git()        
        
class Commit(object):
    def __init__(self,UUID,date,author,email,comment):
        self.UUID = UUID
        self.date = datetime.strptime(date[:19], '%Y-%m-%d %H:%M:%S')
        self.author = author
        self.email = email
        self.comment = comment
   