# -*- coding: utf-8 -*-

'''
This Source Code Form is subject to the terms of the Mozilla
Public License, v. 2.0. If a copy of the MPL was not distributed
with this file, You can obtain one at http://mozilla.org/MPL/2.0/.
'''

import os
import subprocess
import zipfile
import hashlib
import json
import shutil
import ctypes
import time
import sys
import resources
import user_interface
import communication
import stat
import codecs
import platform
import tempfile
import agent_status_config
import gdi
import importlib
import zlib
import base64
import sharedmem

_MAIN_URL = "https://www.dwservice.net/"
_MAIN_URL_QA = "https://qa.dwservice.net:7742/"
_MAIN_URL_SVIL = "https://svil.dwservice.net:7732/dws_site/"
_SERVICE_NAME=u"DWAgent"
_NATIVE_PATH = 'native'
_RUNTIME_PATH = 'runtime'


def get_native():
    if gdi.is_windows():
        return NativeWindow()
    elif gdi.is_linux():
        return NativeLinux()
    elif gdi.is_mac():
        return NativeMac()
        
def stop_monitor(installpath):
    try:
        stopfilename = installpath + os.sep + "monitor.stop"
        if not os.path.exists(stopfilename):
            stopfile= open(stopfilename, "w")
            stopfile.close()
        time.sleep(5) #Attende in modo che si chiudono i monitor
        os.remove(stopfilename) 
    except:
            None

class NativeLinux:
    def __init__(self):
        self._current_path=None
        self._install_path=None
        self._etc_path = "/etc/dwagent"
    
    def set_current_path(self, pth):
        self._current_path=pth
    
    def set_install_path(self, pth):
        self._install_path=pth
        
    def set_install_log(self, log):
        self._install_log=log
        
    def get_proposal_path(self):
        return '/usr/share/dwagent' 
    
    def get_install_path(self) :
        if os.path.exists(self._etc_path):
            f = open(self._etc_path)
            try:
                ar = json.loads(f.read())
                pth = ar['path']
                if os.path.exists(pth):
                    return pth
            finally:
                f.close()
        return  None
    
    def is_task_running(self, pid):
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True
    
    def check_init_run(self):
        return None         
     
    def check_init_install(self):
        if os.geteuid() != 0: #DEVE ESSERE EUID
            return resources.get_message("linuxRootPrivileges")
        return None
    
    def check_init_uninstall(self):
        if os.geteuid() != 0: #DEVE ESSERE EUID
            return resources.get_message("linuxRootPrivileges")
        return None

    def stop_service(self):
        ret =subprocess.call(self._install_path + os.sep + "native" + os.sep + "dwagsvc stop", shell=True, stdout=self._install_log, stderr=subprocess.STDOUT)
        self._install_log.flush()
        return ret==0
    
    def start_service(self):
        ret = subprocess.call(self._install_path + os.sep + "native" + os.sep + "dwagsvc start", shell=True, stdout=self._install_log, stderr=subprocess.STDOUT)
        self._install_log.flush()
        return ret==0
    
    def replace_key_file(self, path,  key,  val):
        fin = open(path, "r")
        data = fin.read()
        fin.close()
        fout = open(path, "w")
        fout.write(data.replace(key,val))
        fout.close()
        
    def prepare_file_service(self, pth):
        #Service
        fdwagsvc=pth + os.sep + "dwagsvc"
        self.replace_key_file(fdwagsvc, "@PATH_DWA@",  self._install_path)
        os.chmod(fdwagsvc,  stat.S_IRWXU + stat.S_IRGRP + stat.S_IROTH)
        fdwagent=pth + os.sep + "dwagent.service"
        self.replace_key_file(fdwagent, "@PATH_DWA@",  self._install_path)
        os.chmod(fdwagent,  stat.S_IRUSR + stat.S_IWUSR + stat.S_IRGRP + stat.S_IROTH)
    
    def prepare_file_sh(self, pth):
        #DWAgent
        appf=pth + os.sep + "dwagent"
        self.replace_key_file(appf, "@PATH_DWA@",  self._install_path)
        os.chmod(appf,  stat.S_IRWXU + stat.S_IRGRP +  stat.S_IXGRP + stat.S_IROTH + stat.S_IXOTH)
        
        #DWAgent
        appf=pth + os.sep + "configure"
        self.replace_key_file(appf, "@PATH_DWA@",  self._install_path)
        os.chmod(appf,  stat.S_IRWXU + stat.S_IRGRP +  stat.S_IXGRP + stat.S_IROTH + stat.S_IXOTH)
        
        #DWAgent
        appf=pth + os.sep + "uninstall"
        self.replace_key_file(appf, "@PATH_DWA@",  self._install_path)
        os.chmod(appf,  stat.S_IRWXU + stat.S_IRGRP +  stat.S_IXGRP + stat.S_IROTH + stat.S_IXOTH)
        
        #Menu
        fmenuconf=pth + os.sep + "dwagent.desktop"
        if os.path.exists(fmenuconf):
            self.replace_key_file(fmenuconf, "@PATH_DWA@",  self._install_path)
            os.chmod(fmenuconf,  stat.S_IRWXU + stat.S_IRGRP + stat.S_IRWXO)
        
    
    #LO USA ANCHE agent.py
    def prepare_file_monitor(self, pth):
        appf=pth + os.sep + "systray"
        if os.path.exists(appf):
            self.replace_key_file(appf, "@PATH_DWA@",  self._install_path)
            os.chmod(appf,  stat.S_IRWXU + stat.S_IRGRP +  stat.S_IXGRP + stat.S_IROTH + stat.S_IXOTH)
        
        fmenusystray=pth + os.sep + "systray.desktop"
        if os.path.exists(fmenusystray):
            self.replace_key_file(fmenusystray, "@PATH_DWA@",  self._install_path)
            os.chmod(fmenusystray,  stat.S_IRWXU + stat.S_IRGRP + stat.S_IRWXO)
    
    def prepare_file(self):
        self.prepare_file_service(self._install_path + os.sep + "native")
        self.prepare_file_sh(self._install_path + os.sep + "native")
        self.prepare_file_monitor(self._install_path + os.sep + "native")
    
    def prepare_file_runonfly(self):
        None
    
    def start_runonfly(self):
        libenv = os.environ
        libenv["LD_LIBRARY_PATH"]=os.path.abspath(self._current_path + os.sep + u"runtime" + os.sep + u"lib")
        subprocess.Popen([sys.executable, u'agent.pyc', u'-runonfly', u'-filelog'], env=libenv);

    def install_service(self):
        ret = subprocess.call(self._install_path + os.sep + "native" + os.sep + "dwagsvc install", shell=True, stdout=self._install_log, stderr=subprocess.STDOUT)
        self._install_log.flush()
        return ret==0
    
    def delete_service(self):
        ret = subprocess.call(self._install_path + os.sep + "native" + os.sep + "dwagsvc delete", shell=True, stdout=self._install_log, stderr=subprocess.STDOUT)
        self._install_log.flush()
        return ret==0
    
    def install_auto_run_monitor(self):
        try:
            pautos = "/etc/xdg/autostart"
            shutil.copy2(self._install_path + os.sep + "native" + os.sep + "systray.desktop", pautos + os.sep + "dwagent_systray.desktop")
            os.chmod(pautos + os.sep + "dwagent_systray.desktop",  stat.S_IRWXU + stat.S_IRGRP + stat.S_IRWXO)
            #SI DEVE LANCIARE CON L'UTENTE CONNESSO A X
            #Esegue il monitor
            #os.system(self._install_path + os.sep + "native" + os.sep + "dwaglnc systray &")
        except:
            None
        return True
    
    def remove_auto_run_monitor(self):
        try:
            fnm = "/etc/xdg/autostart/dwagent_systray.desktop"
            if os.path.exists(fnm):
                os.remove(fnm)
        except:
            None
        return True
    
    def install_extra(self):
        return True
    
    def install_shortcuts(self):
        try:
            #Crea MENU
            subprocess.call(self._install_path + os.sep + "native" + os.sep + "dwagsvc install_shortcuts", shell=True, stdout=self._install_log, stderr=subprocess.STDOUT)
            self._install_log.flush()
            
            #CREA /etc/dwagent
            if os.path.exists(self._etc_path):
                os.remove(self._etc_path)
            ar = {'path': self._install_path}
            s = json.dumps(ar, sort_keys=True, indent=1)
            f = open(self._etc_path, 'wb')
            f.write(s)
            f.close()
            return True
        except:
            return False
        
        
    def remove_shortcuts(self) :
        try:
            #RIMUOVE /etc/dwagent
            if os.path.exists(self._etc_path):
                os.remove(self._etc_path)
                
            #RIMUOVE MENU
            subprocess.call(self._install_path + os.sep + "native" + os.sep + "dwagsvc uninstall_shortcuts", shell=True, stdout=self._install_log, stderr=subprocess.STDOUT)
            self._install_log.flush()
        
            return True
        except:
            return False

