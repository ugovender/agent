# -*- coding: utf-8 -*-

'''
This Source Code Form is subject to the terms of the Mozilla
Public License, v. 2.0. If a copy of the MPL was not distributed
with this file, You can obtain one at http://mozilla.org/MPL/2.0/.
'''

import ctypes
import os
import platform
import agent


def load_library(name):
    retlib = None
    if os.path.exists("native\\" + name):
        retlib = ctypes.CDLL("native\\" + name)
    else: 
        #Develop Mode
        if agent.is_os_32bit():
            retlib = ctypes.CDLL("native_win_x86_32\\" + name)
        elif agent.is_os_64bit():
            retlib = ctypes.CDLL("native_win_x86_64\\" + name)
    return retlib;

def unload_library(olib):
    import _ctypes
    _ctypes.FreeLibrary(olib._handle)
    del olib

class Main():
        
    def __init__(self):
        self._dwaglib=None

    def load_library(self):
        if self._dwaglib is None:
            self._dwaglib = load_library("dwaglib.dll");
    
    def unload_library(self):
        unload_library(self._dwaglib)
        self._dwaglib=None

    def task_kill(self, pid) :
        bret = self._dwaglib.taskKill(pid)
        return bret==1
    
    def is_task_running(self, pid):
        bret=self._dwaglib.isTaskRunning(pid);
        return bret==1
    
    def set_file_permission_everyone(self,file):
        self._dwaglib.setFilePermissionEveryone(file)    
    
    def fix_file_permissions(self,operation,path,path_src=None):
        None
               
    def is_gui(self):
        return True 