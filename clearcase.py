from datetime import datetime, timedelta
import time

from common import *

class Clearcase:
    # Dictionary used to hold currentVersion cache
    currentVersions = dict()
    
    def __init__(self):
        self.LSH_BASE = ['lshistory', '-fmt', '%o%m|%d|%u|%En|%Vn|'+self.getCommentFmt()+'\\n']
    
    @classmethod
    def _exec(cls,cmd):
        return popen('cleartool', cmd, CC_DIR)

    def getViewHistory(self, since=None, _filter=None, raw=False):
        cmd = self.LSH_BASE[:]
        cmd.extend(['-recurse'])
        if since:
            cmd.extend(['-since', self.formatForLshistory(since)])
        cmd.extend(cfg.getList('include', '.'))
        output = self._exec(cmd)
        if raw:
           return output 
        return self.parseHistory(output,_filter)
           
        
    def getElementHistory(self, element, since=None, _filter=None, raw=False):
        cmd = self.LSH_BASE[:]
        if since:
            cmd.extend(['-since', self.formatForLshistory(since)])
        cmd.extend([element.path])
        output = self._exec(cmd)
        if raw:
            return output
        return self.parseHistory(output,_filter)
        
    # Turns the output of a lshistory call and returns a list of checkins that represent that ouput
    # Accepts the optional argument _filter: a filter function to be used to filter the final list of 
    # parsed values
    def parseHistory(self, history, _filter=None):
        checkins = []
        def add(split, comment):
            if not split:
                return
            citype = split[0]
            if citype in TYPES:
                ci = TYPES[citype](split[1],split[2],split[3],split[4],comment)
                if _filter(ci):
                    checkins.append(ci)
        last = None
        comment = None
        for line in history.splitlines():
            split = line.split("|")
            if len(split) == 1 and last:
                comment += "\n" + split[0]
            else:
                add(last, comment)
                comment = split[5]
                last = split
        return checkins
    # TODO: Decide if we really need this...
    def getCurrentVersions():
        lsc = ['ls','-recurse','-short'][:]
        lsc.extend(cfg.getList('include','.'))
        ls = self._exec(lsc).splitlines()
        versions = dict()
        for line in ls:
            if line.count('@@') > 0:
                split = line.split('@@')
                versions[split[0]] = Element(split[0],split[1])
        return versions
    
    # Gets the current version of file/dir specified by the element passed in.  If there is no
    # version of the element in the current view, then None is returned.  Otherwise, a new
    # element that represents the version in the current view is returned.
    @classmethod
    def getCurrentVersion(cls,elm):
        if elm.path in cls.currentVersions:
            return cls.currentVersions[elm.path]
        if os.path.exists(elm.getAbsolutePath()):
            split = cls._exec(['ls','-short',elm.path]).splitlines()[0].split("@@")
            if len(split) < 2:
            	return None
            cls.currentVersions[split[0]] = Element(split[0],split[1])
            return cls.currentVersions[split[0]]
        else:
            return None

    # Returns a time_stuct (i.e. date) given a valid string
    # that is formated as a clearcase date (%Y-%m-%dT%H:%M:%S)
    #
    # Also, since clearcase reports the timestamp including the UTC offset
    # we convert the date to the current timezone to make it valid for 
    # us in comparisons
    @classmethod
    def parseDate(cls,timestamp):
        def calcOffset(utc):
            utc = utc.replace(":",""); # remove ':'
            if len(utc) > 3:
                utcHours = float(utc[:-2])
                utcMinutes = float(utc[-2:])
            else: 
                utcHours = float(utc)
                utcMinutes = 0
            if utcHours < 0:
                offset = utcHours - utcMinutes/60 
            else:
                offset = utcHours + utcMinutes/60
            return time.timezone/60/60 + offset
    
        if len(timestamp) > 22: # UTC offset is -HH:MM (happens on windows 2003 server) 
            timestr = timestamp[:-6]
            offset = calcOffset(timestamp[-6:])
        else: # UTC offset is -HH
            timestr = timestamp[:-3]
            offset = calcOffset(timestamp[-3:])
        return datetime.strptime(timestr, '%Y-%m-%dT%H:%M:%S') + timedelta(hours=-offset)            
    
    def getFileForElement(self,elm,toFile):
        self._exec(['get','-to', toFile, elm.getCCName()])
        
    def formatForLshistory(self,date):
        if isinstance(date,str):
            # TODO: Add check here that the str is in the correct format before returning
            return date
        return datetime.strftime(date, '%d-%b-%Y.%H:%M:%S')
    
    def rebase(self):
        pass
    def mkact(self, comment):
        pass
    def rmactivity(self):
        pass
    def commit(self):
        pass

    @classmethod
    def getCommentFmt(self):
        return '%Nc'
    def getRealComment(self, comment):
        return comment