class NativeMac:
    def __init__(self):
        self._current_path=None
        self._install_path=None
        self._lncdmn_path = "/Library/LaunchDaemons/net.dwservice.agent.plist"

    def set_current_path(self, pth):
        self._current_path=pth

    def set_install_path(self, pth):
        self._install_path=pth
        
    def set_install_log(self, log):
        self._install_log=log
        
    def get_proposal_path(self):
        return '/Library/DWAgent' 
    
    def get_install_path(self) :
        #Verificare la cartella dei servizi
        if os.path.exists(self._lncdmn_path) and os.path.islink(self._lncdmn_path):
            return os.path.dirname(os.path.dirname(os.path.realpath(self._lncdmn_path)))
        
        #COMPATIBILITA CON INSTALLAZIONI PRECEDENTI
        oldlncdmn_path = "/System/Library/LaunchDaemons/org.dwservice.agent.plist"
        if os.path.exists(oldlncdmn_path) and os.path.islink(oldlncdmn_path):
            return os.path.dirname(os.path.dirname(os.path.realpath(oldlncdmn_path)))
        
        return  None             
    
    def is_task_running(self, pid):
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True
    
    def check_init_run(self):
        return None
    
    def check_init_install(self):
        if os.geteuid() != 0: #DEVE ESSERE EUID
            f = open("runasadmin.install", 'wb')
            f.close()
            raise SystemExit
        return None
    
    def check_init_uninstall(self):
        if os.geteuid() != 0: #DEVE ESSERE EUID
            return resources.get_message("linuxRootPrivileges")
        return None

    def stop_service(self):
        ret =subprocess.call(self._install_path + os.sep + "native" + os.sep + "dwagsvc stop", shell=True, stdout=self._install_log, stderr=subprocess.STDOUT)
        self._install_log.flush()
        return ret==0
    
    def start_service(self):
        ret = subprocess.call(self._install_path + os.sep + "native" + os.sep + "dwagsvc start", shell=True, stdout=self._install_log, stderr=subprocess.STDOUT)
        self._install_log.flush()
        return ret==0
    
    def replace_key_file(self, path, enc,  key,  val):
        import codecs
        #fin = open(path, "rb")
        fin=codecs.open(path,"r", enc)
        data = fin.read()
        fin.close()
        #fout = open(path, "wb")
        fout=codecs.open(path,"w", enc)
        fout.write(data.replace(key,val))
        fout.close()
            
    def prepare_file_service(self, pth):
        #Service
        fapp=pth + os.sep + "dwagsvc"
        self.replace_key_file(fapp, "us-ascii", "@PATH_DWA@",  self._install_path)
        os.chmod(fapp,  stat.S_IRWXU + stat.S_IRGRP + stat.S_IROTH)
        
        fapp=pth + os.sep + "dwagent.plist"
        self.replace_key_file(fapp, "us-ascii", "@PATH_DWA@",  self._install_path)
        os.chmod(fapp,  stat.S_IRUSR + stat.S_IWUSR + stat.S_IRGRP + stat.S_IROTH)
    
    def prepare_file_app(self, pth):
        
        
        shutil.copytree(pth + "/DWAgent.app",pth + "/Configure.app")
        shutil.copytree(pth + "/DWAgent.app",pth + "/Uninstall.app")
                
        os.chmod(pth + "/DWAgent.app/Contents/MacOS/DWAgent",  stat.S_IRUSR + stat.S_IWUSR + stat.S_IXUSR + stat.S_IRGRP + stat.S_IXGRP + stat.S_IROTH + stat.S_IXOTH)           
        self.replace_key_file(pth + "/DWAgent.app/Contents/Info.plist", "us-ascii", "@EXE_NAME@" ,  "DWAgent")
        self.replace_key_file(pth + "/DWAgent.app/Contents/MacOS/DWAgent", "us-ascii","@MOD_DWA@",  "monitor")
        self.replace_key_file(pth + "/DWAgent.app/Contents/MacOS/DWAgent", "us-ascii","@PATH_DWA@",  self._install_path)
        
        shutil.move(pth + "/Configure.app/Contents/MacOS/DWAgent",  pth + "/Configure.app/Contents/MacOS/Configure")
        os.chmod(pth + "/Configure.app/Contents/MacOS/Configure",  stat.S_IRUSR + stat.S_IWUSR + stat.S_IXUSR + stat.S_IRGRP + stat.S_IXGRP + stat.S_IROTH + stat.S_IXOTH)
        self.replace_key_file(pth + "/Configure.app/Contents/Info.plist", "us-ascii", "@EXE_NAME@" ,  "Configure")
        self.replace_key_file(pth + "/Configure.app/Contents/MacOS/Configure", "us-ascii","@MOD_DWA@",  "configure")
        self.replace_key_file(pth + "/Configure.app/Contents/MacOS/Configure", "us-ascii","@PATH_DWA@",  self._install_path)
        
        shutil.move(pth + "/Uninstall.app/Contents/MacOS/DWAgent",  pth + "/Uninstall.app/Contents/MacOS/Uninstall")
        os.chmod(pth + "/Uninstall.app/Contents/MacOS/Uninstall",  stat.S_IRUSR + stat.S_IWUSR + stat.S_IXUSR + stat.S_IRGRP + stat.S_IXGRP + stat.S_IROTH + stat.S_IXOTH)
        self.replace_key_file(pth + "/Uninstall.app/Contents/Info.plist", "us-ascii", "@EXE_NAME@" ,  "Uninstall")
        self.replace_key_file(pth + "/Uninstall.app/Contents/MacOS/Uninstall", "us-ascii","@MOD_DWA@",  "uninstall")
        self.replace_key_file(pth + "/Uninstall.app/Contents/MacOS/Uninstall", "us-ascii","@PATH_DWA@",  self._install_path)
        
    
    def prepare_file_monitor(self, pth):
        None
        '''fdwagtray=pth + os.sep + "dwagtray"
        self.replace_key_file(fdwagtray, "@PATH_DWA@",  self._install_path)
        os.chmod(fdwagtray,  stat.S_IRWXU + stat.S_IRGRP + stat.S_IROTH + stat.S_IXOTH)
        fmenusystray=pth + os.sep + "systray.plist"
        if os.path.exists(fmenusystray):
            self.replace_key_file(fmenusystray, "@PATH_DWA@",  self._install_path)
            os.chmod(fmenusystray,  stat.S_IRWXU + stat.S_IRGRP + stat.S_IRWXO)'''
    
    def prepare_file(self):
        self.prepare_file_service(self._install_path + os.sep + "native")
        self.prepare_file_app(self._install_path + os.sep + "native")
        self.prepare_file_monitor(self._install_path + os.sep + "native")
    
    def prepare_file_runonfly(self):
        None

    def start_runonfly(self):
        libenv = os.environ
        libenv["LD_LIBRARY_PATH"]=os.path.abspath(self._current_path + os.sep + u"runtime" + os.sep + u"lib")
        subprocess.Popen([sys.executable, u'agent.pyc', u'-runonfly', u'-filelog'], env=libenv);

    def install_service(self):
        ret = subprocess.call(self._install_path + os.sep + "native" + os.sep + "dwagsvc install", shell=True, stdout=self._install_log, stderr=subprocess.STDOUT)
        self._install_log.flush()
        return ret==0
    
    def delete_service(self):
        ret = subprocess.call(self._install_path + os.sep + "native" + os.sep + "dwagsvc delete", shell=True, stdout=self._install_log, stderr=subprocess.STDOUT)
        self._install_log.flush()
        return ret==0
    
    def install_auto_run_monitor(self):
        #ret = subprocess.call(self._install_path + os.sep + "native" + os.sep + "dwagtray install", shell=True, stdout=self._install_log, stderr=subprocess.STDOUT)
        #self._install_log.flush()
        #return ret==0
        return True
    
    def remove_auto_run_monitor(self):
        #ret = subprocess.call(self._install_path + os.sep + "native" + os.sep + "dwagtray delete", shell=True, stdout=self._install_log, stderr=subprocess.STDOUT)
        #self._install_log.flush()
        #return ret==0
        return True
    
    def install_extra(self):
        return True
    
    def install_shortcuts(self):
        try:
            pathsrc = self._install_path + os.sep + "native/"
            pathdst = "/Applications/"
            if os.path.exists(pathdst):
                shutil.copytree(pathsrc+"DWAgent.app", pathdst+"DWAgent.app", symlinks=True)
            return True
        except:
            return False
        
        
    def remove_shortcuts(self) :
        try:
            pathsrc = "/Applications/DWAgent.app"
            if os.path.exists(pathsrc):
                shutil.rmtree(pathsrc)
            return True
        except:
            return False

