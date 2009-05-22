from proc import Process
from exceptions import MergeException
from common import *


def popen(exe, cmd, cwd, env=None, decode=True):
    cmd.insert(0, exe)
    if DEBUG:
        debug('> ' + ' '.join(cmd))
    process = Popen(cmd, cwd=cwd, stdout=PIPE, env=env)
    input = process.stdout.read()
    
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
        
    def _exec2(self, args, check=False, env=None, returnCode=None):
        proc = Process('git', args, GIT_DIR, env, outcome=returnCode)
        proc.call()
        return proc        

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
        proc = git._exec2(['rebase', branch], returnCode=0)
        if proc.returncode != 0:
            raise Exception('Error during rebase. ' + proc.stdout + proc.stderr)
        return proc.stdout
      
    def merge(self,branch,message='cc->git auto merge'):
        return self._exec(['merge','-m',message,branch])

    def pull(self,):
        return self._exec2(['pull']).stdout
        
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
    
    def show(self, sha1):
        proc = self._exec2(['show',sha1])
        return proc.stdout
        
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
                elif git.getMergeBase(startCommit,parent).strip() == startCommit:
                    commits.append(parent)
                    walkHistory(parent)
        commits.append(endCommit)  
        walkHistory(endCommit)
        return commits

    def mergeFiles(self, file1, base, file2, outputfile):
        merge_proc = self._exec2(['merge-file', '-p', file1, base, file2])
        conflicts = merge_proc.returncode
        if conflicts > 0:
            debug("Automatic Merge failed.  " + str(merge_proc.returncode) + ' conflicts need to be resolved manually')
            if not self.openMergeTool(file1, base, file2, outputfile):
                raise MergeException(outputfile, "Manual merge failed.")
        elif conflicts < 0:
            raise MergeException(outputfile, "Error during automatic merge: " + merge_proc.stderr)
        else:
            write(outputfile, merge_proc.stdout)
        
    def openMergeTool(self, local, base, remote, output):
        proc = Process("c:\\Program Files\\Perforce\\p4merge.exe", [base, remote, local, output], GIT_DIR)
        proc.call()
        debug("Merge program exited with " + str(proc.returncode))
        if proc.returncode == 0:
            return True
        return False
        



git = Git()        
        
class Commit(object):
    def __init__(self,id,date,author,email,comment):
        self.id = id
        self.date = datetime.strptime(date[:19], '%Y-%m-%d %H:%M:%S')
        self.author = author
        self.email = email
        self.comment = comment
   