import time
from datetime import datetime, timezone
import calendar

DEBUG = False

BLUE = '\033[94m'
RED = '\033[92m'
BOLD = '\033[1m'
END = '\033[0m'

def dbg(msg, end='\n'):
    if DEBUG:
        print(BLUE+BOLD+'[DBG] '+END+msg, end=end)

def err(msg):
    print(RED+BOLD+'[ERR] '+END+msg)
    assert False

TIME_FORMAT = '%Y-%m-%dT%H:%M:%S.%fZ'

def local_to_utc(local_posix_time):
    date = datetime.now(tz=timezone.utc)
    return local_posix_time + time.altzone

def tstr_to_posix(tstr):
    if tstr is None:
        date = datetime.now(tz=timezone.utc)
    else:
        date = datetime.strptime(tstr, TIME_FORMAT)
    return calendar.timegm(date.timetuple())

