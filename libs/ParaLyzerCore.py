# -*- coding: utf-8 -*-
"""
Created on Tue May  9 18:46:57 2017

@author: Martin Leonhardt (martin.leonhardt87@gmail.com)
"""

from libs import coreUtilities as coreUtils

from libs.ArduinoCore import ArduinoCore
from libs.ziHf2Core import ziHf2Core
from libs.inSpheroChipTilterCore import inSpheroChipTilterCore


class ParaLyzerCore:
        
    _fileKeys = ['cfg', 'swc', 'chc', 'stf', 'log', 'lfl']
    _detKeys  = ['hf2', 'ard', 'cam', 'til']

### -------------------------------------------------------------------------------------------------------------------------------
    
    def __init__(self, **flags):
        
        
        # use given core start time or create new one
        if 'coreStartTime' in flags.keys():
            self.coreStartTime = flags['coreStartTime']
        else:
            self.coreStartTime = coreUtils.GetDateTimeAsString()
            
            
        
        # initialize logger
        if 'logger' in flags.keys():
            self.logger  = flags['logger']
        elif 'logToFile' in flags.keys():
            if flags['logToFile']:
                if 'logFile' in flags.keys():
                    self.logFile = flags['logFile']
                else:
                    self.logFile = 'session_' + self.coreStartTime + '.log'
                    
                self.logger = coreUtils.InitLogger(self.logFile, __name__)
            else:
                self.logger = coreUtils.InitLogger(caller=__name__)
                
        
        
        # standard content of config file
        self.stdConfig = {
                'cfg':  './cfg/Config.json',
                'swc':  './cfg/SwitchConfig.json',
                'chc':  './cfg/ChipConfig.json',
                'stf':  './mat_files/',
                'stsf': '',
                'gui': {
                        'dbg': True                 # enable debug outputs, by default to file
                    }
            }
        
        self.cfgStatus = {
                'cfg': True,
                'swc': True,
                'chc': True,
                'stf': True,
                'log': True,
                'lfl': True
            }
            
        self.isRunning = False
        
            
        # create folders and config file, if necessary
        # otherwise read config and update stdConfig and cfgStatus
        self.CreateDefaultStructure()
        
        flags = {
            'coreStartTime': self.coreStartTime,
            'logToFile'    : True
        }
        
        # file flags for calling Arduino constructor
        # if files are not accesible, then pass empty dictionary - Arduino tries to use default ones
        files = {}
        if self.cfgStatus['chc']:
            files['chipConfigFile'] = self.stdConfig['chc']
        if self.cfgStatus['swc']:
            files['switchConfigFile'] = self.stdConfig['swc']
        
        
        # initialize devices
        self.arduino = ArduinoCore           ( self.SetupArduino,     **flags, **files, baudrate=115200, dtr=False )   # higher baudrate and avoid reset when opening serial port
        self.hf2     = ziHf2Core             ( self.stdConfig['stf'], **flags                                      )
        self.tilter  = inSpheroChipTilterCore( **flags                                                             )
        self.camera  = None
        
### -------------------------------------------------------------------------------------------------------------------------------
        
    def __del__(self):
        self.arduino.__del__()
        self.hf2.__del__()
        self.tilter.__del__()
        
        
                
            
            
