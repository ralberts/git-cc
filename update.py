"""Update the git repository with Clearcase manually, ignoring history"""

from common import *
import sync, reset, git

def main(message):
    cc_exec(['update', '.'])
    sync.main('*')
    git._exec(['add', '.'])
    git._exec(['commit', '-m', message])
    git.tag(CI_TAG)
    reset.main('HEAD')
