# -*- coding: utf-8 -*-
"""
Created on Wed Apr 26 09:49:58 2017

@author: Martin Leonhardt (martin.leonhardt87@gmail.com)
"""

import threading

from time import sleep

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






class ChipTilterCore(CoreDevice):

    # HEX addresses for certain commands
    # for check sum calculation address needs to be stored as two individual bytes
    __addresses__ = {
            'posAngle'   : ['0xFF', '0x00'],
            'negAngle'   : ['0xFF', '0x01'],
            'posMotion'  : ['0xFF', '0x02'],
            'negMotion'  : ['0xFF', '0x03'],
            'posPauseMin': ['0xFF', '0x04'],
            'negPauseMin': ['0xFF', '0x05'],
            'posPauseSec': ['0xFF', '0x06'],
            'negPauseSec': ['0xFF', '0x07'],
            'horPauseMin': ['0xFF', '0x08'],
            'horPauseSec': ['0xFF', '0x09'],
            'totTimeHrs' : ['0xFF', '0x0A'],
            'totTimeMin' : ['0xFF', '0x0B'],
            'status'     : ['0xFF', '0x0C']
        }
    
    # status bits
    # NOTE: single bits should not touch other values (overwrite)
    #       use OR to set
    #       use ~ to unset
    __statusBits__ = {
            'stopTilter'  : 0x00,
            'startTilter' : 0x01,
            'plusMinusOff': 0x00,
            'plusMinusOn' : 0x04,
            'resetErrors' : 0x08,
            'soundOff'    : 0x10,
            'tryReconnect': 0x80,
            'noControl'   : 0x00
        }
        
    # parameters received from the tilter
    __parameters__ = ['ID', 'A+', 'A-', 'M+', 'M-', 'm', 'P+', 'P-', 'p', 'H', 'T', 't', 'S']

    # supported events for callback functions
    __supportedEvents__ = ['onPosDown', 'onPosUp', 'onNegDown', 'onNegUp', 'onPosWait', 'onNegWait']
        
    # titler can be auto detected through this string
    __usbName__ = 'USB Serial Port'
    
    # message for detection
    __detMsg__ = 'Try to detect inSphero chip tilter...'
    
    # define number for force writing
    __numForces__ = 3
    
### -------------------------------------------------------------------------------------------------------------------------------
    
    def __init__(self, **flags):
        
        # to stop while loop for reading tilter stream
        self._isReading       = False
        self._inMessageThread = None
        self._isTilting       = False
        self._eventThreads    = {}          # contains a list of event threads that are started in parallel
        
        # structure with default values
        self._setup = self._GetDefaultSetup()
        
        self._resetStream = self._GetResetStream()
        
        # in case multiple setups have to be written
        self._setups = []
        
        # list for messages received from the tilter
        self._inMessageQueue = []
        
        # for counting the performed cycles and detecting the position
        self._tilterState = self._GetDefaultTilterState()
        
        # define tilting events
        # internally handled as list to enable multiple function calls for one event (see SetEventHandler)
        self._tilterEvents = self._GetDefaultEventDescriptors()
        
        self._currentParameterSet = self._GetDefaultParameterSet()
        
        
        flags['initAfterDetectFunc'] = self.StartInMessageThread
        
        CoreDevice.__init__(self, **flags)
        
### -------------------------------------------------------------------------------------------------------------------------------

    def __del__(self):
        
        self.StopInMessageThread()
        
        CoreDevice.__del__(self)
        
        
        
        
        
### -------------------------------------------------------------------------------------------------------------------------------
    #######################################################################
    ###               --- TILTER MEMORY AND COMMANDS ---                ###
    #######################################################################
### -------------------------------------------------------------------------------------------------------------------------------
    
    def GenerateByteStream(self, address, value):
    
        command = []
        
        # calculate sum over first three bytes: 2 address bytes + load
        checkSum = int(address[0], 16) + int(address[1], 16) + value
        # take least 8 bits and hexlify
        checkSum = format(checkSum & 0xFF, '#04x')
        # generate command by concatenating bytes, check sum and '#'
        command.append( address[0]            )
        command.append( address[1]            )
        command.append( format(value, '#04x') )
        command.append( checkSum              )
        command.append( hex(ord('#'))         )
        # remove all the nasty '0x' from hex numbers to send clean command
        command = ''.join(command).replace('0x','')
        
        # convert to bytes for sending
        return int(command, 16).to_bytes(5, 'big');
    