### -------------------------------------------------------------------------------------------------------------------------------
    
    def DetectDevices(self, key):
        
        success = True
        
        if key == 'ard':
            
            flags = {'baudrate': 115200, 'dtr':False}
            success = self.arduino.DetectDeviceAndSetupPort(self.arduino._usbName, flags, 'Try to detect Arduino Uno...')
            
        elif key == 'hf2':
            
            success = self.hf2.DetectDeviceAndSetupPort()
            
        elif key == 'til':
            
            success = self.tilter.DetectDeviceAndSetupPort(self.tilter._usbName, {}, 'Try to detect inSphero tilter...')
            
        return success
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def CreateDefaultStructure(self):
        
        success = True
        
        # first check if there's a config file... load it
        if coreUtils.IsAccessible(self.stdConfig['cfg']):
            self.cfgStatus['cfg'] = self.ReadConfigFile()
            success = self.cfgStatus['cfg']
            
        # no config found...create standard
        else:
            # first check if directory exists
            if coreUtils.SafeMakeDir(self.stdConfig['cfg']):
                self.cfgStatus['cfg'] = coreUtils.DumpJsonFile(self.stdConfig, self.stdConfig['cfg'])
            else:
                success = False
        
        # check for log folder and permission
        # create if not exists
        if coreUtils.IsAccessible('./log/', 'write'):
            self.cfgStatus['lfl'] = True
        else:
            success = False
            
        # if stream folder does not exist, try to create
        if not coreUtils.IsAccessible(self.stdConfig['stf'], 'write'):
            if coreUtils.SafeMakeDir(self.stdConfig['stf']):
                self.cfgStatus['stf'] = True
            else:
                success = False
                    
        return success
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def ReadConfigFile(self):
        
        success = True
        
        newCfg = coreUtils.LoadJsonFile(self.stdConfig['cfg'])
        
        if newCfg != {}:
        
            # set standard config from file
            # nothing happens if its empty
            self.UpdateConfigStructure(newCfg)
            
            # check if all necessary keys exist
            # if one is missing update it
            # otherwise take info from file -> master
            self.UpdateConfigFile(newCfg)
            
        else:
            success = False
            
        return success
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def StartMeas(self, **flags):
        
        success        = True
        startRightAway = True
        
        # mandatory for starting measurement
        if not flags['ard'] or not flags['hf2']:
            success = {'ard': False, 'hf2': False}
        else:
            # check if tilter is connected
            if flags['til'] and flags['utr']:
                        
                # and then check if tilter events should be configured
                if 'prc' in flags:
                    if flags['prc']:
                        self.tilter.SetTilterEvent( 'onPosUp', self.arduino.Start                             )
                        self.tilter.SetTilterEvent( 'onPosUp', self.hf2.StartPoll                             )
                        self.tilter.SetTilterEvent( 'onNegUp', self.arduino.Stop                              )
                        self.tilter.SetTilterEvent( 'onNegUp', lambda flags=flags: self.hf2.StopPoll(**flags) )
                        
                        # events take care of start and stopping
                        startRightAway = False
                    else:
                        self.tilter.UnsetTilterEvent( 'onPosUp' )
                        self.tilter.UnsetTilterEvent( 'onNegUp' )
                
                if 'swt' in flags:
                    if flags['swt']:
                        self.tilter.SetTilterEvent( 'onPosUp'  , lambda flags=flags: self.arduino.SetupArduino(**flags) )
                        flags.update(cnti=False, viai=True)
                        self.tilter.SetTilterEvent( 'onNegWait', lambda flags=flags: self.arduino.SetupArduino(**flags), delay=flags['switchDelay'] )
                    else:
                        self.tilter.UnsetTilterEvent( 'onPosUp'   )
                        self.tilter.UnsetTilterEvent( 'onNegWait' )
                
                # just start tilter if the others are at least connected
                if not self.tilter.StartTilter():
                    success = {'til': False}
            
            # if no events were defined just start streaming
            if startRightAway:
                if not self.arduino.Start():
                    success = {'ard': False}
    
                if not self.hf2.StartPoll():
                    success = {'hf2': False}
    
            # if something went wrong try to stop
            if success != True:
                self.arduino.Stop()
                self.hf2.StopPoll()
                self.tilter.StopTilter()
            else:
                self.isRunning = True
                    
        return success
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def StopMeas(self, **flags):
        
        success = True

        if not flags['ard'] or not self.arduino.Stop():
            success = {'ard': False}

        if not flags['hf2'] or not self.hf2.StopPoll():
            success = {'hf2': False}

        if flags['til']:
            if not self.tilter.StopTilter():
                success = {'til': False}

        self.isRunning = False
        
        return success
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def IsRunning(self):
        return self.isRunning
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def SetupArduino(self, activeElectrodes, **flags):
        
        ePairs       = []
        collectFirst = True
        collectCnt   = False
        collectVia   = False
        
        if 'perChamber' in flags:
            if flags['perChamber']:
                collectFirst = False
                
        if 'cnti' in flags:
            if flags['cnti']:
                collectCnt = True
                
        if 'viai' in flags:
            if flags['viai']:
                collectVia = True
                
                
        if collectFirst:
            
            cntPairs = []
            viaPairs = []

            # collect pairs from active electrodes
            for key, val in sorted(activeElectrodes.items()):
                # counting pairs - odd numbers
                if int(key) % 2:
                    if collectCnt:
                        cntPairs.append( val )
                        
                # counting pairs - even numbers
                else:
                    if collectVia:
                        viaPairs.append( val )
                        
            ePairs = cntPairs + viaPairs
        
        # just sort the list in ascending fashion
        else:
            for key, val in sorted(activeElectrodes.items()):
                ePairs.append( val )
                
        return ePairs
        
        
        
            
            
### -------------------------------------------------------------------------------------------------------------------------------
    #######################################################################
    ###                     --- UPDATE FUNCTIONS ---                    ###
    #######################################################################    
