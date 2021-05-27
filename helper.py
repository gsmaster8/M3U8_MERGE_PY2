import time
import re
import datetime

def utc_convert(str1, pat = r'([\d]{4})([\d]{2})([\d]{2})([\d]{2})([\d]{2})([\d]{2})([\d]{3})'):
    regex = re.compile(pat)
    result = regex.match(str1)
    if result:
        year = int(result.group(1))
        month = int(result.group(2))
        day = int(result.group(3))
        hour = int(result.group(4))
        min = int(result.group(5))
        second = int(result.group(6))
        milisecond = int(result.group(7))

        date_ = datetime.datetime(year, month, day, hour, min, second)
        timestamp2 = time.mktime(date_.timetuple())
        #print(timestamp2)
        return  timestamp2 + milisecond * 0.001
        
    else:
        return None

if '__main__' == __name__:
    utc_unix = utc_convert('20190815123947473')
    print(utc_unix)

