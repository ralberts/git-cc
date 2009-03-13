from common import *
from os.path import join, dirname

class Status:
    def __init__(self, files):
        self.setFile(files[0])
    def setFile(self, file):
        self.file = file
    def cat(self):
        blob = git_exec(['cat-file', 'blob', getBlob(self.id, self.file)], decode=False)
        try:
            write(join(CC_DIR, self.file), blob)
        except Exception as e:
            print("Error when trying to write file",self.file,"   ",str(e))
    def stageDirs(self, t):
        dir = dirname(self.file)
        dirs = []
        while not exists(join(CC_DIR, dir)):
            dirs.append(dir)
            dir = dirname(dir)
        self.dirs = dirs
        t.stageDir(dir)
    def commitDirs(self, t):
        while len(self.dirs) > 0:
            dir = self.dirs.pop();
            if not exists(join(CC_DIR, dir)):
                cc_exec(['mkelem', '-nc', '-eltype', 'directory', dir])
                t.add(dir)

class Modify(Status):
    def stage(self, t):
        try:
            t.stage(self.file)
        except Exception as e:
            print("Error when trying to stage file",self.file,"   ",str(e))
           
    def commit(self, t):
        self.cat()

class Add(Status):
    def stage(self, t):
        self.stageDirs(t)
    def commit(self, t):
        self.commitDirs(t)
        self.cat()
        cc_exec(['mkelem', '-nc', self.file])
        t.add(self.file)

class Delete(Status):
    def stage(self, t):
        t.stageDir(dirname(self.file))
    def commit(self, t):
        # TODO Empty dirs?!?
        cc_exec(['rm', self.file])

class Rename(Status):
    def __init__(self, files):
        self.old = files[0]
        self.new = files[1]
        self.setFile(self.new)
    def stage(self, t):
        t.stageDir(dirname(self.old))
        t.stage(self.old)
        self.stageDirs(t)
    def commit(self, t):
        self.commitDirs(t)
        cc_exec(['mv', '-nc', self.old, self.new])
        t.checkedout.remove(self.old)
        t.add(self.new)
        self.cat()
