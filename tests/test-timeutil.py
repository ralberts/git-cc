from __init__ import *
import sys, os, shutil
sys.path.append("..")
import common
import unittest
import timeutil

common.CC_DIR = "/tmp/cc_temp"


# This test is pretty dumb, in that it will only work in CST 
#      Sorry Charles!
#
class TestTimeUtil(TestCaseEx):
    def testParseClearcaseDate(self):
        # Test two-digit UTC offset
        testdate = timeutil.parseClearcaseDate("2008-12-04T13:59:59-05")
        self.assertEqual(testdate.strftime("%Y-%m-%dT%H:%M:%S"),"2008-12-04T12:59:59")
        
        # Test HH:MM UTC offset
        testdate = timeutil.parseClearcaseDate("2008-12-04T13:59:59-05:00")
        self.assertEqual(testdate.strftime("%Y-%m-%dT%H:%M:%S"),"2008-12-04T12:59:59")
        testdate = timeutil.parseClearcaseDate("2008-12-04T13:59:59-03:30")
        self.assertEqual(testdate.strftime("%Y-%m-%dT%H:%M:%S"),"2008-12-04T11:29:59")
        
        # Test -06:00 offset (CST)
        testdate = timeutil.parseClearcaseDate("2008-12-04T13:59:59-06:00")
        self.assertEqual(testdate.strftime("%Y-%m-%dT%H:%M:%S"),"2008-12-04T13:59:59")

if __name__ == "__main__":
    unittest.main()    
    
    