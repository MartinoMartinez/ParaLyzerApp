# -*- coding: utf-8 -*-
"""
Created on Tue May  9 18:44:04 2017

@author: Martin Leonhardt (martin.leonhardt87@gmail.com)
"""

import threading

import tkinter as tk
from tkinter import messagebox
from tkinter import filedialog

from time import sleep
from datetime import datetime
from copy import deepcopy

import re

from libs.StatusBar import StatusBar
from libs.Logger import Logger
import libs.coreUtilities as coreUtils
#import libs.guiUtilities as guiUtils
from libs.ParaLyzerCore import ParaLyzerCore


                

class ParaLyzerApp(Logger, StatusBar):

    # NOTE: if you add a label AND it will be changed during program execution you need to enter it twice
    # here for initial settings
    # and in lbl_txts again
    # ... this dictionary is not supposed to change during execution
    __lbl_txts__ = {
            'hf2': 'No HF2LI detected!',
            'ard': 'No Arduino detected!',
            'cam': 'No Camera detected!',
            'til': 'No Tilter detected!',
            'cfg': 'Not found',
            'chc': 'Not found',
            'swc': 'Not found',
            'stf': 'Not found',
            'cnt': 'Cint:',
            'via': 'Vint:',
            'pan': 'A+',
            'nan': 'A-',
            'pmo': 'M+',
            'nmo': 'M-',
            'ppa': 'P+',
            'npa': 'P-',
            'swd': 'Switch Delay:',
            'stm': 'File size:',
            'unt': 'MB'
        }
       
