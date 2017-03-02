# -*- coding: utf-8 -*-

'''
This Source Code Form is subject to the terms of the Mozilla
Public License, v. 2.0. If a copy of the MPL was not distributed
with this file, You can obtain one at http://mozilla.org/MPL/2.0/.
'''

import communication
import threading
from Queue import Queue
import time
import sys
import json
import string
import random
import os
import base64
import zlib
import zipfile
import signal
import platform
import logging.handlers
import hashlib
import agent_status_config
import agent_listener
import traceback
import ctypes
import shutil
import sharedmem
import importlib 
import urllib
import applications
import struct
import mimetypes

def is_windows():
    return (platform.system().lower().find("window") > -1)

def is_linux():
    return (platform.system().lower().find("linux") > -1)

def is_mac():
    return (platform.system().lower().find("darwin") > -1)

def get_os_type():
    if is_linux():
        return "Linux"
    elif is_windows():
        return "Windows"
    elif is_mac():
        return "Mac"
    else:
        return "Unknown"

def get_os_type_code():
    if is_linux():
        return 0
    elif is_windows():
        return 1
    elif is_mac():
        return 2
    else:
        return -1

def is_os_32bit():
    return not sys.maxsize > 2**32

def is_os_64bit():
    return sys.maxsize > 2**32

def get_arch():
    try:
        sapp = platform.machine()
        if sapp is not None:
            if sapp.upper()=="AMD64" or sapp.lower()=="x86_64" or sapp.lower()=="i386" or sapp.lower()=="x86":
                return "x86"
            elif len(sapp)==4 and sapp[0]=="i" and sapp[2:4]=="86":
                return "x86"
            elif sapp!="":
                return sapp
    except:
        None
    return "unknown"
    

def load_osmodule():
    oret=None;
    if is_windows():
        import native_windows
        oret=native_windows.Main()
    elif is_linux():
        import native_linux
        oret=native_linux.Main()
    elif is_mac():
        import native_mac
        oret=native_mac.Main()
    oret.load_library();
    return oret

def unload_osmodule(omdl):
    omdl.unload_library();

def get_prop(prop,key,default=None):
    if key in prop:
        return prop[key]
    return default
        
def generate_key(n):
    c = "".join([string.ascii_lowercase, string.ascii_uppercase,  string.digits])
    return "".join([random.choice(c) 
                    for x in xrange(n)])
        
def str2bool(v):
        return v.lower() in ("yes", "true", "t", "1")    

def bool2str(v):
    if v is None or v is False:
        return 'False'
    else:
        return 'True'

def hash_password(pwd):
    encoded = hashlib.sha256(pwd).digest()
    encoded = base64.b64encode(encoded)
    return encoded

def check_hash_password(pwd, encoded_pwd):
    pwd=hash_password(pwd)
    pwd_len   = len(pwd)
    encoded_pwd_len = len(encoded_pwd)
    result = pwd_len ^ encoded_pwd_len
    if encoded_pwd_len > 0:
        for i in xrange(pwd_len):
            result |= ord(pwd[i]) ^ ord(encoded_pwd[i % encoded_pwd_len])
    return result == 0

def obfuscate_password(pwd):
    return base64.b64encode(zlib.compress(pwd))

def read_obfuscated_password(enpwd):
    return zlib.decompress(base64.b64decode(enpwd))
    
class Worker(threading.Thread):
    
    def __init__(self, parent,  queue, i):
        self._parent = parent
        threading.Thread.__init__(self, name="TPWorker_" + str(i))
        self.daemon=True
        self._queue=queue
        
    def run(self):
        while True:
            func, args, kargs = self._queue.get()
            try: 
                func(*args, **kargs)
            except Exception as e: 
                self._parent.write_except(e)
            self._queue.task_done()
    
class ThreadPool():
    
    def __init__(self, parent,  queue_size, core_size):
            self._parent = parent
            self._queue = Queue(queue_size)
            for i in range(core_size):
                self._worker = Worker(self, self._queue, i)
                self._worker.start()
    
    def write_except(self, e):
        self._parent.write_except(e)
        
    def execute(self, func, *args, **kargs):
        self._queue.put([func, args, kargs])
    
    def destroy(self):
        None

class StdRedirect(object):
    
    def __init__(self,lg,lv):
        self._logger = lg;
        self._level = lv;
        
    def write(self, data):
        for line in data.rstrip().splitlines():
            self._logger.log(self._level, line.rstrip())