### -------------------------------------------------------------------------------------------------------------------------------
    
    def ConvertSetupToStream(self, key, val):
        
        if val != -1:
            self._setup['byteStream'].append( self.GenerateByteStream(key, val) )
        
### -------------------------------------------------------------------------------------------------------------------------------

    def WriteValueToAddress(self, address, value):
        
        if self.SafeOpenComPort():
            self.WriteStream(self.GenerateByteStream(address, value))
            
            self.SafeCloseComPort()
        
### -------------------------------------------------------------------------------------------------------------------------------

    def WriteSetup(self, byteStream=None, mode='normal'):
        
        success = True
        
        if not byteStream:
            byteStream = self._setup['byteStream']
        
        if self.SafeOpenComPort():
            
            for bStream in byteStream:
                if mode == 'normal':
                    success = self.WriteStream(bStream)
                    
                elif mode == 'force':
                    success = self.ForceWriteStream(bStream)
                    
                if not success:
                    break
                
            if not self.SafeCloseComPort():
                success = False
            else:
                self.logger.info('Tilter setup updated.')
            
        return success
    
### -------------------------------------------------------------------------------------------------------------------------------

    def _GetResetStream(self):
        
        stream = []
        
        for key, address in self.__addresses__.items():
            # set following ones to 1 otherwise tilter will get crazy
            if key in ['posAngle', 'negAngle', 'posMotSec', 'negMotSec']:
                stream.append( self.GenerateByteStream(address, 1) )
            else:
                stream.append( self.GenerateByteStream(address, 0) )
                
        return stream
        
    
### -------------------------------------------------------------------------------------------------------------------------------

    def ResetTilterSetup(self, mode='normal'):
        return self.WriteSetup(self._resetStream, mode)
    
### -------------------------------------------------------------------------------------------------------------------------------

    def ForceWriteStream(self, b):
        
        success = True
        
        # write multiple time to force tilter to accept stream
        for i in range(self.__numForces__):
            if not self.WriteStream(b):
                success = False
                break
            
        return success
    
### -------------------------------------------------------------------------------------------------------------------------------

    def WriteStream(self, b):
        
        success = True
        
        if self.comPortStatus:
            if self.SafeWriteToComPort(b, leaveOpen=True):
                sleep(50e-3)
                self.logger.debug( 'Sent %s to tilter' % coreUtils.GetTextFromByteStream(b) )
            else:
                success = False
                
        return success
    
### -------------------------------------------------------------------------------------------------------------------------------

    def ReadStream(self):
        
        if self.SafeOpenComPort():
            
            # reset tilter state for new run
            self._tilterState = self._GetDefaultTilterState()
            
            while self._isReading:
                
                # after splitting last entry in list is always emtpy, if character was in stream
                # check for this, otherwise wait for new input
                inMsg = self.SafeReadFromComPort('line', decode=True, leaveOpen=True)
                
                if len(inMsg) != 0:
                    self.HandleInMessageQueue(inMsg)
                    
                # there must be something wrong with the serial port
                # kill task...
                elif not self.comPortStatus:
                    self._isReading = False
                        
            
                # message are sent every 2s by the tilter
                sleep(1)
        
            # properly close port
            self.SafeCloseComPort()
    
