# -*- coding: utf-8 -*-
"""
Created on Tue May  9 18:46:57 2017

@author: Martin Leonhardt (martin.leonhardt87@gmail.com)
"""

#import sys
import serial
import serial.tools.list_ports

import threading
import types

from time import sleep, time

try:
    from libs import coreUtilities as coreUtils
except ImportError:
    import coreUtilities as coreUtils
        
        

class ComDevice:
    
    def __init__(self, detectFunc=None, initAfterDetectFunc=None, listenFunc=None, **flags):
        
        self._comPortList         = []
        self._comPortListIdx      = 0          # in case multiple devices were found use this
        self.comPortInfo          = None
        self.comPort              = None
        self.comPortStatus        = False
        self._comPortName         = self.__usbName__ if hasattr(self, '__usbName__') else None
        self._detMsg              = self.__detMsg__  if hasattr(self, '__detMsg__' ) else None
        self._initAfterDetectFunc = initAfterDetectFunc        # function to be called after initialization of serial port
        
        self._listenFunc          = self._ListenFunction
        self._listenThread        = None
        self._listenAlways        = flags.get('listenAlways', False)
        self._listening           = False
        self._listenStart         = None
        self._listenFor           = None
        
        self._inMessages          = []
        self._keepMessages        = flags.get('keepMessages', True)
        self._messageDelimiter    = flags.get('delimiter', '\n')
        
        self._isReadingWriting    = False
        self._isAboutToOpenClose  = False
        
        self.SetListenFunction(listenFunc)
        
        # use own function to detect device
        if self._comPortName:
            self.DetectDeviceAndSetupPort(**flags)
        # function to be called for device detection and initialization
        elif detectFunc:
            detectFunc()
           
        # directly start listening thread after proper init
#        if self._listenAlways and self.comPortStatus:
#            self.StartListening()
        
### -------------------------------------------------------------------------------------------------------------------------------

    def __del__(self):
        
        # in case we are still listening
        self.StopListening()
        
        self.SafeCloseComPort()
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def DetectDeviceAndSetupPort(self, **flags):
        
        self.DetectDevice()
        self.SetupSerialPort(flags)
        
        if self.comPortStatus and self._initAfterDetectFunc:
            self._initAfterDetectFunc()
        
        return self.comPortStatus
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def DetectDevice(self):
        # try to detect com device
        
        # reset com port variables
        self._comPortList    = []
        self._comPortListIdx = 0
        self.comPort         = None
        self.comPortInfo     = None
        self.comPortStatus   = False
        
        # put message to the logger
        if self._detMsg:
            coreUtils.SafeLogger('info', self._detMsg, self)
        
        # NOTE: serial.tools.list_ports.grep(name) does not seem to work...
        for p in serial.tools.list_ports.comports():
            if self._comPortName in p.description:
                self._comPortList.append(p)
                
                coreUtils.SafeLogger('info', 'Found device \'%s\' on \'%s\'.' % (p[1], p[0]), self)
                
        if len(self._comPortList) == 1:
            self.comPortInfo = self._comPortList[self._comPortListIdx]
        else:
            None
            # multiple ones found...user needs to choose the correct port...
        
        if not self.comPortInfo:
            coreUtils.SafeLogger('info', 'Could not be found!', self)
            
### -------------------------------------------------------------------------------------------------------------------------------
    
    def SetupSerialPort(self, flags={}):
    
        if isinstance(self.comPortInfo, serial.tools.list_ports_common.ListPortInfo):
            
            coreUtils.SafeLogger('info', 'Initializing serial port.', self)
            
            # do it step by step to avoid reset of Arduino by DTR HIGH signal (pulls reset pin)
            # NOTE: some solutions use hardware to solve this problem...
            try:
                self.comPort      = serial.Serial()
                self.comPort.port = self.comPortInfo.device
            except serial.SerialException:
                    coreUtils.SafeLogger('error', 'Could not initialize serial port!', self)
            else:
                try:
                    self.comPort.baudrate = flags.get( 'baudrate', 9600                )
                    self.comPort.bytesize = flags.get( 'bytesize', serial.EIGHTBITS    )
                    self.comPort.parity   = flags.get( 'parity'  , serial.PARITY_NONE  )
                    self.comPort.stopbits = flags.get( 'stopbits', serial.STOPBITS_ONE )
                    self.comPort.timeout  = flags.get( 'timeout' , 0                   )
                    self.comPort.xonxoff  = flags.get( 'xonxoff' , False               )
                    self.comPort.rtscts   = flags.get( 'rtscts'  , False               )
                    self.comPort.dsrdtr   = flags.get( 'dsrdtr'  , False               )
                    self.comPort.dtr      = flags.get( 'dtr'     , False               )
                except ValueError:
                    coreUtils.SafeLogger('error', 'Com port initialization: value out of range!', self)
                    
                # if no exception was raised until here, com port status should be fine
                else:
                    self.comPortStatus = True
            