class Main():
    _STATUS_OFFLINE = 0
    _STATUS_ONLINE = 1
    _STATUS_DISABLE = 3
    _STATUS_UPDATING = 10
    _CONNECTION_TIMEOUT= 60
    
    def __init__(self,args):
        #Prepara il log
        self._logger = logging.getLogger()
        hdlr = None
        self._noctrlfile=False
        self._bstop=False
        self._runonfly=False
        self._runonfly_conn_retry=0
        self._runonfly_user=None
        self._runonfly_password=None
        self._runonfly_sharedmem=None        
        self._runonfly_action=None #RIMASTO PER COMPATIBILITA' CON VECCHIE CARTELLE RUNONFLY
        for arg in args: 
            if arg=='-runonfly':
                self._runonfly=True
            if arg=='-filelog':
                hdlr = logging.handlers.RotatingFileHandler('dwagent.log', 'a', 1000000, 3)
            if arg=='-noctrlfile':
                signal.signal(signal.SIGTERM, self._signal_handler)
                self._noctrlfile=True
        if hdlr is None:
            hdlr = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        hdlr.setFormatter(formatter)
        self._logger.addHandler(hdlr) 
        self._logger.setLevel(logging.INFO)
        #Reindirizza stdout e stderr
        sys.stdout=StdRedirect(self._logger,logging.DEBUG);
        sys.stderr=StdRedirect(self._logger,logging.ERROR);
        
        #Inizializza campi
        self._task_pool = None
        self._path_config='config.json'
        self._config=None
        self._brun=True
        self._brebootagent=False
        self._breloadconfig=True
        self._breloadagent=False
        if self._runonfly:
            self._cnt_min=0
            self._cnt_max=10
        else:
            self._cnt_min=5
            self._cnt_max=30
        self._cnt_random=0
        self._cnt=self._cnt_max
        self._agent_status_config=None
        self._agent_listener=None
        self._proxy_info=None
        self._session = None
        self._connections={}
        self._apps={}
        self._apps_to_reload={}
        self._agent_log_semaphore = threading.Condition()
        self._agent_connection_semaphore = threading.Condition()
        self._appsload_semaphore = threading.Condition()
        self._agent_enabled = True
        self._agent_status= self._STATUS_OFFLINE
        self._agent_debug_mode = None
        self._agent_url_primary = None
        self._agent_key = None
        self._agent_password = None
        self._agent_server = None
        self._agent_port= None
        self._agent_method_connect_port= None
        self._agent_instance= None
        self._agent_version = None
        self._agent_url_node = None
        self._config_semaphore = threading.Condition()
        self._osmodule = load_osmodule();
        self._svcpid=None
        
        #Inizializza il path delle shared mem
        sharedmem.init_path()
    
    def unload_library(self):
        if self._osmodule is not None:
            unload_osmodule(self._osmodule);
            self._osmodule=None
    
    #RIMASTO PER COMPATIBILITA' CON VECCHIE CARTELLE RUNONFLY
    def set_runonfly_action(self,action):
        self._runonfly_action=action
    
    def _signal_handler(self, signal, frame):
        if self._noctrlfile==True:
            self._bstop=True
        else:
            f = open("dwagent.stop", 'wb')
            f.close()
           
    def _write_config_file(self):
        s = json.dumps(self._config, sort_keys=True, indent=1)
        f = open(self._path_config, 'wb')
        f.write(s)
        f.close()
        
    def _read_config_file(self):
        self._config_semaphore.acquire()
        try:
            try:
                self.write_info("Reading config file...");
                f = open(self._path_config)
            except Exception:
                self.write_err("Error reading config file.");
                self._config = None
                return
            try:
                self._config = json.loads(f.read())
                self.write_info("Readed config file.");
            except Exception:
                self.write_err("Error parse config file.");
                self._config = None
            finally:
                f.close()
        finally:
            self._config_semaphore.release()
    
    def get_proxy_info(self):
        self._config_semaphore.acquire()
        try:
            if self._proxy_info is None:
                self._proxy_info=communication.ProxyInfo()
                if 'proxy_type' in self._config:
                    self._proxy_info.set_type(self._config['proxy_type'])
                else:
                    self._proxy_info.set_type("SYSTEM")
                if 'proxy_host' in self._config:
                    self._proxy_info.set_host(self._config['proxy_host'])
                if 'proxy_port' in self._config:
                    self._proxy_info.set_port(self._config['proxy_port'])
                if 'proxy_user' in self._config:
                    self._proxy_info.set_user(self._config['proxy_user'])
                if 'proxy_password' in self._config:
                    if self._config['proxy_password'] == "":
                        self._proxy_info.set_password("")
                    else:
                        self._proxy_info.set_password(read_obfuscated_password(self._config['proxy_password']))
            return self._proxy_info
        finally:
            self._config_semaphore.release()
    
    
    def get_session(self):
        return self._session
    
    def get_osmodule(self):
        return self._osmodule 
    
    def get_status(self):
        return self._agent_status
    
    def get_connection_count(self):
        self._agent_connection_semaphore.acquire()
        try:
            return len(self._connections)
        finally:
            self._agent_connection_semaphore.release()
    
    def _load_config(self):
        self.write_info("Reading configuration...");
        try:
            self._agent_debug_mode = self._get_config('debug_mode',False)
            if self._agent_debug_mode:
                self._logger.setLevel(logging.DEBUG)
            #VERIFICA agentConnectionPropertiesUrl
            self._agent_url_primary = self._get_config('url_primary', None)
            if self._agent_url_primary  is None:
                self.write_info("Missing url_primary configuration.");
                return False
            app_url = None
            prp_url = None
            if not self._runonfly:
                self._agent_key = self._get_config('key', None)
                self._agent_password = self._get_config('password', None)
                if self._agent_key is None or self._agent_password is None:
                    self.write_info("Missing agent authentication configuration.");
                    return False
                self._agent_password = read_obfuscated_password(self._agent_password)
                app_url = self._agent_url_primary + "getAgentProperties.dw?key=" + self._agent_key
            else:
                spapp = ";".join(self.get_supported_applications())
                app_url = self._agent_url_primary + "getAgentPropertiesOnFly.dw?osTypeCode=" + str(get_os_type_code()) +"&supportedApplications=" + urllib.quote_plus(spapp)
                self._agent_key = None
                self._agent_password = None 
            try:
                prp_url = communication.get_url_prop(app_url, self.get_proxy_info())
                if "error" in prp_url:
                    self.write_info("Error read agentUrlPrimary: " + prp_url['error']);
                    return False
                if self._runonfly:
                    self._agent_key = get_prop(prp_url, 'key', None)
                    apppwd = get_prop(prp_url, 'password', None)
                    arpwd = []
                    for i in reversed(range(len(apppwd))):
                        arpwd.append(apppwd[i:i+1])
                    self._agent_password="".join(arpwd)
                    self._runonfly_user=get_prop(prp_url, 'userLogin', None)
                    self._runonfly_password=get_prop(prp_url, 'userPassword', None)
                                        
            except Exception as e:
                self.write_info("Error read agentUrlPrimary: " + str(e));
                return False
                
            appst = get_prop(prp_url, 'state', None)
            if appst=="D":
                self.write_info("Agent disabled.")
                return False
            elif appst=="S":
                self.write_info("Agent suppressed.")
                self.remove_key();
                return False
            self._agent_server = get_prop(prp_url, 'server', None)
            if self._agent_server is None:
                self.write_info("Missing server configuration.")
                return False
            self._agent_port = get_prop(prp_url, 'port', "7730")
            self._agent_method_connect_port = get_prop(prp_url, 'methodConnectPort', None)
            self._agent_instance = get_prop(prp_url, 'instance', None)
            if self._agent_instance is None:
                self.write_info("Missing instance configuration.")
                return False
            self._agent_version= get_prop(prp_url, 'agentVersion', None)
            
            
            self.write_info("Primary url: " + self._agent_url_primary)
            self.write_info("Proxy: " + self.get_proxy_info().get_type())
            self.write_info("Configuration readed.")
            return True
        except Exception as e:
            #self.write_info("Reading configuration unexpected errore.");
            self.write_except(e)
            return False
    
    def set_config_password(self, pwd):
        self._config_semaphore.acquire()
        try:
            self._config['config_password']=hash_password(pwd)
            self._write_config_file()
        finally:
            self._config_semaphore.release()
    
    def check_config_auth(self, usr, pwd):
        cp=self._get_config('config_password', hash_password(""))
        return usr=="admin" and pwd==cp
    
    def set_proxy(self, stype,  host,  port,  user,  password):
        if stype is None or (stype!='NONE' and stype!='SYSTEM' and stype!='HTTP' and stype!='SOCKS4' and stype!='SOCKS4A' and stype!='SOCKS5'):
            raise Exception("Invalid proxy type.")
        if (stype=='HTTP' or stype=='SOCKS4' or stype=='SOCKS4A' or stype=='SOCKS5') and host is None:
            raise Exception("Missing host.")
        if (stype=='HTTP' or stype=='SOCKS4' or stype=='SOCKS4A' or stype=='SOCKS5') and port is None:
            raise Exception("Missing port.")
        if port is not None and not isinstance(port, int) :
            raise Exception("Invalid port.")
        self._config_semaphore.acquire()
        try:
            self._config['proxy_type']=stype
            if host is not None:
                self._config['proxy_host']=host
            else:
                self._config['proxy_host']=""
            if port is not None:
                self._config['proxy_port']=port
            else:
                self._config['proxy_port']=""
            if user is not None:
                self._config['proxy_user']=user
            else:
                self._config['proxy_user']=""
            if password is not None:
                self._config['proxy_password']=obfuscate_password(password)
            else:
                self._config['proxy_password']=""
            self._write_config_file()
            self._proxy_info=None #In questo modo lo ricarica
        finally:
            self._config_semaphore.release()
        self._reload_config()
    
    def install_new_agent(self, user, password, name):
        spapp = ";".join(self.get_supported_applications())
        url = self._agent_url_primary + "installNewAgent.dw?user=" + urllib.quote_plus(user) + "&password=" + urllib.quote_plus(password) + "&name=" + urllib.quote_plus(name) + "&osTypeCode=" + str(get_os_type_code()) +"&supportedApplications=" + urllib.quote_plus(spapp)
        try:
            prop = communication.get_url_prop(url, self.get_proxy_info())
        except:
            raise Exception("CONNECT_ERROR")
        if 'error' in prop:
            raise Exception(prop['error'])
        #Installa chiave
        self._config_semaphore.acquire()
        try:
            self._config['key']=prop['key']
            self._config['password']=obfuscate_password(prop['password'])
            self._config['enabled']=True
            self._write_config_file()
        finally:
            self._config_semaphore.release()
        self._reload_config()
    
    def install_key(self,  code):
        spapp = ";".join(self.get_supported_applications())
        url = self._agent_url_primary + "checkInstallCode.dw?code=" + urllib.quote_plus(code) + "&osTypeCode=" + str(get_os_type_code()) +"&supportedApplications=" + urllib.quote_plus(spapp)
        try:
            prop = communication.get_url_prop(url, self.get_proxy_info())
        except:
            raise Exception("CONNECT_ERROR")
        if 'error' in prop:
            raise Exception(prop['error'])
        #Installa chiave
        self._config_semaphore.acquire()
        try:
            self._config['key']=prop['key']
            self._config['password']=obfuscate_password(prop['password'])
            self._config['enabled']=True
            self._write_config_file()
        finally:
            self._config_semaphore.release()
        self._reload_config()
        
    def remove_key(self):
        self._config_semaphore.acquire()
        try:
            bok=False
            if 'key' in self._config:
                del(self._config['key'])
                bok=True
            if 'password' in self._config:
                del(self._config['password'])
                bok=True
            if 'enabled' in self._config:
                del(self._config['enabled'])
                bok=True
            self._write_config_file()
        finally:
            self._config_semaphore.release()
        if not bok:
            raise Exception("KEY_NOT_INSTALLED")
        self._reload_config()
    
    
    def _get_config(self, key, default=None):
        self._config_semaphore.acquire()
        try:
            if self._config is not None:
                if key in self._config:
                    return self._config[key]
                else:
                    return default
            else:
                return default
        finally:
            self._config_semaphore.release()
    
    def get_config_str(self, key):
        if (key=="enabled"):
            return bool2str(self._get_config(key))
        elif (key=="key"):
            v = self._get_config(key)
            if v is None:
                v=""
            return v
        elif (key=="proxy_type"):
            return self._get_config(key, "SYSTEM")
        elif (key=="proxy_host"):
            return self._get_config(key, "")
        elif (key=="proxy_port"):
            v = self._get_config(key)
            if v is None:
                return ""
            else:
                return str(v)
        elif (key=="proxy_user"):
            return self._get_config(key, "")
        elif (key=="monitor_tray_icon"):
            v = self._get_config(key)
            if v is None or v is True:
                v="True"
            else:
                v="False"
            return v
        else:
            raise Exception("INVALID_CONFIG_KEY")
    
    def _set_config(self, key, val):
        self._config_semaphore.acquire()
        try:
            self._config[key]=val
            self._write_config_file()
        finally:
            self._config_semaphore.release()

    def set_config_str(self, key, val):
        if (key=="enabled"):
            b=str2bool(val)
            self._set_config(key, b)
            self._agent_enabled = b
            self._reload_config()
        elif (key=="monitor_tray_icon"):
            b=str2bool(val)
            self._set_config(key, b)
        else:
            raise Exception("INVALID_CONFIG_KEY")
    
    def _check_hash_file(self, fpath, shash):
        md5 = hashlib.md5()
        with open(fpath,'rb') as f: 
            for chunk in iter(lambda: f.read(8192), b''): 
                md5.update(chunk)
        h = md5.hexdigest()
        if h!=shash:
            raise Exception("Hash not valid. (file '{0}').".format(fpath))

    def _unzip_file(self, fpath, unzippath, licpath=None):
        #Decoprime il file
        zfile = zipfile.ZipFile(fpath)
        try:
            for nm in zfile.namelist():
                #print "UNZIP:" + nm
                npath=unzippath
                if nm.startswith("LICENSES"):
                    if licpath is not None:
                        npath=licpath                
                appnm = nm
                appar = nm.split("/")
                if (len(appar)>1):
                    appnm = appar[len(appar)-1]
                    npath+= nm[0:len(nm)-len(appnm)].replace("/",os.sep)
                if not os.path.exists(npath):
                    os.makedirs(npath)
                npath+=appnm
                if os.path.exists(npath):
                    os.remove(npath)
                fd = open(npath,"wb")
                fd.write(zfile.read(nm))
                fd.close()
        finally:
            zfile.close()

    def _check_update_file(self, cur_vers, rem_vers, name_file, folder):
        if name_file in cur_vers:
            cv = cur_vers[name_file]
        else:
            cv = "0"
        if name_file + '@version' in rem_vers:
            rv = rem_vers[name_file + '@version']
            if cv!=rv:
                if not os.path.exists(folder):
                    os.makedirs(folder)
                self.write_info("Downloading file update " + name_file + "...")
                app_url = self._agent_url_node + "getAgentFile.dw?name=" + name_file + "&version=" + rem_vers[name_file + '@version']
                app_file = folder + name_file
                communication.download_url_file(app_url ,app_file, self.get_proxy_info(), None)
                self._check_hash_file(app_file, rem_vers[name_file + '@hash'])
                self._unzip_file(app_file, folder)
                os.remove(app_file)
                cur_vers[name_file]=rv
                self.write_info("Downloaded file update " + name_file + ".")
                return True
        return False
    
    def _monitor_update_file_create(self):
        try:
            if not os.path.exists("monitor.update"):
                stopfile= open("monitor.update", "w")
                stopfile.close()
                time.sleep(5)
        except Exception as e:
            self.write_except(e)
    
    def _monitor_update_file_delete(self):
        try:
            if os.path.exists("monitor.update"):
                os.remove("monitor.update") 
        except Exception as e:
            self.write_except(e)
                
    def _check_update(self):
        devmode = self._get_config('develop_mode',False)
        if devmode:
            return True
        if self._is_reboot_agent() or self._update_ready:
            return False
        #self.write_info("Checking update...")
        try:
            #Verifica se è presente un aggiornamento incompleto
            if os.path.exists("update"):
                self.write_info("Update incomplete: Needs reboot.")
                self._update_ready=True
                return False
            f = open('fileversions.json')
            cur_vers = json.loads(f.read())
            f.close()
            self._agent_url_node=None
            try:
                app_url = self._agent_url_primary + "getAgentFile.dw?name=files.xml"
                rem_vers= communication.get_url_prop(app_url, self.get_proxy_info())
                if "error" in rem_vers:
                    self.write_info("Checking update: Error read files.xml: " + rem_vers['error'])
                    return False
                if "nodeUrl" in rem_vers:
                    self._agent_url_node=rem_vers['nodeUrl']
                if self._agent_url_node is None or self._agent_url_node=="":
                    self.write_info("Checking update: Error read files.xml: Node not available.")
                    return False
            except Exception as e:
                self.write_info("Checking update: Error read files.xml: " + str(e))
                return False            
            
            #Rimuove updateTMP
            if os.path.exists("updateTMP"):
                shutil.rmtree("updateTMP")
            
            
            ver_bit="_" + get_arch()
            if is_os_32bit():
                ver_bit+="_32"
            elif is_os_64bit():
                ver_bit+="_64"
            
            #UPDATER
            if not self._runonfly:
                upd_pthnm=None
                upd_libnm=None
                if not self._runonfly:
                    if get_arch()=="x86":
                        if is_windows():
                            upd_pthnm="win"
                            upd_libnm="dwagupd.dll"                
                        elif is_linux():
                            upd_pthnm="linux"
                            upd_libnm="dwagupd"
                        elif is_mac():
                            upd_pthnm="mac"
                            upd_libnm="dwagupd"
                    if upd_libnm is not None:
                        if self._check_update_file(cur_vers, rem_vers, "agentupd_" + upd_pthnm + ver_bit + ".zip",  "updateTMP" + os.sep + "native" + os.sep):
                            if os.path.exists("updateTMP" + os.sep + "native" + os.sep + upd_libnm):
                                if os.path.exists("native" + os.sep + upd_libnm):
                                    os.remove("native" + os.sep + upd_libnm)
                                shutil.move("updateTMP" + os.sep + "native" + os.sep + upd_libnm, "native" + os.sep + upd_libnm)
                    
            #AGENT
            self._check_update_file(cur_vers, rem_vers, "agent.zip",  "updateTMP" + os.sep)
            if not self._runonfly:
                if self._check_update_file(cur_vers, rem_vers, "agentui.zip",  "updateTMP" + os.sep):
                    self._monitor_update_file_create()
            self._check_update_file(cur_vers, rem_vers, "agentapps.zip",  "updateTMP" + os.sep)
                                    
            #LIB
            if get_arch()=="x86":
                if is_windows():
                    self._check_update_file(cur_vers, rem_vers, "agentlib_win" + ver_bit + ".zip",  "updateTMP" + os.sep + "native" + os.sep)
                elif is_linux():
                    None
                elif is_mac():
                    None
                    
            #GUI
            monitor_pthnm=None
            monitor_libnm=None
            if not self._runonfly:
                if get_arch()=="x86":
                    if is_windows():
                        monitor_pthnm="win"
                        monitor_libnm="dwaggdi.dll"                
                    elif is_linux():
                        monitor_pthnm="linux"
                        monitor_libnm="dwaggdi.so"
                    elif is_mac():
                        monitor_pthnm="mac"
                        monitor_libnm="dwaggdi.so"
                #AGGIORNAMENTO LIBRERIE UI
                if monitor_pthnm is not None:
                    if self._check_update_file(cur_vers, rem_vers, "agentui_" + monitor_pthnm + ver_bit + ".zip",  "updateTMP" + os.sep + "native" + os.sep):
                        self._monitor_update_file_create()
                        if os.path.exists("updateTMP" + os.sep + "native" + os.sep + monitor_libnm):
                            shutil.move("updateTMP" + os.sep + "native" + os.sep + monitor_libnm, "updateTMP" + os.sep + "native" + os.sep + monitor_libnm + "NEW")
                
            if os.path.exists("updateTMP"):
                s = json.dumps(cur_vers , sort_keys=True, indent=1)
                f = open("updateTMP" + os.sep + "fileversions.json", "wb")
                f.write(s)
                f.close()
                shutil.move("updateTMP", "update")
                self.write_info("Update ready: Needs reboot.")
                self._update_ready=True
                return False
        except Exception as e:
            if os.path.exists("updateTMP"):
                shutil.rmtree("updateTMP")
            self.write_except(e)
            return False        
        
        #AGGIORNAMENTI LIBRERIE UI
        try:
            monitor_libnm=None            
            if is_windows():
                monitor_libnm="dwaggdi.dll"
            elif is_linux():
                monitor_libnm="dwaggdi.so"
            elif is_mac():
                monitor_libnm="dwaggdi.so"
            if monitor_libnm is not None:
                if os.path.exists("native" + os.sep + monitor_libnm + "NEW"):
                    if os.path.exists("native" + os.sep + monitor_libnm):
                        os.remove("native" + os.sep + monitor_libnm)
                    shutil.move("native" + os.sep + monitor_libnm + "NEW", "native" + os.sep + monitor_libnm)
        except:
            self.write_except("Update monitor ready: Needs reboot.")
        self._monitor_update_file_delete()
        
        return True
    
    def _reload_config(self):
        self._config_semaphore.acquire()
        try:
            self._cnt = self._cnt_max
            self._cnt_random = 0
            self._breloadconfig=True
        finally:
            self._config_semaphore.release()
    
    def _reload_config_reset(self):
        self._config_semaphore.acquire()
        try:
            self._breloadconfig=False
        finally:
            self._config_semaphore.release()
    
    def _is_reload_config(self):
        self._config_semaphore.acquire()
        try:
            return self._breloadconfig
        finally:
            self._config_semaphore.release()    
    
    def _reboot_agent(self):
        self._config_semaphore.acquire()
        try:
            self._cnt = self._cnt_max
            self._cnt_random = 0
            self._brebootagent=True
        finally:
            self._config_semaphore.release()
    
    def _reboot_agent_reset(self):
        self._config_semaphore.acquire()
        try:
            self._brebootagent=False
        finally:
            self._config_semaphore.release()
    
    def _is_reboot_agent(self):
        self._config_semaphore.acquire()
        try:
            return self._brebootagent
        finally:
            self._config_semaphore.release()    
    
    def _reload_agent(self):
        self._config_semaphore.acquire()
        try:
            self._breloadagent=True
        finally:
            self._config_semaphore.release()
    
    def _reload_agent_reset(self):
        self._config_semaphore.acquire()
        try:
            self._breloadagent=False
        finally:
            self._config_semaphore.release()
    
    def _is_reload_agent(self):
        self._config_semaphore.acquire()
        try:
            return self._breloadagent
        finally:
            self._config_semaphore.release()
    
    def _elapsed_max(self):
        self._config_semaphore.acquire()
        try:
            if self._cnt_random>0:
                self._cnt_random=self._cnt_random-1
                return False
            else:
                if self._cnt >= self._cnt_max:
                    self._cnt_random = random.randrange(0, self._cnt_max) #Evita di avere connessioni tutte assieme
                    self._cnt=0
                    return True
                else:
                    self._cnt+=1
                    return False
        finally:
            self._config_semaphore.release()
        
    def start(self):
        self.write_info("Start agent manager")
        apparchbit=" (" + get_arch()
        if is_os_32bit():
            apparchbit+=" 32bit"
        elif is_os_64bit():
            apparchbit+=" 64bit"
        else:
            apparchbit+="unknown "
        apparchbit+=")"
        self.write_info("Runtime: Python " + str(sys.version_info.major) + "." + str(sys.version_info.minor) + "." + str(sys.version_info.micro) + apparchbit)
        self.write_info("SSL: " + communication.get_ssl_info());
        
        
        if self._runonfly:
            fieldsdef=[]
            fieldsdef.append({"name":"status","size":50})
            fieldsdef.append({"name":"user","size":30})
            fieldsdef.append({"name":"password","size":20})
            fieldsdef.append({"name":"pid","size":20})
            self._runonfly_sharedmem=sharedmem.Property()
            self._runonfly_sharedmem.create("runonfly", fieldsdef)
            self._runonfly_sharedmem.set_property("status", "CONNECTING")
            self._runonfly_sharedmem.set_property("user", "")
            self._runonfly_sharedmem.set_property("password", "")
            self._runonfly_sharedmem.set_property("pid", str(os.getpid()))
        
        if not self._runonfly or self._runonfly_action is None:
            #Legge pid
            self._check_pid_cnt=0
            self._svcpid=None
            if os.path.exists("dwagent.pid"):
                try:
                    f = open("dwagent.pid")
                    spid = f.read()
                    f.close()
                    self._svcpid = int(spid)
                except Exception:
                    None
            
            if self._noctrlfile==False:
                #Crea il file .start
                f = open("dwagent.start", 'wb')
                f.close()
        
                
        #Crea cartelle necessarie
        if not os.path.exists("native"):
            os.makedirs("native")
        
        #Crea taskpool
        self._task_pool = ThreadPool(self, 15, 30)
        
        #Avvia agent status
        if not self._runonfly:
            try:
                self._agent_status_config=agent_status_config.Main(self)
                self._agent_status_config.start()
            except Exception as asc:
                self.write_except(asc, "INIT STATUSCONFIG LISTENER: ")
        self._update_ready=False
        while self.is_run() is True and not self._is_reboot_agent() and not self._update_ready:
            if self._elapsed_max():
                communication.release_detected_proxy()
                if self._runonfly:
                    self._update_onfly_status("CONNECTING")
                #Carica il config file
                if self._is_reload_config():
                    self._read_config_file()
                    if self._config is not None:
                        self._reload_config_reset()
                
                #Avvia il listener (PER USI FUTURI)
                if not self._runonfly:
                    if self._agent_listener is None:
                        try:
                            self._agent_listener = agent_listener.Main(self._get_config('listen_port', 7950), self)
                            self._agent_listener.start()                
                        except Exception as ace:
                            self.write_except(ace, "INIT LISTENER: ")
                        
                self._reboot_agent_reset()
                if not (self._agent_enabled is False and self._agent_status == self._STATUS_DISABLE):
                    #Legge la configurazione
                    if self._config is not None:
                        self._agent_enabled = self._get_config('enabled',True)
                        if self._agent_enabled is False:
                            self.write_info("Agent disabled")
                            self._agent_status = self._STATUS_DISABLE
                        elif self._load_config() is True:
                            self.write_info("Agent enabled")
                            self._agent_status = self._STATUS_UPDATING
                            #Verifica se ci sono aggiornamenti
                            if self._check_update() is True:
                                #Avvia l'agente
                                if self._run_agent() is True and self._agent_enabled is True:
                                    self._cnt = self._cnt_max
                                    self._cnt_random = random.randrange(self._cnt_min, self._cnt_max) #Evita di avere connessioni tutte assieme
                            self._agent_status = self._STATUS_OFFLINE
                if self._runonfly:
                    self._runonfly_conn_retry+=1
                    self._update_onfly_status("WAIT:" + str(self._runonfly_conn_retry))
            time.sleep(1)
        self._task_pool.destroy()
        self._task_pool = None
        
        if self._agent_listener is not None:
            try:
                self._agent_listener.close()
            except Exception as ace:
                self.write_except(ace, "TERM LISTNER: ")
        
        if self._agent_status_config is not None:
            try:
                self._agent_status_config.close()
            except Exception as ace:
                self.write_except(ace, "TERM STATUSCONFIG LISTENER: ")
        
        if self._runonfly_sharedmem is not None:
            try:
                self._runonfly_sharedmem.close()
                self._runonfly_sharedmem=None
            except Exception as ace:
                self.write_except(ace, "CLOSE RUNONFLY SHAREDMEM: ")
            
        self.write_info("Stop agent manager");
        
    def _check_pid(self, pid):
        if self._svcpid is not None:
            if self._svcpid==-1:
                return False
            elif self._check_pid_cnt>15:
                self._check_pid_cnt=0
                if not self._osmodule.is_task_running(pid):
                    self._svcpid=-1
                    return False
            else:
                self._check_pid_cnt+=1
        return True

    def is_run(self):
        if self._runonfly and self._runonfly_action is not None:
            ret = self._update_onfly_status("ISRUN")
            if ret is not None:
                return ret
            return self._brun
        else:
            if self._noctrlfile==True:
                return not self._bstop
            else:
                if os.path.exists("dwagent.stop"):
                    return False
                if self._svcpid is not None:
                    if not self._check_pid(self._svcpid):
                        return False
                return self._brun

    def destroy(self):
        self._brun=False
    
    def kill(self):
        if self._agent_status_config is not None:
            try:
                self._agent_status_config.close()
            except Exception as ace:
                self.write_except(ace, "TERM STATUS LISTENER: ")

    def _write_log(self, level, msg):
        self._agent_log_semaphore.acquire()
        try:
            ar = []
            ar.append(threading.current_thread().name)
            ar.append(" ")
            ar.append(msg)
            self._logger.log(level, ''.join(ar))
        finally:
            self._agent_log_semaphore.release()

    def write_info(self, msg):
        self._write_log(logging.INFO,  msg)

    def write_err(self, msg):
        self._write_log(logging.ERROR,  msg)
        
    def write_debug(self, msg):
        self._write_log(logging.DEBUG,  msg)
    
    def write_except(self, e,  tx = ""):
        msg = tx
        msg += str(e)
        msg += "\n" + traceback.format_exc()
        #msg += e.__class__.__name__
        #if e.args is not None and len(e.args)>0 and e.args[0] != '':
        #        msg = e.args[0]
        self._write_log(logging.ERROR,  msg)
    
    def _update_onfly_status(self,st):
        if self._runonfly:
            if self._runonfly_sharedmem is not None:
                if st!="ISRUN":
                    self._runonfly_sharedmem.set_property("status", st)
                    if st=="CONNECTED":
                        self._runonfly_sharedmem.set_property("user", self._runonfly_user)
                        self._runonfly_sharedmem.set_property("password", self._runonfly_password)
                    else:
                        self._runonfly_sharedmem.set_property("user", "")
                        self._runonfly_sharedmem.set_property("password", "")
            
            #RIMASTO PER COMPATIBILITA' CON VECCHIE CARTELLE RUNONFLY
            if self._runonfly_action is not None:
                prm=None
                if st=="CONNECTED":
                    prm={"action":"CONNECTED","user":self._runonfly_user,"password":self._runonfly_password}
                elif st=="CONNECTING":
                    prm={"action":"CONNECTING"}
                elif st=="ISRUN":
                    prm={"action":"ISRUN"}
                elif st is not None and st.startswith("WAIT:"):
                    prm={"action":"WAIT", "retry": int(st.split(":")[1])}            
                if prm is not None:
                    return self._runonfly_action(prm)            
        return None
    
    def _run_agent(self):
        self.write_info("initializing agent.");
        ses = None
        try:
            prop = {}
            prop['host'] = self._agent_server
            prop['port'] = self._agent_port
            prop['methodConnectPort']  = self._agent_method_connect_port
            prop['instance'] = self._agent_instance
            prop['userName'] = 'AG' + self._agent_key
            prop['password'] = self._agent_password
            prop['localeID'] = 'en_US'
            prop['version'] = self._agent_version
            #RIMASTO PER COMPATIBILITA' CON VECCHIE CARTELLE RUNONFLY            
            if self._runonfly and self._runonfly_action is not None: 
                ses = communication.Session(self._task_pool, {"on_message": self._on_msg});
            else:            
                ses = communication.Session(self, {"on_message": self._on_msg});
            ses.open(prop, self.get_proxy_info())
            self._session=ses
            self._connections={}
            self._apps={}
            self._apps_to_reload={}
            self._reload_agent_reset()
            #ready agent
            m = {
                    'name':  'ready', 
                    'osType':  get_os_type(),
                    'osTypeCode':  str(get_os_type_code()), 
                    'fileSeparator':  os.sep,
                    'supportedApplications': ";".join(self.get_supported_applications())
                }
            #Invia le informazioni di file version
            devmode = self._get_config('develop_mode',False)
            if not devmode:
                f = open('fileversions.json')
                cur_vers = json.loads(f.read())
                f.close()
                for vn in cur_vers:
                    if vn[0:4]!="app_":
                        m["version@" + vn]=cur_vers[vn]
            
            ses.send_message(m)
            self._agent_status = self._STATUS_ONLINE
            self.write_info("initialized agent.")
            if self._runonfly:
                self._update_onfly_status("CONNECTED")
                self._runonfly_conn_retry=0
            
            rnd_wait_reload=-1
            while self.is_run() and not ses.is_close() and not self._is_reboot_agent() and not self._is_reload_config():
                time.sleep(1)
                if rnd_wait_reload==0:
                    self._agent_connection_semaphore.acquire()
                    try:
                        if len(self._connections)==0:
                            break
                    finally:
                        self._agent_connection_semaphore.release()
                elif rnd_wait_reload>0:
                    rnd_wait_reload-=1
                elif rnd_wait_reload==-1:
                    if self._is_reload_agent():
                        #ATTENDE UN TEMPO CASUALE PER NON RIAVVIARE TUTTI GLI AGENTI ASSIEME
                        rnd_wait_reload = random.randrange(0, 86400) # 24 ORE

            if self._runonfly:
                self._runonfly_user=None
                self._runonfly_password=None
            return True
        except Exception as inst:
            self.write_except(inst);
            return False
        finally:
            self._close_all_connections()
            if ses is not None:
                self.write_info("terminated agent.");
                self._session=None
                self._connections={}
                self._destroy_apps()
                ses.close()
            self._reload_agent_reset()
    
    def get_supported_applications(self):
        return applications.get_supported(self)
    
    def _update_app_file(self, cur_vers, rem_vers, name_file,  folder):
        if name_file in cur_vers:
            cv = cur_vers[name_file]
        else:
            cv = "0"
        rv  = rem_vers[name_file + '@version']
        if cv!=rv:
            app_file = folder + name_file
            if os.path.exists(app_file):
                os.remove(app_file)
            self.write_info("Downloading file " + name_file + "...")
            app_url = self._agent_url_node + "getAgentFile.dw?name=" + name_file + "&version=" + rem_vers[name_file + '@version']
            communication.download_url_file(app_url ,app_file, self.get_proxy_info(), None)
            self._check_hash_file(app_file, rem_vers[name_file + '@hash'])
            self._unzip_file(app_file, folder,"." + os.sep)
            os.remove(app_file)
            cur_vers[name_file]=rv
            self.write_info("Downloaded file " + name_file + ".")
            return True
        return False
    
    def _update_app_file_exists(self,arfiles,name):
        for fn in arfiles:
            if fn==name:
                return True
        return False
    
    def _update_app(self,name):
        devmode = self._get_config('develop_mode',False)
        if devmode:
            return
        try:
            self.write_info("Checking update app " + name + "...")
            rem_vers=None
            try:
                app_url = self._agent_url_node + "getAgentFile.dw?name=files.xml"
                rem_vers = communication.get_url_prop(app_url, self.get_proxy_info())
            except Exception as e:
                raise Exception("Error read files.xml: "  + str(e))
            if "error" in rem_vers:
                raise Exception("Error read files.xml: " + rem_vers['error'])
            #Verifica se esiste l'applicazione
            arfiles = rem_vers['files'].split(";")
            if self._update_app_file_exists(arfiles, "app_" + name + ".zip"):
                bupdatefvers=False 
                f = open('fileversions.json')
                cur_vers = json.loads(f.read())
                f.close()
                if not os.path.exists("apps"):
                    os.makedirs("apps")
                if not os.path.exists("apps" + os.sep + "__init__.pyc"):
                    import compileall
                    f = open("apps" + os.sep + "__init__.py", "wb")
                    f.close()
                    compileall.compile_file("apps" + os.sep + "__init__.py")
                    os.remove("apps" + os.sep + "__init__.py")
                bup = self._update_app_file(cur_vers, rem_vers, "app_" +  name + ".zip",  "apps" + os.sep)
                if bup:
                    bupdatefvers=True
                namelib=name;
                if is_windows():
                    namelib+="_win"
                elif is_linux():
                    namelib+="_linux"
                elif is_mac():
                    namelib+="_mac"
                else:
                    raise Exception("Unknown operating system")
                namelib+="_" + get_arch()
                if is_os_32bit():
                    namelib+="_32"
                elif is_os_64bit():
                    namelib+="_64"
                if self._update_app_file_exists(arfiles,"app_" + namelib + ".zip"):
                    bup = self._update_app_file(cur_vers, rem_vers, "app_" + namelib + ".zip",  "native" + os.sep)
                    if bup:
                        bupdatefvers=True
                if bupdatefvers:                
                    s = json.dumps(cur_vers , sort_keys=True, indent=1)
                    f = open("fileversions.json", "wb")
                    f.write(s)
                    f.close()
                self.write_info("App " + name + " updated.")
            else:
                raise Exception("Not found.")
        except Exception as e:
            raise Exception("Error updating app " + name + ": " + str(e))
            
    
    def get_app(self,name):
        self._appsload_semaphore.acquire()
        try:
            if name in self._apps_to_reload:
                if name in self._apps:
                    try:
                        if self._destroy_app(name,False):
                            del self._apps[name]
                            del self._apps_to_reload[name]
                    except Exception as e:
                        raise Exception("Error destroy app " + name + " to reload: " + str(e))
                else:
                    del self._apps_to_reload[name]
            if name not in self._apps:
                self.write_info("Loading app " + name + "...")
                self._update_app(name)
                func=None
                try:
                    objlib = importlib.import_module("apps." + name)
                    reload(objlib)
                    func = getattr(objlib,  'Main')
                    ret = func(self)
                    self._apps[name]=ret;
                    self.write_info("App " + name + " loaded.")
                except Exception as e:
                    raise Exception("Error loading app " + name + ": " + str(e))
            return self._apps[name]
        except Exception as e:
            self.write_except(e);
            raise e
        finally:
            self._appsload_semaphore.release()
    
    def _destroy_app(self, name, force):
        md = self._apps[name]
        try:
            #self.write_info("Destroy app " + name + "...")
            func_destroy = getattr(md,  'destroy')
            #self.write_info("App " + name + " destroyed.")
            return func_destroy(force)
        except AttributeError:
            None
        return True
            
    def _destroy_apps(self):
        self._appsload_semaphore.acquire()
        try:
            for k in self._apps:
                try:
                    self._destroy_app(k,True)
                except Exception as e:
                    self.write_except(e)
            self._apps={}
        finally:
            self._appsload_semaphore.release()
            
    def _fire_close_conn_apps(self, idconn):
        for k in self._apps:
            md = self._apps[k]
            try:
                func = None
                try:
                    func = getattr(md,  'on_conn_close')
                except AttributeError:
                    None
                if func is not None:
                    func(idconn)
            except Exception as e:
                self.write_except(e)
    
    def _close_all_connections(self):
        self._agent_connection_semaphore.acquire()
        try:
            conn = self._connections
            for sid in conn.keys():
                #self._fire_close_conn_apps(sid)
                conn[sid].close();
                #del conn[sid]
        finally:
            self._agent_connection_semaphore.release()
            
    def _on_msg(self,  msg):
        ses = self._session
        try:
            if ses is None:
                return
            msg_name = msg["name"]
            if msg_name=="reboot":
                self._reboot_agent()
            elif msg_name=="reload":
                self._reload_agent()
            elif msg_name=="reloadApps":
                self._appsload_semaphore.acquire()
                try:
                    arAppsUpdated = msg["appsUpdated"].split(";")
                    for appmn in arAppsUpdated:
                        self._apps_to_reload[appmn]=True
                finally:
                    self._appsload_semaphore.release()
            if msg_name=="openConnection":
                self.init_connection(msg)
        except Exception as e:
            self.write_except(e)
            me = str(e)
            #me=''
            #if e.args is not None and len(e.args)>0 and e.args[0] != '':
            #    me += e.args[0]
            m = {
                'name': 'error' , 
                'requestKey':  msg['requestKey'] , 
                'class':  e.__class__.__name__ , 
                'message':  me
            }
            ses.send_message(m)

    def init_connection(self, msg):
        id_agent=msg["idAgent"]
        ses = self._session
        conn = self._connections
        sid = None
        sidStream = None
        self._agent_connection_semaphore.acquire()
        try:
            while True:
                sid = id_agent + "@" + generate_key(20)
                if sid not in conn:
                    cinfo=Connection(self,sid,json.loads(msg["permissions"]))
                    conn[sid]=cinfo
                    sidStream=cinfo.get_id_stream()
                    break                
        finally:
            self._agent_connection_semaphore.release()
        m = {
                'name': 'response', 
                'requestKey':  msg["requestKey"], 
                'id':  sid,
                'idStream': sidStream
            }
        ses.send_message(m)
        self.write_debug("initConnection (id=" + sid + ")");


    def term_connection(self, conn):
        self._agent_connection_semaphore.acquire()
        try:
            sid = conn.get_id_connection()
            self._fire_close_conn_apps(sid)
            del self._connections[sid]
        finally:
            self._agent_connection_semaphore.release()
        self.write_debug("termConnection (id=" + sid + ")");
    
    def get_app_permission(self,cinfo,name):
        prms = cinfo.get_permissions()
        if "applications" in prms:
            for a in prms["applications"]:
                if name == a["name"]:
                    return a
        return None
    
    def has_app_permission(self,cinfo,name):
        prms = cinfo.get_permissions()
        if prms["fullAccess"]:
            return True
        else:
            return self.get_app_permission(cinfo,name) is not None
            
    
    def invoke_app(self, app_name, cmd_name, cinfo, params):
        objmod = self.get_app(app_name)
        if not objmod.has_permission(cinfo):
            raise Exception('Permission denied to invoke app ' + app_name + '.')
        func=None
        try:
            func = getattr(objmod, 'req_' + cmd_name)
        except AttributeError:
            raise Exception('Command ' + cmd_name + ' not found in app ' + app_name + '.')
        else:
            ret = func(cinfo, params)
            return ret
        