class NativeWindow:
    def __init__(self):
        self._current_path=None
        self._install_path=None
    
    def set_current_path(self, pth):
        self._current_path=pth
    
    def set_install_path(self, pth):
        self._install_path=pth
        
    def set_install_log(self, log):
        None
        #self._install_log=log

    def get_proposal_path(self):
        return os.environ["ProgramFiles"] + os.sep + "DWAgent"
    
    def get_install_path(self) :
        try:
            import _winreg 
            keyVal = u"Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\" + _SERVICE_NAME
            key=_winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, keyVal)#, 0, _winreg.KEY_READ)
            sret = _winreg.QueryValueEx(key, "InstallLocation")
            _winreg.CloseKey(key)
            #if os.path.exists(sret[0]): //VERIFICA SE POI NON VA IN ERRORE NEL CASO TROVA LA CHIAVE DI REGISTRO
            return sret[0]
        except: 
            return None
    
    def is_task_running(self, pid):
        return gdi.is_windows_task_running(pid)
    
    def check_init_run(self):
        if gdi.is_windows_user_in_admin_group():
            if gdi.is_windows_run_as_admin():
                try:
                    if gdi.is_windows_process_elevated():
                        return None
                    else:
                        f = open("runasadmin.install", 'wb')
                        f.close()
                        raise SystemExit
                except:
                    return None #XP
            else:
                f = open("runasadmin.run", 'wb')
                f.close()
                raise SystemExit
        else:
            return None
    
    def check_init_install(self):
        if gdi.is_windows_user_in_admin_group() and gdi.is_windows_run_as_admin():
            try:
                if gdi.is_windows_process_elevated():
                    return None
                else:
                    f = open("runasadmin.install", 'wb')
                    f.close()
                    raise SystemExit
            except:
                return None #XP
        else:
            f = open("runasadmin.install", 'wb')
            f.close()
            raise SystemExit
        
    
    def check_init_uninstall(self):
        if gdi.is_windows_user_in_admin_group() and gdi.is_windows_run_as_admin():
            try:
                if gdi.is_windows_process_elevated():
                    return None
                else:
                    return resources.get_message("windowsAdminPrivileges")
            except:
                return None #XP
        else:
            return resources.get_message("windowsAdminPrivileges")
        
    
    def stop_service(self):
        cmd=u'"' + self._install_path + os.sep + u'native' + os.sep + u'dwagsvc.exe" stopService'
        appout = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate() 
        lines = appout[0].splitlines()
        for l in lines:
            if l=='OK':
                return True
        return False
    
    def start_service(self):
        cmd=u'"' + self._install_path + os.sep + u'native' + os.sep + u'dwagsvc.exe" startService'
        appout = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate() 
        lines = appout[0].splitlines()
        for l in lines:
            if l=='OK':
                return True
        return False
    
    def prepare_file(self):
        #Scrive service.properties
        pth=self._install_path
        arf = []
        arf.append(u''.join([u"serviceName=",_SERVICE_NAME,u"\r\n"]))
        arf.append(u''.join(["pythonPath=",  pth, os.sep, u"runtime", os.sep, u"dwagent.exe", u"\r\n"]))
        arf.append(u"parameters=agent.pyc -filelog")
        f=codecs.open(pth + os.sep + 'native' + os.sep + 'service.properties', 'w', "CP" + str(ctypes.windll.kernel32.GetACP()))
        f.write(u''.join(arf))
        f.close()
    
    def prepare_file_runonfly(self):
        #Scrive service.properties
        pth=self._install_path
        arf = []
        arf.append(u''.join([u"serviceName=",_SERVICE_NAME + "RunOnFly",u"\r\n"]))
        arf.append(u''.join(["pythonPath=",  self._current_path, os.sep, u"runtime", os.sep, u"dwagent.exe", u"\r\n"]))
        arf.append(u"parameters=agent.pyc -runonfly -filelog")
        f=codecs.open(pth + os.sep + 'native' + os.sep + 'service.properties', 'w', "CP" + str(ctypes.windll.kernel32.GetACP()))
        f.write(u''.join(arf))
        f.close()
    
    def start_runonfly(self):
        badmin=False
        if gdi.is_windows_user_in_admin_group() and gdi.is_windows_run_as_admin():
            try:
                if gdi.is_windows_process_elevated():
                    badmin=True
            except:
                badmin=True #XP
        if badmin:
            bsvcok=False
            cmd=u'"' + u'native' + os.sep + u'dwagsvc.exe" startRunOnFly'
            appout = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate() 
            lines = appout[0].splitlines()
            for l in lines:
                if l=='OK':
                    bsvcok = True
            if bsvcok==False:
                libenv = os.environ
                subprocess.Popen([sys.executable, u'agent.pyc', u'-runonfly', u'-filelog'], env=libenv);
        else:
            libenv = os.environ
            subprocess.Popen([sys.executable, u'agent.pyc', u'-runonfly', u'-filelog'], env=libenv);
    
    def install_service(self):
        cmd=u'"' + self._install_path + os.sep + u'native' + os.sep + u'dwagsvc.exe" installService'
        appout = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate() 
        lines = appout[0].splitlines()
        for l in lines:
            if l=='OK':
                return True
        return False
    
    def delete_service(self):
        cmd=u'"' + self._install_path + os.sep + u'native' + os.sep + u'dwagsvc.exe" deleteService'
        appout = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate() 
        lines = appout[0].splitlines()
        for l in lines:
            if l=='OK':
                return True
        return False
        
    def install_auto_run_monitor(self):
        b=False
        cmd=u'"' + self._install_path + os.sep + u'native' + os.sep + u'dwagsvc.exe" installAutoRun'
        appout = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate() 
        lines = appout[0].splitlines()
        for l in lines:
            if l=='OK':
                b = True
                break
        if b==True:
            #Esegue il monitor
            filename=self._install_path + os.sep + "native" + os.sep + "dwaglnc.exe" 
            subprocess.call([filename.encode(sys.getfilesystemencoding()), "systray"])
        return b
    
    def remove_auto_run_monitor(self):
        cmd=u'"' + self._install_path + os.sep + u'native' + os.sep + u'dwagsvc.exe" removeAutoRun'
        appout = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate() 
        lines = appout[0].splitlines()
        for l in lines:
            if l=='OK':
                return True
        return False
    
    def install_extra(self):
        cmd=u'"' + self._install_path + os.sep + u'native' + os.sep + u'dwagsvc.exe" enableSoftwareSASGeneration'
        appout = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate() 
        lines = appout[0].splitlines()
        for l in lines:
            if l=='OK':
                return True
        return False
    
    def install_shortcuts(self) :
        cmd=u'"' + self._install_path + os.sep + u'native' + os.sep + u'dwagsvc.exe" installShortcuts'
        appout = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate() 
        lines = appout[0].splitlines()
        for l in lines:
            if l=='OK':
                return True
        return False
    
    def remove_shortcuts(self) :
        cmd=u'"' + self._install_path + os.sep + u'native' + os.sep + u'dwagsvc.exe" removeShortcuts'
        appout = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate() 
        lines = appout[0].splitlines()
        for l in lines:
            if l=='OK':
                return True
        return False