### -------------------------------------------------------------------------------------------------------------------------------

    def HandleInMessageQueue(self, msg):
        
        # store for later handling, if no delimiter was found
        self._inMessageQueue.append(msg)
        
        msgStr = ''.join(self._inMessageQueue)
        
        # is '#' in stream? -> complete message
        if '#' in msgStr:
            
            # in case multiple readings where necessary flatten list to string
            # split again at correct positions with '#'
            # also multiple messages can be handled
            self._inMessageQueue = msgStr.split('#')
            
            while len(self._inMessageQueue) != 0:
                
                # get first message
                msg = self._inMessageQueue.pop(0)
                
                # read parameter values from last message and fill variable
                self._ExtractParameters(msg)
                
                # check pause time
                if self._currentParameterSet['p'] > 0 and self._currentParameterSet['m'] == 0:
                    
                    # only then update the waiting position
                    if not self._tilterState['isWaiting']:
                        # first wait is on positive side
                        if not self._tilterState['posWait']:
                            self._tilterState['posWait'] = True
                            
                            self._EventHandler('onPosWait')
                        
                        # then on the negative side
                        elif self._tilterState['posWait']:
                            self._tilterState['posWait'] = False
                            self._tilterState['negWait'] = True

                            self._EventHandler('onNegWait')
                            
                        self._tilterState['isMoving']  = False
                        self._tilterState['isWaiting'] = True

                        print('isWaiting')
                        
                # check motion time
                elif self._currentParameterSet['m'] > 0 and self._currentParameterSet['p'] == 0:
                    
                    # only then update the moving direction
                    if not self._tilterState['isMoving']:
                        # start with the first movement -> always the positive angle
                        if not any( [self._tilterState['posDown'], self._tilterState['posUp'], self._tilterState['negDown'], self._tilterState['negUp']] ):
                            self._tilterState['posDown'] = True

                            self._EventHandler('onPosDown')
                        
                        # return from waiting on positive side
                        elif self._tilterState['posDown']:
                            self._tilterState['posDown'] = False
                            self._tilterState['posUp']   = True

                            self._EventHandler('onPosUp')
                        
                        # return from waiting on negative side
                        elif self._tilterState['negDown']:
                            self._tilterState['negDown'] = False
                            self._tilterState['negUp']   = True

                            self._EventHandler('onNegUp')
                            
                    
                        # update states
                        self._tilterState['isMoving']  = True
                        self._tilterState['isWaiting'] = False

                        print('isMoving')
                            
                    # there might be a transition from up to down if there's not horizontal waiting...
                    # can be detected if the new time if larger than the old one
                    elif self._tilterState['isMoving'] and self._currentParameterSet['m'] > self._tilterState['moveTime']:
                        
                        # transition from posUp to negDown
                        if self._tilterState['posUp']:
                            self._tilterState['posUp']   = False
                            self._tilterState['negDown'] = True

                            self._EventHandler('onNegDown')
                        
                        # transition from negUp to posDown
                        # also we have a full cycle
                        elif self._tilterState['negUp']:
                            self._tilterState['negUp']      = False
                            self._tilterState['posDown']    = True
                            self._tilterState['numCycles'] += 1

                            self._EventHandler('onPosDown')
                            
                        print('transition')
                        

                    # set new 'old' value for next comparision
                    self._tilterState['moveTime']  = self._currentParameterSet['m']
    
### -------------------------------------------------------------------------------------------------------------------------------

    def _ExtractParameters(self, msg):
        
        for key in self.__parameters__:
            paramSet = msg.split(';')
            for param in paramSet:
                if key in param:
                    val = param.split(key)[-1]
                    
                    try:
                        val = int(val)
                    except ValueError:
                        self.logger.error('Could not extract number from %s' % val)
                    else:
                        self._currentParameterSet[key] = val
    
### -------------------------------------------------------------------------------------------------------------------------------

    def _EventHandler(self, event):
        
#        print('event in EventHandler: %s' % event)
        
        # call user defined function
        if self._tilterEvents[event]['defined']:
            
            for funcIdx in range(self._tilterEvents[event]['numFuncs']):
            
                # increment iteration counter
                self._tilterEvents[event]['itercnt'][funcIdx] += 1

                if self._tilterEvents[event]['itercnt'][funcIdx] == self._tilterEvents[event]['iter'][funcIdx]:
                    
                    # callback function
                    # push all event function to another thread
                    # NOTE: use dictionary to store different threads and access them later to join
                    eventKey = '%s%s' % (event, funcIdx)
                    
                    # so first try to join it
                    if eventKey in self._eventThreads.keys() and self._eventThreads[eventKey]:
                        self._eventThreads[eventKey].join()
                        
                    self._eventThreads[eventKey] = threading.Thread( target=lambda event=event, func=funcIdx: self._DelayEvent(event, func) )
                    self._eventThreads[eventKey].start()
