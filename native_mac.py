# -*- coding: utf-8 -*-

'''
This Source Code Form is subject to the terms of the Mozilla
Public License, v. 2.0. If a copy of the MPL was not distributed
with this file, You can obtain one at http://mozilla.org/MPL/2.0/.
'''

import os
import ctypes
import agent
import stat

def load_library(name):
    retlib = None
    if os.path.exists("native/" + name):
        retlib  = ctypes.CDLL("native/" + name)
    else: 
        #Develop Mode
        if agent.is_os_32bit():
            retlib  = ctypes.CDLL("native_mac_x86_32/" + name)
        elif agent.is_os_64bit():
            retlib  = ctypes.CDLL("native_mac_x86_64/" + name)
    return retlib

def unload_library(olib):
    import _ctypes
    _ctypes.dlclose(olib._handle)
    del olib
    
class Main():
    
    def __init__(self):
        None
    
    def load_library(self):
        None
    
    def unload_library(self):
        None
    
    def task_kill(self, pid) :
        try:
            os.kill(pid, -9)
        except OSError:
            return False
        return True
    
    def is_task_running(self, pid):
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True
    
    def set_file_permission_everyone(self,f):
        os.chmod(f, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH)
    
    def fix_file_permissions(self,operation,path,path_src=None):
        apppath=path
        if apppath.endswith(os.sep):
            apppath=apppath[0:len(apppath)-1]
        apppath_src=path_src
        if apppath_src is not None:
            if apppath_src.endswith(os.sep):
                apppath_src=apppath_src[0:len(apppath_src)-1]
        else:
            apppath_src=os.path.dirname(path)    
        stat_info = os.stat(apppath_src)
        mode = stat.S_IMODE(stat_info.st_mode)
        if operation=="CREATE_DIRECTORY":
            os.chmod(path,mode)
            os.chown(path, stat_info.st_uid, stat_info.st_gid)
        elif operation=="CREATE_FILE":
            os.chmod(path, ((mode & ~stat.S_IXUSR) & ~stat.S_IXGRP) & ~stat.S_IXOTH)
            os.chown(path, stat_info.st_uid, stat_info.st_gid)
        elif operation=="COPY_DIRECTORY" or operation=="COPY_FILE":
            os.chmod(path,mode)
            stat_info = os.stat(os.path.dirname(path)) #PRENDE IL GRUPPO E L'UTENTE DELLA CARTELLA PADRE 
            os.chown(path, stat_info.st_uid, stat_info.st_gid)
        elif operation=="MOVE_DIRECTORY" or operation=="MOVE_FILE":
            os.chmod(path,mode)
            os.chown(path, stat_info.st_uid, stat_info.st_gid)
    
    def is_gui(self):
        return True
 