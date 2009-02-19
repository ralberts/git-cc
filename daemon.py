#!/usr/bin/env python
import time
import smtplib
from common import *
import rebase, checkin, update, reset

""" 
Config Options Used By Daemon
admin_email = email of administrator to notify of changes, or when things go wrong
checkin_branch = git branch to monitor for commits to be checked into clearcase
sleep_time = amount of time in minutes to wait between synchronizations
"""
CHECKIN_BRANCH= cfg.get("checkin_branch","")
ADMIN_EMAIL=cfg.get("admin_email","")
SLEEP_TIME=cfg.get("sleep_time",5)

def main():
    while loop():
       print("Waiting " + SLEEP_TIME + " minutes for next sync")
       time.sleep(60 * float(SLEEP_TIME))

def loop():
    # Just in case we were are in a broken merge
    git_exec(['checkout', '-f', CHECKIN_BRANCH])
    git_exec(['pull'])
    try:
        rebase.main(merge=True)
    except Exception as e:
        sendEmail(ADMIN_EMAIL,str(e))
        return False
    merge = git_exec(['merge', CC_TAG])
    if merge.find('CONFLICT') >= 0:
        sendEmail(ADMIN_EMAIL,merge)
        return True
    try:
        checkin.main(sendmail=True)
        # If everything checked in, then we want to tag the HEAD of the checkin-branch with the clearcase_CI tag.
        tag(CI_TAG,CHECKIN_BRANCH)
        git_exec(['push','origin',CHECKIN_BRANCH]);
    except Exception as e:
        sendEmail(ADMIN_EMAIL,str(e))
        # Someone just checked in - rebase again
        return False
    
    try:
        rebase.main(merge=True)
    except Exception as e:
        sendEmail(ADMIN_EMAIL,str(e))
        return False
    return True

if __name__ == '__main__':
    main()
