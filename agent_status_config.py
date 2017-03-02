# -*- coding: utf-8 -*-

'''
This Source Code Form is subject to the terms of the Mozilla
Public License, v. 2.0. If a copy of the MPL was not distributed
with this file, You can obtain one at http://mozilla.org/MPL/2.0/.
'''

import threading
import time
import sys
import sharedmem
import json
import os
import hashlib
import base64
import stat

def open_property(path=None):
    prop=sharedmem.Property()
    prop.open("status_config",bpath=path)
    return prop

def invoke_request(prop, usr, pwd, req, prms=None):
    sret=""
    try:
        spid=str(os.getpid())
        bok=False
        #Attende 40 secondi
        cnt=prop.get_property("counter")
        testcnt=0
        for i in range(400):
            bok=True
            if prop.get_property("request_pid")=="": #PRONTO AD ACCETTARE RICHIESTE
                prop.set_property("request_pid",spid)
                if prms is None:
                    prms={}
                prms["_request"]=req
                prms["_user"]=usr
                #Hash password
                encpwd= hashlib.sha256(pwd).digest()
                encpwd= base64.b64encode(encpwd)
                prms["_password"]=encpwd
                
                prop.set_property("request_data",json.dumps(prms))
                prop.set_property("response_data","")
                break
            time.sleep(0.1)
            testcnt+=1
            if testcnt==20:
                testcnt=0
                appcnt=prop.get_property("counter")
                if cnt==appcnt:
                    break
        if bok:
            #Attende 40 secondi
            cnt=prop.get_property("counter")
            testcnt=0
            for i in range(400):
                sret=prop.get_property("response_data")
                #Gestione concorrenza
                if prop.get_property("request_pid")!=spid:
                    sret=""
                    break
                if sret!="":
                    break
                time.sleep(0.1)
                testcnt+=1
                if testcnt==20:
                    testcnt=0
                    appcnt=prop.get_property("counter")
                    if cnt==appcnt:
                        break
            if prop.get_property("request_pid")==spid:
                prop.set_property("response_data","")
                prop.set_property("request_data","")
            if sret=="":
                sret = 'ERROR:REQUEST_TIMEOUT'
        else:
            sret = 'ERROR:REQUEST_TIMEOUT'
    except: 
        sret = 'ERROR:REQUEST_TIMEOUT'
    return sret

class Main(threading.Thread):
    def __init__(self,agent):
        self._agent=agent
        self._prop = None
        self._status = None
        self._config = None
    
    def start(self):
        self._prop = sharedmem.Property()
        fieldsdef=[]
        fieldsdef.append({"name":"counter","size":30})
        fieldsdef.append({"name":"state","size":5})
        fieldsdef.append({"name":"connections","size":20})
        fieldsdef.append({"name":"request_pid","size":20})
        fieldsdef.append({"name":"request_data","size":1024*16})
        fieldsdef.append({"name":"response_data","size":1024*16})
        self._prop.create("status_config", fieldsdef, self._agent)
        self._prop.set_property("response_data","")
        self._prop.set_property("request_data","")
        self._prop.set_property("request_pid","")
        
        self._status=Status(self._agent,self._prop)
        self._status.start();
        self._config=Config(self._agent,self._prop)
        self._config.start();
    
    def close(self):
        if self._config!=None:
            self._config.close();
            self._config.join(5000)
        if self._status!=None:
            self._status.close();
            self._status.join(5000)
        self._prop.close()

class Status(threading.Thread):
    def __init__(self,agent,prop):
        threading.Thread.__init__(self, name="AgentStatus")
        self.daemon=True
        self._agent=agent
        self._prop=prop
        self._bclose=False
        self._cnt=0

    def run(self):
        while not self._bclose:
            if self._cnt==sys.maxint:
                self._cnt=0
            else:
                self._cnt+=1
            self._prop.set_property("counter", str(self._cnt))
            self._prop.set_property("state", str(self._agent.get_status()))
            self._prop.set_property("connections", str(self._agent.get_connection_count()))
            time.sleep(1)
        self._bclose=True        
    
    def close(self):
        self._bclose=True
        

