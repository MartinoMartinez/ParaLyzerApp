# -*- coding: utf-8 -*-
"""
Created on Tue May  9 18:46:57 2017

@author: Martin Leonhardt (martin.leonhardt87@gmail.com)
"""

#import sys
import serial
import serial.tools.list_ports

from time import sleep

# just load in case it has not been loaded yet
#if 'coreUtilities' not in sys.modules:
#    try:
#        from libs import coreUtilities as coreUtils
#    except ImportError:
#        import coreUtilities as coreUtils
        
        

class ComDevice:
    
    def __init__(self, detCallback=None, onDetCallback=None, **flags):
        
        self._comPortList              = []
        self._comPortListIdx           = 0          # in case multiple devices were found use this
        self.comPortInfo               = None
        self.comPort                   = None
        self.comPortStatus             = False
        self._comPortName              = self.__usbName__ if hasattr(self, '__usbName__') else None
        self._detMsg                   = self.__detMsg__  if hasattr(self, '__detMsg__' ) else None
        self._comPortDetectCallback    = onDetCallback        # function to be called after initialization of serial port
        self._isReadingWriting         = False
        self._isAboutToOpenClose       = False
        
        # use own function to detect device
        if self._comPortName:
            self.DetectDeviceAndSetupPort(**flags)
        # function to be called for device detection and initialization
        elif detCallback:
            detCallback()
        
### -------------------------------------------------------------------------------------------------------------------------------

    def __del__(self):
        
        self.SafeCloseComPort()
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def DetectDeviceAndSetupPort(self, **flags):
        
        self.DetectDevice()
        self.SetupSerialPort(flags)
        
        if self.comPortStatus and self._comPortDetectCallback:
            self._comPortDetectCallback()
        
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
        if self._detMsg and hasattr(self, 'logger'):
            self.logger.info(self._detMsg)
        
        # NOTE: serial.tools.list_ports.grep(name) does not seem to work...
        for p in serial.tools.list_ports.comports():
            if self._comPortName in p.description:
                self._comPortList.append(p)
                
                if hasattr(self, 'logger'):
                    self.logger.info('Found device \'%s\' on \'%s\'.' % (p[1], p[0]))
                
        if len(self._comPortList) == 1:
            self.comPortInfo = self._comPortList[self._comPortListIdx]
        else:
            None
            # multiple ones found...user needs to choose the correct port...
        
        if not self.comPortInfo and hasattr(self, 'logger'):
            self.logger.info('Could not be found!')
            
### -------------------------------------------------------------------------------------------------------------------------------
    
    def SetupSerialPort(self, flags={}):
    
        if isinstance(self.comPortInfo, serial.tools.list_ports_common.ListPortInfo):
            
            if hasattr(self, 'logger'):
                self.logger.info('Initializing serial port.')
            
            # do it step by step to avoid reset of Arduino by DTR HIGH signal (pulls reset pin)
            # NOTE: some solutions use hardware to solve this problem...
            try:
                self.comPort      = serial.Serial()
                self.comPort.port = self.comPortInfo.device
            except serial.SerialException:
                if hasattr(self, 'logger'):
                    self.logger.error('Could not initialize serial port!')
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
                    if hasattr(self, 'logger'):
                        self.logger.error('Com port initialization: value out of range!')
                    
                # if no exception was raised until here, com port status should be fine
                else:
                    self.comPortStatus = True
            
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
            
                if hasattr(self, 'logger'):
                    self.logger.error('Could not open serial port!')
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
                
                if hasattr(self, 'logger'):
                    self.logger.error('Could not close serial port!')
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
                if hasattr(self, 'logger'):
                    self.logger.error( 'Could not write: \'%s\' to port \'%s\'!' % (outData, self.comPortInfo[0]) )                
                
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
                if hasattr(self, 'logger'):
                    self.logger.error('Could not read bytes from port \'%s\'!' % self.comPortInfo[0])
            
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
                