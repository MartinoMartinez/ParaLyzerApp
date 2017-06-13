# -*- coding: utf-8 -*-
"""
Created on Tue May  9 18:44:04 2017

@author: Martin Leonhardt (martin.leonhardt87@gmail.com)
"""

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
    



class ArduinoCore(CoreDevice):
    
    # serial port flags
    __baudrate__ = 115200
    __dtr__      = False       # avoid pull-down of reset upon serial port opening
    
    # name for auto detection
    __usbName__ = 'Arduino Uno'
    
    # message for detection
    __detMsg__ = 'Try to detect Arduino Uno...'
    
    def __init__(self, chipConfig='', switchConfig='', selectElectrodePairs=None, **flags):
            
        # setup com port
        flags['baudrate']     = self.__baudrate__
        flags['dtr']          = self.__dtr__
        
        CoreDevice.__init__(self, **flags)
        
        # use given chipConfig file or use default one
        self._chipConfigFile   = chipConfig   if chipConfig   else './cfg/ChipConfig.json'
        # use given switchConfig file or use default one
        self._switchConfigFile = switchConfig if switchConfig else './cfg/SwitchConfig.json'
        
        # callback function for selecting and sorting previously defined electrode pairs
        self._selectElectrodePairs = selectElectrodePairs
        
        # contains chamber-electrode connections, counting from 0 to 29
        # each two are one chamber with two different electrode pairs for counting and measuring viability
        # so 60 entries are in this file
        self.UpdateConfig( chipConfig=self._chipConfigFile    )
        
        # contains switch-electrode assignment, counting from -2 to 29
        # 64 switches are availble in total, for flexibility 32 can be used in both directions (stim+rec)
        # two of them are used for debugging on current PCB (v4.0 Ketki) ... -2,-1 are not accessible as array index
        # the order is related to the IC on the PCB, starting with 0 from the connector (Sebastian counted the pad IDs descending from 29 in the same direction)
        self.UpdateConfig( switchConfig=self._switchConfigFile )
        
        # define empty electrode pair dictionary
        self._definedElectrodePairs = {
        # this dictionary contains several standard structures depending on the electrode pairs that were defined
#                'ID': {
#                     'ePair': -1,
#                     'int'  : -1
#                }
            }
            
        self._debugMode = False

### -------------------------------------------------------------------------------------------------------------------------------

    def __del__(self):
        
        CoreDevice.__del__(self)
        
        
            
            
            
            
### -------------------------------------------------------------------------------------------------------------------------------

    def UpdateConfig(self, chipConfig=None, switchConfig=None):
        
        success = True
        
        if chipConfig:
            self._chipConfig = coreUtils.LoadJsonFile( chipConfig, self )
            
            if self._chipConfig != {}:
                self.chipConfigStatus = True
            else:
                self.chipConfigStatus = False
                success = False
                self.logger.error('Could not find chip config file: %s' % chipConfig)
                
        if switchConfig:
            self._switchConfig = coreUtils.LoadJsonFile( switchConfig, self )
            
            if self._switchConfig != {}:
                self.switchConfigStatus = True
            else:
                self.switchConfigStatus = False
                success = False
                self.logger.error('Could not find switch config file: %s' % switchConfig)
                
        return success
        
### -------------------------------------------------------------------------------------------------------------------------------

    def SendMessage(self, msg):
        """ Send binary data to Arduino Uno.
            Line ending is \r.
            Serial port is kept open in case debug is enabled till answer from Arduino was received.
        """
        
        success = False
        
        if self.SafeOpenComPort():
            
            # calculate check sum to make sure Arduino receives the correct stuff
            # just sum up the whole shit and add to message in HEX format, e.g. 1A9 for 0x01A9
            checkSum = hex(sum([ord(i) for i in msg])).replace('0x','')
            
            # write message
            # NOTE: encoding as byte is required by pySerial
            # do not forget '\n' (newline) for command recognition
            # NOTE: flush is deprecated with pySerial > v3.0
            msg = 'START %s %s END\r' % (checkSum, msg)
            
            print(msg)

            
            success = self.SafeWriteToComPort(msg.encode('latin-1'), leaveOpen=True)
            
            
            if success:
                if self._debugMode:
                    
                    inMsg = self.SafeReadFromComPort(mode='waiting', waitFor=1, bePatient=25, decode=True).replace('\n', ', ')
                    
                    self.logger.debug('Received message from Arduino: %s' % inMsg)
                        
        return success
    