class Install:
    
    def __init__(self,gotoopt):
        self._gotoopt=gotoopt
        self._native = get_native()
        self._ambient="PROD"
        self._uinterface=None
        self._current_path=None;
        self._install_path=user_interface.VarString()
        self._inatall_agent_mode=None
        self._install_code=user_interface.VarString()
        self._install_newag_user=user_interface.VarString()
        self._install_newag_password=user_interface.VarString("", True)
        self._install_newag_name=user_interface.VarString()
        self._proxy_type=user_interface.VarString("SYSTEM")
        self._proxy_host=user_interface.VarString("")
        self._proxy_port=user_interface.VarString("")
        self._proxy_user=user_interface.VarString("")
        self._proxy_password=user_interface.VarString("", True)
        self._proxy = None
        self._prop = None
        self._listen_port = 7950
        self._runWithoutInstall = False
        self._runWithoutInstallAgentAlive = True
        self._runWithoutInstallAgentCloseByClient=False
        self._bdebug=False
        
        
    def _get_main_url(self):
        if self._ambient=="QA":
            return _MAIN_URL_QA;
        elif self._ambient=="SVIL":
            return _MAIN_URL_SVIL;
        return _MAIN_URL;

    def _uinterface_action(self,e):
        if e["action"]=="CLOSE":
            self._runWithoutInstallAgentAlive=False
            self._runWithoutInstallAgentCloseByClient=True

    def start(self, bgui=True):
        self._current_path=os.getcwdu();
        if self._current_path.endswith(os.sep) is True:
            self._current_path=self._current_path[0:len(self._current_path)-1]
        self._native.set_current_path(self._current_path)
                                        
        self._uinterface = user_interface.Main(resources.get_message('titleInstall'), self.step_init)
        self._uinterface.set_action(self._uinterface_action)
        self._uinterface.start(bgui)
        self.close_req()

    '''def _read_info_file(self):
        try:
            f = open("info.json")
            prop = json.loads(f.read())
            f.close()   
            return prop
        except Exception:
            return None'''
            
        

    def step_init(self, ui):
        #Verifica version dell'installer se è valida per la macchina
        if not gdi.is_windows() and not gdi.is_linux() and not gdi.is_mac():
            return user_interface.Message(resources.get_message('versionInstallNotValid').format(""))
        chs = user_interface.Chooser()
        #m=resources.get_message('welcomeInstall') + "\n\n" + resources.get_message('welcomeLicense') + "\n\n" + resources.get_message('welcomeSecurity') + "\n\n" + resources.get_message('welcomeSoftwareUpdates')
        m=resources.get_message('welcomeLicense') + "\n\n" + resources.get_message('welcomeSecurity') + "\n\n" + resources.get_message('welcomeSoftwareUpdates')
        chs.set_message(m)
        chs.set_message_height(320)
        chs.add("install", resources.get_message('accept') + " - " + resources.get_message('install'))
        chs.add("runWithoutInstallation", resources.get_message('accept') + " - " + resources.get_message('runWithoutInstallation'))
        chs.add("decline", resources.get_message('decline'))
        chs.set_variable(user_interface.VarString("decline"))
        chs.set_accept_key("install;runWithoutInstallation")
        
        if self._gotoopt is not None:
            return self.step_install_choose(chs)
        else:
            chs.next_step(self.step_install_choose)
            return chs
        
    
    def step_install_choose(self, ui):
        sopt=None
        if self._gotoopt is not None and self._gotoopt=="install":
            self._gotoopt=None
            sopt="install"
        elif self._gotoopt is not None and self._gotoopt=="run":
            self._gotoopt=None
            sopt="run"
        elif self._gotoopt is not None:
            self._gotoopt=None
            return self.step_init(ui)
        else:
            if ui.get_key() is None and ui.get_variable().get()=="runWithoutInstallation":
                msg = self._native.check_init_run()
                if msg is not None:
                    return user_interface.Message(msg)
                sopt="run"                
            else:
                msg = self._native.check_init_install()
                if msg is not None:
                    return user_interface.Message(msg)
                sopt="install"
                
        if sopt=="run":
            self._runWithoutInstall=True
            return self.step_install(ui)
        else:
            self._runWithoutInstall=False
            return self.step_check_already_install(ui)

    def step_check_already_install(self, ui):
        pth = self._native.get_install_path()
        if pth is not None:
            return user_interface.Message(resources.get_message('alreadyInstalled'))
        else:
            #Scelta percorso
            ipt = user_interface.Inputs()
            if self._install_path.get() is None:
                self._install_path.set(self._native.get_proposal_path())
            ipt.set_message(resources.get_message('selectPathInstall'))
            ipt.add('path', resources.get_message('path'), self._install_path, True)
            ipt.prev_step(self.step_init)
            ipt.next_step(self.step_check_install_path)
            return ipt

    def step_check_install_path(self, ui):
        pth = self._install_path.get()
        if pth.startswith("#SVIL#"):
            self._ambient="SVIL"
            pth=pth[6:]
            self._install_path.set(pth)
        elif pth.startswith("#QA#"):
            self._ambient="QA"
            pth=pth[4:]
            self._install_path.set(pth)       
                
        if os.path.exists(pth):
            m=resources.get_message('confirmInstall').format(pth) + '\n' + resources.get_message('warningRemovePath')
        else:
            m=resources.get_message('confirmInstall').format(pth)
        chs = user_interface.Chooser()
        chs.set_message(m)
        chs.add("yes", resources.get_message('yes'))
        chs.add("no", resources.get_message('no'))
        chs.set_variable(user_interface.VarString("no"))
        chs.set_accept_key("yes")
        chs.prev_step(self.step_check_already_install)
        chs.next_step(self.step_install)
        return chs
    
    def _download_progress(self, rtp):
        perc = int((float(rtp.get_byte_transfer()) / float(rtp.get_byte_length())) * 100.0)
        msg=resources.get_message('downloadFile').format(rtp.get_property('file_name'))
        prog = rtp.get_property('prog_start') + ((rtp.get_property('prog_end') - rtp.get_property('prog_start')) * (float(perc)/100.0))
        self._uinterface.wait_message(msg, perc,  prog)
    
    def _download_file(self, node_url, name, version, pstart,  pend):
        pth = self._install_path.get()
        url = node_url +  "getAgentFile.dw?name=" + name + "&version=" + version
        file_name = pth + os.sep + name
        #Scarica il file
        rtp = communication.Response_Transfer_Progress({'on_data': self._download_progress})
        rtp.set_property('file_name', name)
        rtp.set_property('prog_start', pstart)
        rtp.set_property('prog_end', pend)
        communication.download_url_file(url, file_name, self._proxy, rtp)
    
    def _check_hash_file(self, name, hash):
        pth = self._install_path.get()
        fpath=pth + os.sep + name
        
        md5 = hashlib.md5()
        with open(fpath,'rb') as f: 
            for chunk in iter(lambda: f.read(8192), b''): 
                md5.update(chunk)
        h = md5.hexdigest()
        if h!=hash:
            raise Exception("Hash not valid. (file '{0}').".format(name))

    def _unzip_file(self, name, unzippath):
        pth = self._install_path.get()
        #Decoprime il file
        if unzippath!='':
            unzippath+=os.sep 
        fpath=pth + os.sep + name
        zfile = zipfile.ZipFile(fpath)
        for nm in zfile.namelist():
            npath=pth + os.sep + unzippath
            appnm = nm
            appar = nm.split("/")
            if (len(appar)>1):
                appnm = appar[len(appar)-1]
                npath+= nm[0:len(nm)-len(appnm)].replace("/",os.sep)
            if not os.path.exists(npath):
                os.makedirs(npath)
            npath+=appnm
            fd = open(npath,"wb")
            fd.write(zfile.read(nm))
            fd.close()
        zfile.close()
    
    def load_prop_json(self, fname):
        f = open(fname)
        prp  = json.loads(f.read())
        f.close()
        return prp        
    
    def store_prop_json(self, prp, fname):
        s = json.dumps(prp, sort_keys=True, indent=1)
        f = open(fname, 'wb')
        f.write(s)
        f.close()
    
    def obfuscate_password(self, pwd):
        return base64.b64encode(zlib.compress(pwd))

    def read_obfuscated_password(self, enpwd):
        return zlib.decompress(base64.b64decode(enpwd))
        
    def _download_files(self, pstart, pend):
        pth = self._install_path.get()
        fileversions = {}
        
        msg=resources.get_message('downloadFile').format('config.xml')
        self._uinterface.wait_message(msg,  0,  pstart)
        prpconf = communication.get_url_prop(self._get_main_url() + "getAgentFile.dw?name=config.xml", self._proxy )
        if not self._runWithoutInstall:
            prpconf['listen_port'] = self._listen_port
        self.store_prop_json(prpconf, pth + os.sep + 'config.json')
        
        if not (self._runWithoutInstall and os.path.exists(pth + os.sep + "config.json") 
                and os.path.exists(pth + os.sep + "fileversions.json") and os.path.exists(pth + os.sep + "agent.pyc") 
                and os.path.exists(pth + os.sep + "communication.pyc") and os.path.exists(pth + os.sep + "sharedmem.pyc")):
            msg=resources.get_message('downloadFile').format('files.xml')
            self._uinterface.wait_message(msg, 0,  pstart)
            prpfiles = communication.get_url_prop(self._get_main_url() + "getAgentFile.dw?name=files.xml", self._proxy )
            
            if "nodeUrl" in prpfiles:
                node_url = prpfiles['nodeUrl']
            if node_url is None or node_url=="":
                raise Exception("Download files: Node not available.")        
            
            fls = []
            ver_bit="_" + gdi.get_arch();
            if gdi.is_os_32bit():
                ver_bit+="_32"
            elif gdi.is_os_64bit():
                ver_bit+="_64"
            
            if not self._runWithoutInstall:
                if gdi.get_arch()=="x86":
                    if gdi.is_windows():
                        fls.append({'name':'agentupd_win' + ver_bit + '.zip', 'unzippath':'native'})                
                    elif gdi.is_linux():
                        fls.append({'name':'agentupd_linux' + ver_bit + '.zip', 'unzippath':'native'})
                    elif gdi.is_mac():
                        fls.append({'name':'agentupd_mac' + ver_bit + '.zip', 'unzippath':'native'})
            
            fls.append({'name':'agent.zip', 'unzippath':''})
            if not self._runWithoutInstall:
                fls.append({'name':'agentui.zip', 'unzippath':''})
            fls.append({'name':'agentapps.zip', 'unzippath':''})
            
            if gdi.is_windows():
                if not self._runWithoutInstall:
                    fls.append({'name':'agentui_win' + ver_bit + '.zip', 'unzippath':'native'})
                fls.append({'name':'agentlib_win' + ver_bit + '.zip', 'unzippath':'native'})
            elif gdi.is_linux():
                if not self._runWithoutInstall:
                    fls.append({'name':'agentui_linux' + ver_bit + '.zip', 'unzippath':'native'})
            elif gdi.is_mac():
                if not self._runWithoutInstall:
                    fls.append({'name':'agentui_mac' + ver_bit + '.zip', 'unzippath':'native'})
            step = (pend-pstart) / float(len(fls))
            pos = pstart
            for i in range(len(fls)):
                file_name = pth + os.sep + fls[i]['name']
                #Elimina file
                try:
                    os.remove(file_name)
                except Exception:
                    None
                #Scarica file
                self._download_file(node_url, fls[i]['name'], prpfiles[fls[i]['name'] + '@version'], pos,  pos+step)
                #Verifica hash
                self._check_hash_file(fls[i]['name'], prpfiles[fls[i]['name'] + '@hash'])
                #Unzip file
                self._unzip_file(fls[i]['name'], fls[i]['unzippath'])
                #Elimina file
                try:
                    os.remove(file_name)
                except Exception:
                    None
                fileversions[fls[i]['name'] ]=prpfiles[fls[i]['name'] + '@version']
                pos+=step
            
            #Scrive files.json
            self.store_prop_json(fileversions, pth + os.sep + 'fileversions.json')
        
    
    def _count_file_in_path(self,  valid_path):
        x = 0
        for root, dirs, files in os.walk(valid_path):
            for f in files:
                x = x+1
        return x

    def _copy_tree_file(self,  fs, fd, msginfo):
        if os.path.isdir(fs):
            if not os.path.exists(fd):
                os.makedirs(fd)
            lst=os.listdir(fs)
            for fname in lst:
                self._copy_tree_file(fs + os.sep + fname, fd + os.sep + fname, msginfo)
        else:
            msginfo["progr"]+=msginfo["step"]
            perc =  int(((msginfo["progr"] - msginfo["pstart"] ) / (msginfo["pend"] - msginfo["pstart"] )) * 100.0)
            self._uinterface.wait_message(msginfo["message"], perc,  msginfo["progr"])
            if os.path.exists(fd):
                os.remove(fd)
            if os.path.islink(fs):
                linkto = os.readlink(fs)
                os.symlink(linkto, fd)
            else:
                shutil.copy2(fs, fd)
                
        
    def _copy_tree(self, fs, ds, msg, pstart, pend):
        self._uinterface.wait_message(msg, 0, pstart)
        #Conta file
        nfile = self._count_file_in_path(fs)
        step = (pend-pstart) / nfile
        self._copy_tree_file(fs, ds, {'message':msg,  'pstart':pstart,  'pend':pend,  'progr':pstart, 'step':step })
        
    def _make_directory(self, pstart, pend):    
        pth = self._install_path.get()
        if os.path.exists(pth):
            self._uinterface.wait_message(resources.get_message('removeFile'), None, pstart)
            shutil.rmtree(pth)
        #Crea le cartelle necessarie
        try:
            self._uinterface.wait_message(resources.get_message('pathCreating'),  None, pend)
            os.makedirs(pth)
        except:
            raise Exception(resources.get_message('pathNotCreate'))
        
        
    
    def _install_service(self, pstart, pend):
        msg=resources.get_message('installService')
        self._uinterface.wait_message(msg, None,  pstart)
        
        #Rimuove un eventuale vecchia installazione
        self._append_log("Service - Try to remove dirty installation...")
        self._native.stop_service()
        self._native.delete_service()
        
        #Installa nuovo servizio
        self._append_log("Service - Installation...")
        if not self._native.install_service():
            raise Exception(resources.get_message('installServiceErr'))
            
        #avvia il servizio
        self._append_log("Service - Starting...")
        msg=resources.get_message('startService')
        self._uinterface.wait_message(msg, None,  pend)
        if not self._native.start_service():
            raise Exception(resources.get_message("startServiceErr"))        
    
    def _install_monitor(self, pstart, pend):
        msg=resources.get_message('installMonitor')
        self._uinterface.wait_message(msg,  None, pstart)
        
        
        #Arresta un eventuale monitor attivo
        self._append_log("Monitor - Stopping...")
        stop_monitor(self._install_path.get())
        
        #Rimuove vecchia installazione
        self._append_log("Monitor - Try to remove dirty installation...")
        self._native.remove_auto_run_monitor()
        
        self._append_log("Monitor - Installing...")
        if not self._native.install_auto_run_monitor():
            raise Exception(resources.get_message('installMonitorErr'))
    
    def _install_shortcuts(self, pstart, pend):
        msg=resources.get_message('installShortcuts')
        self._uinterface.wait_message(msg,  None, pstart)
        
        #Rimuove collegamenti
        self._append_log("Shortcut - Try to remove dirty installation...")
        self._native.remove_shortcuts()
        
        #Installazione collegamneti
        self._append_log("Shortcut - Installing...")
        if not self._native.install_shortcuts():
            raise Exception(resources.get_message('installShortcutsErr'))
    
    def step_config_init(self, ui):
        #Benvenuto
        chs = user_interface.Chooser()
        m=resources.get_message('configureInstallAgent')
        chs.set_message(m)
        chs.set_key("chooseInstallMode")
        chs.set_param('firstConfig',ui.get_param('firstConfig',False))
        chs.add("installCode", resources.get_message('configureInstallCode'))
        chs.add("installNewAgent", resources.get_message('configureInstallNewAgent'))        
        chs.set_variable(user_interface.VarString("installCode"))
        chs.next_step(self.step_config)
        return chs
    
    def step_config(self, ui):
        if ui.get_param('tryAgain',False):
            if ui.get_variable().get()=='configureLater':
                return user_interface.Message(resources.get_message('endInstallConfigLater'))
        
        if ui.get_key() is not None and ui.get_key()=='chooseInstallMode':
            self._inatall_agent_mode=ui.get_variable().get()
        
        if self._inatall_agent_mode=="installNewAgent":
            ipt = user_interface.Inputs()
            ipt.set_key('configure')
            ipt.set_param('firstConfig',ui.get_param('firstConfig',False))
            ipt.set_message(resources.get_message('enterInstallNewAgent'))
            if self._install_newag_user.get() is None:
                self._install_newag_user.set("")
            ipt.add('user', resources.get_message('dwsUser'), self._install_newag_user, True)
            if self._install_newag_password.get() is None:
                self._install_newag_password.set("")
            ipt.add('password', resources.get_message('dwsPassword'), self._install_newag_password, True)
            if self._install_newag_name.get() is None:
                self._install_newag_name.set("")
            ipt.add('name', resources.get_message('agentName'), self._install_newag_name, True)
        else:
            ipt = user_interface.Inputs()
            ipt.set_key('configure')
            ipt.set_param('firstConfig',ui.get_param('firstConfig',False))
            if self._install_code.get() is None:
                self._install_code.set("")
            ipt.set_message(resources.get_message('enterInstallCode'))
            ipt.add('code', resources.get_message('code'), self._install_code, True)
        ipt.prev_step(self.step_config_init)
        ipt.next_step(self.step_config_install_request)
        return ipt
    
    def invoke_req(self, req, prms=None):
        try:
            if self._prop==None or self._prop.is_close():
                self._prop=agent_status_config.open_property(self._install_path.get())
            return agent_status_config.invoke_request(self._prop, "admin", "", req, prms);
        except: 
            return 'ERROR:REQUEST_TIMEOUT'
    
    def close_req(self):
        if self._prop!=None and not self._prop.is_close():
            self._prop.close()
    
    def _send_proxy_config(self):
        pt = ''
        if self._proxy.get_port() is not None:
            pt=str(self._proxy.get_port())
        return self.invoke_req("set_proxy",{'type': self._proxy.get_type(), 
                                   'host': self._proxy.get_host(), 
                                   'port': pt, 
                                   'user': self._proxy.get_user(), 
                                   'password': self._proxy.get_password()})
    
    def step_configure_proxy_type(self, ui):
        chs = user_interface.Chooser()
        chs.set_key(ui.get_key())
        chs.set_message(resources.get_message('chooseProxyType'))
        chs.add("SYSTEM", resources.get_message('proxySystem'))
        chs.add("HTTP", resources.get_message('proxyHttp'))
        chs.add("SOCKS4", resources.get_message('proxySocks4'))
        chs.add("SOCKS4A", resources.get_message('proxySocks4a'))
        chs.add("SOCKS5", resources.get_message('proxySocks5'))
        chs.add("NONE", resources.get_message('proxyNone'))
        chs.set_variable(self._proxy_type)
        if ui.get_key()=="install":
            if not self._runWithoutInstall:
                chs.prev_step(self.step_check_install_path)
            else:
                chs.prev_step(self.step_init)
        elif ui.get_key()=="runonfly":
            None #non abilita il tasto prev
        else:
            chs.prev_step(self.step_config)
        chs.next_step(self.step_configure_proxy_info)
        return chs
    
    def step_configure_proxy_info(self, ui):
        if ui.get_variable().get()=='HTTP' or ui.get_variable().get()=='SOCKS4' or ui.get_variable().get()=='SOCKS4A' or ui.get_variable().get()=='SOCKS5':
            ipt = user_interface.Inputs()
            ipt.set_key(ui.get_key())
            ipt.set_message(resources.get_message('proxyInfo'))
            ipt.add('proxyHost', resources.get_message('proxyHost'), self._proxy_host,  True)
            ipt.add('proxyPort', resources.get_message('proxyPort'), self._proxy_port,  True)
            ipt.add('proxyAuthUser', resources.get_message('proxyAuthUser'), self._proxy_user,  False)
            ipt.add('proxyAuthPassword', resources.get_message('proxyAuthPassword'), self._proxy_password,  False)
            ipt.prev_step(self.step_configure_proxy_type)
            ipt.next_step(self.step_configure_proxy_set)
            return ipt
        else:
            self._proxy_host.set("")
            self._proxy_port.set("")
            self._proxy_user.set("")
            self._proxy_password.set("")
            return self.step_configure_proxy_set(ui)
    
    def step_configure_proxy_set(self, ui):
        if ui.get_param('tryAgain',False):
            if ui.get_variable() is not None and ui.get_variable().get()=='configureLater':
                return self.step_config(ui)
        #Verifica se la porta è numerica
        oldprx = self._proxy
        self._proxy=communication.ProxyInfo()
        self._proxy.set_type(self._proxy_type.get())
        self._proxy.set_host(self._proxy_host.get())
        if self._proxy_type.get()=='HTTP' or self._proxy_type.get()=='SOCKS4' or self._proxy_type.get()=='SOCKS4A' or self._proxy_type.get()=='SOCKS5':
            try:
                self._proxy.set_port(int(self._proxy_port.get()))
            except:
                self._proxy = oldprx
                return user_interface.ErrorDialog(resources.get_message("validInteger") .format(resources.get_message('proxyPort')))
        self._proxy.set_user(self._proxy_user.get())
        self._proxy.set_password(self._proxy_password.get())
        if ui.get_key()=='install':
            ui.set_key('retryDownloadProxy')
            return self.step_install(ui)
        elif ui.get_key()=="runonfly":
            ui.set_key('retryRunOnFlyProxy')
            return self.step_runonfly(ui)
        else:
            try:
                s=self._send_proxy_config()
                if s=='OK':
                    return self.step_config_install_request(ui)
                elif s=="ERROR:REQUEST_TIMEOUT":
                    return user_interface.ErrorDialog(resources.get_message('errorConnectionConfig'))
                else:
                    return user_interface.ErrorDialog(s) 
            except:
                chs = user_interface.Chooser()
                chs.set_key(ui.get_key())
                chs.set_param("tryAgain", True)
                chs.set_message(resources.get_message('errorConnectionConfig'))
                chs.add("noTryAgain", resources.get_message('noTryAgain'))
                chs.add("configureLater", resources.get_message('configureLater'))
                chs.set_variable(user_interface.VarString("noTryAgain"))
                chs.prev_step(self.step_config)
                chs.next_step(self.step_configure_proxy_set)
                return chs
            return self._configure_proxy_set(ui)
        
    

    def step_config_install_request(self, ui):        
        if ui.get_param('tryAgain',False):
            if ui.get_variable().get()=='configureLater':
                return user_interface.Message(resources.get_message('endInstallConfigLater'))
            elif ui.get_variable().get()=='configProxy':
                return self.step_configure_proxy_type(ui)
        
        if self._inatall_agent_mode=="installNewAgent":
            msg=resources.get_message('createNewAgent')
        else:
            msg=resources.get_message('checkInstallCode')            
        self._uinterface.wait_message(msg)
        page = None
        try:
            #Imposta il proxy
            if ui.get_param('firstConfig',False) and self._proxy is not None:
                s=self._send_proxy_config()
                if s!='OK':
                    if s=="ERROR:REQUEST_TIMEOUT":
                        return user_interface.ErrorDialog(resources.get_message('errorConnectionConfig'))
                    else:
                        return user_interface.ErrorDialog(s)
            #Verifica codice
            s = None
            if self._inatall_agent_mode=="installNewAgent":
                s = self.invoke_req("install_new_agent",{'user': self._install_newag_user.get(), 'password': self._install_newag_password.get(), 'name':self._install_newag_name.get()})
            else:
                s = self.invoke_req("install_key",{'code': self._install_code.get().strip().replace(" ", "")})
            if s=='OK':
                return user_interface.Message(resources.get_message('endInstall'))
            elif s=="ERROR:INVALID_CODE" or s=="ERROR:INVALID_USER_PASSWORD" or s=="ERROR:NAME_NOT_VALID" or s=="ERROR:ALREADY_EXISTS" or s=="ERROR:AGENT_MAX":
                chs = user_interface.Chooser()
                chs.set_key('configure')
                chs.set_param('tryAgain',True);
                if s=="ERROR:INVALID_CODE":
                    chs.set_message(resources.get_message('errorInvalidCode'))
                elif s=="ERROR:INVALID_USER_PASSWORD":
                    chs.set_message(resources.get_message('errorInvalidUserPassword'))
                elif s=="ERROR:NAME_NOT_VALID":
                    chs.set_message(resources.get_message('errorAgentNameNotValid'))
                elif s=="ERROR:ALREADY_EXISTS":
                    chs.set_message(resources.get_message('errorAgentAlreadyExsists').format(self._install_newag_name.get()))
                elif s=="ERROR:AGENT_MAX":
                    chs.set_message(resources.get_message('errorAgentMax'))
                else:
                    chs.set_message(s)
                chs.add("reEnter", resources.get_message('reEnterData'))
                chs.add("configureLater", resources.get_message('configureLater'))
                chs.set_variable(user_interface.VarString("reEnter"))
                chs.next_step(self.step_config)
                chs.prev_step(self.step_config)
                return chs
            elif s=="ERROR:CONNECT_ERROR":
                chs = user_interface.Chooser()
                chs.set_key('configure')
                chs.set_param('tryAgain',True);
                chs.set_message(resources.get_message('errorConnectionQuestion'))
                chs.add("configProxy", resources.get_message('yes'))
                chs.add("noTryAgain", resources.get_message('noTryAgain'))
                chs.add("configureLater", resources.get_message('configureLater'))
                chs.set_variable(user_interface.VarString("noTryAgain"))
                chs.prev_step(self.step_config)
                chs.next_step(self.step_config_install_request)
                return chs
            elif s=="ERROR:REQUEST_TIMEOUT":
                return user_interface.ErrorDialog(resources.get_message('errorConnectionConfig'))
            else:
                return user_interface.ErrorDialog(s) 
        except:
            chs = user_interface.Chooser()
            chs.set_key('configure')
            chs.set_param('tryAgain',True);
            chs.set_message(resources.get_message('errorConnectionConfig'))
            chs.add("noTryAgain", resources.get_message('noTryAgain'))
            chs.add("configureLater", resources.get_message('configureLater'))
            chs.set_variable(user_interface.VarString("noTryAgain"))
            chs.prev_step(self.step_config)
            chs.next_step(self.step_config_install_request)
            return chs
        finally:
            if page is not None:
                page.close()
    
    def _append_log(self, txt):
        try:
            if self._install_log is not None:
                self._install_log.write(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()) + " - " + txt + "\n")
                self._install_log.flush()
        except:
            None    
    
    def _runonfly_update(self,pthsrc,pthdst):
        lst=os.listdir(pthsrc)
        for fname in lst:
            if os.path.isfile(pthsrc + os.sep + fname):
                os.remove(pthdst + os.sep + fname)
                shutil.copy2(pthsrc + os.sep + fname, pthdst + os.sep + fname)
            elif os.path.isdir(pthsrc + os.sep + fname):
                self._runonfly_update(pthsrc + os.sep + fname,pthdst + os.sep + fname)
     
    def step_runonfly(self, ui):
        
        if self._proxy is not None:
            prpconf = self.load_prop_json('config.json')
            if self._proxy.get_type() is not None:
                prpconf['proxy_type'] = self._proxy.get_type()
            if self._proxy.get_host() is not None:
                prpconf['proxy_host'] = self._proxy.get_host()
            if self._proxy.get_port() is not None:
                prpconf['proxy_port'] = self._proxy.get_port()
            if self._proxy.get_user() is not None:
                prpconf['proxy_user'] = self._proxy.get_user()
            else:
                prpconf['proxy_user'] = ""
            if self._proxy.get_password() is not None:
                prpconf['proxy_password'] = self.obfuscate_password(self._proxy.get_password())
            else:
                prpconf['proxy_password'] = ""
            self.store_prop_json(prpconf, 'config.json')
        
        if ui.get_key() is not None and ui.get_key()=='retryRunOnFly':
            if ui.get_variable().get()=='configProxy':
                ui.set_key('runonfly')
                return self.step_configure_proxy_type(ui)
        
        os.chdir(self._install_path.get())
        pstsharedmem=None
        try:   
            while self._runWithoutInstallAgentAlive:
                self._uinterface.wait_message(resources.get_message("runWithoutInstallationStarting"))
                                
                if os.path.exists(u"update"):
                    self._uinterface.wait_message(resources.get_message("runWithoutInstallationUpdating"))
                    self._runonfly_update(u"update",".");
                    shutil.rmtree(u"update")
            
                #CHECK FILE
                if os.path.exists("dwagent.pid"):
                    os.remove("dwagent.pid")
                if os.path.exists("dwagent.start"):
                    os.remove("dwagent.start")
                if os.path.exists("dwagent.stop"):
                    os.remove("dwagent.stop")
                if os.path.exists("dwagent.status"):
                    os.remove("dwagent.status")
                
                #Scrive pid
                f = open("dwagent.pid", 'wb')
                f.write(str(os.getpid()))
                f.close()            
                 
                #Avvia il servizio
                self._native.start_runonfly()
                    
                #Attende L'avvio
                cnt=0
                while (not os.path.exists("dwagent.start")):
                    time.sleep(1)
                    cnt+=1
                    if cnt>10: #10 Secondi
                        raise Exception(""); #GESTITO SOTTO
                if os.path.exists("dwagent.start"):
                    os.remove("dwagent.start")
                
                #GESTISCE STATO
                pstsharedmem = sharedmem.Property()
                pstsharedmem.open("runonfly")
                agpid=int(pstsharedmem.get_property("pid"))
                curst=""
                while self._native.is_task_running(agpid):
                    st = pstsharedmem.get_property("status")
                    if st!=curst:
                        curst=st
                        if st=="CONNECTED":
                            usr=pstsharedmem.get_property("user")
                            usr=usr[0:3] + u"-" + usr[3:6] + u"-" + usr[6:9] + u"-" + usr[9:]            
                            self._uinterface.wait_message(resources.get_message("runWithoutInstallationConnected").format(usr,pstsharedmem.get_property("password")), allowclose=True)                        
                        elif st=="CONNECTING":
                            self._uinterface.wait_message(resources.get_message("runWithoutInstallationConnecting"), allowclose=True)
                        elif st is not None and st.startswith("WAIT:"):
                            retry=int(st.split(":")[1])
                            if retry>3:
                                self._runWithoutInstallAgentAlive=False
                            else:
                                self._uinterface.wait_message(resources.get_message("runWithoutInstallationWait").format(str(retry)), allowclose=True)

                    if self._runWithoutInstallAgentAlive==False:
                        break
                    time.sleep(1)
                
                self._uinterface.wait_message(resources.get_message("runWithoutInstallationClosing"))
                f = open("dwagent.stop", 'wb')
                f.close()
                cnt=0
                while self._native.is_task_running(agpid):
                    time.sleep(1)
                    cnt+=1
                    if cnt>5: #5 Secondi
                        break
                
                pstsharedmem.close()
                pstsharedmem=None
                time.sleep(1)
                
        except Exception as e:
            f = open("dwagent.stop", 'wb')
            f.close()
            try:
                if pstsharedmem is not None:
                    pstsharedmem.close()
                    pstsharedmem=None
            except:
                None
            #Se non è partito l'agente potrebbe dipendere da un problema di file corrotti
            return user_interface.Message(resources.get_message("runWithoutInstallationUnexpectedError").format(self._current_path))
        
        os.chdir(self._current_path)
          
        if self._runWithoutInstallAgentCloseByClient:
            return user_interface.Message(resources.get_message('runWithoutInstallationEnd'))  
        else:
            self._runWithoutInstallAgentAlive=True
            chs = user_interface.Chooser()
            chs.set_key("retryRunOnFly")
            chs.set_message(resources.get_message('errorConnectionQuestion'))
            chs.add("configProxy", resources.get_message('yes'))
            chs.add("noTryAgain", resources.get_message('noTryAgain'))
            chs.set_variable(user_interface.VarString("noTryAgain"))
            chs.next_step(self.step_runonfly)
            return chs
        
            
    
    def step_install(self, ui):
        if os.path.exists(self._current_path + os.sep + "ambient.svil"):
            self._ambient="SVIL"
        elif os.path.exists(self._current_path + os.sep + "ambient.qa"):
            self._ambient="QA"
            
        #Imposta il path di cacerts.pem
        communication.set_cacerts_path(self._current_path + os.sep + u"cacerts.pem")
        
        if self._runWithoutInstall:
            self._install_path.set(tempfile.gettempdir() + os.sep + u"dwagentonfly");
        
        if ui.get_key() is None and ui.get_variable().get()=="no":
            return user_interface.Message(resources.get_message('cancelInstall'))
        
        if ui.get_key() is not None and ui.get_key()=='retryDownload':
            if ui.get_variable().get()=='configProxy':
                ui.set_key('install')
                return self.step_configure_proxy_type(ui)
        
        pth = self._install_path.get()
        if pth.endswith(os.sep) is True:
            pth=pth[0:len(pth)-1]
        
        if self._runWithoutInstall and not os.path.exists(pth):
            os.mkdir(pth)
                
        #Inizializza log
        try:
            self._install_log=open(u'install.log', 'wb')  #Potrebe essere la cartella solo lettura
        except:
            self._install_log=open(tempfile.gettempdir() + os.sep + u'dwagent_install.log', 'wb')
        
        self._install_path.set(unicode(pth))
        #Imposta path per native
        self._native.set_install_path(unicode(pth))
        self._native.set_install_log(self._install_log)
            
        try:
            if not self._runWithoutInstall:
                if ui.get_key()!='retryDownload' and ui.get_key()!='retryDownloadProxy':
                    #Crea cartella
                    self._append_log("Make folder " + pth + "...")
                    self._make_directory(0.01, 0.02)
                                        
            #Copia Licenza
            pthlic = self._install_path.get() + os.sep + u"LICENSES"
            if not os.path.exists(pthlic):
                os.makedirs(pthlic)
                #if not self._runWithoutInstall:
                shutil.copy2(u"LICENSES" + os.sep + u"README", self._install_path.get() + os.sep + u"README")
                shutil.copy2(u"LICENSES" + os.sep + u"runtime", pthlic + os.sep + u"runtime")
                shutil.copy2(u"LICENSES" + os.sep + u"agent", pthlic + os.sep + u"agent")
            #Download file
            try:
                self._append_log("Download files...")
                if not self._runWithoutInstall:
                    self._download_files(0.03, 0.5)
                else:
                    #Carica proxy
                    if os.path.exists("config.json"):
                        prpconf=self.load_prop_json("config.json")
                        if 'proxy_type' in prpconf and prpconf['proxy_type']!="":
                            self._proxy=communication.ProxyInfo()
                            self._proxy.set_type(prpconf['proxy_type'])
                            if 'proxy_host' in prpconf:
                                self._proxy.set_host(prpconf['proxy_host'])
                            if 'proxy_port' in prpconf and prpconf['proxy_port']!="":
                                self._proxy.set_port(prpconf['proxy_port'])
                            if 'proxy_user' in prpconf:
                                self._proxy.set_user(prpconf['proxy_user'])
                            if 'proxy_password' in prpconf and prpconf['proxy_password']!="":
                                self._proxy.set_password(self.obfuscate_password(prpconf['proxy_password']))
                    self._download_files(0.01, 0.9)
            except Exception as e:
                self._append_log("Error Download files: " + str(e))
                chs = user_interface.Chooser()
                chs.set_key("retryDownload")
                chs.set_message(resources.get_message('errorConnectionQuestion'))
                chs.add("configProxy", resources.get_message('yes'))
                chs.add("noTryAgain", resources.get_message('noTryAgain'))
                chs.set_variable(user_interface.VarString("noTryAgain"))
                if not self._runWithoutInstall:
                    chs.prev_step(self.step_check_install_path)
                else:
                    chs.prev_step(self.step_init)
                    self._install_path.set(None)
                chs.next_step(self.step_install)
                return chs
            
            if not self._runWithoutInstall:
                #Copia Runtime
                self._append_log("Copy runtime...")
                if not os.path.exists(_RUNTIME_PATH):
                    raise Exception(resources.get_message('missingRuntime'))
                ds= self._install_path.get() + os.sep + "runtime"
                msg=resources.get_message('copyRuntime')
                self._copy_tree(_RUNTIME_PATH,ds,msg,0.51, 0.75)
                
                #Copia Native
                self._append_log("Copy native...")
                if not os.path.exists(_NATIVE_PATH):
                    raise Exception(resources.get_message('missingNative'))
                
                ds= self._install_path.get() + os.sep + "native"
                msg=resources.get_message('copyNative')
                self._copy_tree(_NATIVE_PATH,ds,msg,0.76, 0.8)
                
                #Prepare file
                self._append_log("Prepare file...")
                self._native.prepare_file()
                            
                #Installa Servizio
                self._append_log("Install service...")
                self._install_service(0.81, 0.85)
                
                #Installa Monitor
                self._append_log("Install monitor...")
                self._install_monitor(0.86, 0.90)
                
                #Installa Shortcuts
                self._append_log("Install Shortcuts...")
                self._install_shortcuts(0.91,  1)
                
                #Installazioni specifiche per os
                self._append_log("Install Extra OS...")
                self._native.install_extra()
                
                #Inizia la configurazione
                ui.set_param('firstConfig',True)
                return self.step_config_init(ui)
            else:
                #Copia Native
                self._append_log("Copy native...")
                if not os.path.exists(_NATIVE_PATH):
                    raise Exception(resources.get_message('missingNative'))
                ds= self._install_path.get() + os.sep + "native"
                msg=resources.get_message('copyNative')
                self._copy_tree(_NATIVE_PATH,ds,msg,0.91, 1)
                
                #Prepare file
                self._append_log("Prepare file...")
                self._native.prepare_file_runonfly()
                
                return self.step_runonfly(ui);
            
        except Exception as e:            
            self._append_log("Error Install: " + str(e))
            #return user_interface.Message(str(e))
            return user_interface.ErrorDialog(str(e)) 
        finally:
            try:
                if self._install_log is not None:
                    self._install_log.close()
            except:
                None
            

