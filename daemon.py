""" Daemon that automatically syncs a git branch with your clearcase view """

import time, smtplib, sys, traceback, checkin, acquire
from common import *
from git import *



""" 
Config Options Used By Daemon
admin_email = email of administrator to notify of changes, or when things go wrong
checkin_branch = git branch to monitor for commits to be checked into clearcase
sleep_time = amount of time in minutes to wait between synchronizations
"""

ARGS = {
    'no_checkin' : 'No checkin occurs, only history imports from clearcase',
    'reset' : 'Assume that everything is in sync, and reset the daemon to start fresh'
}

CHECKIN_BRANCH=cfg.get("checkin_branch","")
ADMIN_EMAIL=cfg.get("admin_email","")
SLEEP_TIME=cfg.get("sleep_time",5)
SYNC_BRANCH="gitcc_sync_branch"
RECOVERY_MODE=False


def main(no_checkin=False, reset=False):
    if reset and ask("Before resetting, be sure that everything is in sync.\nAre you sure you want to do this?") == 'y':
        purgeBranches()
        resetConfig()
    while loop(no_checkin):
       print("Waiting " + SLEEP_TIME + " minutes for next sync")
       time.sleep(60 * float(SLEEP_TIME))

def loop(no_checkin):
    last_commit = cfg.get("last_commit_id",'HEAD')
    
    RECOVERY_MODE = git.branchExists(SYNC_BRANCH) or git.branchExists(CC_TAG)
    if RECOVERY_MODE:
        quest = "It looks like I was in the middle of a sync. I can try to\n"
        quest += "continue from this point (best option).  Or, I can start over.\n"
        quest += "\nWARNING!! Starting over could cause unexpected results!\n"
        quest += "\nWould you like me to attempt to continue, or start fresh?" 
        answer = ask(quest,["Continue", "Restart"])
        if answer.upper().find('R') == 0:
            purgeBranches()
            RECOVERY_MODE = False
        elif answer.upper().find('C') == 0:
            print('OK... Continuing where I left off...')
        else:
            print('Invalid option ' + answer)
            return False
    try:
        if not RECOVERY_MODE:
            # Pull most recent changes
            git.checkout(CHECKIN_BRANCH);
            pull = git._exec(["pull"])
    
            # Get list of commits
            commits = git.getCommitList(last_commit, git.getLastCommit(CHECKIN_BRANCH).id)
            if len(commits) > 1 and not no_checkin:
                
                # build temporary sync branch
                commits.pop() # pop off the first commit (we don't need it, and it could be a merge commit, which causes problems!)
                commits.reverse()
                buildSyncBranch(commits, last_commit)
                
                # check that the sync branch is accurate
                diff = checkDiff(SYNC_BRANCH,CHECKIN_BRANCH)
                if diff != None:
                    sendAdminEmail("Sync branch does not match " + CHECKIN_BRANCH + "! Aborting...",diff)
                    return False
    
                # update clearcase view
                cc_exec(['update', '.'])
    
        # if SYNC_BRANCH already existed, then we need to start 
        # from the last_sync_commit_id when committing new changes
        # Therefore, we must remove already synced commits from
        # the list.
        if RECOVERY_MODE: 
            if not git.branchExists(SYNC_BRANCH):
                git.createBranch(SYNC_BRANCH, CHECKIN_BRANCH)
            git.checkout(SYNC_BRANCH)
            
        
        if getLastSyncCommit() and RECOVERY_MODE:
            sync_commits = git.getCommitHistory(getLastSyncCommit(),'HEAD')
        else:
            # set initial last_sync_commit_id == last_commit
            setLastSyncCommit(last_commit)
            sync_commits = git.getCommitHistory(last_commit,'HEAD')


        # commit all commits on sync-branch
        for commit in sync_commits:
            statuses = checkin.getStatuses(commit.id, getLastSyncCommit())
            checkin.checkout(statuses, commit.comment)
            sendSummaryMessage(commit.email, commit.id, getLastSyncCommit())
            setLastSyncCommit(commit.id)
            
        # All commits happened succesfully
        setLastSyncCommit("")

            
    except Exception as e:
        print('Error',e)
        traceback.print_exc(file=sys.stdout)
        sendAdminEmail("Error during checkin!",str(e))
        return False

    try:

        # Check to see if we are recovering from a previous sync
        # If the clearcase branch doesn't exist, then we had not 
        # gotten to that point yet.  If we havn't, then we must 
        # first.
        # 1.) create 'clearcase' branch
        # 2.)acquire clearcase history

        if not git.branchExists(CC_TAG):
            git.createBranch(CC_TAG,last_commit)
            acquire.main()

        # rebase aquired history onto sync_branch
        git.checkout(CC_TAG)
        if git.branchExists(SYNC_BRANCH):
            out = git.rebase(SYNC_BRANCH)
        
        # prepare list of commits from 'clearcase' branch to cherry-pick
        fromCommit = SYNC_BRANCH
        if not git.branchExists(SYNC_BRANCH):
            fromCommit = last_commit
        if RECOVERY_MODE and getLastCherryPickCommit(): 
            fromCommit = getLastCherryPickCommit()
        commits = git.getCommitHistory(fromCommit,CC_TAG)
        
        # checkout checkin branch
        git.checkout(CHECKIN_BRANCH)

        # TODO: Add checks to ensure that Cherry-pick happened successfully
        # cherry-pick commit from the 'clearcase' branch
        for commit in commits:
            git._exec(['cherry-pick', commit.id])
            setLastCherryPickCommit(commit.id)

        # If we get to this point, reset the last_cherry_pick_commit 
        setLastCherryPickCommit("")
        
        # check that the clearcase branch matches the CHECKIN_BRANCH, at this point, they
        # should be the same.
        diff = checkDiff(CC_TAG,CHECKIN_BRANCH)
        if diff != None:
            sendAdminEmail("clearcase branch does not match " + CHECKIN_BRANCH + "! Aborting...", diff)
            return False


        # clean up -- delete clearcase and sync braches
        git.deleteBranch(CC_TAG, force=True)
        git.deleteBranch(SYNC_BRANCH, force=True)

        # all is well! set last_commit_id to the last commit on the checkin branch
        cfg.set('last_commit_id',git.getLastCommit(CHECKIN_BRANCH).id)
        cfg.write();

        # pull in any changes, and check for conflicts
        out = git.pull()
        if out.upper().find('CONFLICT') >= 0:
            sendAdminEmail("Merge Needed!",out)
            return False

    except Exception as e:
        print('Error: ',e)
        traceback.print_exc(file=sys.stdout)
        sendAdminEmail("Error during clearcase history acquisition!",str(e))
        return False

    try: 
        # Push changes out to the master repo
        git._exec(['push','origin',CHECKIN_BRANCH])
    except Exception as e:
        print('Error: ',e)
        traceback.print_exc(file=sys.stdout)
        sendAdminEmail("Error during push!",str(e))
        return False
    return True
        

