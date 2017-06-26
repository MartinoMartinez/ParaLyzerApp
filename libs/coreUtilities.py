# -*- coding: utf-8 -*-
"""
Created on Tue May  9 18:44:04 2017

@author: Martin Leonhardt (martin.leonhardt87@gmail.com)
"""

# size estimation stuff
from sys import getsizeof
from itertools import chain
from collections import deque

import os
import logging as log
import scipy as sp
import binascii
import textwrap
import json
from datetime import datetime

#_logger = log.getLogger('coreUtilities')

### -------------------------------------------------------------------------------------------------------------------------------

def LoadJsonFile(fName, caller=None):
    
    jsonStruct = {}
    
    if IsAccessible(fName):
        try:
            # file is opened, read and automatically closed
            with open(fName, 'rt') as f:
                jsonStruct = json.load(f)
        except PermissionError:
            SafeLogger('error', 'Could not access file: \'%s\'! Please check permissions...' % fName, caller)
        except FileNotFoundError:
            SafeLogger('error', 'Could not find file: \'%s\'!' % fName, caller)
        except IOError:
            SafeLogger('error', 'Could not read file: \'%s\'!' % fName, caller)
        except ValueError:
            SafeLogger('error', 'Could not encode JSON structure from file: \'%s\'!' % fName, caller)
    
    return jsonStruct

### -------------------------------------------------------------------------------------------------------------------------------

def DumpJsonFile(jsonStruct, fName, caller=None):
    
    try:
        # file is opened, read and automatically closed
        with open(fName, 'wt') as f:
            json.dump(jsonStruct, f)
    except PermissionError:
        SafeLogger('error', 'Could not access file: \'%s\'! Please check permissions...' % fName, caller)
        raise
    except FileNotFoundError:
        SafeLogger('error', 'Could not find file: \'%s\'!' % fName, caller)
        raise
    else:
        return True
    
### -------------------------------------------------------------------------------------------------------------------------------
    
def IsIdentical(f1, f2):
    return os.path.samefile(f1, f2)
    
### -------------------------------------------------------------------------------------------------------------------------------
    
def IsAccessible(f, flag='read'):
    
    result = False
    
    if flag == 'read':
        result = os.access(f, os.R_OK)
    elif flag == 'write':
        result = os.access(f, os.W_OK)
    
    return result
        
### -------------------------------------------------------------------------------------------------------------------------------
    
def GetFolderFromFilePath(p):
    return os.path.dirname(p)
        
### -------------------------------------------------------------------------------------------------------------------------------
    
def GetRelativePath(absPath, caller=None):
    
    try:
        if os.path.isfile(absPath):
            relPath = './' + os.path.relpath(absPath).replace('\\', '/')
        else:
            relPath = './' + os.path.split(absPath)[-1] + '/'
    except ValueError:
        SafeLogger('error', 'Invalid path \'%s\'' % absPath, caller)
        
    return relPath
    
### -------------------------------------------------------------------------------------------------------------------------------
    
def SafeMakeDir(folder, caller=None):
    
    success = True
    
    # in case user passed file instead of folder...
    if os.path.isfile(folder):
        folder = os.path.dirname(folder)
    
    if not os.path.exists(folder):
        try:
            os.makedirs(folder)
        except OSError:
            SafeLogger('error', 'Could not create folder \'%s\'!' % folder, caller)
            success = False
        else:
            SafeLogger('info', 'Created folder \'%s\'' % folder, caller)
            
    return success
    
### -------------------------------------------------------------------------------------------------------------------------------
    
def ToBool(val):
    if val:
        return True
    else:
        return False
                
### -------------------------------------------------------------------------------------------------------------------------------
    
def GetDateTimeAsString():
    return datetime.now().strftime('%Y%m%d_%H%M%S')
    
### -------------------------------------------------------------------------------------------------------------------------------

def GetMinSecFromString(tString):
    
    secs = 0
    mins = 0
    
    # in case a number was passed don't freak out
    if isinstance(tString, int):
        tString = str(tString)
        
    assert isinstance(tString, str), 'Expect string or integer, not %r' % type(tString)
    
    # just seconds
    if tString.find(':') == -1:
        try:
            secs = int(tString)
        except ValueError:
            pass
        else:
            if secs > 59:
                secs = secs-60
                mins = 1
                
    # minutes and seconds
    else:
        tString = tString.split(':')
        
        try:
            mins = int(tString[0])
            secs = int(tString[1])
        except ValueError:
            pass
    
    return mins, secs
    