#                    
#                    # if delay is zero, directly call callback
#                    if self._tilterEvents[event]['delay'][funcIdx] == 0:
#                        self._tilterEvents[event]['cb'][funcIdx]()
#                    # otherwise use DelayEvent
#                    else:
#                        self._eventThread.update( { = )
#                        self._eventThread.start()
#                        self._eventThread.join()
                    
                    
                    # reset iteration counter
                    self._tilterEvents[event]['itercnt'][funcIdx] = 0
    
### -------------------------------------------------------------------------------------------------------------------------------

    def _DelayEvent(self, event, func):
        # wait for delay
        sleep(self._tilterEvents[event]['delay'][func])
        # execute after waiting time
        self._tilterEvents[event]['cb'][func]()
    
### -------------------------------------------------------------------------------------------------------------------------------

    def StartTilter(self):
        
        success = True
        
        if not self.comPortStatus:
            self.logger.error('Attempting to start tilter, without proper initialization! Check connection to inSphero tilter!')
            success = False
            
        # com port status is OK
        else:
            
            if self.SafeOpenComPort():
                
                # try to start tilter
                success = self.WriteStream( self.GenerateByteStream(self.__addresses__['status'], self.__statusBits__['startTilter']) )
                    
                self.SafeCloseComPort()
                
                if success:
                    self._isTilting = True
                    self.logger.info('Started tilting.')
        
        return success
    
### -------------------------------------------------------------------------------------------------------------------------------

    def StopTilter(self):
        
        success = True
        
        if not self.comPortStatus:
            self.logger.error('Could not stop tilting! Check connection to inSphero tilter!')
            success = False
            
        # com port status is OK
        else:
            
            if self.SafeOpenComPort():
                
                # try to stop tilter
                success = self.WriteStream( self.GenerateByteStream(self.__addresses__['status'], self.__statusBits__['stopTilter']) )
                    
                self.SafeCloseComPort()
                
                if success:
                    self._isTilting = False
                    self.logger.info('Stopped tilting.')
            
        return success
    
### -------------------------------------------------------------------------------------------------------------------------------

    def StartInMessageThread(self):
        
        # otherwise there is no need to start thread
        if self.comPortStatus:
            
            # sleep for 30 ms to make sure no concurrent task tries to open the serial port for the tilter...
#            sleep(30e-3)
            
            # initialize new thread
            self._inMessageThread = threading.Thread(target=self.ReadStream)
            # once message thread is started loop is running till StopTilter() was called
            self._isReading = True
            # start parallel thread
            self._inMessageThread.start()
            
    
### -------------------------------------------------------------------------------------------------------------------------------

    def StopInMessageThread(self):
                
        # to stop while loop for reading tilter stream
        self._isReading = False
        
        if self.comPort:
            while self.comPort.isOpen():
                sleep(1e-3)
        
        if self._inMessageThread:
            # join concurrent and main thread
            self._inMessageThread.join()
                
### -------------------------------------------------------------------------------------------------------------------------------
    #######################################################################
    ###                    --- SET/GET FUNCTIONS ---                    ###
    #######################################################################
### -------------------------------------------------------------------------------------------------------------------------------

    def SetValue(self, key, val):
        
        if key in self._setup.keys():
            
            if key not in ['byteStream', 'posPause', 'negPause', 'horPause', 'totTime']:
                try:
                    val = int(val)
                except ValueError:
                    self.logger.error('Could not convert \'%s\' to integer' % val)
                else:
                    if key in ['posAngle', 'negAngle', 'posMotion', 'negMotion'] and val < 1:
                        val = 1
                        
                    self._setup.update       ( {key: val}                   )
                    self.ConvertSetupToStream( self.__addresses__[key], val )
                    
            elif key in ['posPause', 'negPause', 'horPause', 'totTime']:
                
                self._setup.update( {key: val} )
                
                if key in ['posPause', 'negPause', 'horPause']:
                    
                    mins, secs = coreUtils.GetMinSecFromString(val)
                    
                    self._setup.update( {'%sMin'%key: mins} )
                    self._setup.update( {'%sSec'%key: secs} )
                    
                    self.ConvertSetupToStream( self.__addresses__['%sMin'%key], mins )
                    self.ConvertSetupToStream( self.__addresses__['%sSec'%key], secs )
                    
                elif key == 'totTime':
                    
                    hrs, mins = coreUtils.GetMinSecFromString(val)
                    
                    self._setup.update( {'%sHrs'%key: hrs}  )
                    self._setup.update( {'%sMin'%key: mins} )
                    
                    self.ConvertSetupToStream( self.__addresses__['%sHrs'%key], hrs  )
                    self.ConvertSetupToStream( self.__addresses__['%sMin'%key], mins )
    
