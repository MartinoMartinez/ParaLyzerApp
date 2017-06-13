# -*- coding: utf-8 -*-
"""
Created on Tue May  9 17:23:26 2017

@author: Martin Leonhardt (martin.leonhardt87@gmail.com)
"""

import threading
import zhinst.utils
#import numpy as np
import scipy as sp

from time import sleep, time, perf_counter

# in case this guy is used somewhere else
# we need different loading of modules
try:
    from libs.CoreDevice import CoreDevice
except ImportError:
    from CoreDevice import CoreDevice

try:
    from libs import coreUtilities as coreUtils
except ImportError:
    import coreUtilities as coreUtils


    
class Hf2Core(CoreDevice):
    
    __deviceId__         = ['dev10', 'dev275']
    __deviceApiLevel__   = 1
        
    __recordingDevices__ = '/demods/*/sample'   # device ID is added later...
    
    # default parameters for storing determination
    __maxStrmFlSize__    = 10     # 10 MB
    __maxStrmTime__      = 0.5    # 30 s
    
    # supported stream modes
    __storageModes__     = ['fileSize', 'recTime', 'tilterSync']
    
### -------------------------------------------------------------------------------------------------------------------------------
    
    def __init__(self, baseStreamFolder='./mat_files', storageMode='fileSize', **flags):
        
        # store chosen device name here
        self.deviceName = None
        
        # dictionary to store all demodulator results
        self._demods = {}
        
        # to stop measurement
        # initially no measurement is running
        self._poll       = False
        self._pollThread = None
        # create locker to safely run parallel threads
        self._pollLocker = threading.Lock()
        
        # not know so far, cause no device is connected
        self._recordingDevices = ''
        
        self._recordString = 'Stopped.'
        
        # flags if somethign during recording went wrong
        self._recordFlags = {
                    'dataloss'        : False,
                    'invalidtimestamp': False
                }
        
        # variables to count streams (folder + files)
        self._baseStreamFolder = baseStreamFolder
        self._streamFolder     = baseStreamFolder
        self._strmFlCnt        = 0
        self._strmFldrCnt      = 0
        
        # check if folder is available, if not create
        coreUtils.SafeMakeDir(self._baseStreamFolder, self)
        
        if storageMode in self.__storageModes__:
            self._storageMode = storageMode
        else:
            raise Exception('Unsupported storage mode: %s' % storageMode)
            
        # check for ambiguous setup
        if 'streamFileSize' in flags.keys() and 'streamTime' in flags.keys():
            raise Exception('Congruent storage mode setup! Please choose only one of the given stream setups.')
        else:
            self.SetStreamFileSize( flags.get( 'streamFileSize', self.__maxStrmFlSize__ ) )
            self.SetStreamTime    ( flags.get( 'streamTime'    , self.__maxStrmTime__   ) )
        
        flags['detectFunc'] = self.DetectDeviceAndSetupPort
        
        CoreDevice.__init__(self, **flags)
    
### -------------------------------------------------------------------------------------------------------------------------------
        
    def __del__(self):

        self.StopPoll()
        
        CoreDevice.__del__(self)
        
    
### -------------------------------------------------------------------------------------------------------------------------------
        
    def DetectDeviceAndSetupPort(self):
        
        for device in self.__deviceId__:
            
            self.logger.info('Try to detect %s...' % device)
            
            try:
                (daq, device, props) = zhinst.utils.create_api_session( device, self.__deviceApiLevel__ )
            except RuntimeError:
                self.logger.info('Could not be found')
            else:
                self.logger.info('Created API session for \'%s\' on \'%s:%s\' with api level \'%s\'' % (device, props['serveraddress'], props['serverport'], props['apilevel']))
                
                self.deviceName        = device
                self.comPort           = daq
                self.comPortStatus     = props['available']
                self.comPortInfo       = ['', '%s on %s:%s' % (device.upper(), props['serveraddress'], props['serverport'])]
                self._recordingDevices = '/' + device + self.__recordingDevices__
                
                # no need to search further
                break
                
        return self.comPortStatus
    