### -------------------------------------------------------------------------------------------------------------------------------
       
    def __init__(self, master):
        # create general face of the app

        # forbid resize by user
        master.resizable(width=False, height=False)

        # set window title
        master.title('ParaLyzerApp')

        # store core start time...for creating folders and files
        self._appStartTime = coreUtils.GetDateTimeAsString()
        self._logFile      = 'session_' + self._appStartTime + '.log'
        
        # init logger
        Logger.__init__(self, logFile=self._logFile)
        
        self.logger.info('Starting program...')

        self.master = master
        
        self.frms       = {}
        self.lfrms      = {}
        self.btns       = {}
        self.lbls       = {}
        self.rbtns      = {}
        self.rbnt_vals  = {}
        self.ckbtns     = {}
        self.ckbtn_vals = {}
        self.entrs      = {}
        self.entr_vals  = {}
        self.optm       = {}
        self.optm_vals  = {}
        self.optm_opts  = {}


        # use these guys here as default vars
        # do not touch them, unless GUI needs to be changed
        self.btn_txts = {
                    'hf2': 'Detect HF2LI',
                    'ard': 'Detect Arduino',
                    'cam': 'Detect Camera',
                    'til': 'Detect Tilter',
                    'chc': 'Chip Config',
                    'swc': 'Switch Config',
                    'stf': 'Stream Folder',
                    'wac': 'Write Config',
                    'usr': 'Define Switching...',
                    'sts': 'Start',                 # and Stop Arduino, HF2 and tilter...
                    'wtc': 'Write Config',
                    'rtm': 'Reset',
                    'stt': 'Start',                 # tilter
                    'rts': 'Read Config'            # update tilter setup in App
                }

        self.lbl_txts = deepcopy(self.__lbl_txts__)
        
        self.rbtn_txts = {
                    'std': 'Count + Viability',
                    'cnt': 'Counting only',
                    'via': 'Viability only',
                    'usr': 'User defined'                          
                }
                
        self.ckbtn_txts = {
                    'dbg': 'Enable debug',
                    'enn': 'Enable notifier',
                    'utr': 'Use tilter',
                    'sac': 'Select all',
                    'ofa': 'One for all',
                    # 'scv': 'Same cnt + via',
                    'swt': 'Sync with tilter',
                    'prc': 'Pause recording'
                }
        
        # define color for highlighted fields
        self.wrongEntryColor = 'gold'
        
        # for checking if checkbox status has changed
        # update of Arduino necessary
        self.ePairsChanged = False
        
        # only start streaming if at least one electrode pair was selected
        self.somethingsSelected = False
        
        # no timer is running, so set TRUE
        self.stopTimeThread = True
        
        # also no thread is defined yet
        self.runTimeThread = None
        
        # parameters to start measurement
        self.streamFlags = {
                    'ard'        : False,
                    'hf2'        : False,
                    'til'        : False,
                    'debugMode'  : False,
                    'cnti'       : False,
                    'viai'       : False,
                    'swt'        : False,
                    'prc'        : False,
                    'utr'        : False,
                    'switchDelay': 0,
                    'stopDelay'  : 0
                }
        
        
                
        
        # check whether GUI is about to close
        master.protocol('WM_DELETE_WINDOW', self.onClose)
                
        
        # create core class object
        # by passing logFile logToFile is automatically true
        self.paraLyzerCore = ParaLyzerCore(coreStartTime=self._appStartTime, logFile=self._logFile)
        
        
        
        
        
        
        
        self.frms['start'] = tk.Frame(master)
        self.frms['start'].pack()
        
        # button to start/stop measurement
        self.CreateButtons( self.frms['start'], ['sts'], padx=10, pady=10 )
        
        
        
        
        #################################
        #   --- CONNECTED DEVICES ---   #
        #################################
        self.frms['cdfm'] = tk.Frame(master)
        self.frms['cdfm'].pack(anchor=tk.NW)
        
        
        self.lfrms['cnd'] = tk.LabelFrame(self.frms['cdfm'], text='Connected Devices: ', font=('Helvetica', 12))
        self.lfrms['cnd'].pack(side=tk.LEFT, anchor=tk.NW, fill=tk.Y, padx=15, pady=15)
        
        # HF2LI frame
        self.frms['cndb'] = tk.Frame(self.lfrms['cnd'])
        self.frms['cndb'].pack(side=tk.LEFT, fill=tk.X, padx=10, pady=10)
        # label frame
        self.frms['cndl'] = tk.Frame(self.lfrms['cnd'])
        self.frms['cndl'].pack(side=tk.LEFT, fill=tk.X, padx=10, pady=10)
        
        # create detection buttons and labels
        self.CreateButtons( self.frms['cndb'], ['hf2','ard','til'], fill=tk.X, pady=2   )
        self.CreateLabels ( self.frms['cndl'], ['hf2','ard','til'], anchor=tk.W, pady=5 )
        
        
            
        
        ############################
        #   --- FILE MANAGER ---   #
        ############################
        self.lfrms['flm'] = tk.LabelFrame(self.frms['cdfm'], text='File Manager: ', font=('Helvetica', 12))
        self.lfrms['flm'].pack(side=tk.LEFT, anchor=tk.N, fill=tk.Y, padx=15, pady=15)
        
        # label to inform user about cfg file
        self.lbls['cfg'] = tk.Label(self.lfrms['flm'])
        self.lbls['cfg'].pack(anchor=tk.N, pady=10)
        
        # button frame
        self.frms['flmb'] = tk.Frame(self.lfrms['flm'])
        self.frms['flmb'].pack(side=tk.LEFT, fill=tk.X, padx=10, pady=10)
        
        # label frame
        self.frms['flml'] = tk.Frame(self.lfrms['flm'])
        self.frms['flml'].pack(side=tk.LEFT, fill=tk.X, padx=10, pady=10)
        
        # dialog button to select folder to store files
        self.CreateButtons( self.frms['flmb'], ['chc', 'swc', 'stf'], fill=tk.X, pady=2   )
        self.CreateLabels ( self.frms['flml'], ['chc', 'swc', 'stf'], anchor=tk.W, pady=5 )
        
        
        
        
        #################################
        #   --- SWITCHING SCHEMES ---   #
        #################################
        self.frms['swmc'] = tk.Frame(master)
        self.frms['swmc'].pack(anchor=tk.W)
        
        
        self.lfrms['scs'] = tk.LabelFrame(self.frms['swmc'], text='Switching Schemes: ', font=('Helvetica', 12))
        self.lfrms['scs'].pack(side=tk.LEFT, anchor=tk.NW, padx=15, pady=15)
        
        # frame for radio buttons and write config button
        self.frms['swso'] = tk.Frame(self.lfrms['scs'])
        self.frms['swso'].pack(anchor=tk.NW, padx=5, pady=5, fill=tk.X)
        
        # frame for radio buttons
        self.frms['swsr'] = tk.Frame(self.frms['swso'])
        self.frms['swsr'].pack(anchor=tk.NW, padx=5, pady=5, fill=tk.X, side=tk.LEFT)
        
        # frame for write config button
        self.frms['swsw'] = tk.Frame(self.frms['swso'])
        self.frms['swsw'].pack(anchor=tk.NW, padx=5, pady=5, fill=tk.BOTH)
        
        # frame to contain all chamber selections with timings
        self.frms['swsc'] = tk.Frame(self.lfrms['scs'])
        self.frms['swsc'].pack(padx=5, pady=5)
        
        # to share between radio buttons
        self.sw_scm_rbtn_var = tk.StringVar()
        self.sw_scm_rbtn_var.set('std')
        
        # radio buttons for selecting the switching scheme
        self.CreateRadioButton(self.frms['swsr'], 'sws', ['std', 'cnt', 'via'], 'std', anchor=tk.W)

        # for user defined serve another input scheme via dialog opened by button
        self.CreateButton( self.frms['swsw'], 'wac', anchor=tk.CENTER)
        
        
        
        # option to set all chambers at once
        ofa_scv_swt_frm = tk.Frame(self.frms['swsc'])
        ofa_scv_swt_frm.pack(anchor=tk.W)
        ofa_frm = tk.Frame(ofa_scv_swt_frm)
        ofa_frm.pack(anchor=tk.NW, side=tk.LEFT)
        
        ofa_ckbtn_frm = tk.Frame(ofa_frm)
        ofa_ckbtn_frm.pack(anchor=tk.W, fill=tk.Y )
        
        ofa_cnt_frm = tk.Frame(ofa_frm)
        ofa_cnt_frm.pack(anchor=tk.W, pady=2)
        
        ofa_via_frm = tk.Frame(ofa_frm)
        ofa_via_frm.pack(anchor=tk.W, pady=2)
        
        self.CreateCheckButton( ofa_ckbtn_frm, 'ofa'                                                           )
        self.CreateLabel      ( ofa_cnt_frm  , 'cnt'   , side=tk.LEFT                                          )
        self.CreateUserEntry  ( ofa_cnt_frm  , 'cntofa', width=6, padx=10, justify=tk.RIGHT, state=tk.DISABLED )
        self.CreateLabel      ( ofa_via_frm  , 'via'   , side=tk.LEFT                                          )
        self.CreateUserEntry  ( ofa_via_frm  , 'viaofa', width=6, padx=10, justify=tk.RIGHT, state=tk.DISABLED )
        
        self.CreateCheckButton( ofa_frm, 'sac', anchor=tk.W )
        
        # same for count and viablity
        scv_swt_frm = tk.Frame(ofa_scv_swt_frm)
        scv_swt_frm.pack(anchor=tk.N)
        scv_frm = tk.Frame(scv_swt_frm)
        scv_frm.pack(anchor=tk.N, side=tk.LEFT)
        
        # self.CreateCheckButton( scv_frm, 'scv' )
        
        # synchronization with tilter
        # only give wait time for counting
        swt_frm = tk.Frame(scv_swt_frm)
        swt_frm.pack(anchor=tk.N)
        
        self.CreateCheckButton( swt_frm, 'swt', anchor=tk.W )
        self.CreateCheckButton( swt_frm, 'prc', anchor=tk.W )
        
        self.CreateLabel    ( swt_frm, 'swd', side=tk.LEFT, padx=2                                 )
        self.CreateUserEntry( swt_frm, 'swd', width=6, padx=2, justify=tk.RIGHT, state=tk.DISABLED )
        

        # enable user to change base timings
        # either mm:ss, ms or us
        # cbt_frm = tk.Frame(ofa_scv_swt_frm)
        # cbt_frm.pack()
        #
        # self.optm_opts['cbt'] = ['mm:ss', 'ms', 'us']
        # self.optm_vals['cbt'] = tk.StringVar(value='mm:ss')
        #
        # # trace wants a callback with nearly useless parameters, fixing with lambda.
        # self.optm_vals['cbt'].trace('w', lambda nm, idx, mode, key='cbt', var=self.optm_vals['cbt']: self.onComboChange(key, var))
        #
        # self.optm['cbt'] = tk.OptionMenu(cbt_frm, self.optm_vals['cbt'], *self.optm_opts['cbt'])
        # self.optm['cbt'].pack(anchor=tk.SE, pady=10)
        
        
        
        # create array with all the check boxes and input lines for all chambers   
        self.CreateSwitchingSchemeArray(self.frms['swsc'])
        
        
        
        
        
        ######################
        #   --- TILTER ---   #
        ######################
        self.lfrms['til'] = tk.LabelFrame(self.frms['swmc'], text='Tilter: ', font=('Helvetica', 12))
        self.lfrms['til'].pack(anchor=tk.N, padx=15, pady=15)
        
        self.CreateCheckButton( self.lfrms['til'], 'utr', anchor=tk.W, fill=tk.X )
        
        # label frame
        self.frms['till'] = tk.Frame(self.lfrms['til'])
        self.frms['till'].pack(side=tk.LEFT, fill=tk.X, padx=2, pady=10)
        # entry frame
        self.frms['tile'] = tk.Frame(self.lfrms['til'])
        self.frms['tile'].pack(side=tk.LEFT, fill=tk.X, padx=2, pady=10)
        
        self.tilterKeys     = ['pan','nan','pmo','nmo','ppa','npa']
        self.tilterDefaults = ['1','1','1','1','mm:ss','mm:ss']
        
        # create detection buttons and labels
        self.CreateLabels     ( self.frms['till'], self.tilterKeys, fill=tk.X, pady=1, padx=5                                           )
        self.CreateUserEntries( self.frms['tile'], self.tilterKeys, self.tilterDefaults, anchor=tk.W, pady=2, width=6, justify=tk.RIGHT )
        
        self.CreateButtons( self.lfrms['til'], ['stt', 'wtc', 'rtm', 'rts'], padx=5, pady=2, fill=tk.X  )
        
        
        
        
        ############################
        #   --- STORAGE MODE ---   #
        ############################
        self.lfrms['stm'] = tk.LabelFrame(self.frms['swmc'], text='Storage Mode: ', font=('Helvetica', 12))
        self.lfrms['stm'].pack(anchor=tk.NW, padx=15, pady=15)
        
        # change storage mode menu
        self.optm_opts['csm'] = ['File size', 'Record time', 'Tilter sync']
        self.optm_vals['csm'] = tk.StringVar(value=self.optm_opts['csm'][0])
        
        # trace wants a callback with nearly useless parameters, fixing with lambda.
        self.optm_vals['csm'].trace('w', lambda nm, idx, mode, key='csm', var=self.optm_vals['csm']: self.onComboChange(key, var))
        
        self.optm['csm'] = tk.OptionMenu(self.lfrms['stm'], self.optm_vals['csm'], *self.optm_opts['csm'])
        self.optm['csm'].pack(anchor=tk.CENTER, pady=10)
        
        self.CreateLabel    ( self.lfrms['stm'], 'stm', side=tk.LEFT                                    )
        self.CreateUserEntry( self.lfrms['stm'], 'stm', '10.0', width=6, justify=tk.RIGHT, side=tk.LEFT )
        self.CreateLabel    ( self.lfrms['stm'], 'unt'                                                  )
        
        # not in usage
        # debug messages are always printed to log