### -------------------------------------------------------------------------------------------------------------------------------
    
    def _ListenFunction(self):
        ''' listen to incoming messages and process them according to user flag 'keepMessages'
        '''
        
        if self.SafeOpenComPort():
            
            while self._listening:
                
                inMsg = self.SafeReadFromComPort('waiting', decode=True, leaveOpen=True)
                
#                print('\''+inMsg+'\'')
                
                if len(inMsg) > 0:
                    inMsg = inMsg.split(self._messageDelimiter)
                    
                    
                    # if user wants to handle messages
                    # append new messages to class member
                    # user can access later via GetMessages()
                    if self._keepMessages:
                        self._inMessages += inMsg
                    else:
                        while len(inMsg) > 0:
                            msg = inMsg.pop(0)
                            if msg:
                                coreUtils.SafeLogger('info', msg.strip(chr(241)), self)
                                
                # automatically stop loop
                if self._listenFor:
                    if (time() - self._listenStart) > self._listenFor:
                        self._listening = False
                        
                sleep(1e-4)
                
            self.SafeCloseComPort()
            
### -------------------------------------------------------------------------------------------------------------------------------
    
    def StartListening(self, listenFunc=None):
        
        self.SetListenFunction(listenFunc)
        
        # try to join from last run
        if self._listenThread:
            self._listenThread.join()
        
        self._listenThread = threading.Thread(target=self._listenFunc)
        
        # enable while loop in listen func
        self._listening = True
        
        self._listenThread.start()
            
### -------------------------------------------------------------------------------------------------------------------------------
    
    def StopListening(self):
        
        # stop while loop in listen func
        self._listening = False
        
        if self._listenThread:
            self._listenThread.join()
            
### -------------------------------------------------------------------------------------------------------------------------------
    
    def ListenFor(self, secs):
        
        assert isinstance(secs, (int, float)), 'Expected int or float, not %r' % type(secs)
        
        self._listenFor = secs
        
        # stop from last run
        self.StopListening()
        
        self._listenThread = threading.Thread(target=self._listenFunc)
        
        # enable while loop in listen func
        self._listening = True
        
        self._listenThread.start()
        
        self._listenStart = time()
            
### -------------------------------------------------------------------------------------------------------------------------------
    
    def SetListenFunction(self, listenFunc):
        
        if listenFunc:
            
            assert isinstance(listenFunc, types.FunctionType), 'Expect callable, not %r' % type(listenFunc)
            
            self._listenFunc = listenFunc
            
### -------------------------------------------------------------------------------------------------------------------------------
    
    def SafeOpenComPort(self):
        
        success = False
        
        if self.comPortStatus:
            # wait until reading/writing was finished
            # or the port is opened/closed by somebody else
            while self._isReadingWriting or self._isAboutToOpenClose:
                sleep(50e-6)
                
            # try to open now, if not already...
            self._isAboutToOpenClose = True
            
            try:
                if not self.comPort.isOpen():
                    self.comPort.open()
            except serial.SerialException:
                
                # to avoid any contact afterwards
                self.comPortStatus = False
            
                coreUtils.SafeLogger('error', 'Could not open serial port!', self)
            else:
                # opening finished
                self._isAboutToOpenClose = False
                success = True
            
        return success
            
