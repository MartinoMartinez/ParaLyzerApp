# -*- coding: utf-8 -*-
"""
Created on Sat Jun 17 00:42:53 2017

@author: Martin
"""

import threading
import queue
from scipy import io
from collections import OrderedDict, defaultdict
import scipy as sp

from time import sleep, time, perf_counter

try:
    from libs import coreUtilities as coreUtils
except ImportError:
    import coreUtilities as coreUtils
    



    
    
class DataSaver:
    
    # default parameters for storing determination
    __maxStrmFlSize__    = 10     # 10 MB
    __fileSizeScaler__   = 'MB'
    __maxStrmTime__      = 5      # 5 min
    __timeLenScaler__    = 'min'
    
    # supported stream modes
    __storageModes__     = ['fileSize', 'recordTime', 'eventSync']
    
    def __init__(self, matlabKey='Simulator', baseFolder='./mat_files/', 
                 filePrefix='stream', storageMode='fileSize', 
                 streamFileSize=None, streamTime=None, 
                 fileSizeScaler=None, timeLenScaler=None, **flags):
        
        # name or key to store matlab data structure
        self._matlabKey = matlabKey
        
        # check for valid storage mode
        if storageMode in self.__storageModes__:
            self._storageMode = storageMode
        else:
            raise Exception('Unsupported storage mode: %s' % storageMode)
        
        self._maxStreamFileSize = 0
        self._maxStreamTime     = 0
        
        # check for ambiguous setup
        if streamFileSize and streamTime:
            raise Exception('Congruent storage mode setup! Please choose only one of the given stream setups.')
        
        self.SetStreamFileSize( streamFileSize if streamFileSize else self.__maxStrmFlSize__ )
        self.SetStreamTime    ( streamTime     if streamTime     else self.__maxStrmTime__   )
        
        self._fileSizeScaler = fileSizeScaler if fileSizeScaler else self.__fileSizeScaler__
        self._timeLenScaler  = timeLenScaler  if timeLenScaler  else self.__timeLenScaler__
        
        # store mat files under this path
        self._baseFolder    = ''
        self._streamFolder  = ''
        self._folderCounter = 0
        # store data under name
        self._filePrefix    = filePrefix
        # use a counter to store multiple files
        self._fileCounter   = 0
        
        self.SetBaseFolder(baseFolder)
        
### --------------------------------------------------------------------------------------------------
        
    def SetBaseFolder(self, baseFolder):
        assert isinstance(baseFolder, str), 'Expect string, not %r' % type(baseFolder)
        
        if self._CreateBaseFolder(baseFolder):
            self._baseFolder   = baseFolder
            self._streamFolder = baseFolder
        else:
            Exception('Cannot access \'%s\' for writing!')
        
### --------------------------------------------------------------------------------------------------
        
    def _CreateBaseFolder(self, baseFolder):
        if coreUtils.SafeMakeDir(baseFolder, self):
            if coreUtils.IsAccessible(baseFolder, 'write'):
                return True
        return False
        
### --------------------------------------------------------------------------------------------------
        
    def SetFilePrefix(self, filePrefix):
        assert isinstance(filePrefix, str), 'Expect string, not %r' % type(filePrefix)
        self._filePrefix = filePrefix
        
### --------------------------------------------------------------------------------------------------
        
    def SaveData(self):
        
        fName = self._streamFolder + self._filePrefix + '%05d.mat'%self._fileCounter
        
#        print(fName)
#        print(self._matlabKey)
#        print(self._data)
        
        # store the file
        io.savemat(fName, {self._matlabKey: self._data})
        
        # increment file counter
        self._fileCounter += 1
        