#        self.CreateCheckButton( self.lfrms['msc'], 'dbg', anchor=tk.W )
#        self.CreateCheckButton( self.lfrms['msc'], 'enn', anchor=tk.W )
        
        
        
        
        # core was initialized ... status was updated
        # in case device is connected later
        # or files/folders defined later
        # update is called on button click
        self.UpdateFileManagerLabels()
        
        self.UpdateDetectionLabels()
        
        self.UpdateCheckboxStates()
        
        
        
        StatusBar.__init__(self, master, 'Current streaming folder: ', 'Run time: ', 'Status: ')
        self.UpdateStatusBar(self.lbl_txts['stf'], '0:00:00', self.paraLyzerCore.hf2.GetRecordingString() )
        
        
        
        
        
        
        
### -------------------------------------------------------------------------------------------------------------------------------
    #######################################################################
    ###                       --- FUNCTIONS ---                         ###
    #######################################################################
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def PopObjectArgs(self, **kwargs):
        args = {}
        for com in ['text', 'width', 'height', 'state', 'command', 'justify', 'textvariable']:
            if com in kwargs.keys():
                args[com] = kwargs.pop(com)
        
        return kwargs, args
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def CreateButton(self, master, key, **kwargs):
        
        # remove certain items to not cause problems with pack
        kwargs, args = self.PopObjectArgs(**kwargs)
            
        self.btns[key] = tk.Button( master, text=self.btn_txts[key], **args )
        self.btns[key].configure( command=lambda key=key: self.onButtonClick(key) )
        self.btns[key].pack(**kwargs)
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def CreateButtons(self, master, keys, **kwargs):
        for key in keys:
            if key in self.btn_txts.keys():    
                self.CreateButton( master, key, **kwargs )
            else:
                raise Exception('%s not in self.btn_txts' % key)
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def CreateLabel(self, master, key, **kwargs):
        
        # remove certain items to not cause problems with pack
        kwargs, args = self.PopObjectArgs(**kwargs)
        
        self.lbls[key] = tk.Label( master, text=self.__lbl_txts__[key], **args )
        self.lbls[key].pack(**kwargs)
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def CreateLabels(self, master, keys, **kwargs):
        for key in keys:
            if key in self.__lbl_txts__.keys():
                self.CreateLabel(master, key, **kwargs)
            else:
                raise Exception('%s not in self._lbl_txts' % key)
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def CreateRadioButton(self, master, rbtn_parent, keys, default='', **kwargs):
        
        # if default was not given use first entry of list
        if default == '':
            default = keys[0]

        if default in keys:
            
            self.rbnt_vals[rbtn_parent] = tk.StringVar(value=default)
        
            for key in keys:
                if key in self.rbtn_txts.keys():
                    self.rbtns[key] = tk.Radiobutton( master, text=self.rbtn_txts[key] )
                    self.rbtns[key].configure(variable=self.rbnt_vals[rbtn_parent])
                    self.rbtns[key].configure(value=key)
                    self.rbtns[key].configure( command=lambda selected=self.rbnt_vals[rbtn_parent]: self.onRadioClick(selected.get()) )
                    self.rbtns[key].pack(**kwargs)
                else:
                    raise Exception('%s is not in self.rbtn_txts' % key)
            
            # default radio button selection
            self.rbtns[default].select()
            
            flags = {default:True}
            
            self.UpdateStreamFlags(**flags)
            
        else:
            raise Exception('%s is not in %s' % (key, keys))
        
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def CreateCheckButton(self, master, key, default=0, **kwargs):
        
        self.ckbtn_vals[key] = tk.IntVar(value=default)
        
        # remove certain items to not cause problems with pack
        kwargs, args = self.PopObjectArgs(**kwargs)
        
        # if no text was given try to find in global array
        if 'text' not in kwargs:
            if key in self.ckbtn_txts.keys():
                args['text'] = self.ckbtn_txts[key]
                
        self.ckbtns[key] = tk.Checkbutton( master, **args )
        self.ckbtns[key].configure( variable=self.ckbtn_vals[key] )
        self.ckbtns[key].configure( command=lambda key=key, state=self.ckbtn_vals[key]: self.onCheckClick(key, coreUtils.ToBool(state.get())) )
        self.ckbtns[key].pack(**kwargs)
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def CreateUserEntries(self, master, keys, defaults=[''], **kwargs):
        
        if len(defaults) == 1:
            defaults = defaults * len(keys)
        
        for key, default in zip(keys, defaults):
            self.CreateUserEntry(master, key, default, **kwargs)
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def CreateUserEntry(self, master, key, default='0.0', **kwargs):
        
        # remove certain items to not cause problems with pack
        kwargs, args = self.PopObjectArgs(**kwargs)
        
        state = tk.NORMAL
        # pop state and set later
        # to be able to write text to entry
        for k, v in args.items():
            if tk.DISABLED == v:
                state = args.pop(k)
                break
                
        # define entry
        self.entrs[key] = tk.Entry( master, **args)
        self.entrs[key].insert(0, default)
        self.entrs[key].configure(state=state)
        
        # bind three events to check the time
        self.entrs[key].bind('<Key>'     , lambda event, key=key: self.ValidateTime(event, key) )
        self.entrs[key].bind('<Return>'  , lambda event, key=key: self.onPressKey  (event, key) )
        self.entrs[key].bind('<FocusIn>' , lambda event, key=key: self.ValidateTime(event, key) )
        self.entrs[key].bind('<FocusOut>', lambda event, key=key: self.ValidateTime(event, key) )
        self.entrs[key].pack(**kwargs)
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def UpdateLabelText(self, key):
        
        if key in self.lbls.keys():
            if key == 'cfg':
                self.lbls[key].configure(text='Loaded from: \'%s\'' % self.lbl_txts[key])
            else:
                self.lbls[key].configure(text=self.lbl_txts[key])
            
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def UpdateDetectionLabels(self, key='all'):
        
        # change text according to detection status
        detectStatus = self.paraLyzerCore.GetDetectionStatus(key)
        
        # to simplify function structure pack bool into dictionary
        if key != 'all':
            detectStatus = {key:detectStatus}
            
        for key, val in detectStatus.items():
            # call update function to print new value
            if val:
                self.lbl_txts[key] = self.paraLyzerCore.GetComPortInfo(key)
                
            # take default value
            else:
                self.lbl_txts[key] = self.__lbl_txts__[key]
            
            self.UpdateLabelText(key)
            
        self.UpdateStreamFlags(**detectStatus)
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def UpdateFileManagerLabels(self):
        
        # change text accordingly if file or folder does not exist
        fileStatus = self.paraLyzerCore.GetFileStatus()
        for key, val in fileStatus.items():
            # and call update function to print new value
            if val:
                self.lbl_txts[key] = self.paraLyzerCore.GetConfig(key)
                
            # take default value
            else:
                self.lbl_txts[key] = self._lbl_txts[key]

            self.UpdateLabelText(key)
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def UpdateCheckboxStates(self):
        
        guiFlags = self.paraLyzerCore.GetGuiFlags()
        