### -------------------------------------------------------------------------------------------------------------------------------

    def GetValue(self, key):
            
        if key in self._setup.keys():
            return self._setup[key]
        else:
            self.logger.error('%s not in setup' % key)
        
    
### -------------------------------------------------------------------------------------------------------------------------------

    def GetParameter(self, key):
            
        if key in self.__parameters__:
            return self._currentParameterSet[key]
        else:
            self.logger.error('%s not in parameter set' % key)
        
    
### -------------------------------------------------------------------------------------------------------------------------------

    def GetParameters(self):
        return self._currentParameterSet
    
### -------------------------------------------------------------------------------------------------------------------------------

    def _GetDefaultSetup(self):
        return {
            'posAngle'   : -1,
            'negAngle'   : -1,
            'posMotion'  : -1,
            'negMotion'  : -1,
            'posPause'   : '',
            'posPauseMin': -1,
            'posPauseSec': -1,
            'negPause'   : '',
            'negPauseMin': -1,
            'negPauseSec': -1,
            'horPause'   : '',
            'horPauseMin': -1,
            'horPauseSec': -1,
            'totTime'    : '',
            'totTimeHrs' : -1,
            'totTimeMin' : -1,
            'status'     : -1,
            'byteStream' : [], # each setup should have it's own stream
            'numCycles'  : -1       # also each setup should store the number of cycles it's active
        }
    
### -------------------------------------------------------------------------------------------------------------------------------

    def _GetDefaultTilterState(self):
        return {
            'isMoving' : False,
            'posDown'  : False,
            'posUp'    : False,
            'negDown'  : False,
            'negUp'    : False,
            'isWaiting': False,
            'posWait'  : False,
            'negWait'  : False,
            'moveTime' : 0,
            'waitTime' : 0,
            'numCycles': 0
        }
    
### -------------------------------------------------------------------------------------------------------------------------------

    def _GetDefaultEventDescriptors(self):
        
        d = {}
        
        for k in self.__supportedEvents__:
            d.update( {k: self._GetDefaultEventDescriptor()} )
            
        return d
    
### -------------------------------------------------------------------------------------------------------------------------------

    def _GetDefaultEventDescriptor(self):
        return {'defined': False, 'numFuncs': 0, 'cb': [], 'iter': [], 'itercnt': [], 'delay': []}
    
### -------------------------------------------------------------------------------------------------------------------------------

    def _GetDefaultParameterSet(self):
        
        d = {}
        
        for k in self.__parameters__:
            d.update({k: -1})
            
        return d

### -------------------------------------------------------------------------------------------------------------------------------

    def SetTilterEvent(self, event, cb, it=1, delay=0):
        
        print('event in SetTilterEvent: %s' % event)
        
        if event in self._tilterEvents.keys():
            self._tilterEvents[event]['defined'] = True
            
            # append new function to list, if not already exists
            if cb not in self._tilterEvents[event]['cb']:
                self._tilterEvents[event]['cb'].append     ( cb    )
                self._tilterEvents[event]['iter'].append   ( it    )
                self._tilterEvents[event]['itercnt'].append( 0     )
                self._tilterEvents[event]['delay'].append  ( delay )
                # increment func counter
                self._tilterEvents[event]['numFuncs'] += 1

            # if already exist, update values
            else:
                # find index of current callback in list
                for idx in range(self._tilterEvents[event]['numFuncs']):
                    if self._tilterEvents[event]['cb'][idx] == cb:
                        break
                    
                self._tilterEvents[event]['iter'][idx]    = it
                self._tilterEvents[event]['itercnt'][idx] = 0
                self._tilterEvents[event]['delay'][idx]   = delay
    
