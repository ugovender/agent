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
import subprocess

def load_library(name):
    retlib = None
    if os.path.exists("native/" + name):
        retlib  = ctypes.CDLL("native/" + name)
    else: 
        #Develop Mode
        if agent.is_os_32bit():
            retlib  = ctypes.CDLL("native_linux_x86_32/" + name)
        elif agent.is_os_64bit():
            retlib  = ctypes.CDLL("native_linux_x86_64/" + name)
    return retlib

def unload_library(olib):
    import _ctypes
    _ctypes.dlclose(olib._handle)
    del olib

'''

del olib
    olib.dlclose(olib._handle)
while isLoaded('./mylib.so'):
    dlclose(handle)

It's so unclean that I only checked it works using:

def isLoaded(lib):
   libp = os.path.abspath(lib)
   ret = os.system("lsof -p %d | grep %s > /dev/null" % (os.getpid(), libp))
   return (ret == 0)

def dlclose(handle)
   libdl = ctypes.CDLL("libdl.so")
   libdl.dlclose(handle)
'''
    
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
    
        
    def fix_file_permissions(self,operation,path,path_template=None):
        apppath=path
        if apppath.endswith(os.sep):
            apppath=apppath[0:len(apppath)-1]
        apppath_template=path_template
        if apppath_template is not None:
            if apppath_template.endswith(os.sep):
                apppath_template=apppath_template[0:len(apppath_template)-1]
        
        if operation=="CREATE_DIRECTORY":
            apppath_template=os.path.dirname(path)    
            stat_info = os.stat(apppath_template)
            mode = stat.S_IMODE(stat_info.st_mode)
            os.chmod(path,mode)
            os.chown(path, stat_info.st_uid, stat_info.st_gid)
        elif operation=="CREATE_FILE":
            apppath_template=os.path.dirname(path)    
            stat_info = os.stat(apppath_template)
            mode = stat.S_IMODE(stat_info.st_mode)
            os.chmod(path, ((mode & ~stat.S_IXUSR) & ~stat.S_IXGRP) & ~stat.S_IXOTH)
            os.chown(path, stat_info.st_uid, stat_info.st_gid)
        elif operation=="COPY_DIRECTORY" or operation=="COPY_FILE":
            if apppath_template is not None:
                stat_info = os.stat(apppath_template)
                mode = stat.S_IMODE(stat_info.st_mode)
                os.chmod(path,mode)
                stat_info = os.stat(os.path.dirname(path)) #PRENDE IL GRUPPO E L'UTENTE DELLA CARTELLA PADRE 
                os.chown(path, stat_info.st_uid, stat_info.st_gid)
        elif operation=="MOVE_DIRECTORY" or operation=="MOVE_FILE":
            if apppath_template is not None:
                stat_info = os.stat(apppath_template)
                mode = stat.S_IMODE(stat_info.st_mode)
                os.chmod(path,mode)
                os.chown(path, stat_info.st_uid, stat_info.st_gid)
        
    def is_gui(self):
        try:
            appout = subprocess.Popen("ps ax -ww | grep 'X.*-auth .*'", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate() 
            lines = appout[0].splitlines()
            for l in lines:
                if 'X.*-auth .*' not in l:
                    return True
        except:
            None
        return False
    
    