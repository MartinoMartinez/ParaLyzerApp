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

from time import sleep

try:
    from libs import coreUtilities as coreUtils
except ImportError:
    import coreUtilities as coreUtils
    
    
class DataSaver:
    def __init__(self, fileName='stream0000.mat'):
        
        # store data underthis path and name
        self._fName              = fileName
        # set an event to halt the computation while file is being written
        self._runProcessingEvent = threading.Event()
        # immediately set it to allow processing
        self._runProcessingEvent.set()
        
    def SetFileName(self, fileName):
        assert isinstance(fileName, str), 'Expect string, not %r' % type(fileName)
        self._fName = fileName
        
    def SaveData(self):
        # clear event to halt processing
        # no data is fetched from the queue
        self._runProcessingEvent.clear()
        
        # store the file
        io.savemat(self._fName, self._data)
        
        # reset internal data structure
        self._ResetData()
        
        # set flag again to allow processing with fresh structure
        self._runProcessingEvent.set()
        
        
    

class DataProcessor(threading.Thread, DataSaver):
    
    __lockInAmpClock__ = 210e6
    
    def __init__(self, **flags):
        
        threading.Thread.__init__(self, target=self._DataProcessor)
        DataSaver.__init__(self, **flags)
        
        self._data                 = None
        self._dataSize             = 0
        self._startTime            = -1
        self._runTime              = 0
        self._uniqueElectrodePairs = []

        self._ResetData()
        
        # pipeline for new incoming data
        # gets processed in an ordered fashion in _DataProcessor
        self._newDataQueue = queue.Queue()
        
        # thread condition to sleep while no data is available
        self._newDataEvent = threading.Event()
        
        # enable data procesor to run
        self._activeProcessor = True
        self.start()
        
### --------------------------------------------------------------------------------------------------
                    
    def __del__(self):
        
        self.Stop()
        
        # wait for process watcher
        self.join()
        
### --------------------------------------------------------------------------------------------------
    
    def _ResetData(self):
        self._data     = defaultdict(OrderedDict)
        self._dataSize = 0
        
### --------------------------------------------------------------------------------------------------

    def _DataProcessor(self):
        
        # run as long as user puts new data
        while self._activeProcessor:
            
            # wait until file was written
            # in case there is now file being written at the moment, just pass
            self._runProcessingEvent.wait()
             
            # get next task from queue
            try:
                _data = self._newDataQueue.get(block=False)
            except queue.Empty:
                # in case queue is empty wait for more data        
                self._newDataEvent.clear()
                self._newDataEvent.wait(timeout=1e-4)
            else:
                
                # estimate size
                # NOTE: several parts are missing here, like r, psd and motility - add them later to make it faster
                self._dataSize += coreUtils.GetTotalSize(_data)
                
                for demod,data in _data.items():
                    
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
                    
                        # just copy if standard values
                        if key in ['timestamp', 'frequency', 'dio']:
                            self._data[demod][key] = sp.concatenate( [self._data[demod][key], data[key]] )
                        
                        # OR simple adding
                        elif key == 'ePairs':
                            self._data[demod][key].extend(ePairs)
                            # update unique electrode pairs
                            self._UpdateUniqueElectrodePairs(ePairs)
                            # and don't forget to update size
                            self._dataSize += coreUtils.GetTotalSize(ePairs)
                            
                        # OR slicing is necessary
                        else:
                            # slice x,y and others with given slice indices
                            for k,slices in sliceIdices.items():
                                # get new np array in case electrode pairs was never used before
                                if k not in self._data[demod][key].keys():
                                    self._data[demod][key][k] = sp.array([])
                                    
                                # data that is originally there but needs to be sliced
                                if key in data.keys():
                                    self._data[demod][key][k] = sp.concatenate( [self._data[demod][key][k], data[key][slices]] )
                                
                                # data that is not originally there but still has to be slices
                                elif key == 'r':
                                    
                                    r = sp.sqrt( data['x'][slices]**2 + data['y'][slices]**2 )
                                    self._data[demod]['r'][k] = sp.concatenate( [self._data[demod]['r'][k], r] )
                                    
                                    # and don't forget to update size
                                    self._dataSize += coreUtils.GetTotalSize(r)
                                
                                elif key == 'motility':
                                    None
                                elif key == 'counts':
                                    None
                                elif key == 'psd':
                                    None
                                elif key == 'spectrum':
                                    None
                
                # indicate that current task was done
                self._newDataQueue.task_done()
        
### --------------------------------------------------------------------------------------------------
                    
    def UpdateData(self, newData):
        
        if newData:
            # user data is pushed into parallel thread to ensure fast return
            # actual processing takes place in _DataProcessor
            self._newDataQueue.put(newData, False)
            
            self._newDataEvent.set()
        
### --------------------------------------------------------------------------------------------------
    
    def Start(self):
        pass
#        self._newDataEvent.set()
        
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
#            ('t'        , sp.array([])),
            ('timestamp', sp.array([])),
            ('frequency', sp.array([])),
            ('dio'      , sp.array([])),
            ('ePairs'   , [])
        ])
        
### --------------------------------------------------------------------------------------------------
                    
    def DemodNumber(self, s):
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
        return self._data
### --------------------------------------------------------------------------------------------------
                    
    def GetDataSize(self):
        return self._dataSize
    
### --------------------------------------------------------------------------------------------------
                    
    def GetElectrodePairList(self):
        return self._uniqueElectrodePairs
    


if __name__ == '__main__':
    
    from time import perf_counter
    
    fileIdx = 0
    dataProcessor = DataProcessor(fileName='./mat_files/stream%04d.mat'%fileIdx)
    
    t = []
    dataProcessor.Start()
    for i in range(100):
        
        newData = coreUtils.DataGen(1,10000,2)
        st = perf_counter()
        dataProcessor.UpdateData(newData)
        t.append(perf_counter()-st)
        
        if i%10 == 0:
            print('size: %3.5f MB' % (dataProcessor.GetDataSize()/1024**2))
            
        if (dataProcessor.GetDataSize()//1024**2) > 4:
            dataProcessor.SaveData()
            fileIdx += 1
            dataProcessor.SetFileName('./mat_files/stream%04d.mat'%fileIdx)
    
    dataProcessor.Stop()
    
    print('avg time expired: %3.5f ms' % (sp.mean(t)*1000))
    
    print('size: %2.3f MB' % (dataProcessor.GetDataSize()/1024**2))
    
    sp.io.savemat('./mat_files/test.mat', {'Simulator': dataProcessor._data})
    
    dataProcessor.__del__()