### -------------------------------------------------------------------------------------------------------------------------------

    def UnsetTilterEvent(self, event, func=None):
        
        if event in self._tilterEvents.keys():
            if func:
                for idx in range(self._tilterEvents[event]['numFuncs']):
                    if self._tilterEvents[event]['cb'][idx] == func:
                        self._tilterEvents[event]['cb'].pop     ( idx )
                        self._tilterEvents[event]['iter'].pop   ( idx )
                        self._tilterEvents[event]['itercnt'].pop( idx )
                        self._tilterEvents[event]['delay'].pop  ( idx )
                        # decrement func counter
                        self._tilterEvents[event]['numFuncs'] -= 1
                        break
                        
                if self._tilterEvents[event]['numFuncs'] == 0:
                    self._tilterEvents[event]['defined'] = False
                    
            # undefine all functions
            else:
                self._tilterEvents[event] = self._GetDefaultEventDescriptor()
    
### -------------------------------------------------------------------------------------------------------------------------------

    def IsTilting(self):
        return self._isTilting
            
            
            
            
###############################################################################
###############################################################################
###                      --- YOUR CODE HERE ---                             ###
###############################################################################
###############################################################################

if __name__ == '__main__':
    
    # create tilter object and initialize
    tilter = ChipTilterCore()
    # suppress debug messages and only show info + error
#    tilter = ChipTilterCore(logLevel='INFO')
    
    # reset tilter memory to default values
    tilter.ResetTilterSetup()
    #tilter.ResetTilterSetup(mode='force')
    
    # change level here
    tilter.logger.setLevel('INFO')
    
    ##############################
    ### - SET TILTING ANGLES - ###
    ##############################
    
    # set positive tilting angle to 45 degree
    tilter.SetValue('posAngle', 65)
    # set negative tilting angle to 30 degree
    tilter.SetValue('negAngle', 65)
    
    ##############################
    ### - SET MOTION TIMINGS - ###
    ##############################
    
    # set positive motion time to 12 sec
    tilter.SetValue('posMotion', 18)
    # set negative motion time to 15 sec
    tilter.SetValue('negMotion', 18)
    
    #############################
    ### - SET PAUSE TIMINGS - ###
    #############################
    
    # set positive waiting time to 30 sec
    tilter.SetValue('posPause', 18)
    # set negative waiting time to 1:30
    tilter.SetValue('negPause', 18)
    
    
    ##############################
    ### - WRITE TILTER SETUP - ###
    ##############################
    
    # now let's write the setup to the tilter
    tilter.WriteSetup()
    #tilter.WriteSetup(mode='force')
    
    
    # change back to debug
    tilter.logger.setLevel('DEBUG')
    
#    ##############################
#    ### - START/STOP TILTING - ###
#    ##############################
#    
#    # start tilting with current setup
    tilter.StartTilter()
#    
#    # sleep for 10 seconds
#    sleep(100)
#    
    try:
        while True:
            None
    except KeyboardInterrupt:
        # stop tilting
        tilter.StopTilter()
    
    
#    #################################
#    ### - DEFINE TILTING EVENTS - ###
#    #################################
#    # define event for waiting on the positive side
#    tilter.SetTilterEvent( 'onPosWait', onPosWait               )
#    
#    # define event for moving down on the negative side
#    tilter.SetTilterEvent( 'onNegDown', onNegDown               )
#    
#    # define event for waiting on the negative side to start the counter for the delay
#    tilter.SetTilterEvent( 'onNegWait', onNegWait               )
#    
#    # define event for waiting on the negative side, but delayed by 5 seconds
#    tilter.SetTilterEvent( 'onNegWait', onNegWaitDelay, delay=5 )
#    
#    # define stop command when the tilter moves up on the negative side - one cycle finished
#    #tilter.SetTilterEvent( 'onNegUp'  , tilter.StopTilter       )
#    
#    # define event to execute the function every second time the tilter is waiting on the positive side
#    tilter.SetTilterEvent( 'onPosWait', onPosWaitEveryTwo, it=2 )
#    
#    
#    
#    # start tilting again to see the printouts from the callback functions for the defined events
#    tilter.StartTilter()
#    
#    
#    
#    # print current positive angle received from the tilter
#    print( 'A+ %s' % tilter.GetParameter('A+')   )
#    
#    # print current positive motion time received from the tilter
#    print( 'M+ %s s' % tilter.GetParameter('M+') )
#    
#    
#    
#    while tilter.IsTilting():
#        print('My pause still takes %s s' % tilter.GetParameter('p'))
#        sleep(2)

    tilter.__del__()