### -------------------------------------------------------------------------------------------------------------------------------
    
    def StartPoll(self, sF=None):
        
        success              = True
        useGivenStreamFolder = False
        
        # check if stream folder was given
        if sF:
            if coreUtils.IsAccessible(sF, 'write'):
                self._streamFolder = sF
                useGivenStreamFolder = True
            
            # if not, try to create new folders
        if not sF or not useGivenStreamFolder:
            sF = self._baseStreamFolder
            if coreUtils.SafeMakeDir(sF, self):
                sF += '/session_' + self.coreStartTime + '/'
                if coreUtils.SafeMakeDir(sF, self):
                    sF += 'stream%04d/' % self._strmFldrCnt
                    if coreUtils.SafeMakeDir(sF, self):
                        # set new stream folder to class var
                        self._streamFolder = sF
                        # increment folder counter for multiple streams
                        self._strmFldrCnt += 1
                    else:
                        success = False
            

        if success:
            
            # initialize new thread
            self._pollThread = threading.Thread(target=self._PollData)
            # once polling thread is started loop is running till StopPoll() was called
            self._poll = True
            # start parallel thread
            self._pollThread.start()
            
            self._recordString = 'Recording...'
            
            
#            self._debugThread = threading.Thread(target=self.DebugDioThread)
#            self._debugThread.start()
        
        return success
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def StopPoll(self, **flags):
        
        if self._poll:
            # end loop in _PollData method
            self._poll = False
            # end poll thread
            self._pollThread.join()
#            self._debugThread.join()
            
            # write last part of the data to disk
            self.WriteMatFileToDisk()
            # reset file counter for next run
            self._strmFlCnt = 0
            
            if 'prc' in flags:
                if flags['prc']:
                    self._recordString = 'Paused...'
                else:
                    self._recordString = 'Stopped.'
            else:
                self._recordString = 'Stopped.'
            
#            plt.plot(self.timer['idx'], self.timer['elt'])
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def IsPolling(self):
        return self._poll
        
### -------------------------------------------------------------------------------------------------------------------------------

    def _PollData(self):
        
        # for lag measurement
        idx   = 0
        start = perf_counter()
        self.timer = {'idx':[], 'elt':[]}
                
        # get stream time
        streamTime = time()

        # clear from last run
        self._recordFlags = {
                        'dataloss':False,
                        'invalidtimestamp':False
                    }
        
        # check status of device... start if OK
        if self.comPortStatus:
            
            self.comPort.subscribe(self._recordingDevices)
            
            # clear old data from polling buffer
            self.comPort.sync()
            
            while self._poll:
                
                # lock thread to safely process
                self._pollLocker.acquire()
                
                # for lag debugging
                self.timer['idx'].append(idx)
                idx += 1
                self.timer['elt'].append(perf_counter()-start)
                
                # for lag debugging
                start = perf_counter()

                # fetch data
                # block for 1 ms, timeout 10 ms, throw error if data is lost and return flat dictionary
                # NOTE: poll downloads all data since last poll, sync or subscription
                dataBuf = self.comPort.poll(1e-3, 10, 0x04, True)
                
                # get all demods in data stream
                for key in dataBuf.keys():
                    
                    # check if demodulator is already in dict, add if not (with standard structure)
                    if key not in self._demods.keys():
                        self._demods.update({key: self._GetStandardRecordStructure()})
                    
                    # fill structure with new data
                    for k in self._demods[key].keys():
                        if k in dataBuf[key].keys():
                            self._demods[key][k] = sp.concatenate( [self._demods[key][k], dataBuf[key][k]] )
                            
                        # save flags for later use in GUI
                        # look at dataloss and invalid time stamps
                        if k in ['dataloss', 'invalidtimestamp'] and dataBuf[key][k]:
                            self.logger.warning('%s was recognized! Data might be corrupted!' % k)
                            self._recordFlags[k] = True


                self._demods[key]['ePair'] = DioByteToChamber(self._demods[key]['dio'])
                    
########################################################
#   --- THIS IS HERE FOR SIMPLE PLOTTING REASONS ---   #
########################################################
                    