### --------------------------------------------------------------------------------------------------
        
    def CreateNewStreamFolder(self):
        
        success = False
        
        sF = self._baseFolder
        if coreUtils.SafeMakeDir(sF, self):
            sF += 'session_' + self.coreStartTime + '/'
            if coreUtils.SafeMakeDir(sF, self):
                sF += 'stream%04d/' % self._folderCounter
                if coreUtils.SafeMakeDir(sF, self):
                    # set new stream folder to class var
                    self._streamFolder = sF
                    # increment folder counter for multiple streams
                    self._folderCounter += 1
                    
                    success = True
                
        return success
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def SetStorageMode(self, storageMode):
        
        if storageMode in self.__storageModes__:
            self._storageMode = storageMode
        else:
            raise Exception('Unsupported storage mode: %s' % storageMode)
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def SetStreamFileSize(self, fileSize):
        
        assert isinstance(fileSize, int) or isinstance(fileSize, float), 'Expected int or float, not %r' % type(fileSize)
        assert fileSize > 0, 'File size needs to be larger than 0!'
        
        self._maxStreamFileSize = fileSize
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def SetStreamTime(self, streamTime):
        
        assert isinstance(streamTime, int) or isinstance(streamTime, float), 'Expected int or float, not %r' % type(streamTime)
        assert streamTime > 0, 'Streaming time needs to be larger than 0!'
        
        self._maxStreamTime = streamTime
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def ResetFileCounter(self):
        self._fileCounter = 0

### --------------------------------------------------------------------------------------------------
        
### --------------------------------------------------------------------------------------------------
        
### --------------------------------------------------------------------------------------------------

globalTimeList = []
    

class DataProcessor(DataSaver):
    
    __lockInAmpClock__ = 210e6
    
    def __init__(self, **flags):
        
        DataSaver.__init__(self, **flags)
        
        self._data                 = None
        self._dataSize             = 0
        self._startTime            = -1
        self._runTime              = 0
        self._uniqueElectrodePairs = []
        self._startTime            = 0
        self._tRef                 = -1   # not used at the moment but could be used to replace in data structure -> consider callback functionality

        self._ResetData()
        
        # pipeline for new incoming data
        # gets processed in an ordered fashion in _DataProcessor
        self._newDataQueue = queue.Queue()

        self._queueThread = None

        # thread condition to sleep while no data is available
        self._newDataEvent = threading.Event()
        
        # initially no data processor is running
        self._activeProcessor = False
        
### --------------------------------------------------------------------------------------------------
                    
    def __del__(self):
        
        # call stop to make sure all data chunks in the queue have been processed
        self.Stop()

### --------------------------------------------------------------------------------------------------
    
    def _SaveData(self):
        self.SaveData()
        self._ResetData()
        
### --------------------------------------------------------------------------------------------------
    
    def _ResetData(self):
        self._data      = defaultdict(OrderedDict)
        self._dataSize  = 0
        self._startTime = 0
        
### --------------------------------------------------------------------------------------------------

    def _Dequeuer(self):
        ''' Processor loop.
            Indefinetly calls DataProcessor to process incoming data stream.
            According to storage mode, files are being written.
        '''
        
        # run as long as user puts new data
        while self._activeProcessor:
             
            # get next task from queue
            try:
                newData = self._newDataQueue.get(block=False)
            except queue.Empty:
                # in case queue is empty wait for more data        
                self._newDataEvent.clear()
                self._newDataEvent.wait()#timeout=1e-4)
            else:
                st = perf_counter()

                self.DataProcessor(newData)
                
                # estimate size
                # NOTE: several parts are missing here, like r, psd and motility - add them later to make it faster
                self._dataSize = coreUtils.GetTotalSize(self._data)
                
                # indicate that current task was done
                self._newDataQueue.task_done()
                
                globalTimeList.append(perf_counter()-st)
                
                # check, according to strorage mode, if it's necessary to store a new file
                if self._storageMode == 'fileSize':
                    if self.GetDataSize(self._fileSizeScaler) > self._maxStreamFileSize:
                        self._SaveData()
                        
                elif self._storageMode == 'recTime':
                    if self.GetRunTime(self._timeLenScaler) > self._maxStreamTime:
                        self._SaveData()
                        
                elif self._storageMode == 'eventSync':
                    None
        
