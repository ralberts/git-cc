""" Daemon that automatically syncs a git branch with your clearcase view """

import time
import smtplib
from common import *
from git import *
from clearcase import *

import rebase, checkin, update, merge, acquire

""" 
Config Options Used By Daemon
admin_email = email of administrator to notify of changes, or when things go wrong
checkin_branch = git branch to monitor for commits to be checked into clearcase
sleep_time = amount of time in minutes to wait between synchronizations
"""

ARGS = {
    'no_checkin' : 'No checkin occurs, only history imports from clearcase'
}

CHECKIN_BRANCH=cfg.get("checkin_branch","")
ADMIN_EMAIL=cfg.get("admin_email","")
SLEEP_TIME=cfg.get("sleep_time",5)

def main(no_checkin=False):
    while loop(no_checkin):
       print("Waiting " + SLEEP_TIME + " minutes for next sync")
       time.sleep(60 * float(SLEEP_TIME))

def loop(no_checkin):
    # Just in case we were are in a broken merge
    git._exec(['checkout', '-f', CHECKIN_BRANCH])
    git._exec(['pull'])
    try:
        output = merge.main()
        #lastCommit = git.getLastCommit(CC_TAG)
        #git.tag(CI_TAG,lastCommit.UUID)
        if output.find('CONFLICT') >= 0:
            sendEmail(ADMIN_EMAIL,"Merge Needed!",output)
            return True
    except Exception as e:
        sendEmail(ADMIN_EMAIL,"Error encountered when retrieving clearcase history",str(e))
        return False
    try:
        ## Run pull, and pull an additional changes
        git.checkout(CHECKIN_BRANCH);
        pull = git._exec(["pull"])
        if pull.find('CONFLICT') >= 0:
            sendEmail(ADMIN_EMAIL,"Merge Needed!",pull)
            return True
        if not no_checkin:
            checkin.main(sendmail=True, checkin_branch=CHECKIN_BRANCH)
            # If everything checked in, then we want to tag the HEAD of the checkin-branch with the clearcase_CI tag.
    except Exception as e:
        sendEmail(ADMIN_EMAIL,"Error during checkin!",str(e))
        return False
    try:
        merge.main()
        #lastCommit = git.getLastCommit(CC_TAG)
        #git.tag(CI_TAG,lastCommit.UUID)
    except Exception as e:
        sendEmail(ADMIN_EMAIL,"Error during post checkin pull merge!",str(e))
        return False
    try: 
        git._exec(['push','origin',CHECKIN_BRANCH])
        git._exec(['push','origin',CC_TAG])
    except Exception as e:
        sendEmail(ADMIN_EMAIL,"Error during post checkin push!",str(e))
        return False
    return True
        

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

def sendSummaryMessage(to,commit_id):
    summary =  git_exec(['diff','--name-status', '-z', '%s^..%s' % (commit_id, commit_id)])
    subject = "Your commit <b>" + commit_id + "</b> has been checked into clearcase";
    message = subject + "<br/><br/>"
    message += summary
    try:
        sendEmail(to, subject, message)
    except Exception as e:
        message = "Error when sending commit summary email to " + to + "\n\n" + str(e)
        message += "\n\n The user probably needs to set the correct email in .git/config"
        sendEmail(ADMIN_EMAIL,"Error when sending summary email",message)
        
if __name__ == '__main__':
    main()