#                    # get data from current demodulator
#                    x = dataBuf[key]['x']
#                    y = dataBuf[key]['y']
#                    # calc abs value from real+imag
#                    r = np.sqrt(x**2 + y**2)
#                    
#                    # check if demodulator is already in dict, add if not (with standard structure)
#                    if key not in self.demods.keys():
#                        self.demods.update({key: self.GetStandardHf2Dict()})
#                    
#                        # store first timestamp as a reference, if not available
#                        if self.demods[key]['timeRef'] == -1:
#                            self.demods[key]['timeRef'] = dataBuf[key]['timestamp'][0]
#                    
#                    # calculate real time with reference and clock base and append to array
#                    self.demods[key]['time'] = np.concatenate([self.demods[key]['time'], (dataBuf[key]['timestamp'] - self.demods[key]['timeRef']) / 210e6])
#                    
#                    # append data points
#                    self.demods[key]['r'] = np.concatenate([self.demods[key]['r'], r])
                    
                
                # check, according to strorage mode, if it's necessary to store a new file
                if self._storageMode == 'fileSize':
                    if (coreUtils.GetTotalSize(self._demods) // 1024**2) > (self._maxStreamFileSize-1):
                        self.WriteMatFileToDisk()
                        
                elif self._storageMode == 'recTime':
                    if ( time() - streamTime ) / 60 > self._maxStreamTime:
                        self.WriteMatFileToDisk()
                        streamTime = time()
                        
                elif self._storageMode == 'tilterSync':
                    None
                
                # critical stuff is done, release lock
                self._pollLocker.release()
                    
            # unsubscribe after finished record event
            self.comPort.unsubscribe('*')
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def GetRecordFlags(self):
        return self._recordFlags
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def _GetStandardRecordStructure(self):
        return {
                    'x'        : sp.array([]),
                    'y'        : sp.array([]),
                    'timestamp': sp.array([]),
                    'frequency': sp.array([]),
#                    'phase':     np.array([]),
                    'dio'      : sp.array([]),
                    'ePair'    : sp.array([])           # to decode the DIO byte from HF2 into electrode pair
#                    'auxin0':    np.array([]),
#                    'auxin1':    np.array([])
                    
# just for the test with plotting
#                    'r': np.array([]),
#                    'time': np.array([]),
#                    'timeRef': -1
                }
    
### -------------------------------------------------------------------------------------------------------------------------------
    
    def GetCurrentStreamFolder(self):
        return self._streamFolder
    
### -------------------------------------------------------------------------------------------------------------------------------
    
    def WriteMatFileToDisk(self):
        
        # create this just for debugging...
        outFileBuf = {'demods': []}
            
        for key in self._demods.keys():
            buf = {}
            for k in self._demods[key]:
                buf[k] = self._demods[key][k]
            outFileBuf['demods'].append(buf)
            
        sp.io.savemat(self._streamFolder+'stream_%05d.mat'%self._strmFlCnt, {'%s'%self.deviceName: outFileBuf})
        
        # memory leak was found...try to fix it
        del self._demods
        
        # clear buffer for next recording
        self._demods = {}

        # increment
        self._strmFlCnt += 1
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def GetRecordingString(self):
        return self._recordString
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def SetBaseStreamFolder(self, baseStreamFolder):
        
        if coreUtils.IsAccessible(baseStreamFolder, 'write'):
            self._baseStreamFolder = baseStreamFolder
            self._streamFolder     = baseStreamFolder
        else:
            raise Exception('ERROR: Cannot access given path for writing Matlab files!')
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def SetStorageMode(self, storageMode):
        
        if storageMode in self.__storageModes__:
            self._storageMode = storageMode
        else:
            raise Exception('Unsupported storage mode: %s' % storageMode)
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def SetStreamFileSize(self, fileSize):
        
        assert isinstance(fileSize, int) or isinstance(fileSize, float), 'Expected int or float, not %r' % type(fileSize)
        assert fileSize > 0, 'File size needs to be larger than 0 MB!'
        
        self._maxStreamFileSize = fileSize
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def SetStreamTime(self, streamTime):
        
        assert isinstance(streamTime, int) or isinstance(streamTime, float), 'Expected int or float, not %r' % type(streamTime)
        assert streamTime > 0, 'Streaming time needs to be larger than 0 min!'
        
        self._maxStreamTime = streamTime
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def DebugDioThread(self):
        
        while self._poll:
            for key in self._demods.keys():
                print('DIO: %s' % self._demods[key]['ePair'])
            sleep(1)
            
            
def DioByteToChamber(dioByte):
    ''' HF2 DIO lines are stored in a 32 bit number
        cut relevant bits and switch order
        DIO24 - Pin8 ... DIO20 - Pin12
        so MSB in Arduino is LSB for HF2
        return decimal number from the cut 5 bits
    '''
    return [ int(format(int(i), '032b')[7:12][::-1], 2) for i in dioByte]
            
            
            
###############################################################################
###############################################################################
###                      --- YOUR CODE HERE ---                             ###
###############################################################################
###############################################################################

if __name__ == '__main__':
    
    # create new HF2 object
    hf2 = Hf2Core(storageMode='recTime', streamTime=.2)
#    # create new HF2 object and change standard storage path
#    hf2 = Hf2Core(baseStreamFolder='C:/TEMP/MY_MATLAB_FILES')
    
#    # create new HF2 object and change standard storage mode
#    hf2 = Hf2Core(storageMode='recTime')
    
    hf2.StartPoll()
    
    sleep(5)
    
    hf2.StopPoll()
    
    hf2.__del__()