class Config(threading.Thread):
    
    def __init__(self,agent,prop):
        threading.Thread.__init__(self, name="AgentConfig")
        self.daemon=True
        self._agent=agent
        self._prop=prop
        self._bclose=False
        self._cnt=0
        
    
    def run(self):

        while not self._bclose:
            #VARIFICA NUOVE RICHIESTE DI CONFIGURAZIONE
            request_pid = self._prop.get_property("request_pid");
            if request_pid!="":
                try:
                    request_data = None
                    #Attende 2 secondi che la richiesta
                    for i in range(20):
                        request_data = self._prop.get_property("request_data");
                        if request_data!="":
                            break
                        time.sleep(0.1)
                    if request_data is not None:
                        self._prop.set_property("response_data",self._invoke_request(request_data))                    
                        #Attende 2 secondi che la risposta venga letta
                        for i in range(20):
                            if self._prop.get_property("request_data")=="":
                                break
                            time.sleep(0.1)
                except Exception as e:
                    self._agent.write_except(e);
                self._prop.set_property("response_data","")
                self._prop.set_property("request_data","")
                self._prop.set_property("request_pid","")
            time.sleep(0.1)
        self._bclose=True
    
    def _invoke_request(self, request_data):
        if request_data!=None:
            try:
                prms=json.loads(request_data)
                req = prms["_request"]
                func = getattr(self,  '_req_' + req)
                try:
                    return func(prms)
                except Exception as e:
                    return "ERROR:" + str(e)
            except:
                return "ERROR:INVALID_REQUEST"
        else:
            return "ERROR:INVALID_REQUEST"
    
    def _req_check_auth(self, prms):
        if "_user" in prms and "_password" in prms :
            usr=prms["_user"]
            pwd=prms["_password"]
            if self._agent.check_config_auth(usr, pwd):
                return "OK"
        return "ERROR:FORBIDDEN"

    def _req_change_pwd(self, prms):
        if 'nopassword' in prms:
            nopwd = prms['nopassword']
            if nopwd=='true':
                self._agent.set_config_password("")
                return "OK"
            else:
                return "ERROR:INVALID_AUTHENTICATION"
        elif 'password' in prms:
            pwd = prms['password']
            self._agent.set_config_password(pwd)
            return "OK"
        else:
            return "ERROR:INVALID_AUTHENTICATION"
    
    def _req_set_config(self, prms):
        if "key" in prms and "value" in prms :
            key=prms["key"]
            value=prms["value"]
            self._agent.set_config_str(key, value)
            return "OK"
        return "ERROR:INVALID_PARAMETERS."
    
    def _req_get_config(self, prms):
        if "key" in prms:
            key=prms["key"]
            return "OK:" + self._agent.get_config_str(key)
        return "ERROR:INVALID_PARAMETERS."
        
    def _req_remove_key(self, prms):
        self._agent.remove_key()
        return "OK"
    
    def _req_install_key(self, prms):
        if "code" in prms:
            code=prms["code"]
            self._agent.install_key(code)
            return "OK"
        return "ERROR:INVALID_PARAMETERS."
    
    def _req_install_new_agent(self, prms):
        #user, password, name, id
        if "user" in prms and "password" in prms and "name" in prms:
            user=prms["user"]
            password=prms["password"]
            name=prms["name"]
            self._agent.install_new_agent(user,password,name)
            return "OK"
        return "ERROR:INVALID_PARAMETERS."
    
    def _req_set_proxy(self, prms):
        ptype = None
        host = None
        port = None
        user = None
        password = None
        if 'type' in prms:
            ptype = prms['type']
        if 'host' in prms:
            host = prms['host']
        if 'port' in prms and prms['port'] is not None and prms['port'].strip()!="":
            port = int(prms['port'])
        if 'user' in prms:
            user = prms['user']
        if 'password' in prms:
            password = prms['password']
        self._agent.set_proxy(ptype,  host,  port,  user,  password)
        return "OK"

    
    def close(self):
        self._bclose=True