def sendAdminEmail(subject,content):
    print("I would send an email, but you don't want me to")
    #sendEmail(ADMIN_EMAIL, subject, content)

def sendEmail(to,subject,content):
    sender = 'gitcc@no-reply.com'
    print("Sending email to ",to)
    headers = "From: %s\r\nTo: %s\r\nSubject: %s\r\n\r\n" % (sender, to, subject)
    message = headers + content
    if not cfg.get('smtp_host',None):
        print("Cannot send email, no smtp_host defined in gitcc config")
    server = smtplib.SMTP(cfg.get('smtp_host'))
    server.sendmail(sender, to, message)
    server.quit()

def sendSummaryMessage(to,commit_id,lastCommitId):
    summary =  git_exec(['diff','--name-status','%s..%s' % (lastCommitId, commit_id)])
    subject = "Your commit " + commit_id + " has been checked into clearcase"
    message = subject + "\n\n"
    message += summary
    try:
        sendEmail(to, subject, message)
    except Exception as e:
        message = "Error when sending commit summary email to " + to + "\n\n" + str(e)
        message += "\n\n The user probably needs to set the correct email in .git/config"
        sendEmail(ADMIN_EMAIL,"Error when sending summary email",message)

#------------------------------------------------------------------------------ 
#    Builds a temporary branch, based off of last_commit, by cherry picking 
#    the list of commits returned from git.getCommitList()
#------------------------------------------------------------------------------ 
def buildSyncBranch(commits,last_commit):
    git.createBranch(SYNC_BRANCH,last_commit)
    git.checkout(SYNC_BRANCH)
    i = 0
    for commit in commits:
        print("Cherry picking",commit)
        parents = git.getParentCommits(commit)
        out = ""
        if len(parents) > 1:
            parent_number = None
            if i > 0:
                if parents[0] == commits[i-1]:
                    parent_number = 1
                elif parents[1] == commits[i-1]:
                    parent_number = 2
            else:
                if parents[0] == last_commit:
                    parent_number = 1
                elif parents[1] == last_commit:
                    parent_number = 2
            out = git._exec(['cherry-pick','-m',str(parent_number),commit])
        else:
            out = git._exec(['cherry-pick', commit])
        i += 1    

def setLastSyncCommit(commit_id):           
    cfg.set('last_sync_commit_id',commit_id)
    cfg.write

def getLastSyncCommit(default=None):
    return cfg.get('last_sync_commit_id',default)

def setLastCherryPickCommit(commit_id):
    cfg.set('last_cherry_pick_commit',commit_id)
    cfg.write
    
def getLastCherryPickCommit():
    return cfg.get('last_cherry_pick_commit',None);

def checkDiff(branch1,branch2):
    output = git._exec(['diff','--name-status', branch1, branch2])
    if len(output.strip()) > 0:
        return output
    else:
        return None
def purgeBranches():
    git.checkout(CHECKIN_BRANCH, force=True)
    git.deleteBranch(SYNC_BRANCH, force=True)
    git.deleteBranch(CC_TAG, force=True)
    setLastSyncCommit("")
    setLastCherryPickCommit("")

def resetConfig():
    def calcTimeZone():
        tz = int(time.timezone/60/60)
        prefix = "-"
        if tz < 0:
            prefix = "+"
        if tz < 10:
            return prefix + '0' + str(abs(tz))
        else:
            return preifx + str(abs(tz))
        
    cfg.set("last_commit_id",git.getLastCommit(CHECKIN_BRANCH).id)
    cfg.set("since",datetime.strftime(datetime.today(), '%Y-%m-%dT%H:%M:%S') + calcTimeZone());
    cfg.write()
            
if __name__ == '__main__':
    main()
    