class Connection():
    
    def __init__(self, agent, idconn, perms):
        self._agent=agent
        self._bclose = False
        self._stream = self._agent.get_session().new_stream({"on_data": self._on_data, "on_close": self._on_close})
        self._idstream = self._stream.get_idstream()
        self._idconnection = idconn
        self._permissions = perms
        self._semaphore = threading.Condition()
        self._semaphore_req = threading.Condition()
        self._pending_req={}

    def get_id_connection(self):
        return self._idconnection
    
    def get_id_stream(self):
        return self._idstream
    
    def get_permissions(self):
        return self._permissions
    
    def is_close(self):
        ret = True
        self._semaphore.acquire()
        try:
            ret=self._bclose
        finally:
            self._semaphore.release()
        return ret
    
    def send_response(self,msg,resp):
        m = {
                'name': 'response', 
                'requestKey':  msg['requestKey'], 
                'content':  resp
            }
        if "module" in msg:
            m["module"] = msg["module"]
        if "command" in msg:
            m["command"] = msg["command"]
        self.send_message(m);    
        
    
    def send_message(self,msg):
        ardt = []
        communication.Session.send_message_append(ardt,"dataweb.comunication.Message".encode('utf-8'))
        communication.Session.send_message_append(ardt,"java.lang.String".encode('utf-8'))
        communication.Session.send_message_append(ardt,"CUSTOM".encode('utf-8'))
        #Aggiunge numero elementi
        ardt.append(struct.pack('!i',len(msg)))
        #Aggiunge elementi
        for key in msg.iterkeys():
            communication.Session.send_message_append(ardt,"java.lang.String".encode('utf-8'))
            communication.Session.send_message_append(ardt,key.encode('utf-8'))
            communication.Session.send_message_append(ardt,"java.lang.String".encode('utf-8'))
            communication.Session.send_message_append(ardt,msg[key].encode('utf-8'))
        data = zlib.compress(''.join(ardt))
        sendsz=8*1024
        reqKey = msg['requestKey'].encode("ascii")
        szk = len(reqKey)
        p=0
        while p<len(data):
            szdt=len(data)-p;
            if szdt>sendsz-(4 + szk + 1):
                szdt=sendsz
            cend='0'
            if p+szdt>=len(data):
                cend='1'
            sztot=4+szk+szdt+1
            self._stream.send_data("".join([struct.pack('!I',sztot),struct.pack('!I',szk),reqKey,data[p:p+szdt],cend]))
            p+=szdt
    
    def _on_data(self, stream, data):
        msg = None
        try:
            lenkey=struct.unpack('!I',data[0:4])[0]
            key=data[4:4+lenkey]
            last=data[len(data)-1]
            data=data[4+lenkey:len(data)-1]
            
            dtreq = None
            self._semaphore_req.acquire()
            try:
                if key not in self._pending_req:
                    self._pending_req[key]=[]
                self._pending_req[key].append(data)
                if last=='1':
                    dtreq=''.join(self._pending_req[key])
                    del self._pending_req[key]
            finally:
                self._semaphore_req.release()
            
            if dtreq is not None:
                msg = communication.SessionRead.parse_message(zlib.decompress(dtreq))
                msg = msg["data"]
                if msg is None:
                    raise Exception("Invalid message.")
                if 'requestKey' not in msg:
                    raise Exception("Invalid message missing requestKey.")
                if 'name' not in msg:
                    raise Exception("Invalid message missing name.")
                #print("\ndata:\n" + str(msg) + "\n\n")
        except Exception as e:
            m = str(e)
            self._agent.write_debug(m)
            self.close()
            raise e
        
        if msg is not None:
            self._agent._task_pool.execute(self._on_message, msg)
    
    def _on_message(self, msg):
        try:
            msg_name = msg["name"]
            if msg_name=="close":
                self.close()
            elif msg_name=="request":
                self._request(msg)
            elif msg_name=="download":
                self._download(msg)
            elif msg_name=="upload":
                self._upload(msg)
            elif msg_name=="websocket":
                self._websocket(msg)
            else:
                raise Exception("Invalid message name: " + msg_name)
        except Exception as e:
            self._agent.write_except(e)
            me = str(e)
            #me=''
            #if e.args is not None and len(e.args)>0 and e.args[0] != '':
            #    me += e.args[0]
            m = {
                'name': 'error' , 
                'requestKey':  msg['requestKey'] , 
                'class':  e.__class__.__name__ , 
                'message':  me
            }
            self.send_message(m)
        
    
    def _request(self, msg):
        resp = ""
        try:
            app_name = msg["module"]
            cmd_name = msg["command"]
            params = {}
            params["requestKey"]=msg['requestKey']
            sck = "parameter_";
            for key in msg.iterkeys():
                if key.startswith(sck):
                    params[key[len(sck):]]=msg[key]
            resp=self._agent.invoke_app(app_name, cmd_name, self, params)
            if resp is not None:
                resp = ":".join(["K", resp])
            else:
                resp = "K:null"
        except Exception as e:
            m = str(e)
            self._agent.write_debug(m)
            resp=  ":".join(["E", m])
        self.send_response(msg, resp)
    
    def _websocket(self, msg):
        wsock = self._agent.get_session().new_websocket(msg)
        try:
            self._agent.invoke_app(msg['module'],  "websocket",  self,  wsock)
            resp = {}
            if wsock.is_accept():
                resp["IDStream"]=wsock.get_idstream()
            else:
                resp["error"]="WebSocket not accepted"
        except Exception as e:
            resp = {}
            resp["error"]=str(e)
        resp['name']='response'
        resp['requestKey']=msg['requestKey']
        self.send_message(resp)    
    
    def _download(self, msg):
        fdownload = self._agent.get_session().new_filedownload(msg)
        try:
            self._agent.invoke_app(msg['module'],  "download",  self,  fdownload)
            resp = {}
            if fdownload.is_accept():
                mt = mimetypes.guess_type(fdownload.get_path())
                if mt is None or mt[0] is None or not isinstance(mt[0], str):
                    resp["Content-Type"] = "application/octet-stream"
                else:
                    resp["Content-Type"] = mt[0]
                resp["Content-Disposition"] = "attachment; filename=\"" + fdownload.get_name() + "\""
                #ret["Cache-Control"] = "no-cache, must-revalidate" NON FUNZIONA PER IE7
                #ret["Pragma"] = "no-cache"
                resp["Expires"] = "Sat, 26 Jul 1997 05:00:00 GMT"
                resp["IDStream"] = fdownload.get_idstream()
                resp["Length"] = str(fdownload.get_length())
                fdownload.start()
            else:
                resp["error"]="Download file not accepted"
        except Exception as e:
            resp = {}
            resp["error"]=str(e)
        resp['name']='response'
        resp['requestKey']=msg['requestKey']
        self.send_message(resp)
    
    def _upload(self, msg):
        fupload = self._agent.get_session().new_fileupload(msg)
        try:
            self._agent.invoke_app(msg['module'],  "upload",  self,  fupload)
            resp = {}
            if fupload.is_accept():
                resp["IDStream"] = fupload.get_idstream()
            else:
                resp["error"]="Download file not accepted"
        except Exception as e:
            resp = {}
            resp["error"]=str(e)
        resp['name']='response'
        resp['requestKey']=msg['requestKey']
        self.send_message(resp)
    
    def _on_close(self):
        if not self._bclose:
            self._semaphore.acquire()
            try:
                self._bclose=True
            finally:
                self._semaphore.release()
            self._agent.term_connection(self)
    
    def close(self):
        if not self._bclose:
            self._semaphore.acquire()
            try:
                self._bclose=True
            finally:
                self._semaphore.release()
            self._agent.term_connection(self)
            self._stream.close()
        
    
main = None

def ctrlHandler(ctrlType):
    return 1   


def fmain(args): #SERVE PER MACOS APP
    if is_windows():
        try:
            #Evita che si chiude durante il logoff
            HandlerRoutine = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_uint)(ctrlHandler)
            ctypes.windll.kernel32.SetConsoleCtrlHandler(HandlerRoutine, 1)
        except:
            None
    
    main = Main(args)
    main.start()
    main.unload_library()
    sys.exit(0)
    

if __name__ == "__main__":
    fmain(sys.argv)