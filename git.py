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
    
    def createBranch(self,branchname,rootCommit=None):
        command = ['branch',branchname]
        if rootCommit != None:
            command.append(rootCommit)
        self._exec(command)
        
    def branchExists(self,branchname):
        if branchname in self.getBranchList():
            return True
        return False
    
    def deleteBranch(self,branchname,force=False):
        if self.branchExists(branchname):
            deleteArg = '-d'
            if force:
                deleteArg = '-D'
            self._exec(['branch',deleteArg,branchname])

    def getFileHash(self,file):
        return git_exec(['hash-object', file])[0:-1]
    
    def commit(self,comment="<no comment>",check=False,env=None):
        self._exec(['commit','-m',comment],check,env)
    
    def add(self,path,check=False):
        self._exec(['add',path],check)
        
    def remove(self,path,check=False):
        self._exec(['rm',path],check)
        self._exec(['add',path],check)

    def rebase(self,branch):
        out = git._exec(['rebase',branch])
        return out
      
    def merge(self,branch,message='cc->git auto merge'):
        return self._exec(['merge','-m',message,branch])

    def pull(self,):
        return self._exec(['pull'])
        
    def checkout(self,branchname,force=False):
        if force:
            self._exec(['checkout','-f',branchname],True)
        else:
            self._exec(['checkout',branchname],True)
            
    def checkoutPath(self,ref,path,check=False):
        self._exec(['checkout',ref,path,check])
        
    def getLastCommit(self, branchname):
        return self.getCommit(branchname)

    def getCommit(self,commit_id):
        line = self._exec(['log', '-n', '1', '--pretty=format:%H?*?%ce?*?%cn?*?%ai?*?%s?*?%b', '%s' % commit_id])
        split = line.split("?*?")
        return Commit(split[0],split[3],split[2],split[1],split[4] + '\n' + split[5])

    def getCommitHistory(self, start_id, end_id):
        commits = []
        output = self._exec(['log', '-M', '-z', '--reverse', '--pretty=format:%H?*?%ce?*?%cn?*?%ai?*?%s?*?%b', start_id + '..' + end_id])
        if len(output.strip()) > 0:
            lines = output.split('\x00')
            for line in lines:
                split = line.split("?*?")
                commits.append(Commit(split[0],split[3],split[2],split[1],split[4] + '\n' + split[5]))
        return commits
        
    def checkPristine(self):
        if not exists(".git"):
            fail('No .git directory found')
        if(len(self._exec(['ls-files', '--modified']).splitlines()) > 0):
            fail('There are uncommitted files in your git directory')

    def isFastForwardMerge(self,commitId):
        patch = self._exec(['format-patch','-1',commitId])
        if len(patch):
            print(commitId,"is not a fast-forward merge commit")
            return False
        print(commitId,"is a fast-forward merge")
        return True
    
    def doStash(self, f, stash=True):
        if(stash):
            self._exec(['stash'])
        f()
        if(stash):
            self._exec(['stash', 'pop'])
            
    def tag(self, tag, id="HEAD"):
        git_exec(['tag', '-f', tag, id])  
    
    def getParentCommits(self, commit):
        output = self._exec(['log','--pretty=format:%P', '-n', '1' ,commit])
        parents = output.split(' ')
        return parents
    
    def getMergeBase(self, commit1, commit2):
        output = self._exec(['merge-base',commit1, commit2])
        return output

    #===============================================================================
    #  getCommitList - 
    #    Operating on the CURRENT BRANCH, this method generates a list of 
    #    commits that is suited to cherry-pick to another branch.  The list 
    #    of commits provided is the minimal set required to duplicate the
    #    commit history of from startCommit to endCommit, regardless of the number
    #    of merges/branches that exist between the two points.
    #    
    #    NOTE: The list returned does include endCommit, but NOT startCommit
    #===============================================================================
    def getCommitList(self, startCommit, endCommit):
        commits = []
        def walkHistory(commit):
            parents = git.getParentCommits(commit)
            if commit == startCommit:
                return None
            for parent in parents:
                if len(commits) > 0 and commits[-1] == startCommit:
                    return None
                if parent == startCommit:
                    commits.append(parent)
                    return None
                else:
                    if git.getMergeBase(startCommit,parent).strip() != startCommit:
                        return None
                    else:
                        commits.append(parent)
                        walkHistory(parent)
        commits.append(endCommit)  
        walkHistory(endCommit)
        return commits
#        commits = []
#        def walkHistory(commit):
#            commits.append(commit)
#            if commit == startCommit:
#                return None
#            parents = git.getParentCommits(commit)
#            for parent in parents:
#                if commits[-1] == startCommit:
#                    return None
#                elif git.getMergeBase(startCommit,parent).strip() != startCommit:
#                    return None
#                else:
#                    walkHistory(parent)  
#        walkHistory(endCommit)
#        return commits        

git = Git()        
        
class Commit(object):
    def __init__(self,id,date,author,email,comment):
        self.id = id
        self.date = datetime.strptime(date[:19], '%Y-%m-%d %H:%M:%S')
        self.author = author
        self.email = email
        self.comment = comment
   