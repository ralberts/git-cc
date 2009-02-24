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
ARGS = {}

CHECKIN_BRANCH= cfg.get("checkin_branch","")
ADMIN_EMAIL=cfg.get("admin_email","")
SLEEP_TIME=cfg.get("sleep_time",5)

def main():
    while loop():
       print("Waiting " + SLEEP_TIME + " minutes for next sync")
       time.sleep(60 * float(SLEEP_TIME))

def loop():
    # Just in case we were are in a broken merge
    git._exec(['checkout', '-f', CHECKIN_BRANCH])
    git._exec(['pull'])
    try:
        acquire.main()
    except Exception as e:
        sendEmail(ADMIN_EMAIL,"Error encountered when retrieving clearcase history",str(e))
        return False
    output = git._exec(['merge', CC_TAG])
    if output.find('CONFLICT') >= 0:
        sendEmail(ADMIN_EMAIL,"Merge Needed!",output)
        return True
    try:
        ## Run pull, and pull an additional changes
        pull = git._exec(["pull"])
        if pull.find('CONFLICT') >= 0:
            sendEmail(ADMIN_EMAIL,"Merge Needed!",pull)
            return True
        checkin.main(sendmail=True)
        # If everything checked in, then we want to tag the HEAD of the checkin-branch with the clearcase_CI tag.
        tag(CI_TAG,CHECKIN_BRANCH)
    except Exception as e:
        sendEmail(ADMIN_EMAIL,"Error during checkin!",str(e))
        return False
    try:
        merge.main()
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

if __name__ == '__main__':
    main()