#        testFlags = {}
#        try:
#            with open('./cfg/Config.pickle', 'rb') as f:
#                testFlags = pickle.load(f)
#        except FileNotFoundError:
#            pass
#        except EOFError:
#            pass
#        
#        print(testFlags)
        
        # change state of checkboxes according to loaded setup
        for key in self.ckbtns.keys():
            if key in guiFlags.keys():
                if guiFlags[key]:
                    self.ckbtns[key].select()
                else:
                    self.ckbtns[key].deselect()
            
#            # special treatment for debug mode, since keys in ckbtn list are only three letters
#            elif 'debugMode' in guiFlags.keys():
#                if guiFlags['debugMode']:
#                    self.ckbtns['dbg'].select()
#                else:
#                    self.ckbtns['dbg'].deselect()
                    
        self.UpdateStreamFlags(**guiFlags)
            
### -------------------------------------------------------------------------------------------------------------------------------
    
    def UpdateStreamFlags(self, **flags):
        
        # get new value from flag or use old one
        self.streamFlags['debugMode' ] = flags.get( 'debugMode', self.streamFlags['debugMode' ] )
        self.streamFlags['cnti']       = flags.get( 'std'      , self.streamFlags['cnti']       )
        self.streamFlags['viai']       = flags.get( 'std'      , self.streamFlags['viai']       )
        self.streamFlags['ard' ]       = flags.get( 'ard'      , self.streamFlags['ard' ]       )
        self.streamFlags['hf2' ]       = flags.get( 'hf2'      , self.streamFlags['hf2' ]       )
        self.streamFlags['til' ]       = flags.get( 'til'      , self.streamFlags['til' ]       )
            
### -------------------------------------------------------------------------------------------------------------------------------
    
    def UpdateEntryText(self, key, text):
    
        state = self.entrs[key]['state']
        
        # enable to be able to change text
        self.entrs[key].configure( state=tk.NORMAL )
        self.entrs[key].delete   ( 0, tk.END       )
        self.entrs[key].insert   ( 0, text         )
        self.entrs[key].configure( state=state     )
            
### -------------------------------------------------------------------------------------------------------------------------------
    
    def UpdateEntryTimeBase(self, var):
        
        newVal = var.get()
        
        for key in self.entrs.keys():
            if 'cnti' in key or 'viai' in key or 'cntofa' in key or 'viaofa' in key:
                self.UpdateEntryText(key, newVal)
            
### -------------------------------------------------------------------------------------------------------------------------------
    
    def UpdateEntryStates(self):
                
        for entr_key in ['cnti', 'viai', 'cntofa', 'viaofa', 'swd']:
            # get state for each entry and enable/disable accordingly
            if self.CheckEnableEntries(entr_key):
                state = tk.NORMAL
            else:
                state = tk.DISABLED
            
            for key in self.entrs.keys():
                if entr_key in key:
                    # change state accordingly
                    self.entrs[key].configure(state=state)
            
#            for key in self.ckbtns.keys():
#                if 'id' in key:
#                    self.UpdateEntryColors( key, self.ckbtn_vals[key].get() )
            