### -------------------------------------------------------------------------------------------------------------------------------
    
    def GetActiveSwitchIndices(self, activeElectrodePair):
        '''gets the switch indices which are to be activated when the indicated chamber is active'''
        
        # init return value
        switchesToActivate = []
        oldFileType = False
        
        if isinstance(activeElectrodePair, str):
            
            if 'res' in activeElectrodePair:
                switchesToActivate = [62, 63]
            elif 'short' in activeElectrodePair:
                switchesToActivate = [60, 61]
        else:
            # find corresponding electrode pair in chip config file
            padIdx = 0
            while padIdx < len(self._chipConfig['chamberToPad']):
                # get next pad setup
                pads = self._chipConfig['chamberToPad'][padIdx]
                # stop loop when correct electrode pair setup was found
                # use pads in subsequent code
                if 'ePairId' in pads.keys():
                    if pads['ePairId'] == activeElectrodePair:
                        break
                    else:
                        padIdx += 1
                # probably old file type .. use number as index to access pads
                else:
                    oldFileType = True
                    break
                
            # in case loop left withput any results
            # e.g. an old file setup was used
            # just use the given variable as index
            if oldFileType:
                pads = self._chipConfig['chamberToPad'][activeElectrodePair]
            
            self.logger.debug('pads: %s' % pads)
            
            # get switch index to close connection to stimulation/recording pad
            for switchId in range(len(self._switchConfig)):
                if (self._switchConfig[switchId]['padId'] == pads['stimPadId'] and self._switchConfig[switchId]['padType'] == 'stim'):
                    switchesToActivate.append(switchId)
                if (self._switchConfig[switchId]['padId'] == pads['recPadId']  and self._switchConfig[switchId]['padType'] == 'rec'):
                    switchesToActivate.append(switchId)

                ############################################
                ###    --- PUT YOUR EXTENSION HERE ---   ###
                ###                                      ###
                ### switchesToActivate.append(...)       ###
                ############################################
                    
        # make sure Arduino receives sorted list
        # otherwise daisy chaining might not work
        switchesToActivate.sort()
                    
        return switchesToActivate
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def GenerateSendStream(self, activeElectrodePair, residenceTime=0):
        '''converts chosen chamber and electrode pair to bytes for sending via serial interface
           NOTE: all switches are updated at once (8 bytes + 1 byte for chamber and electrode encoding)
        '''
        
        sendBytes = bytes()
        
        if self.chipConfigStatus and self.switchConfigStatus:
        
            # support the two debugging switches on current PCB (v4.0 Ketki)
            # one with a resister (1k)
            # and the other with a short
            # NOTE: set DIO lines and residence time to zero
            if isinstance(activeElectrodePair, str):
                activeSwitches  = self.GetActiveSwitchIndices(activeElectrodePair)
                electrodeCoding = (0x00).to_bytes(1, 'big')
                
            elif isinstance(activeElectrodePair, int):
                
                # index in PcbConfig file, starting from 0 independent from routing
                activeSwitches = self.GetActiveSwitchIndices(activeElectrodePair)
                
                # chamber and electrode coding
                electrodeCoding = (activeElectrodePair & 0x1F).to_bytes(1, 'big')
                
            # first switch bytes
            # use switch index and convert to bytes
            for sw in activeSwitches:
                sendBytes += sw.to_bytes(1, 'big')
            
            # then chamber number, electrode pair as MSB (NOTE: only five bits are used)
            # append residence time encoded in four bytes
            sendBytes += electrodeCoding 
            sendBytes += residenceTime.to_bytes(4, 'big')
            
            self.logger.debug( 'Active electrode pair: %s' % activeElectrodePair                                                     )
            self.logger.debug( 'Active switches (abs): %s' % activeSwitches                                                          )
            self.logger.debug( 'Active switches: %s on device: %s' % ([i%8 for i in activeSwitches], [i//8 for i in activeSwitches]) )
            
            # wrap the text generated from sendBytes every two half-bytes and print it
            self.logger.debug( 'Prepare %s bytes for storing on Arduino: %s' % (len(activeSwitches)+5, coreUtils.GetTextFromByteStream(sendBytes)) )
    
        return sendBytes.decode('latin-1')
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def SetupArduino(self, selectFunc=None, **flags):
        
        success = True
        
        # check debug flag
        # it's also possible to set self.debugMode directly
        self._debugMode = flags.get('debugMode', self._debugMode)
        
        # empty stream
        sendStream = []

        ePairs = self.SelectElectrodePairs(selectFunc, **flags)
            
        print(ePairs)
        
        if len(ePairs) == 0:
            success = False
        
            
        if success:
            
            # generate byte stream for all electrode pairs
            for ePair in ePairs:
                    
                stream = self.GenerateSendStream(ePair['ePair'], ePair['int'])
                
                # check for valid stream
                # otherwise stop loop
                if len(stream) != 0:
                    sendStream.append( stream )
                else:
                    success = False
                    break
            
                
        if success:
            
            # enable/disable debug for Arduino
            if self._debugMode:
                success = self.SendMessage('debug 1')
            else:
                success = self.SendMessage('debug 0')
                    
            
            # check if something is in stream
            if success and len(sendStream) != 0:
                # send byte stream for setting electrode pair setup
                # Arduino will just call the setups one by one
                # according to the defined timings
                sendStream = ''.join(sendStream)
                
                self.logger.debug('Sending %s bytes to Arduino... %s' % (len(sendStream), coreUtils.GetTextFromByteStream(sendStream)))
                
                success = self.SendMessage('setelectrodes %s %s' % (len(ePairs), sendStream))
                
                if success:
                    self.logger.info('Arduino setup was updated.')
                else:
                    self.logger.error('Failed.')
        
        return success
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def Start(self):
        return self.SendMessage('start')
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def Stop(self):
        return self.SendMessage('stop')
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def EnableDebug(self):
        self.logger.info('Enable debug mode.')
        # locally enable debug mode
        self._debugMode = True
        # enable debug mode for Arduino
        return self.SendMessage('debug 1')
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def DisableDebug(self):
        self.logger.info('Disable debug mode.')
        # locally disable debug mode
        self._debugMode = False
        # disable debug mode for Arduino
        return self.SendMessage('debug 0')
            
### -------------------------------------------------------------------------------------------------------------------------------
    
    def DefineElectrodePair(self, ePair, interval):
        
        # if key is all set new timings for all exisiting chambers
        # coming ones will have directly the timings according to the setup
        
        key      = str(ePair)
        interval = int(interval)
        
        # but only if not already exists
        if key not in self._definedElectrodePairs.keys():
            self._definedElectrodePairs[key] = (self.GetStandardElectrodePair())
        
        self._definedElectrodePairs[key]['ePair'] = ePair
        self._definedElectrodePairs[key]['int']   = interval

        self.logger.debug('Selected electrode pair %s with interval %s us.' % (ePair, interval))
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def UndefineAllElectrodePairs(self):
        self._definedElectrodePairs = {}
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def SelectElectrodePairs(self, selectFunc=None, **flags):
        
        ePairs = []
        
        # in case user passes a select function - overwrite old one
        if selectFunc:
            self._selectElectrodePairs = selectFunc
        
        # use callback to select electrode pairs - if given
        if self._selectElectrodePairs:
            ePairs = self._selectElectrodePairs(self._definedElectrodePairs, **flags)
            
        # otherwise just sort the list in ascending order and return it
        else:
            
            # pre-sort dictionary
            # since dicts use string keys, sort doesn't work properly
            # we need to turn it into an integer list
            dummyList = []
            for key in self._definedElectrodePairs.keys():
                dummyList.append(int(key))
            # sort the integer list
            dummyList.sort()
            # return to string for later use as key
            dummyList = [str(i) for i in dummyList]

            # just sort the list in ascending fashion
            for key in dummyList:
                ePairs.append( self._definedElectrodePairs[key] )
                
        return ePairs
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def GetStandardElectrodePair(self):
        return {
                'ePair': -1,
                'int'  : -1
            }
            
            
            
            
###############################################################################
###############################################################################
###                      --- YOUR CODE HERE ---                             ###
###############################################################################
###############################################################################

def MySelectElectrodePairFunction(definedElectrodePairs, **flags):
    ''' user defined selection and sorting of previously defined electrode pairs
    '''
    
    # init return value
    selectedElectrodePairs = []
    
    # just select even electrode pairs
    for ePair in definedElectrodePairs.values():
        if ePair['ePair'] % 2 == 0:
            selectedElectrodePairs.append(ePair)
            
    # and reverse order
    selectedElectrodePairs.reverse()
    
    return selectedElectrodePairs
    
    
def MySelectElectrodePairFunctionWithFlags(definedElectrodePairs, **flags):
    ''' user defined selection and sorting of previously defined electrode pairs
    '''
    
    # init return value
    selectedElectrodePairs = []
 
    # try to grab mode from flags
    # if not there use 'even' as default
    mode = flags.get('mode', 'even')
    
    # try to grab order from flags
    # if not there use 'ascending' as default
    order = flags.get('order', 'ascending')
    
    # define remainder according to mode
    if mode == 'even':
        remainder = 0
    elif mode == 'odd':
        remainder = 1
    else:
        print('ERROR: Unknown mode: %s' % mode)
        return
    
    # just select even electrode pairs
    for ePair in definedElectrodePairs.values():
        if ePair['ePair'] % 2 == remainder :
            selectedElectrodePairs.append(ePair)
            
    # reverse order, if user wants to
    if order == 'descending':
        selectedElectrodePairs.reverse()
    
    return selectedElectrodePairs
            
            
            
###############################################################################
###############################################################################
###                      --- YOUR CODE HERE ---                             ###
###############################################################################
###############################################################################

if __name__ == '__main__':
    
    # create Arduino instance
    arduino = ArduinoCore()
#    # change source for switch config file
#    arduino = ArduinoCore(switchConfig='./SwitchConfig.json')
#    
#    # change source for chip config file
#    arduino.UpdateConfig(chipConfig='./ChipConfig.json')
    
    # enable debug mode here to catch incoming messages
    
    sleep(1)

#    arduino.EnableDebug()
#        
#    
#    # execute blinking test to check the connection and proper running of Arduino code
#    arduino.SendMessage('test')
#    
#    # test might take a while...so better sleep
#    sleep(4)
#    
    # print all available commands
#    s = 'help'
#    
#    checksum = hex(sum([ord(i) for i in s])).replace('0x','')
#    
#    msg = 'START %s %s END\r' % (checksum, s)
#    
#    arduino.comPort.open()
#    arduino.comPort.write(msg.encode('latin-1'))

#    for i in range(30):
#        arduino.DefineElectrodePair(i, 1e6)

    arduino.UpdateConfig(chipConfig='./cfg/ChipConfigSeb.json')

    arduino.DefineElectrodePair(0, 1e3)
    arduino.DefineElectrodePair(2, 1e3)
        
    arduino.SetupArduino()
    
#    arduino.SendMessage( 'setelectrodes 1 %s' % arduino.GenerateSendStream(15,0) )
#    arduino.SendMessage('setelectrodes 1 125ABCDEFG')
    from time import time
    sT = time()
    while time()-sT < 2:
        print(arduino.comPort.read(arduino.comPort.in_waiting))
        sleep(100e-3)
    
    arduino.Start()
    
    sT = time()
    while time()-sT < 5:
        print(arduino.comPort.read(arduino.comPort.in_waiting))
        sleep(.5)
    
    arduino.Stop()
    arduino.comPort.close()
#    
#    
#    #######################################################
#    ### --- FIRST OPTION TO SEND A SETUP TO ARDUINO --- ###
#    #######################################################
#    
#    # generate debug stream and send command
#    # use one of the fixed switch assignments on the PCB - a short between two switches
#    arduino.SendMessage( 'setelectrodes 1 %s' % arduino.GenerateSendStream('short') )
#    
#    arduino.SetupArduino()
#    
#    
    

    arduino.__del__()