### -------------------------------------------------------------------------------------------------------------------------------
    
    def UpdateConfig(self, keys, vals):
        
        newDict = {}
        success = True
        
        # if single key + value
        # put in list format
        if not isinstance(keys, list) and not isinstance(vals, list):
            keys = [keys]
            vals = [vals]
        
        # update internal config
        if len(keys) == len(vals):
            for key, val in zip(keys, vals):
                if key in self.stdConfig.keys():
                    self.stdConfig[key] = val
                    self.UpdateFileStatus(key)
                    # just for the update config file
                    newDict[key] = val
                    
                    # update configurations in case user selected different files
                    if key in ['chc', 'swc']:
                        success = self.arduino.UpdateConfig( key, self.stdConfig[key] )
                        if not success:
                            break
                    
            # now write to file
            if success:
                success = self.UpdateConfigFile(newDict)
                    
        else:
            raise Exception('Keys and values must have the same length!')
            success = False
            
        return success
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def UpdateFileStatus(self, key='all'):
        
        if key != 'all':
            if key in self.cfgStatus.keys():
                self.cfgStatus[key] = coreUtils.IsAccessible(self.stdConfig[key])
        else:
            for key in self.cfgStatus.keys():
                self.cfgStatus[key] = coreUtils.IsAccessible(self.stdConfig[key])
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def UpdateConfigStructure(self, newDict):
        
        if self.stdConfig != newDict:
            for key in newDict.keys():
                if key in self.stdConfig.keys():
                    if not isinstance(self.stdConfig[key], dict):
                        if self.stdConfig[key] != newDict[key]:
                            self.stdConfig.update({key: newDict[key]})
                    else:
                        for subKey in newDict[key].keys():
                            self.stdConfig[key].update({subKey: newDict[key][subKey]})
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def UpdateConfigFile(self, newDict=None):
        
        success = True
        
        if newDict:
            if self.stdConfig != newDict:
                for key in self.stdConfig.keys():
                    if key not in newDict.keys():
                        newDict.update({key: self.stdConfig[key]})
                    # if key exists, check for sub-keys
                    else:
                        if isinstance(self.stdConfig[key], dict):
                            for subKey in self.stdConfig[key].keys():
                                if subKey not in newDict[key].keys():
                                    newDict[key].update({subKey: self.stdConfig[key][subKey]})
                
                if not coreUtils.DumpJsonFile(newDict, self.stdConfig['cfg']):
                    self.logger.error('Could not update file \'%s\'!' % self.stdConfig['cfg'])
                    success = False
                    
        # no dict given, so just write the internal array to file
        else:
            if not coreUtils.DumpJsonFile(self.stdConfig, self.stdConfig['cfg']):
                self.logger.error('Could not update file \'%s\'!' % self.stdConfig['cfg'])
                success = False
        
        return success
        
                
                
                
                
### -------------------------------------------------------------------------------------------------------------------------------
    #######################################################################
    ###                    --- SET/GET FUNCTIONS ---                    ###
    #######################################################################
### -------------------------------------------------------------------------------------------------------------------------------
    
    def SetConfig(self, key, subK=None, val=True):
        
        if key in self.stdConfig.keys():
            if subK != None:
                if subK in self.stdConfig[key].keys():
                    self.stdConfig[key][subK] = val
                else:
                    raise KeyError('%s was not found in stdConfig[%s]!' % (subK, key))
            else:
                self.stdConfig[key] = val
        else:
            raise KeyError('%s was not found in stdConfig!' % key)
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def GetConfig(self, key):
        
        if key in self.stdConfig.keys():
            cfg = self.stdConfig[key]
        else:
            cfg = None
        return cfg
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def GetComPortInfo(self, key='all'):
        
        comPortInfo = None
        
        if key != 'all':
            if key == 'ard':
                comPortInfo = self.arduino.GetPortInfo()
            elif key == 'hf2':
                comPortInfo = self.hf2.GetPortInfo()
            elif key == 'til':
                comPortInfo = self.tilter.GetPortInfo()
                
        # return all port infos
        else:
            comPortInfo = {}
            comPortInfo['ard'] = self.arduino.GetPortInfo()
            comPortInfo['hf2'] = self.hf2.GetPortInfo()
            comPortInfo['til'] = self.tilter.GetPortInfo()
            
        return comPortInfo
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def GetDetectionStatus(self, key='all'):
        
        status = None
        
        if key != 'all':
            if key == 'ard':
                status = self.arduino.GetPortStatus()
            elif key == 'hf2':
                status = self.hf2.GetPortStatus()
            elif key == 'til':
                status = self.tilter.GetPortStatus()
                
        # return status of all devices
        else:
            status = {}
            status['ard'] = self.arduino.GetPortStatus()
            status['hf2'] = self.hf2.GetPortStatus()
            status['til'] = self.tilter.GetPortStatus()
            
        return status
        
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def GetFileStatus(self, key='all'):
        
        status = None
        
        if key != 'all':
            if key in self.cfgStatus.keys() and self._fileKeys:
                status = self.cfgStatus[key]
        else:
            status = {}
            for key, val in self.cfgStatus.items():
                status[key] = val

        return status
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def GetFileKeys(self):
        return self._fileKeys
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def GetDetectionKeys(self):
        return self._detKeys
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def SetGuiFlag(self, key, val):
        self.stdConfig['gui'][key] = coreUtils.ToBool(val)
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def GetGuiFlags(self):
        return self.stdConfig['gui']