### -------------------------------------------------------------------------------------------------------------------------------
    
    def UpdateTilterEntries(self):
        
        # change text according to detection status
        detectStatus = self.paraLyzerCore.GetDetectionStatus()
        
        if detectStatus['til']:
            for key, val in self.paraLyzerCore.tilter.GetParameters().items():
                k = ''
                if key == 'A+':
                    k = 'pan'
                elif key == 'A-':
                    k = 'nan'
                elif key == 'M+':
                    k = 'pmo'
                elif key == 'M-':
                    k = 'nmo'
                elif key == 'P+':
                    k = 'ppa'
                elif key == 'P-':
                    k = 'npa'
                    
                try:
                    self.entrs[k].delete( 0, tk.END )
                    self.entrs[k].insert( 0, val    )
                except KeyError:
                    pass
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def ResetTilterEntries(self):
        
        for key, default in zip(self.tilterKeys, self.tilterDefaults):
            self.entrs[key].delete( 0, tk.END  )
            self.entrs[key].insert( 0, default )
            
### -------------------------------------------------------------------------------------------------------------------------------
    
    def UserDialog(self, key):
        
        if key == 'chc':
            
            title = 'Select file'
            filetypes = (("ChipConfig files","*.json"),("All files","*.*"))
            
        elif key == 'swc':
            
            title = 'Select file'
            filetypes = (("ChipConfig files","*.json"),("All files","*.*"))
            
        elif key == 'stf':
            
            title = 'Choose folder to stream files...'
        
        initFile = self.paraLyzerCore.GetConfig(key)
        initDir  = coreUtils.GetFolderFromFilePath( initFile )
        
        if key in ['chc', 'swc']:
            result = filedialog.askopenfilename( initialdir=initDir, title=title, filetypes=filetypes )
        elif key == 'stf':
            result = filedialog.askdirectory   ( initialdir=initDir, title=title                      )
        
        
        if coreUtils.IsAccessible(result) and not coreUtils.IsIdentical(result, initFile):
            relPath = coreUtils.GetRelativePath(result)
            if self.paraLyzerCore.UpdateConfig(key, relPath):
                self.lbl_txts[key] = relPath
                self.UpdateLabelText(key)
            
### -------------------------------------------------------------------------------------------------------------------------------
    
#    def UpdateEntryColors(self, key, state):
#        
#        # initial values for counter and viability timings
#        entrKey = key.replace('id','')
#        
#        # if checkbox is not checked don't set new timings
#        # color them accordingly
#        if state and key != 'scv':
#            # check status of check and radio boxes
#            # if still default change background color
#            for key in ['cnti', 'viai', 'cntofa', 'viaofa']:
#                if self.CheckEnableEntries(key):
#                    if key in ['cnti', 'viai']:
#                        tString = self.entrs[key+entrKey].get()
#                    elif key in ['cntofa', 'viaofa']:
#                        tString = self.entrs[key].get()
#                        
#        # state not checked
#        # reset colors
#        elif not state:
#            if 'id' in key:
#                self.entrs['cnti%s'%entrKey].configure( bg='SystemWindow' )
#                self.entrs['viai%s'%entrKey].configure( bg='SystemWindow' )
#            elif key in ['ofa', 'scv', 'swt']:
#                self.entrs['cntofa'].configure( bg='SystemWindow' )
#                self.entrs['viaofa'].configure( bg='SystemWindow' )
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def CreateSwitchingSchemeArray(self, master, numRow=3, numCol=5):
        
        # array of all check buttons with input mask
        for row in range(numRow):
                
            ckbtn_frm = tk.Frame(master)
            ckbtn_frm.pack(anchor=tk.W, padx=25)
        
            cnti_entr_frm = tk.Frame(master)
            cnti_entr_frm.pack(anchor=tk.W, pady=2)
            
            viai_entr_frm = tk.Frame(master)
            viai_entr_frm.pack(anchor=tk.W, pady=2)
            
            # labels for the two entry rows
            self.CreateLabels(cnti_entr_frm, ['cnt'], side=tk.LEFT)
            self.CreateLabels(viai_entr_frm, ['via'], side=tk.LEFT)
                
            for col in range(numCol):
                
                idx = row*numCol+col
                
                self.CreateCheckButton( ckbtn_frm    , 'id%s'%idx  , text='Ch %s-%s' % (row+1,col+1), side=tk.LEFT, fill=tk.X )
                self.CreateUserEntry  ( cnti_entr_frm, 'cnti%s'%idx, width=6, side=tk.LEFT, padx=11, justify=tk.RIGHT         )
                self.CreateUserEntry  ( viai_entr_frm, 'viai%s'%idx, width=6, side=tk.LEFT, padx=11, justify=tk.RIGHT         )
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def ValidateTime(self, event, key):
        
        expoChars = ('e','-','+')
    
        val = event.widget.get()
        
        # use generator construct to find key in list of keys since they additionally contain an index
        if any([k in key for k in ['cnti', 'viai', 'cntofa', 'viaofa']]):
            
            # try to convert to float
            try:
                float(val)
            except ValueError:
                # if it didn't work we should figure our if user wants to use exponential/scientific style
                # we still need to check if the characters occure multiple time and avoid that
                if not val.endswith(expoChars) or any([val.count(c)>1 for c in expoChars]):
                    event.widget.delete(len(val)-1, len(val))
            
#            timeBase = self.optm_vals['cbt'].get()
            
            # check for correct input
            # depending on time base use different patterns
#            if timeBase == 'mm:ss':
#                result = re.match('(^[0-9]{1,2}:[0-9]{1,2})|(^[0-9]{0,2}:?)', tVar).group()
#            elif timeBase == 'ms' or 'us':
#                result = re.match('^[0-9]{0,3}', tVar).group()
            
            # either print result to the entry box or delete it completely
#            if result != tVar:
#                event.widget.delete( 0, tk.END )
#                event.widget.insert( 0, result )
#            elif result == '':
#                event.widget.delete( 0, tk.END )
            
            # with focus reset bg color if it was highlighted before
            if event.type == '9' and event.widget.cget('bg') != 'SystemWindow':
                event.widget.configure(bg='SystemWindow')
        
            elif event.type == '10':
                #if no value was entered, set it to zero
                if len(val) == 0:
                    event.widget.delete( 0, tk.END )
                    event.widget.insert( 0, '0.0'  )
                        
                # check if seconds > 59 were entered...change
