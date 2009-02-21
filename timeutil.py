from datetime import datetime, timedelta
import time

# Returns a python time_stuct (i.e. date) given a valid string
# that is formated as a clearcase date (%Y-%m-%dT%H:%M:%S)
#
# Also, since clearcase reports the timestamp including the UTC offset
# we convert the date to the current timezone to make it valid for 
# us in comparisons
def parseClearcaseDate(timestamp):
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