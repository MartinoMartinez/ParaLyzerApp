# -*- coding: utf-8 -*-
"""
Created on Tue May  9 17:23:26 2017

@author: Martin Leonhardt (martin.leonhardt87@gmail.com)
"""


__simulationMode__ = False


import threading
try:
    import zhinst.utils
except ImportError:
    __simulationMode__ = True


from scipy import io

from time import sleep, time, perf_counter

import matplotlib.pyplot as plt

# in case this guy is used somewhere else
# we need different loading of modules
try:
    from libs.CoreDevice import CoreDevice
except ImportError:
    from CoreDevice import CoreDevice

try:
    from libs.DataProcessor import DataProcessor
except ImportError:
    from DataProcessor import DataProcessor

try:
    from libs import coreUtilities as coreUtils
except ImportError:
    import coreUtilities as coreUtils

    
class Hf2Core(CoreDevice, DataProcessor):
    
    __deviceId__         = ['dev10', 'dev275']
    __deviceApiLevel__   = 1
        
    __recordingDevices__ = '/demods/*/sample'   # device ID is added later...
    
### -------------------------------------------------------------------------------------------------------------------------------
    
    def __init__(self, **flags):
        
        # store chosen device name here
        self.deviceName = None
        
        # to stop measurement
        # initially no measurement is running
        self._poll          = False
        self._pollThread    = None
        self._dataProcessor = None
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
        
        flags['detectFunc'] = self.DetectDeviceAndSetupPort
        
        CoreDevice.__init__(self, **flags)
        
        # in case no device was found use simulation mode
        if not self.comPortStatus:
            global __simulationMode__
            __simulationMode__ = True
            self.deviceName = 'Simulator'
            self.logger.warning('Simulation mode enabled!')
            
        flags['matlabKey'] = self.deviceName
        
        DataProcessor.__init__(self, **flags)
    
### -------------------------------------------------------------------------------------------------------------------------------
        
    def __del__(self):

        self.StopPoll()
        
        DataProcessor.__del__(self)
        
        CoreDevice.__del__(self)
        
    
### -------------------------------------------------------------------------------------------------------------------------------
        
    def DetectDeviceAndSetupPort(self):
        
        for device in self.__deviceId__:
            
            self.logger.info('Try to detect %s...' % device)
            
            try:
                (daq, device, props) = zhinst.utils.create_api_session( device, self.__deviceApiLevel__ )
            except RuntimeError:
                self.logger.info('Could not be found')
            except NameError:
                global __simulationMode__
                __simulationMode__ = True
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
    
    def StartPoll(self):
        
        if self.CreateNewStreamFolder():
            
            # start processor loop
            self.Start()
            
            # initialize new thread
            self._pollThread = threading.Thread(target=self._PollData)
            # once polling thread is started loop is running till StopPoll() was called
            self._poll = True
            # start parallel thread
            self._pollThread.start()
            
            self._recordString = 'Recording...'
            
            return True
        
        return False
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def StopPoll(self, **flags):
        
        if self._poll:
            # end loop in _PollData method
            self._poll = False
            # end poll thread
            self._pollThread.join()
#            self._debugThread.join()

            self.Stop()
            
            # reset file counter for next run
            self._strmFlCnt = 0
            
            if 'prc' in flags:
                if flags['prc']:
                    self._recordString = 'Paused...'
                else:
                    self._recordString = 'Stopped.'
            else:
                self._recordString = 'Stopped.'
            
#            plt.plot(self.timer['idx'], self.ti1mer['elt'])
        
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
            
            # subscribe to all demodulators that have been enabled by LabOne interface
            self.comPort.subscribe(self._recordingDevices)
            
            # clear old data from polling buffer
            self.comPort.sync()
            
        if self.comPortStatus or __simulationMode__:
            
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
                if __simulationMode__:
                    newData = coreUtils.DataGen(6, 10000, 30)
                else:
                    newData = self.comPort.poll(10e-3, 10, 0x04, True)
                    
                self.UpdateData(newData)
                
                # critical stuff is done, release lock
                self._pollLocker.release()
            
            
            # unsubscribe after finished record event
            if self.comPortStatus:
                self.comPort.unsubscribe('*')
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def GetRecordFlags(self):
        return self._recordFlags
    
### -------------------------------------------------------------------------------------------------------------------------------
    
    def GetCurrentStreamFolder(self):
        return self._streamFolder
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def GetRecordingString(self):
        return self._recordString
#            
            
            
###############################################################################
###############################################################################
###                      --- YOUR CODE HERE ---                             ###
###############################################################################
###############################################################################

if __name__ == '__main__':
    
    # create new HF2 object
    hf2 = Hf2Core()
#    # create new HF2 object and change standard storage path
#    hf2 = Hf2Core(baseStreamFolder='C:/TEMP/MY_MATLAB_FILES')
    
#    # create new HF2 object and change standard storage mode
#    hf2 = Hf2Core(storageMode='recTime')
    
    hf2.StartPoll()
    
    sleep(1)
    
    hf2.StopPoll()
    
    hf2.__del__()