#                elif result.find(':') == -1:
#                    result = int(result)
#                    if result > 59:
#                        result = [1, result-60]
#                        event.widget.delete( 0, tk.END                           )
#                        event.widget.insert( 0, '%s:%s' % (result[0], result[1]) )
                        
                        
        elif key in ['pan', 'nan', 'pmo', 'nmo']:
            
            # try to convert to integer
            try:
                int(val)
            except ValueError:
                event.widget.delete(len(val)-1, len(val))
#            
#            if key == 'pmo':
#                result = re.match('', tVar).group()
#                
#                
#                print(re.findall(r'^[0-9]{5}$', tVar))
            
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def CheckEnableEntries(self, key):
        
        enable = False
        
        # read out current status of radio buttons
        rbtn_sel  = self.rbnt_vals['sws'].get()
        ofa_ckbtn = self.ckbtn_vals['ofa'].get()
        swt_ckbtn = self.ckbtn_vals['swt'].get()
        
        if 'cnti' in key:
            enable = ( ('via' or 'usr') not in rbtn_sel and ofa_ckbtn != 1 and swt_ckbtn != 1 )
        elif 'viai' in key:
            enable = ( ('cnt' or 'usr') not in rbtn_sel and ofa_ckbtn != 1 and swt_ckbtn != 1 )
        elif 'cntofa' in key:
            enable = ( ('via' or 'usr') not in rbtn_sel and (ofa_ckbtn == 1 or swt_ckbtn == 1) )
        elif 'viaofa' in key:
            enable = ( ('cnt' or 'usr') not in rbtn_sel and (ofa_ckbtn == 1 or swt_ckbtn == 1) )
        elif 'swd' in key:
            enable = swt_ckbtn
        
        return enable
        
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def GetTimeFromString(self, tStrings):
        
        tNum = {}
        
        for key, val in tStrings.items():
            mins, secs = coreUtils.GetMinSecFromString(val)
            tNum[key] = int((mins*60 + secs) * 1e6)
            
        return tNum
       
### -------------------------------------------------------------------------------------------------------------------------------
        
    def GetTimeFromUserEntry(self, entryId):
    
        tStrings = {}

        # go through categories and grab related time value
        for key in ['cnti', 'viai', 'cntofa', 'viaofa']:
            if self.CheckEnableEntries(key):
                if key in ['cnti', 'viai']:
                    val = self.entrs[key+entryId].get()
                elif key in ['cntofa', 'viaofa']:
                    val = self.entrs[key].get()
                    
                # in case counting and viability is needed, put them together
                if key in ['cnti', 'cntofa']:
                    tStrings['cnti'] = val
                elif key in ['viai', 'viaofa']:
                    tStrings['viai'] = val
                    
        return tStrings
        
### -------------------------------------------------------------------------------------------------------------------------------
        
    def UpdateStorageMode(self, var):
        
        if not self.paraLyzerCore.IsRunning():
        
            self.lbl_txts['stm'] = var
            
            if var == 'File size':
            
                self.entrs['stm'].configure(state=tk.NORMAL)
                self.lbl_txts['unt'] = 'MB'
                
                storageMode = 'fileSize'
                
                self.paraLyzerCore.hf2.SetStreamFileSize(float(self.entrs['stm'].get()))
                
            elif var == 'Record time':
                
                self.entrs['stm'].configure(state=tk.NORMAL)
                self.lbl_txts['unt'] = 'min'
                
                storageMode = 'recordTime'
                
                self.paraLyzerCore.hf2.SetStreamFileSize(float(self.entrs['stm'].get()))
            
            elif var == 'Tilter sync':
                
                self.entrs['stm'].configure(state=tk.DISABLED)
                self.lbl_txts['unt'] = ''
                
                storageMode = 'eventSync'
            
            else:
                Exception('Uknown error occured during storage mode change!')
            
            self.UpdateLabelText('stm')
            self.UpdateLabelText('unt')
            
            self.paraLyzerCore.hf2.SetStorageMode(storageMode)
            
            self.UpdateRightStatus('Storage mode updated.')
        
### -------------------------------------------------------------------------------------------------------------------------------
        
    def UpdateRecTime(self, sTime):
        
        while not self.stopTimeThread:
            
            now = datetime.now().replace(microsecond=0)
            
            self.UpdateLeftStatus ( self.paraLyzerCore.hf2.GetCurrentStreamFolder() )
            self.UpdateMidStatus  ( (now-sTime).__str__()                           )
            self.UpdateRightStatus( self.paraLyzerCore.hf2.GetRecordingString()     )
#            print(self.paraLyzerCore.arduino.comPort.read(self.paraLyzerCore.arduino.comPort.in_waiting))
            
            sleep(1)
        
### -------------------------------------------------------------------------------------------------------------------------------
        
    def UpdateELectrodePairs(self):
            
#        timeBase = self.optm_vals['cbt'].get()
        success  = True

        self.paraLyzerCore.arduino.UndefineAllElectrodePairs()
        
        # collect all selected electrode pairs and store them in class variable
        # NOTE: not all of them have to be send to Arduino at once, eg when sync with tilter is active
        for key in self.ckbtns.keys():
            # only take chamber checkboxes
            if 'id' in key:
                # if checkbox is selected
                if self.ckbtn_vals[key].get():
                    
                    # initial values for counter and viability timings
                    entryId = key.replace('id','')
                    
                    # get time string from particular user entry, depending on radio/check buttons
                    tStrings = self.GetTimeFromUserEntry(entryId)
                    interval = self.GetTimeFromString(tStrings)
                    
                    # process counting interval
                    if 'cnti' in interval.keys():
                        # always odd numbers are counting pairs
                        ePair = int(entryId)*2+1
                        # define new electrode pair with current setup
                        self.paraLyzerCore.arduino.DefineElectrodePair(ePair, interval['cnti'])
                        
                        # in case it's needed by SetupArduino for delay events
                        if self.ckbtn_vals['swt'].get():
                            self.streamFlags['switchDelay'] = float(self.entrs['swd'].get())
                        
                    # process viability interval
                    if 'viai' in interval.keys():
                        # always even numbers are viability pairs
                        ePair = int(entryId)*2
                        # define new electrode pair with current setup
                        self.paraLyzerCore.arduino.DefineElectrodePair(ePair, interval['viai'])
                        
                        # in case it's needed by SetupArduino for delay events
                        # NOTE: maybe use another user entry
                        if self.ckbtn_vals['swt'].get():
                            self.streamFlags['switchDelay'] = float(self.entrs['swd'].get())
                            
                        
        # check if values are correct
