import traceback
from common import *



EMAIL_TEMPLATE="""
ERROR:

%ERROR%

StackTrace:

%STACKTRACE%
"""

       
class MergeException(Exception):
    def __init__(self, file, message="Merge Failed"):
        self.file = file
        self.message = message
        
    def __str__(self):
        return  self.message + '\n\n' + 'File -> ' + self.file 
    
        

    