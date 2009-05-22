import subprocess
from common import *

class Process():
    def __init__(self, exe, cmd, cwd, env=None, decode=True, outcome=None):
        self.cmd = cmd
        self.cmd.insert(0, exe)
        self.cwd = cwd
        self.env = env
        self.decode = decode
        self.outcome = None
    
    def call(self):
        debug('> ' + ' '.join(self.cmd))
        self.process = subprocess.Popen(self.cmd, cwd=self.cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self.env)
        self.stdout = self.__decode(self.process.stdout.read())
        self.stderr = self.__decode(self.process.stderr.read())
        self.returncode = self.process.wait()
    
    def __decode(self, str):
        if self.decode:
            return str.decode(ENCODING)
        return str
    