class Uninstall:
    def __init__(self):
        self._native = get_native()
        self._uinterface=None
        self._install_path=None
    
    def start(self, bgui=True):
        self._uinterface = user_interface.Main(resources.get_message('titleUninstall'), self.step_init)
        self._uinterface.start(bgui)

    def step_init(self, ui):
        msg = self._native.check_init_uninstall()
        if msg is not None:
            return user_interface.Message(msg)
        self._install_path = self._native.get_install_path()
        if self._install_path is None:
            return user_interface.Message(resources.get_message('notInstalled'))
        else:
            self._install_path = unicode(self._install_path)
            #Conferma disinstallazione
            chs = user_interface.Chooser()
            chs.set_message(resources.get_message('confirmUninstall'))
            chs.add("yes", resources.get_message('yes'))
            chs.add("no", resources.get_message('no'))
            chs.set_variable(user_interface.VarString("no"))
            chs.set_accept_key("yes")
            chs.next_step(self.step_remove)
            return chs
    
    def _uninstall_monitor(self, pstart, pend):
        msg=resources.get_message('uninstallMonitor')
        self._uinterface.wait_message(msg,  None, pstart)
        stop_monitor(self._install_path)
        self._native.remove_auto_run_monitor()
    
    def _uninstall_service(self, pstart, pend):
        msg=resources.get_message('uninstallService')
        self._uinterface.wait_message(msg,  None, pstart)
        self._native.stop_service()
        self._native.delete_service()
    
    def _uninstall_shortcuts(self, pstart, pend):
        msg=resources.get_message('uninstallShortcuts')
        self._uinterface.wait_message(msg,  None, pstart)
        self._native.remove_shortcuts()
    
    def _append_log(self, txt):
        try:
            if self._install_log is not None:
                self._install_log.write(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()) + " - " + txt + "\n")
                self._install_log.flush()
        except:
            None   
    
    def step_remove(self, ui):
        if ui.get_key() is None and ui.get_variable().get()=="no":
            return user_interface.Message(resources.get_message('cancelUninstall'))
        try:
            #Inizializza log
            try:
                self._install_log=open('unistall.log', 'wb') #Potrebbe esesere solo lettura
            except:
                self._install_log=open(tempfile.gettempdir() + os.sep + 'dwagent_unistall.log', 'wb')
            
            self._native.set_install_path(self._install_path)
            self._native.set_install_log(self._install_log)
            
            self._append_log("Uninstall monitor...")
            self._uninstall_monitor(0.01, 0.4)
            
            self._append_log("Uninstall service...")
            self._uninstall_service(0.41, 0.8)
            
            self._append_log("Uninstall shortcuts...")
            self._uninstall_shortcuts(0.81, 1)
    
            #Scrive file per eliminazione della cartella
            f = open(self._install_path + os.sep + "agent.uninstall", "w")
            f.write("\x00")
            f.close()
            
            return user_interface.Message(resources.get_message('endUninstall'))
        except Exception as e:
            return user_interface.ErrorDialog(str(e))
        finally:
            try:
                if self._install_log is not None:
                    self._install_log.close()
            except:
                None