### -------------------------------------------------------------------------------------------------------------------------------

def GetStringFromMinSec(secs, mins=-1):
    
    tString = ''
    
    if not isinstance(secs, int) or not isinstance(mins, int):
        raise Exception('Expected int for secs and mins!')
    
    if mins == -1:
        
        # all zero
        if secs == 0:
            tString = '00:00'
            
        # only seconds
        elif secs >= 1 and secs <= 59:
            tString = '0:%s' % secs
            
        # seconds and minutes in secs
        elif secs >= 60 and secs <= 9959:
            tString = '%s:%s' % (str(secs)[:-2], str(secs)[-2:])
            
    else:
        tString = '%s:%s' % (mins, secs)
    
    return tString
    
### -------------------------------------------------------------------------------------------------------------------------------
    
def SafeLogger(level, msg, caller=None):
    
    if hasattr(caller, 'logger'):
        if level == 'debug':
            caller.logger.debug(msg)
        elif level == 'info':
            caller.logger.info(msg)
        elif level == 'warning':
            caller.logger.warning(msg)
        elif level == 'error':
            caller.logger.error(msg)
    else:
        print( '%s: %s' % (level.upper(), msg) )

### -------------------------------------------------------------------------------------------------------------------------------
    
def GetTextFromByteStream(bStream, group=2):
    if isinstance(bStream, str):
        return textwrap.wrap(binascii.b2a_hex(bStream.encode('latin-1')).decode('latin-1'), group)
    else:
        return textwrap.wrap(binascii.b2a_hex(bStream).decode('latin-1'), group)
        
### -------------------------------------------------------------------------------------------------------------------------------

def DataGen(maxDemod=None, arraySize=None, maxElectrodePair=None):
    
    if maxDemod == None:
        maxDemod = 6
    if arraySize == None:
        arraySize = 1000
    if maxElectrodePair == None:
        maxElectrodePair = 31
    
    data = {}
    
    # 1-6 demodulators
    for demod in range(sp.random.randint(1,maxDemod+1)):
        
        key = '/dev10/demods/%s/sample' % demod
        
        data[key] = {}
        
        data[key]['x']         = sp.random.random (             arraySize )
        data[key]['y']         = sp.random.random (             arraySize )
        data[key]['frequency'] = sp.random.randint( 100, 50e6 , arraySize )
        data[key]['timestamp'] = sp.random.randint( 0  , 2**31, arraySize )
        data[key]['dio']       = sp.array([int("{0:032b}".format(int("{0:05b}".format(i)[::-1], 2)<<20), 2) for i in sp.random.randint( 0, maxElectrodePair, arraySize )])
        
    return data

### -------------------------------------------------------------------------------------------------------------------------------

def GetTotalSize(o, handlers={}, verbose=False):
    """ Returns the approximate memory footprint an object and all of its contents.

    Automatically finds the contents of the following builtin containers and
    their subclasses:  tuple, list, deque, dict, set and frozenset.
    To search other containers, add handlers to iterate over their contents:

        handlers = {SomeContainerClass: iter,
                    OtherContainerClass: OtherContainerClass.get_elements}

    """
    dict_handler = lambda d: chain.from_iterable(d.items())
    all_handlers = {tuple: iter,
                    list: iter,
                    deque: iter,
                    dict: dict_handler,
                    set: iter,
                    frozenset: iter,
                }
    all_handlers.update(handlers)     # user handlers take precedence
    seen = set()                      # track which object id's have already been seen
    default_size = getsizeof(0)       # estimate sizeof object without __sizeof__

    def sizeof(o):
        if id(o) in seen:       # do not double count the same object
            return 0
        seen.add(id(o))
        s = getsizeof(o, default_size)

        for typ, handler in all_handlers.items():
            if isinstance(o, typ):
                s += sum(map(sizeof, handler(o)))
                break
        return s

    return sizeof(o)