### --------------------------------------------------------------------------------------------------
                    
    def DataProcessor(self, newData):
        ''' Actual data processor function called by _Dequeuer.
            Intended to be overridden by the user in case a customized
            handling is desired.
        '''
        
        for demod,data in newData.items():
            
            # extract demod number from string
            demod = 'demod_%s' % self.DemodNumber(demod)
            
            # check if current demodulator is already available
            # if not add it to class variable
            if demod not in self._data.keys():
                self._data[demod] = self._DefaultDataContainer()
            
            # copy new data to local structure and change a bit the appearance
            # we need to slice some of the data and also add electrode pairs calculated from 'dio'
            # so first get new ePairs
            ePairs = self.DioToElectrodePair( data['dio'] )
            
            # get slice indices from electrode pairs to slice special values
            sliceIdices = self.SliceIdices(ePairs)
            
            # go through all the keys in the class member
            for key in self._data[demod].keys():
            
                # OR single value that need the first index
                if key == 'frequency':
                    if self._data[demod][key] == -1:
                        self._data[demod][key] = data[key][0]
                
                # OR single value that need the first index from another key
                elif key == 'tRef':
                    if self._data[demod][key] == -1:
                        self._data[demod][key] = data['timestamp'][0]
                
                # OR slicing is necessary
                else:
                    # slice x,y and others with given slice indices
                    # NOTE: uniques always returns a sorted list
                    for k,slices in sliceIdices.items():
                        
                        # get new np array in case electrode pairs was never used before
                        if k not in self._data[demod][key].keys():
                            self._data[demod][key][k] = sp.array([])
                            
                        # data that is originally there but needs to be sliced
                        if key in data.keys():
                            self._data[demod][key][k] = sp.concatenate( [self._data[demod][key][k], data[key][slices]] )
                        
                        # data that is not originally there but still has to be slices
                        # NOTE: x and y get sliced a second time here...can be improved
                        elif key == 'r':
                            
                            r = sp.sqrt( data['x'][slices]**2 + data['y'][slices]**2 )
                            self._data[demod]['r'][k] = sp.concatenate( [self._data[demod]['r'][k], r] )
                            
                            # and don't forget to update size
#                            self._dataSize += coreUtils.GetTotalSize(r)

                        # OR values that need a reference first
                        elif key == 't':
                            if self._data[demod]['tRef'] != -1:
                                t = (data['timestamp'][slices] - self._data[demod]['tRef']) / self.__lockInAmpClock__
                                self._data[demod][key][k] = sp.concatenate( [self._data[demod][key][k], t] )
                                     

                        elif key == 'motility':
                            None
                        elif key == 'counts':
                            None
                        elif key == 'psd':
                            None
                        elif key == 'spectrum':
                            None
        
### --------------------------------------------------------------------------------------------------
                    
    def UpdateData(self, newData):
        
        assert self._activeProcessor, 'Processor needs to be started!'
        
        if newData:
            # user data is pushed into parallel thread to ensure fast return
            # actual processing takes place in _DataProcessor
            self._newDataQueue.put(newData, False)
            
            self._newDataEvent.set()
        
### --------------------------------------------------------------------------------------------------
    
    def Start(self):
        
        # enable data procesor to run
        self._activeProcessor = True
        # get new thread instance
        self._queueThread = threading.Thread(target=self._Dequeuer)
        # start thread
        self._queueThread.start()
        
        if self._storageMode == 'recordTime':
            self._startTime = time()
        
### --------------------------------------------------------------------------------------------------
    
    def Stop(self):
        
        # test if something is still in the pipe
        # join waits until last task_done was called
        self._newDataQueue.join()
        # so here we're safe to kill the process loop
        self._activeProcessor = False
        # call a last time set although no data will be available
        # only to exit the while loop and finish the thread
        self._newDataEvent.set()
        self._newDataEvent.clear()

        # wait for process watcher
        if self._queueThread:
            self._queueThread.join()
        
        # here we are sure nothing is running
        # so we can save the rest of the data
        if self.GetDataSize() > 0:
            self._SaveData()

        self.ResetFileCounter()
        
### --------------------------------------------------------------------------------------------------
    
    def _UpdateUniqueElectrodePairs(self, ePairs):
        # flatten list
        self._uniqueElectrodePairs.extend(ePairs)
        # write new uniques
        self._uniqueElectrodePairs = self.Uniques(self._uniqueElectrodePairs)
        
### --------------------------------------------------------------------------------------------------
                    
    def _GetPsd(self):
        return {}
    
### --------------------------------------------------------------------------------------------------
                    
    def _GetCounts(self):
        return {}
        