class Test:
    def __init__(self):
        self._native = get_native()
        self._native.set_install_path(unicode("C:\\programmi\\dwagent"))
        #self._native._instlib.installAutoRun(u"DWAgentMon",  u"\"" + self._native._install_path + os.sep + u"native" + os.sep + u"dwaglnc.exe\" systray")
        #self._native._instlib.removeAutoRun(u"DWAgentMon")
        labels = resources.get_message('menuConfigure') + u";" + resources.get_message('menuMonitor') + u";" + resources.get_message('menuUninstall')
        self._native._instlib.installShortcuts(self._native._install_path,  labels)
        #self._native._instlib.removeShortcuts()

       
def fmain(args): #SERVE PER MACOS APP
    i = None
    bgui=True
    gotoopt=None
    for arg in args: 
        if arg.lower() == "uninstall":
            i = Uninstall()
        elif arg.lower() == "-console":
            bgui=False
        elif arg.lower().startswith("gotoopt="):
            gotoopt=arg[8:]
        elif arg.lower().startswith("lang="):
            try:
                resources.set_locale(arg[5:])
            except:
                None
    if i is None:
        i = Install(gotoopt)
    i.start(bgui)
    sys.exit(0)
        
if __name__ == "__main__":
    fmain(sys.argv)
   