#        if not success:
#            messagebox.showerror('Error', 'Please enter a valid value in the highlighted fields.')
                    
        

        # try to start streaming
        # if failed pop-up an error
        if success and self.somethingsSelected:
            
            # get debug flag
#            self.streamFlags['dbg'] = self.ckbtn_vals['dbg'].get()
            
            # NOTE: do not use SetupArduino of arduino instance directly
            #       list of electrode pairs has to be prepared according to flags
            if not self.paraLyzerCore.arduino.SetupArduino(**self.streamFlags):
                messagebox.showerror('Error', 'Could not write setup to Arduino! Please check the connection.\nFor more information check the log file.')
                self.UpdateDetectionLabels()
                success = False
            # if setup was successful, reset flag for start procedure
            else:
                self.UpdateRightStatus('Arduino update successful.')
                self.ePairsChanged = False
        elif not self.somethingsSelected:
            messagebox.showinfo('Info', 'Please select at least one electrode pair!')
                
                
        return success
        
### -------------------------------------------------------------------------------------------------------------------------------
        
    def StartRunTimer(self):
        
        sT = datetime.now().replace(microsecond=0)
        
        self.runTimeThread  = threading.Thread(target=lambda sT=sT: self.UpdateRecTime(sT))
        self.stopTimeThread = False
        
        self.runTimeThread.start()
        
### -------------------------------------------------------------------------------------------------------------------------------
        
    def StopRunTimer(self):
        
        self.stopTimeThread = True
        sleep(50e-3)
        if self.runTimeThread:
            self.runTimeThread.join()
        
### -------------------------------------------------------------------------------------------------------------------------------
        
    def CheckError(self, error):
    
        if 'ard' in error.keys():
            messagebox.showerror('Arduino error!', 'Could not connect to Arduino. Recording aborted!')
        elif 'hf2' in error.keys():
            messagebox.showerror('HF2LI error!', 'Could not connect to HF2LI. Recording aborted!')
        elif 'til' in error.keys():
            messagebox.showerror('Tilter error!', 'Could not connect to inSphero tilter. Recording aborted!')
        else:
            messagebox.showerror('Unknown error!', 'Unknown error. Recording aborted!')
            
        
                                
        
        
### -------------------------------------------------------------------------------------------------------------------------------
    #######################################################################
    ###                         --- EVENTS ---                          ###
    #######################################################################    
### -------------------------------------------------------------------------------------------------------------------------------
    
    def onButtonClick(self, button):
        self.logger.debug('Clicked button: %s' % button)
        
        
        #####################
        # START/STOP BUTTON #
        #####################
        if button == 'sts':
            
            
            if self.btns['sts']['text'] == 'Start':
                
                if not self.somethingsSelected:
                
                    messagebox.showinfo('Nothing selected...', 'Could not start streaming. Please select at least one electrode pair.')
                    return
                    
                else:
                    if self.ePairsChanged:
                        result = messagebox.askyesnocancel('Setup changed!', 'Setup was changed after last update of Arduino! Do you want to update and start?')
                    
                    # no update necessary, just start
                    else:
                        result = False
                    
                    if result == True:
                        if self.UpdateELectrodePairs():
                            result = self.paraLyzerCore.StartMeas(**self.streamFlags)
                            if result == True:
                                self.StartRunTimer()
                                self.btns['sts'].configure(text='Stop')
                            else:
                                self.CheckError(result)
                                return
                                    
                                
                    elif result == False:
                        result = self.paraLyzerCore.StartMeas(**self.streamFlags)
                        if result == True:
                            self.StartRunTimer()
                            self.btns['sts'].configure(text='Stop')
                        else:
                            self.CheckError(result)
                            return
                        
                    elif result == None:
                        return
                
            else:
                
                self.StopRunTimer()
                
                result = self.paraLyzerCore.StopMeas(**self.streamFlags)
                        
                # get flags after recording
                status = self.paraLyzerCore.hf2.GetRecordFlags()
        
                self.UpdateMidStatus('0:00:00')
                self.UpdateRightStatus(self.paraLyzerCore.hf2.GetRecordingString())
                
                # throw error if something went wrong
                if status['dataloss']:
                    messagebox.showwarning('Warning', 'Dataloss was discovered during the last recording session!\nData might be corrupted!')
                elif status['invalidtimestamp']:
                    messagebox.showwarning('Warning', 'An invalid time stamp was received during the last recording session!\nData might be corrupted!')
                
                self.btns['sts'].configure(text='Start')
                

        ########################
        # FILE MANAGER BUTTONS #
        # SELECT FILES/FOLDERS #
        ########################
        elif button in ['chc', 'swc', 'stf']:
            
            self.UserDialog(button)
            
            
        #########################
        # DETECT DEVICE BUTTONS #
        #########################
        elif button in ['ard', 'hf2', 'til', 'cam']:
            
            self.paraLyzerCore.DetectDevices( button )
            self.UpdateDetectionLabels      ( button )
        
                
        ###############################
        # WRITE NEW VALUES TO ARDUINO #
        ###############################
        elif button == 'wac':
            
            self.UpdateELectrodePairs()
            
                    
                    
        #####################
        # START TILTER ONLY #
        #####################
        elif button == 'stt':
            if self.btns['stt']['text'] == 'Start' and self.ckbtn_vals['utr'].get():
                if self.paraLyzerCore.tilter.StartTilter():
                    self.btns['stt'].configure(text='Stop')
            elif self.btns['stt']['text'] == 'Stop' and self.ckbtn_vals['utr'].get():
                if self.paraLyzerCore.tilter.StopTilter():
                    self.btns['stt'].configure(text='Start')
                
                
                    
                    
        ##############################
        # WRITE NEW VALUES TO TILTER #
        ##############################
        elif button == 'wtc':
            
            if self.ckbtn_vals['utr'].get():
                
                # positive angle
                self.paraLyzerCore.tilter.SetValue( 'posAngle' , self.entrs['pan'].get() )
                # negative angle
                self.paraLyzerCore.tilter.SetValue( 'negAngle' , self.entrs['nan'].get() )
                # positive motion time
                self.paraLyzerCore.tilter.SetValue( 'posMotion', self.entrs['pmo'].get() )
                # negative motion time
                self.paraLyzerCore.tilter.SetValue( 'negMotion', self.entrs['nmo'].get() )
                # positive pause time mm:ss
                self.paraLyzerCore.tilter.SetValue( 'posPause' , self.entrs['ppa'].get() )
                # negative pause time mm:ss
                self.paraLyzerCore.tilter.SetValue( 'negPause' , self.entrs['npa'].get() )
                
                if not self.paraLyzerCore.tilter.WriteSetup():
                    messagebox.showerror('Error', 'Could not write setup to tilter! Please check the connection...')
                    self.UpdateDetectionLabels()
        
        
                
        #######################
        # RESET TILTER MEMORY #
        #######################
        elif button == 'rtm':
            
            if self.ckbtns['utr'].get():
                
                if not self.paraLyzerCore.tilter.ResetTilterSetup():
                    messagebox.showerror('Error', 'Could not reset tilter setup! Please check the connection...')
                    self.UpdateDetectionLabels()
                else:
                    self.ResetTilterEntries()
            
                    
                    
        ############################
        # READ TILTER SETUP ON APP #
        ############################
        elif button == 'rts':
            
            if self.ckbtn_vals['utr'].get():
                
                params = self.paraLyzerCore.tilter.GetParameters()
                
                for key, val in params.items():
                    if key == 'A+':
                        key = 'pan'
                    elif key == 'A-':
                        key = 'nan'
                    elif key == 'M+':
                        key = 'pmo'
                    elif key == 'M-':
                        key = 'nmo'
                    elif key == 'P+':
                        key = 'ppa'
                        val = coreUtils.GetStringFromMinSec(val)
                    elif key == 'P-':
                        key = 'npa'
                        val = coreUtils.GetStringFromMinSec(val)
                    
                    try:
                        self.entrs[key].delete( 0, tk.END )
                        self.entrs[key].insert( 0, val    )
                    except KeyError:
                        pass
                
                