### -------------------------------------------------------------------------------------------------------------------------------
    
    def SafeCloseComPort(self):
        
        success = False
        
        if self.comPortStatus and isinstance(self.comPort, serial.serialwin32.Serial):
            # wait until reading/writing was finished
            # or the port is opened/closed by somebody else
            while self._isReadingWriting or self._isAboutToOpenClose:
                sleep(50e-6)
                
            # try to close now
            self._isAboutToOpenClose = True
            
            try:
                if self.comPort.isOpen():
                    self.comPort.close()
            except serial.SerialException:
                
                # to avoid any contact afterwards
                self.comPortStatus = False
                
                coreUtils.SafeLogger('error', 'Could not close serial port!', self)
            else:
                # closing finished
                self._isAboutToOpenClose = False
                success = True
                
        return success
            
### -------------------------------------------------------------------------------------------------------------------------------
    
    def SafeWriteToComPort(self, outData, **flags):
        
        success   = True
        leaveOpen = flags.get('leaveOpen', False)
        
        if self.SafeOpenComPort():
            
            # just lock for anybody else
            self._isReadingWriting = True
            
            try:
                if not self._isAboutToOpenClose:
                    self.comPort.write(outData)
            except (serial.SerialException, serial.SerialTimeoutException):
                self.comPortStatus = False
                success = False
                
                coreUtils.SafeLogger('error', 'Could not write: \'%s\' to port \'%s\'!' % (outData, self.comPortInfo[0]), self)
                
            finally:
                # release lock
                self._isReadingWriting = False
                
                if not leaveOpen:
                    success = self.SafeCloseComPort()
                
        return success
            
### -------------------------------------------------------------------------------------------------------------------------------
    
    def SafeReadFromComPort(self, mode='', waitFor=0, bePatient=0, **flags):
        
        inData    = bytes()
        leaveOpen = flags.get( 'leaveOpen', False )
        decode    = flags.get( 'decode'   , False )
        
        if self.SafeOpenComPort():
            
            # just lock for anybody else
            self._isReadingWriting = True
            
            try:
                if mode == '':
                    
                    # check if comport is not going to be killed
                    if not self._isAboutToOpenClose:
                        inData = self.comPort.read()
                        
                elif mode == 'line':
                    # check if comport is not going to be killed
                    if not self._isAboutToOpenClose:
                        inData = self.comPort.readline()
                        
                elif mode == 'waiting':
                    
                    if waitFor > 0 and bePatient > 0:
                        
                        waitingFor = 0
                        
                        while self.comPort.in_waiting == 0 and waitingFor < waitFor*1e3:
                            waitingFor += 1
                            sleep(1e-3)
                            
                        # collecting incoming bytes and wait max 'bePatient' ms for the next one
                        waitingFor = 0
                            
                        while self.comPort.in_waiting != 0 or waitingFor < bePatient:
                            # check if comport is not going to be killed
                            if not self._isAboutToOpenClose:
                                inData += self.comPort.read(self.comPort.in_waiting)
                            
                            # in case there's something more just wait a bit...
                            if self.comPort.in_waiting == 0:
                                waitingFor += 1
                                sleep(1e-3)
                            
                    else:
                        while self.comPort.in_waiting != 0:
                            inData += self.comPort.read(self.comPort.in_waiting)
                            
            except (serial.SerialException, serial.SerialTimeoutException):
                self.comPortStatus = False
                
                coreUtils.SafeLogger('error', 'Could not read bytes from port \'%s\'!' % self.comPortInfo[0], self)
            
            finally:
                # release lock
                self._isReadingWriting = False
                
                if not leaveOpen:
                    self.SafeCloseComPort()
            
            if decode:
                inData = inData.decode('latin-1')
                
        return inData
            
### -------------------------------------------------------------------------------------------------------------------------------
    
    def GetPortStatus(self):
        return self.comPortStatus
            
### -------------------------------------------------------------------------------------------------------------------------------
    
    def GetPortInfo(self):
        return self.comPortInfo[1]
            
### -------------------------------------------------------------------------------------------------------------------------------
    
    def GetMessages(self):
        return self._inMessages
                