### --------------------------------------------------------------------------------------------------
                    
    def Uniques(self, lst):
        ''' return a list of unique elements in lst
        '''
        return list(set(lst))
        
### --------------------------------------------------------------------------------------------------
                    
    def SliceIdices(self, lst):
        ''' returns a dictionary with all unique elements in lst as key
            with their corresponding indices in lst
        '''
        
        items = self.Uniques(lst)
        ind   = defaultdict(list)
        
        for i, v in enumerate(lst):
            if v in items: ind['ePair_%s'%v].append(i)
        
        return ind
    
### --------------------------------------------------------------------------------------------------
                    
    def _DefaultDataContainer(self):
        ''' Return ordered dict to make sure x,y is always updated first
            Makes the following calculation steps easier to handle
        '''
        return OrderedDict([
            ('x'        , {}),
            ('y'        , {}),
            ('r'        , {}),
            ('motility' , {}),
            ('counts'   , {}),
            ('psd'      , {}),
            ('spectrum' , {}),
            ('tRef'     , -1),
            ('t'        , {}),
#            ('timestamp', []),
            ('frequency', -1),
#            ('dio'      , sp.array([])),
#            ('ePairs'   , [])
        ])
        
### --------------------------------------------------------------------------------------------------
                    
    def DemodNumber(self, s):
        ''' Returns the corresponding demodulator number 
            extracted from the given string.
        '''
        return int(s.split('/')[-2])
    
### --------------------------------------------------------------------------------------------------
                    
    def DioToElectrodePair(self, dio):
        ''' HF2 DIO lines are stored in a 32 bit number
            cut relevant bits and switch order
            DIO24 - Pin8 ... DIO20 - Pin12
            so MSB in Arduino is LSB for HF2
            return decimal number from the cut 5 bits
        '''
        return [ int(format(int(i), '032b')[7:12][::-1], 2) for i in dio]
        
### --------------------------------------------------------------------------------------------------
                    
    def GetData(self):
        ''' Return the current data structure.
            NOTE: Can already be changed while it is returned
                  when processor is running!
        '''
        return self._data
    
### --------------------------------------------------------------------------------------------------
                    
    def GetDataSize(self, scale='MB'):
        ''' return the size in bytes, kB, MB or GB, depending on the scale
        '''
        
        if scale == 'B':
            return self._dataSize
        elif scale == 'kB':
            return self._dataSize / 1024
        elif scale == 'MB':
            return self._dataSize / 1024**2
        elif scale == 'GB':
            return self._dataSize / 1024**3
        else:
            Exception('Unknown scaler: %s' % scale)
            
### --------------------------------------------------------------------------------------------------
                    
    def GetRunTime(self, scale='min'):
        ''' return the run time since last start was invoked
        '''
        
        if scale == 'sec':
            return time()-self._startTime
        elif scale == 'min':
            return (time()-self._startTime)/60
        elif scale == 'hrs':
            return (time()-self._startTime)/3600
        elif scale == 'days':
            return (time()-self._startTime)/86400
        else:
            Exception('Unknown scaler: %s' % scale)
            
### --------------------------------------------------------------------------------------------------
                    
    def GetElectrodePairList(self):
        return self._uniqueElectrodePairs
    


if __name__ == '__main__':
    
    dataProcessor = DataProcessor()
    
    t = []
    dataProcessor.Start()
    for i in range(200):
        
        newData = coreUtils.DataGen(6,10000,30)
        st = perf_counter()
        dataProcessor.UpdateData(newData)
        t.append(perf_counter()-st)
        
        if i%10 == 0:
            print('size: %3.5f MB' % (dataProcessor.GetDataSize('MB')))
            
#        if (dataProcessor.GetDataSize()//1024**2) > 4:
#            dataProcessor.SaveData()
            
    dataProcessor.Stop()
    
    print('avg time expired: %3.5f ms' % (sp.mean(t)*1000))
    print('avg time for proc: %3.5f ms' % (sp.mean(globalTimeList)*1000))
    
#    print('size: %2.3f MB' % (dataProcessor.GetDataSize()/1024**2))
    
#    sp.io.savemat('./mat_files/test.mat', {'Simulator': dataProcessor._data})
    
    dataProcessor.__del__()