### -------------------------------------------------------------------------------------------------------------------------------
    
    def onCheckClick(self, key, state):
        self.logger.debug('Clicked checkbutton \'%s\' state \'%s\'' % (key, state))
        
        # change state in config structure
#        self.paraLyzerCore.SetGuiFlag(key, state)
        
        
        # enable/disable debug
        # OR enable/disable one interval for both counting and viability
        # OR enable/disable sync with tilter
        # OR enable/disable dead time to save memory
        if key in ['dbg', 'scv', 'swt', 'prc', 'utr']:
            self.streamFlags[key] = state

            if key == 'dbg':
                self.paraLyzerCore.SetConfig('gui', 'dbg', state)
            elif key == 'scv':
                self.streamFlags['cnti'] = True
                self.streamFlags['viai'] = True
            elif key == 'swt':
                self.streamFlags['cnti'] = True
                self.streamFlags['viai'] = False
            elif key == 'prc':
                None
            
        # a certain chamber was selected
        elif 'id' in key:
            # inform start button procedure that there was a change
            self.ePairsChanged = True
            
            if state:
                # from here we are sure that something was selected
                # if it's valid we don't know yet - to be checked in UpdateELectrodePairs
                # to call SetupArduino() later...
                self.somethingsSelected = True
                
            # in case nothing's selected anymore reset variable
            else:
                reset = True
                # go through all checkbuttons
                for key in self.ckbtns.keys():
                    # only take chamber checkboxes
                    if 'id' in key:
                        # if checkbox is selected
                        if self.ckbtn_vals[key].get():
                            reset = False
                            break
                if reset:
                    self.somethingsSelected = False
                    
        # select all chambers
        elif key == 'sac':
            
            # inform start button procedure that there was a change
            self.ePairsChanged = True
            
            # toggle all chamber check buttons
            for key in self.ckbtns.keys():
                if 'id' in key:
                    if state:
                        self.ckbtns[key].select()
                    else:
                        self.ckbtns[key].deselect()
                    
            if state:
                # from here we are sure that something was selected
                # if it's valid we don't know yet - to be checked in UpdateELectrodePairs
                # to call SetupArduino() later...
                self.somethingsSelected = True
            else:
                self.somethingsSelected = False
                    
        # enable or disable entries according to all check boxes and radio buttons
        self.UpdateEntryStates()
                
### -------------------------------------------------------------------------------------------------------------------------------
    
    def onRadioClick(self, selected):
        self.logger.debug('Clicked radiobutton \'%s\'' % selected)
        
        # enable or disable entries according to all check boxes and radio buttons
        self.UpdateEntryStates()
        
        if selected == 'std':
            self.streamFlags['cnti'] = True
            self.streamFlags['viai'] = True
        elif selected == 'cnt':
            self.streamFlags['cnti'] = True
            self.streamFlags['viai'] = False
        elif selected == 'via':
            self.streamFlags['cnti'] = False
            self.streamFlags['viai'] = True
                
### -------------------------------------------------------------------------------------------------------------------------------
    
    def onComboChange(self, key, var):
        self.logger.debug('Combo box \'%s\' was changed to \'%s\'' % (key, var.get()))
        
        # change storage mode
        if key == 'csm':
            self.UpdateStorageMode(var.get())
                
### -------------------------------------------------------------------------------------------------------------------------------
    
    def onPressKey(self, event, key):
        
        if key == 'stm':
            self.UpdateStorageMode(self.optm_vals['csm'].get())
        
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def onClose(self):
        
        if self.paraLyzerCore.IsRunning():
            title = 'Warning'
            msg   = 'Recording is currently running!\nDo you really want to quit?'
        else:
            title = 'Quit'
            msg   = 'Do you really wish to quit?'
        
        if messagebox.askokcancel(title, msg):
            
#            try:
#                with open('./cfg/Config.pickle', 'wb') as f:
#                    pickle.dump(self.ckbtn_vals, f)
#            except TypeError:
#                pass

            # stop timer first
            self.StopRunTimer()
            if self.paraLyzerCore.IsRunning():
                self.paraLyzerCore.StopMeas(**self.streamFlags)
                
            # write gui flags
#            self.paraLyzerCore.UpdateConfigFile()
            
            # call shut down function to clean up open handles
            self.paraLyzerCore.__del__()
            
            Logger.__del__(self)
            
            # close GUI
            self.master.destroy()
        
        

            
            
##############################################################################
##############################################################################
##############################################################################
###                             MAIN SECTION                               ###
##############################################################################
##############################################################################
##############################################################################


if __name__ == '__main__':
    
    master = tk.Tk()
    
    # initialize window
    ParaLyzerApp(master)
    
    # show window
    master.mainloop()

# in case somebody wants to kill window with quit()
# otherwise window will freeze
#myParaLyzer.destroy()