class Element(object):
    def __init__(self,path,version):
        self.path = path
        self.version = version
        self.branch = self.getBranch()
    def getCCName(self):
        return buildPath([CC_DIR,self.path + '@@' + self.version])
    def getAbsolutePath(self):
        return buildPath([CC_DIR,self.path])
    def getBranch(self):
        if len(self.version.split("\\")) == 1:
            return self.version
        return "\\".join(self.version.split("\\")[:-1])
    def getRelativePath(self):
        return self.path

class FileCheckin(Element):
    def __init__(self, date, user, path, version, comment=""):
        Element.__init__(self, path, version)
        if isinstance(date,str):
            self.date = Clearcase.parseDate(date)
        else:
            self.date = date
        self.user = user
        self.comment = comment
        self.subject = comment.split("\n")[0]
        self.type = "FILE"

class DirectoryCheckin(FileCheckin):
    def __init__(self, date, user, path, version, comment=""):
        FileCheckin.__init__(self, date, user, path, version, comment)
        self.removed = []
        self.added = []
        self.type = "DIRECTORY"
    def getAddedRemoved(self):
        diff = Clearcase._exec(['diff', '-diff_format', '-pred', self.path])
        def getFile(line):
            return join(self.path, line[2:line.find(' --') - 1])
        for line in diff.split('\n'):
            if line.startswith('<'):
                self.removed.append(getFile(line))
            elif line.startswith('>'):
                self.added.append(getFile(line))

TYPES= {\
    'checkinversion': FileCheckin,\
    'checkindirectory version': DirectoryCheckin,\
}


class UCM:
    def __init__(self):
        self.activities = {}
    def rebase(self):
        out = cc_exec(['rebase', '-rec', '-f'])
        if not out.startswith('No rebase needed'):
            debug(out)
            debug(cc_exec(['rebase', '-complete']))
    def mkact(self, comment):
        self.rebase()
        self.activity = self._getActivities().get(comment)
        if self.activity:
            cc_exec(['setact', self.activity])
            return
        _comment = cc_exec(['mkact', '-f', '-headline', comment])
        _comment = _comment.split('\n')[0]
        self.activity = _comment[_comment.find('"')+1:_comment.rfind('"')]
        self._getActivities()[comment] = self.activity
    def rmactivity(self):
        cc_exec(['setact', '-none'])
        cc_exec(['rmactivity', '-f', self.activity])
    def commit(self):
        cc_exec(['setact', '-none'])
        debug(cc_exec(['deliver','-f']))
        debug(cc_exec(['deliver', '-com', '-f']))
    def getCommentFmt(self):
        return '%[activity]p'
    def getRealComment(self, activity):
        return cc_exec(['lsactivity', '-fmt', '%[headline]p', activity]) if activity else activity
    def _getActivities(self):
        if not self.activities:
            for line in cc_exec(['lsactivity', '-fmt', '%[headline]p|%n\n']).split('\n'):
                if line:
                    line = line.strip().split('|')
                    self.activities[line[0]] = line[1]
        return self.activities

cc = (UCM if cfg.get('type') == 'UCM' else Clearcase)();

#############################################################
# Common filters that can be used to filter clearcase history
#############################################################   
def chainFilters(filters):
    def f(elm):
        for filter in filters:
            if not filter(elm):
                return False
        return True
    return f


# Build a filter based on a date range fromDate -> toDate
# by default, toDate = the current datetime
def dateRangeFilter(toDate=None,fromDate=None):
    def f(ci): 
        rval = True
        if fromDate:
            rval = rval and ci.date > fromDate
        if rval and toDate:
            rval = rval and ci.date < toDate
        return rval;
    return f

def branchFilter(element):
    version = element.getBranch()
    for branch in cfg.getList('branches', 'main'):
        if branch == 'main':
            branch = '\\main'
        elif len(branch.split('\\')) == 1:
            branch = '\\' + '\\'.join(['main', branch])
        if version == branch:
            return True
    return False     

def onlyAncestorsFilter(elm):
    if branchFilter(elm):
        cur = cc.getCurrentVersion(elm)
        if cur and cur.branch != elm.branch:
            if datetime.fromtimestamp(os.path.getmtime(elm.getAbsolutePath())) > elm.date:
                return True
        elif cur and cur.branch == elm.branch:
            return True
    return False
    