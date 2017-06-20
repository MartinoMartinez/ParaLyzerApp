# -*- coding: utf-8 -*-
"""
Created on Sat Jun 17 00:42:53 2017

@author: Martin
"""

import threading
import queue
import numpy as np
from collections import OrderedDict, defaultdict

from time import sleep

try:
    from libs import coreUtilities as coreUtils
except ImportError:
    import coreUtilities as coreUtils
    

class DataProcessor(threading.Thread):
    
    __lockInAmpClock__ = 210e6
    
    def __init__(self):
        
        threading.Thread.__init__(self, target=self._DataProcessor)
        
        self._data                 = {}
        self._dataSize             = 0
        self._startTime            = -1
        self._runTime              = 0
        self._uniqueElectrodePairs = []
        
        # pipeline for new incoming data
        # gets processed in an ordered fashion in _DataProcessor
        self._newDataQueue = queue.Queue()
        
        # enable data procesor to run
        self._activeProcessor = True
        self.start()
        
### --------------------------------------------------------------------------------------------------
                    
    def __del__(self):
        
        # test if something is still in the pipe
        # join waits until last task_done was called
        self._newDataQueue.join()
        # so here we're safe to kill the process loop
        self._activeProcessor = False
        
        # wait for process watcher
        self.join()
        
### --------------------------------------------------------------------------------------------------
    
    def _DataProcessor(self):
        
        gotX, gotY = False, False
        
        # run as long as user puts new data
        while self._activeProcessor:
            
            # get next task from queue
            try:
                _data = self._newDataQueue.get(block=False)
            except queue.Empty:
                pass
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
                    
                    # update unique electrode pairs
                    self._UpdateUniqueElectrodePairs(ePairs)
                    
                    # get slice indices from electrode pairs to slice special values
                    sliceIdices = self.SliceIdices(ePairs)
                    
                    # go through all the keys in the class member
                    for key in self._data[demod].keys():
                    
                        # just copy if standard values
                        if key in ['timestamp', 'frequency', 'dio']:
                            self._data[demod][key] = np.concatenate( [self._data[demod][key], data[key]] )
                        
                        # OR simple adding
                        elif key == 'ePairs':
                            self._data[demod][key] += ePairs
                            # and don't forget to update size
                            self._dataSize += coreUtils.GetTotalSize(ePairs)
                            
                        # OR slicing is necessary
                        else:
                            # slice x,y and others with given slice indices
                            for k,slices in sliceIdices.items():
                                # get new np array in case electrode pairs was never used before
                                if k is not self._data[demod][key].keys():
                                    self._data[demod][key][k] = np.array([])
                                
                                # data that is originally there but needs to be sliced
                                if key in data.keys():
                                    self._data[demod][key][k] = np.concatenate( [self._data[demod][key][k], data[key][slices]] )
                                
                                # data that is not originally there but still has to be slices
                                elif key == 'r':
                                    
                                    r = np.sqrt( data['x'][slices]**2 + data['y'][slices]**2 )
                                    self._data[demod]['r'][k] = np.concatenate( [self._data[demod]['r'][k], r] )
                                    
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
                    ######
                    # UPDATE R, PSD and OTHER STUFF HERE
                    #############
                
                
                # indicate thta task was done
                self._newDataQueue.task_done()
        
### --------------------------------------------------------------------------------------------------
                    
    def UpdateData(self, newData):
        
        # user data is pushed into parallel threads to ensure fast return
        # actual processing takes place in _DataProcessor
        self._newDataQueue.put(newData, False)
        
### --------------------------------------------------------------------------------------------------
    
    def _UpdateUniqueElectrodePairs(self, ePairs):
        # flatten list
        lst = sum([self._uniqueElectrodePairs, ePairs],[])
        # write new uniques
        self._uniqueElectrodePairs = self.Uniques(lst)
        
### --------------------------------------------------------------------------------------------------
                    
    def _GetPsd(self):
        return {}
    
### --------------------------------------------------------------------------------------------------
                    
    def _GetCounts(self):
        return {}
        
### --------------------------------------------------------------------------------------------------
                    
    def Uniques(self, lst):
        return list(set(lst))
        
### --------------------------------------------------------------------------------------------------
                    
    def SliceIdices(self, lst):
        
        items = self.Uniques(lst)
        ind   = defaultdict(list)
        
        for i, v in enumerate(lst):
            if v in items: ind[v].append(i)
        
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
#            ('t'        , np.array([])),
            ('timestamp', np.array([])),
            ('frequency', np.array([])),
            ('dio'      , np.array([])),
            ('ePairs'   , [])
        ])
        
### --------------------------------------------------------------------------------------------------
                    
    def DemodNumber(self, s):
        return int(s.split('/')[-3])
    
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
    
def DataGen(maxDemod=None, maxNewData=None, maxElectrodePair=None):
    
    if maxDemod == None:
        maxDemod = 6
    if maxNewData == None:
        maxNewData = 1000
    if maxElectrodePair == None:
        maxElectrodePair = 31
    
    data = {}
    
    # 1-6 demodulators
    for demod in range(np.random.randint(1,maxDemod+1)):
        
        key = 'dev10/demods/%s/sample/' % demod
        
        data[key] = {}
        
        # min 10, max 1000 new entries
        arraySize = np.random.randint(1,maxNewData)
        
        data[key]['x']         = np.random.random (             arraySize )
        data[key]['y']         = np.random.random (             arraySize )
        data[key]['frequency'] = np.random.randint( 100, 50e6 , arraySize )
        data[key]['timestamp'] = np.random.randint( 0  , 2**31, arraySize )
        data[key]['dio']       = np.array([int("{0:032b}".format(int("{0:05b}".format(i)[::-1], 2)<<20), 2) for i in np.random.randint( 0, maxElectrodePair, arraySize )])
        
    return data

if __name__ == '__main__':
    
    from time import perf_counter
    
    dataProcessor = DataProcessor()
    
    t = []
    
    for i in range(100):
        
        newData = DataGen(6,1000,10)
        st = perf_counter()
        dataProcessor.UpdateData(newData)
        t.append(perf_counter()-st)
    
    print('avg time expired: %3.5f ms' % (np.mean(t)*1000))
    
    sleep(.1)
    print('size: %2.3f MB' % (dataProcessor.GetDataSize()/1024**2))
    
    dataProcessor.__del__()