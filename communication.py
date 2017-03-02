# -*- coding: utf-8 -*-

'''
This Source Code Form is subject to the terms of the Mozilla
Public License, v. 2.0. If a copy of the MPL was not distributed
with this file, You can obtain one at http://mozilla.org/MPL/2.0/.
'''

import ssl
import struct
import time
import random
import json
import socket
import threading
import xml.etree.ElementTree
import zlib
import os
import shutil
import gzip
import base64
import StringIO
import traceback
import platform


#GESTIONE TOKEN MESSAGE
# 4 byte (int)    - Lunghezza del token
# 8 byte (long)   - Identificativo del messaggio
# 1 byte (byte)   - Tipo
# 2 byte (short)  - Numero di File associati al messaggio
# 2 byte (short)  - Numero di InputStream associati al messaggio
# 8 byte (long)   - Lunghezza del messaggio
# n byte          - Dati del token

_TYPE_MESSAGE = '\x00'
_TYPE_REQUEST_KEEP_ALIVE = '\x14'
_TYPE_REQUEST_OK_ALIVE = '\x15'
_TYPE_STREAM_DATA= '\x00'


#_SOCKET_TIMEOUT_CONNECT = 10
_SOCKET_TIMEOUT_READ = 20

WEBSOCKET_DATA_STRING = 's'
WEBSOCKET_DATA_BYTEARRAY = 'b';

_cacerts_path="cacerts.pem"
_proxy_detected = {}
_proxy_detected["semaphore"]=threading.Condition()
_proxy_detected["check"] = False
_proxy_detected["info"] = None

def is_windows():
    return (platform.system().lower().find("window") > -1)

def is_linux():
    return (platform.system().lower().find("linux") > -1)

def is_mac():
    return (platform.system().lower().find("darwin") > -1)

def get_ssl_info():
    sslret=ssl.OPENSSL_VERSION + " ("
    if hasattr(ssl, 'PROTOCOL_TLSv1_2'):
        sslret += "TLSv1.2" 
    elif hasattr(ssl, 'PROTOCOL_TLSv1_1'):
        sslret += "TLSv1.1"
    elif hasattr(ssl, 'PROTOCOL_TLSv1'):
        sslret += "TLSv1"
    else:
        sslret += "Unknown"
    sslret += ")"
    return sslret

def _get_ssl_ver():
    if hasattr(ssl, 'PROTOCOL_TLSv1_2'):
        return ssl.PROTOCOL_TLSv1_2 
    if hasattr(ssl, 'PROTOCOL_TLSv1_1'):
        return ssl.PROTOCOL_TLSv1_1
    if hasattr(ssl, 'PROTOCOL_TLSv1'):
        return ssl.PROTOCOL_TLSv1
    if hasattr(ssl, 'PROTOCOL_TLS'):
        return ssl.PROTOCOL_TLS
    return ssl.PROTOCOL_SSLv23 #DEFAULT

def _connect_proxy_http(sock, host, port, proxy_info):
    usr = proxy_info.get_user()
    pwd = proxy_info.get_password()
    arreq=[]
    arreq.append("CONNECT %s:%d HTTP/1.0" % (host, port))
    if usr is not None and len(usr)>0:
        auth=base64.b64encode(usr + ":" + pwd)
        arreq.append("\r\nProxy-Authorization: Basic %s" % (auth))
    arreq.append("\r\n\r\n")
    sock.sendall("".join(arreq))    
    resp = Response(sock)
    if resp.get_code() != '200':
        raise Exception("Proxy http error " + str(resp.get_code()) + ".")
    

def _connect_proxy_socks(sock, host, port, proxy_info):
    usr = proxy_info.get_user()
    pwd = proxy_info.get_password()
    if proxy_info.get_type()=='SOCKS5':
        mthreq=0x00
        if usr is not None and len(usr)>0 and pwd is not None and len(pwd)>0:
            mthreq=0x02
        arreq = []
        arreq.append(struct.pack(">BBB", 0x05, 0x01, mthreq))
        sock.sendall("".join(arreq))
        resp = sock.recv(2)
        ver = ord(resp[0:1])
        mth = ord(resp[1:2])
        if ver!=0x05 or mth!=mthreq:
            raise Exception("Proxy socks error.")
        if mth==0x02:
            arreq.append(struct.pack(">B", len(usr)))
            arreq.append(usr)
            arreq.append(struct.pack(">B", len(pwd)))
            arreq.append(pwd)
            sock.sendall("".join(arreq))
            ver = ord(resp[0:1])
            status = ord(resp[1:2])
            if ver!=0x05 or status != 0x00:
                raise Exception("Proxy socks error.")
        arreq = []
        arreq.append(struct.pack(">BBB", 0x05, 0x01, 0x00))
        try:
            addr_bytes = socket.inet_aton(host)
            arreq.append(b"\x01")
            arreq.append(addr_bytes)
        except socket.error:
            arreq.append(b"\x03")
            arreq.append(struct.pack(">B", len(host)))
            arreq.append(host)
        arreq.append(struct.pack(">H", port))
        sock.sendall("".join(arreq))
        resp = sock.recv(1024)
        ver = ord(resp[0:1])
        status = ord(resp[1:2])
        if ver!=0x05 or status != 0x00:
            raise Exception("Proxy socks error.")
    else:
        remoteresolve=False
        try:
            addr_bytes = socket.inet_aton(host)
        except socket.error:
            if proxy_info.get_type()=='SOCKS4A':
                addr_bytes = b"\x00\x00\x00\x01"
                remoteresolve=True
            else:
                addr_bytes = socket.inet_aton(socket.gethostbyname(host))               
            
        arreq = []
        arreq.append(struct.pack(">BBH", 0x04, 0x01, port))
        arreq.append(addr_bytes)
        if usr is not None and len(usr)>0:
            arreq.append(usr)
        arreq.append(b"\x00")
        if remoteresolve:
            arreq.append(host)
            arreq.append(b"\x00")
        sock.sendall("".join(arreq))
        
        resp = sock.recv(8)
        if resp[0:1] != b"\x00":
            raise Exception("Proxy socks error.")
        status = ord(resp[1:2])
        if status != 0x5A:
            raise Exception("Proxy socks error.")

def _detect_proxy_windows():
    prxi=None
    try:
        sproxy=None
        import _winreg
        aReg = _winreg.ConnectRegistry(None,_winreg.HKEY_CURRENT_USER)
        aKey = _winreg.OpenKey(aReg, r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
        try: 
            subCount, valueCount, lastModified = _winreg.QueryInfoKey(aKey)
            penabled=False
            pserver=None
            for i in range(valueCount):                                           
                try:
                    n,v,t = _winreg.EnumValue(aKey,i)
                    if n.lower() == 'proxyenable':
                        penabled = v and True or False
                    elif n.lower() == 'proxyserver':
                        pserver = v
                except EnvironmentError:                                               
                    break
            if penabled and pserver is not None:
                sproxy=pserver
        finally:
            _winreg.CloseKey(aKey)   
        if sproxy is not None:
            stp=None
            sho=None
            spr=None            
            lst = sproxy.split(";")
            for v in lst:
                if len(v)>0:
                    ar1 = v.split("=")
                    if len(ar1)==1:
                        stp="HTTP"
                        ar2 = ar1[0].split(":")
                        sho=ar2[0]
                        spr=ar2[1]
                        break
                    elif ar1[0].lower()=="http":
                        stp="HTTP"
                        ar2 = ar1[1].split(":")
                        sho=ar2[0]
                        spr=ar2[1]
                        break
                    elif ar1[0].lower()=="socks":
                        stp="SOCKS5"
                        ar2 = ar1[1].split(":")
                        sho=ar2[0]
                        spr=ar2[1]
                    
            if stp is not None:
                prxi = ProxyInfo()
                prxi.set_type(stp)
                prxi.set_host(sho)
                prxi.set_port(int(spr))
                #print "PROXY WINDOWS DETECTED:" + stp + "  " + spr
                
    except:
        None
    return prxi

def _detect_proxy_linux():
    prxi=None
    try:
        sprx=None
        sprx=os.getenv("all_proxy")
        if "http_proxy" in os.environ:
            sprx = os.environ["http_proxy"]
        elif "all_proxy" in os.environ:
            sprx = os.environ["all_proxy"]
        if sprx is not None:
            stp=None
            if sprx.endswith("/"):
                sprx=sprx[0:len(sprx)-1]            
            if sprx.lower().startswith("socks:"):
                stp="SOCKS5"
                sprx=sprx[len("socks:"):]
            elif sprx.lower().startswith("http:"):
                stp="HTTP"
                sprx=sprx[len("http:"):]
            if stp is not None:
                sun=None
                spw=None
                sho=None
                spr=None
                ar = sprx.split("@")
                if len(ar)==1:
                    ar1 = sprx[0].split(":")
                    sho=ar1[0]
                    spr=ar1[1]
                else: 
                    ar1 = sprx[0].split(":")
                    sun=ar1[0]
                    spw=ar1[1]
                    ar2 = sprx[1].split(":")
                    sho=ar2[0]
                    spr=ar2[1]
                prxi = ProxyInfo()
                prxi.set_type(stp)
                prxi.set_host(sho)
                prxi.set_port(int(spr))
                prxi.set_user(sun)
                prxi.set_password(spw)
    except:
        None
    return prxi

def release_detected_proxy():
    global _proxy_detected
    _proxy_detected["semaphore"].acquire()
    try:
        _proxy_detected["check"]=False
        _proxy_detected["info"]=None
    finally:
        _proxy_detected["semaphore"].release()

def _set_detected_proxy_none():
    global _proxy_detected
    _proxy_detected["semaphore"].acquire()
    try:
        _proxy_detected["check"]=True
        _proxy_detected["info"]=None
    finally:
        _proxy_detected["semaphore"].release()
    
def set_cacerts_path(path):
    global _cacerts_path
    _cacerts_path=path

def _connect_socket(host, port, proxy_info):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(_SOCKET_TIMEOUT_READ)
        bprxdet=False
        prxi=proxy_info
        if prxi is None or prxi.get_type() is None or proxy_info.get_type()=='SYSTEM':
            global _proxy_detected
            _proxy_detected["semaphore"].acquire()
            try:
                if not _proxy_detected["check"]:
                    try:
                        if is_windows():
                            _proxy_detected["info"] = _detect_proxy_windows()
                        elif is_linux():
                            _proxy_detected["info"] = _detect_proxy_linux()
                        elif is_mac():
                            _proxy_detected["info"]=None
                    except:
                        _proxy_detected=None
                    bprxdet=True
                prxi = _proxy_detected["info"]
                _proxy_detected["check"]=True
            finally:
                _proxy_detected["semaphore"].release()
            
        conn_ex=None    
        func_prx=None
        if prxi is None or prxi.get_type() is None or prxi.get_type()=='NONE':
            sock.connect((host, port))
        elif prxi.get_type()=='HTTP':
            try:
                sock.connect((prxi.get_host(), prxi.get_port()))
                func_prx=_connect_proxy_http
            except Exception as ep:
                conn_ex=ep
        elif prxi.get_type()=='SOCKS4' or prxi.get_type()=='SOCKS4A' or prxi.get_type()=='SOCKS5':
            try:
                sock.connect((prxi.get_host(), prxi.get_port()))
                func_prx=_connect_proxy_socks
            except Exception as ep:
                conn_ex=ep
        else:
            sock.connect((host, port))
        
        if func_prx is not None:
            try:
                func_prx(sock, host, port, prxi)
            except Exception as ep:
                conn_ex=ep
        
        if conn_ex is not None:
            if bprxdet:
                try:
                    release_detected_proxy()
                    sock.close()
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(_SOCKET_TIMEOUT_READ)
                    sock.connect((host, port)) #PROVA A COLLEGARSI SENZA PROXY
                    _set_detected_proxy_none()
                except:
                    raise conn_ex
            else:
                raise conn_ex
                
        
        #VALIDA CERITFICATI
        global _cacerts_path
        if hasattr(ssl, 'SSLContext'):
            ctx = ssl.SSLContext(_get_ssl_ver())
            ctx.verify_mode = ssl.CERT_REQUIRED
            ctx.check_hostname = True
            ctx.load_verify_locations(_cacerts_path)
            sock = ctx.wrap_socket(sock,server_hostname=host)
        else:
            iargs = None
            try:
                import inspect
                iargs = inspect.getargspec(ssl.wrap_socket).args
            except:                   
                None
            if iargs is not None and "cert_reqs" in iargs and "ca_certs" in iargs: 
                sock = ssl.wrap_socket(sock, ssl_version=_get_ssl_ver(), cert_reqs=ssl.CERT_REQUIRED, ca_certs=_cacerts_path)
            else:
                sock = ssl.wrap_socket(sock, ssl_version=_get_ssl_ver())

    except Exception as e:
        sock.close()
        raise e
    return sock

def prop_to_xml(prp):
    ardata = []
    ardata.append('<!DOCTYPE properties SYSTEM "http://java.sun.com/dtd/properties.dtd">');
    root_element = xml.etree.ElementTree.Element("properties")
    for key in prp.iterkeys():
        child = xml.etree.ElementTree.SubElement(root_element, "entry")
        child.attrib['key'] = key
        child.text = prp[key]
    ardata.append(xml.etree.ElementTree.tostring(root_element));
    return ''.join(ardata)

def xml_to_prop(s):
    prp = {}
    root = xml.etree.ElementTree.fromstring(s)
    for child in root:
        prp[child.attrib['key']] = child.text
    return prp

def _split_utl(url):
    lnhttps = 8
    #legge server e porta
    p=url[lnhttps:].find('/')
    host=url[lnhttps:lnhttps+p]
    port=443
    i=host.find(':')
    if i>=0:
        port=int(host[i+1:])
        host=host[:i]
    #Legge path
    u = url[p+lnhttps:]
    return {'host':host,  'port':port,  'path':u}

def download_url_file(urlsrc, fdest, proxy_info=None, response_transfer_progress=None):
    sredurl=None
    sp = _split_utl(urlsrc)
    #Richiesta al server
    sock = _connect_socket(sp["host"], sp["port"], proxy_info)
    try:
        req = Request("GET", sp["path"],  {'Host' : sp["host"] + ':' + str(sp["port"],),  'Connection' : 'close'})
        sock.sendall(req.to_message())
    
        #Legge risposta
        if os.path.exists(fdest):
            os.remove(fdest)
        ftmp = fdest + "TMP"
        if os.path.exists(ftmp):
            os.remove(ftmp)        
        resp = Response(sock, ftmp, response_transfer_progress)
        if resp.get_code() == '301':
            sredurl=resp.get_headers()["Location"]
        elif resp.get_code() != '200':
            raise Exception("Download error " + str(resp.get_code()) + ".")
    finally:
        sock.shutdown(1)
        sock.close();
    if sredurl is not None:
        download_url_file(sredurl, fdest, proxy_info, response_transfer_progress)
    else:
        if os.path.exists(ftmp):
            shutil.move(ftmp, fdest)

def get_url_prop(url, proxy_info=None):
    sredurl=None
    sp = _split_utl(url)
    #Richiesta al server
    sock = _connect_socket(sp["host"], sp["port"], proxy_info)
    try:
        req = Request("GET", sp["path"],  {'Host' : sp["host"] + ':' + str(sp["port"],),  'Connection' : 'close'})
        sock.sendall(req.to_message())
        
        #Legge risposta
        prpresp = None;
        resp = Response(sock)
        if resp.get_code() == '200':
            prpresp = xml_to_prop(resp.get_body())
        elif resp.get_code() == '301':
            sredurl=resp.get_headers()["Location"]
        else:
            raise Exception("Get url properties error " + str(resp.get_code())  + ".")
    finally:
        sock.shutdown(1)
        sock.close();
    if sredurl is not None:
        prpresp = get_url_prop(sredurl,proxy_info)
    return prpresp

class ProxyInfo:
    def __init__(self):
        self._type="None"
        self._host=None
        self._port=None
        self._user=None
        self._password=None
        
    def set_type(self, type):
        self._type=type
    
    def set_host(self, host):
        self._host=host
        
    def set_port(self, port):
        self._port=port
    
    def set_user(self,  user):
        self._user=user
    
    def set_password(self,  password):
        self._password=password
    
    def get_type(self):
        return self._type
    
    def get_host(self):
        return self._host
        
    def get_port(self):
        return self._port
    
    def get_user(self):
        return self._user
    
    def get_password(self):
        return self._password
        

class Request:
    def __init__(self, method, url, prp=None):
        self._method = method
        self._url = url
        self._prp = prp
        self._body = None

    def set_body(self, body):
        self._body = body

    def to_message(self):
        arhead = []
        arhead.append(self._method)
        arhead.append(' ')
        arhead.append(self._url)
        arhead.append(' ')
        arhead.append('HTTP/1.1')
        if self._prp is not None:
            for k in self._prp:
                arhead.append('\r\n')
                arhead.append(k)
                arhead.append(': ')
                arhead.append(self._prp[k])
            
        if self._body is not None:
            arhead.append('\r\n')
            arhead.append('Compression: zlib')
            arhead.append('\r\n')
            arhead.append('Content-Length: ')
            arhead.append(str(len(self._body)));
        arhead.append('\r\n')
        arhead.append('\r\n')
        if self._body is not None:
            arhead.append(self._body)
        return ''.join(arhead)

class Response_Transfer_Progress:
    
    def __init__(self, events=None):
            self._on_data=None
            self._properties={}
            self._byte_transfer=0
            self._byte_length=0
            if events is not None:
                if 'on_data' in events:
                    self._on_data=events['on_data']
    
    def set_property(self, key, value):
        self._properties[key]=value
    
    def get_property(self, key):
        if key not in self._properties:
            return None
        return self._properties[key]
    
    def get_byte_transfer(self):
        return self._byte_transfer
    
    def get_byte_length(self):
        return self._byte_length
    
    def fire_on_data(self,  byte_transfer,  byte_length):
        self._byte_transfer=byte_transfer
        self._byte_length=byte_length
        if self._on_data is not None:
            self._on_data(self)

class Response:
    def __init__(self, sock, body_file_name=None,  response_transfer_progress=None):
        data = ''
        while data.find('\r\n\r\n') == -1:
            app=sock.recv(1024 * 4)
            if app is None or len(app)==0:
                raise Exception('Close connection')
            data += app 
        ar = data.split('\r\n\r\n')
        head = ar[0].split('\r\n')
        appbody = []
        appbody.append(ar[1])
        self._code = None
        self._headers = {}
        clenkey=None
        for item in head:
            if self._code is None:
                self._code = item.split(' ')[1]
            else:
                apppos = item.index(':')
                appk=item[0:apppos].strip()
                if appk.lower()=="content-length":
                    clenkey=appk
                self._headers[appk] = item[apppos+1:].strip()
        #Legge eventuale body
        if self._code != '301' and clenkey is not None:
            self._extra_data=None
            lenbd = int(self._headers[clenkey])
            fbody=None
            try:
                if body_file_name is not None:
                    fbody=open(body_file_name, 'wb')
                    fbody.write(''.join(appbody))
                cnt=len(''.join(appbody))
                if response_transfer_progress is not None:
                    response_transfer_progress.fire_on_data(cnt,  lenbd)
                szbuff=1024*2
                buff=None
                while lenbd > cnt:
                    buff=sock.recv(szbuff)
                    if buff is None or len(buff)==0:
                        break
                    cnt+=len(buff)
                    if response_transfer_progress is not None:
                        response_transfer_progress.fire_on_data(cnt,  lenbd)
                    if body_file_name is None:
                        appbody.append(buff)
                    else:
                        fbody.write(buff)
            finally:
                if fbody is not None:
                    fbody.close()
                else:
                    self._body=''.join(appbody)
        else:
            self._extra_data=''.join(appbody)
            if len(self._extra_data)==0:
                self._extra_data=None

    def get_extra_data(self):
        return self._extra_data

    def get_code(self):
        return self._code

    def get_headers(self):
        return self._headers
    
    def get_body(self):
        return self._body


class Counter:
    def __init__(self):
        self._semaphore = threading.Condition()
        self._current_elapsed = 0
        self._current_time = long(time.time() * 1000)

    def reset(self):
        self._current_elapsed = 0
        self._current_time = long(time.time() * 1000)
    
    def is_elapsed(self, ms):
        return self.get_value()>=ms
   
    def get_value(self):
        self._semaphore.acquire()
        try:
            apptm=long(time.time() * 1000)
            elp=apptm-self._current_time
            if elp>=0:
                self._current_elapsed+=elp
                self._current_time=apptm
            else:
                self._current_time=long(time.time() * 1000)
            #print "self._current_elapsed(" + str(self) + "): " +  str(self._current_elapsed)
            return self._current_elapsed
        finally:
            self._semaphore.release()
    

class SessionRead (threading.Thread):
    
    def __init__(self, session, init_data, alive):
        threading.Thread.__init__(self, name="SessionRead")
        self.daemon=True
        self._session = session
        self._alive = alive
        self._temp_msg = {}
        self._init_data=init_data

    def _read_fully(self, sock, ln):
        data = []
        cnt=0
        while ln > cnt:
            if self._init_data is not None:
                appln=ln
                if ln>len(self._init_data):
                    appln=len(self._init_data)                
                s=self._init_data[0:appln]
                self._init_data=self._init_data[appln:]
                if len(self._init_data)==0:
                    self._init_data=None
            else:    
                s = sock.recv(ln-cnt)
            if s is None or len(s) == 0:
                return ''
            self._session._tdalive.reset();
            data.append(s)
            cnt+=len(s)
        return ''.join(data)
    
    @staticmethod
    def _parse_message_next_token(typ,str,cur):
        np = cur['pos']
        if typ=='java.lang.String':
            ln = struct.unpack('!i', str[np:np+4])[0]
            np+=4;
            cur['pos']=np+ln;
            cur['data']=str[np:np+ln].decode('utf-8')
        elif typ=='java.lang.Integer':
            i = struct.unpack('!i', str[np:np+4])[0]
            np+=4;
            cur['pos'] = np
            cur['data'] = i;
            
        #print cur['data']

    @staticmethod
    def _parse_message_next_object(str,cur):
        SessionRead._parse_message_next_token('java.lang.String',str,cur)
        SessionRead._parse_message_next_token(cur['data'],str,cur)

    @staticmethod
    def parse_message(str):
        #print str
        name = None
        msg = {}
        cur = {'pos': 0, 'data': None}
        #skip name class Message
        SessionRead._parse_message_next_token('java.lang.String',str,cur)
        #skip Message name (CUSTOM)
        SessionRead._parse_message_next_object(str,cur)
        '''if not self._session._inizialize:
            if cur['data']!='INITIALIZE':
                return None #CLOSE
        else:
            if cur['data']!='CUSTOM' or cur['data']!='BUFFERSIZE':
                return None #CLOSE'''
        name=cur['data'];
        #legge numero di elementi
        cnt = struct.unpack('!i', str[cur['pos']:cur['pos']+4])[0]
        cur['pos']+=4;
        cur['data']=None
        #legge map
        for i in range(0,cnt):
            SessionRead._parse_message_next_object(str,cur)
            k=cur['data']
            SessionRead._parse_message_next_object(str,cur)
            v=cur['data']
            msg[k]=v
        
        return {'name':name,'data':msg}

    def run(self):
        #print "Thread read started"
        bfireclose=False
        sock = self._session.get_socket()
        try:
            while not self._session.is_shutdown():
                data = self._read_fully(sock, 2)
                if len(data) == 0:
                    bfireclose=not self._session.is_close()
                    break
                else:
                    lendt=0;
                    if ord(data[1]) <= 125:
                        if ord(data[1]) > 0:
                            lendt = ord(data[1]);
                        else:
                            if ord(data[0]) == 136: #CLOSE
                                bfireclose=not self._session.is_close()
                                break
                            elif ord(data[0]) == 138: #PONG
                                #self._session._tdalive.reset();
                                #print "SESSION - PONG RICEVUTO!"
                                continue
                            else:
                                continue    
                    elif ord(data[1]) == 126:
                        data = self._read_fully(sock, 2)
                        if len(data) == 0:
                            bfireclose=not self._session.is_close()
                            break
                        lendt=struct.unpack('!H',data)[0]
                    elif ord(data[1]) == 127:
                        data = self._read_fully(sock, 4)
                        if len(data) == 0:
                            bfireclose=not self._session.is_close()
                            break
                        lendt=lendt=struct.unpack('!I',data)[0]
                    #Legge data
                    data = self._read_fully(sock, lendt)
                    if len(data) == 0:
                        bfireclose=not self._session.is_close()
                        break
                    head = struct.unpack('!qc', data[0:9])
                    if (head[1] == _TYPE_MESSAGE):
                        #self._session._tdalive.reset();
                        idmsg = head[0]
                        msgh = struct.unpack('!hhq', data[9:9+12])
                        msgt=None
                        if not idmsg in self._temp_msg:
                            msgt={'len':msgh[2], 'data':data[9+12:]}
                            self._temp_msg[idmsg] = msgt
                        else:
                            msgt=self._temp_msg[idmsg]
                            msgt['data']+=data[9+12:]
                        if msgt['len']==len(msgt['data']):
                            data = msgt['data'];
                            del self._temp_msg[idmsg]
                            msg = SessionRead.parse_message(zlib.decompress(data))
                            if msg is None:
                                bfireclose=not self._session.is_close()
                                break
                            if not self._session._inizialize:
                                if msg["name"]=='INITIALIZE':
                                    msg=msg["data"]
                                    self._session._idsession = msg["IDSession"]
                                    self._session._localeid = msg["LocaleID"]
                                    self._session._set_band_limiter_write(self._session, msg["BandLimitID"],msg["BandLimitBPS"]);
                                    self._session._inizialize = True
                                else:
                                    bfireclose=not self._session.is_close()
                                    break
                            else:   
                                if msg["name"]=='CUSTOM':
                                    msg=msg["data"]
                                    self._session.fire_message(msg)
                                elif msg["name"]=='WRITEBANDLIMITER':
                                    msg=msg["data"]
                                    if "IDStream" not in msg:
                                        self._session._set_band_limiter_write(self._session,msg["BandLimitID"],msg["BandLimitBPS"]);
                                    else:
                                        strm = self._session.get_stream_by_id(msg["IDStream"])
                                        if strm is not None:
                                            self._session._set_band_limiter_write(strm,msg["BandLimitID"],msg["BandLimitBPS"]);
                                else:
                                    bfireclose=not self._session.is_close()
                                    break
                    elif (head[1] == _TYPE_REQUEST_OK_ALIVE):
                        #print "SESSION - PONG RICEVUTO!"
                        None
                    else:
                        bfireclose=not self._session.is_close()
                        break
        except Exception:
            bfireclose=not self._session.is_close()
            #traceback.print_exc()
        self._session.shutdown()
        if bfireclose is True:
            self._session.fire_close()
        #print "Thread read stopped"

class BandLimiterWrite():
    _BUFFER_SIZE_MAX = 1024 * 32
    _BUFFER_SIZE_MIN = 1024
    _TIMEOUT_PREFERRED = 200
    
    def __init__(self, sid, bl):
        self._semaphore = threading.Condition()
        self._buffer_size = BandLimiterWrite._BUFFER_SIZE_MIN;
        self._channel_buffer_size=BandLimiterWrite._BUFFER_SIZE_MIN;
        self._id=sid
        self._band_limit=bl
        self._byte_transfered = 0
        self._last_time = long(time.time() * 1000)
        self._last_byte = 0
        self._last_timeout = 0
        self._last_time_debug = long(time.time() * 1000)
        self._last_byte_debug = 0        
        self._channels=[]
        self._resize_buffer_size()
    
    def get_id(self):
        return self._id
    
    def _resize_buffer_size(self):
        if len(self._channels)==0 or self._band_limit == 0:
            self._channel_buffer_size = BandLimiterWrite._BUFFER_SIZE_MAX;
            self._buffer_size = BandLimiterWrite._BUFFER_SIZE_MAX;
        else:
            f= float(self._band_limit) / (float(1000) / float(BandLimiterWrite._TIMEOUT_PREFERRED))
            self._channel_buffer_size = int(f);
            self._buffer_size = self._channel_buffer_size
            #self._buffer_size = int(f / float(len(self._channels)))
            if self._buffer_size >= BandLimiterWrite._BUFFER_SIZE_MAX:
                self._buffer_size = BandLimiterWrite._BUFFER_SIZE_MAX;
            elif (self._buffer_size <= BandLimiterWrite._BUFFER_SIZE_MIN):
                self._buffer_size = BandLimiterWrite._BUFFER_SIZE_MIN;
            else:
                self._buffer_size = int((float(self._buffer_size) / float(512)) * float(512))
    
    def add_channel(self, chl):
        self._semaphore.acquire()
        try:
            if chl not in self._channels:
                self._channels.append(chl)
                self._resize_buffer_size()
        finally:
            self._semaphore.release() 
    
    
    def remove_channel(self,chl):
        self._semaphore.acquire()
        try:
            if chl in self._channels:
                self._channels.remove(chl)
                self._resize_buffer_size()
        finally:
            self._semaphore.release()         
    
    
    def get_channel_count(self):
        self._semaphore.acquire()
        try:
            return len(self._channels)
        finally:
            self._semaphore.release()
        
    def get_buffer_size(self):
        self._semaphore.acquire()
        try:
            return self._buffer_size
        finally:
            self._semaphore.release()
    
    def get_channel_buffer_size(self) :
        self._semaphore.acquire()
        try:
            return self._channel_buffer_size
        finally:
            self._semaphore.release()
    
    '''def _print_debug(self):
        cur_time=long(time.time() * 1000)
        elapsed = (cur_time - self._last_time_debug)
        if elapsed >= 1000:
            bps = (int)(float(float(self._byte_transfered-self._last_byte_debug) * (float(1000) / float(elapsed))))
            print("bps:" + str(int(float(bps) / float(1024))) + "  byte:" + str(self._byte_transfered-self._last_byte_debug))
            self._last_time_debug=cur_time;
            self._last_byte_debug=self._byte_transfered;'''
        

    def get_wait_time(self, c):
        self._semaphore.acquire()
        try:
            timeout=0
            if c > 0:
                self._byte_transfered += c
                if self._band_limit > 0 :
                    #INIZIO DEBUG
                    #self._print_debug()
                    #FINE DEBUG
                    cur_time=long(time.time() * 1000)
                    if cur_time >= self._last_time:
                        elapsed = (cur_time - self._last_time)
                        timeout = (int)(float(float(self._byte_transfered-self._last_byte) * float(1000) / float(self._band_limit)) - float(elapsed))
                    else:
                        remaining = self._last_time-cur_time;
                        if remaining<=self._last_timeout:
                            timeout = (int)(float(float(self._byte_transfered-self._last_byte) * float(1000) / float(self._band_limit)) + float(remaining))
                    if timeout > 0:
                        self._last_time=cur_time+timeout
                        self._last_byte=self._byte_transfered
                        self._last_timeout=timeout
                    else:
                        self._last_time = cur_time
                        self._last_byte=self._byte_transfered
                        self._last_timeout=0;
                    
            return timeout
        finally:
            self._semaphore.release()

class SessionAlive (threading.Thread):
    _SESSION_KEEPALIVE_INTERVALL = 30
    _SESSION_KEEPALIVE_THRESHOLD = 5
    
    def __init__(self, session):
        threading.Thread.__init__(self, name="SessionAlive")
        self.daemon=True
        self._session = session
        self._counter=Counter()
        self._session_keepalive_send=False
        self._semaphore = threading.Condition()

    def _send_keep_alive(self):
        try:
            if not self._session.is_close():
                self._session._semaphore_send.acquire()
                try:
                    #self._session._send_ws_ping(self._session._sock)
                    self._session._send_ws_data(self._session, self._session._sock, struct.pack('!qc', 0, _TYPE_REQUEST_KEEP_ALIVE))
                    #print "SESSION - PING INVIATO!"
                finally:
                    self._session._semaphore_send.release()
        except Exception:
            #traceback.print_exc()
            None

    def reset(self):
        self._semaphore.acquire()
        try:
            self._counter.reset()
            self._session_keepalive_send = False
        finally:
            self._semaphore.release()
        
            
    def run(self):
        #print "Thread alive started"
        bfireclose=False
        while not self._session.is_shutdown():
            time.sleep(1)
            self._semaphore.acquire()
            try:
                #Verifica alive
                if not self._session_keepalive_send:
                    if self._counter.is_elapsed((SessionAlive._SESSION_KEEPALIVE_INTERVALL-SessionAlive._SESSION_KEEPALIVE_THRESHOLD)*1000):
                        self._session_keepalive_send=True
                        self._session._task_pool.execute(self._send_keep_alive)                        
                else:
                    if self._counter.is_elapsed(SessionAlive._SESSION_KEEPALIVE_INTERVALL*1000):
                        bfireclose=not self._session.is_close()
                        break                  
            finally:
                self._semaphore.release()
                
            #KEEP ALIVE STREAM
            self._session._semaphore.acquire()
            try:
                stream_keys = self._session._streams.keys()
            finally:
                self._session._semaphore.release()
            for sid in stream_keys:
                try:
                    self._session._streams[sid]._tdalive.on_tick()
                except:
                    None    
            
            
            
        self._session.close();
        if bfireclose is True:
            self._session.fire_close()
        #print "Thread alive stopped"

class Session:
            
    def __init__(self, agent_main, events):
        self._agent_main = agent_main
        self._task_pool = self._agent_main._task_pool
        self._on_message = None
        self._on_close = None
        self._close=True
        self._shutdown=False
        if events is not None:
            if "on_message" in events:
                self._on_message = events["on_message"]
            if "on_close" in events:
                self._on_close = events["on_close"]
        self._semaphore = threading.Condition()
        self._semaphore_send = threading.Condition()
        self._count_send_message=0
        self._sock = None
        self._tdalive = None
        self._tdread = None
        self._streams = {}
        self._idsession = None
        self._inizialize = False
        self._localeid = None
        self._band_limiter_write = None        
        self._band_limiter_write_list = {}
        
            
    def open(self, prop, proxy_info):
        
        if self._sock is not None:
            raise Exception("Already connect!")

        #Apre socket
        self._prop = prop
        self._proxy_info = proxy_info
        self._sock = _connect_socket(self._prop['host'], int(self._prop['port']), proxy_info)
        try:
            '''method_connect_port = self._prop['methodConnectPort']
            if not method_connect_port is None and method_connect_port!="0": 
                req = Request("CONNECT", self._prop['host'] + ":" + method_connect_port ,  {'Host' : self._prop['host'] + ':' + method_connect_port,  'Proxy-Connection' :  'Keep-Alive'})
                self._sock.sendall(req.to_message())
                resp = Response(self._sock)
                if resp.get_code() != '200':
                    raise Exception("Connect method error.")'''
            
            
            init_data = self._send_opensession(self._prop)
            
            '''if "SetIpUrl" in prpresp:
                self._call_setipurl(self._prop['host'],  self._prop['port'],  proxy_info,  prpresp['SetIpUrl'])
                prpresp = self._send_opensession(self._prop)
                except Exception as e:
                self.shutdown()
                raise e'''
            
            self._close=False
            
            self._sock.settimeout(None)
            
            #Avvia thread alive
            self._tdalive = SessionAlive(self)
            self._tdalive.start()
    
            #Avvia thread lettura
            self._tdread = SessionRead(self, init_data, self._tdalive)
            self._tdread.start()
                
            #Attende ID Sessione
            cnt = 0;
            while not self._inizialize:
                time.sleep(0.2)
                cnt+=0.2
                if self._close:
                    raise Exception("Connection closed.");
                if cnt >= 10:
                    raise Exception("Connection timeout.");
                
        except Exception as e:
            self.shutdown()
            raise e

    def get_idsession(self):
        return self._idsession
    
    def get_buffersize_write(self):
        if self._band_limiter_write is None:
            return 32*1024
        else:
            return self._band_limiter_write.get_buffer_size();
    
    def _set_band_limiter_write(self, chl, sid, bl):
        self._semaphore_send.acquire()
        try:
            if chl._band_limiter_write is not None:
                chl._band_limiter_write.remove_channel(chl)
                if chl._band_limiter_write.get_channel_count()==0:
                    del self._band_limiter_write_list[chl._band_limiter_write]
            if sid is not None:
                if sid in self._band_limiter_write_list:
                    chl._band_limiter_write = self._band_limiter_write_list[sid]
                else:
                    chl._band_limiter_write = BandLimiterWrite(sid,bl);
                    self._band_limiter_write_list[sid]=chl._band_limiter_write
                chl._band_limiter_write.add_channel(chl)
                chl._sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, chl._band_limiter_write.get_channel_buffer_size())
        finally:
            self._semaphore_send.release()
    
    
    def new_websocket(self, props=None):
        if props is not None and "simulate" in props and props["simulate"]=="true": 
            return WebSocketSimulate(self,props)
        else:
            return WebSocket(self, props)
        
    def new_filedownload(self, props=None):
        return FileDownload(self, props)
    
    def new_fileupload(self, props=None):
        return FileUpload(self, props)
    
    def get_stream_by_id(self, sid):
        self._semaphore.acquire()
        try:
            if sid in self._streams:
                return self._streams[sid]
        finally:
            self._semaphore.release()
        return None
    
    def new_stream(self, events=None,  props=None):
        strm = None
        if self._sock is not None:
            strm = Stream(self,  events,  props)
            self._semaphore.acquire()
            try:
                self._streams[strm.get_idstream()]=strm
            finally:
                self._semaphore.release()
        return strm
    
    def _remove_stream(self, sid):
        self._semaphore.acquire()
        try:
            if sid in self._streams:
                del self._streams[sid]
        finally:
            self._semaphore.release()
        

    def _send_opensession(self, prop):
        #Invia richiesta
        appprp = {}
        for k in prop:
            if prop[k] is not None:
                appprp["dw_" + k]=prop[k];
        appprp["dw_compressType"]='zlib';
                
        appprp["host"] = prop['host'] + ":" + prop['port']
        appprp["Connection"] = 'keep-alive, Upgrade'
        appprp["Upgrade"] = 'websocket'
        appprp["Sec-WebSocket-Key"] = 'XV3+Fd9KMg54tXP7Tsrl8Q=='
        appprp["Sec-WebSocket-Version"] = '13'
                
        req = Request("GET", "/opensession.dw", appprp)
        self._sock.sendall(req.to_message())

        #Legge risposta
        resp = Response(self._sock);
        if resp.get_code() == '101':
            return resp.get_extra_data()
        else:
            if resp.get_body() is not None:
                raise Exception(resp.get_body())
            else:
                raise Exception("Server error.")
        
    '''def _call_setipurl(self, host,  port,  proxy_info,  url):
        s = _connect_socket(host, int(port),  proxy_info)
        try:
            req = Request("GET", url,  {'Host' : host + ':' + port,  'Connection' : 'close'})
            s.sendall(req.to_message())
            resp = Response(s)
            if resp.get_code() != '200':
                raise Exception("call SetIpUrl error.")
        finally:
            s.shutdown(1)
            s.close()'''
    
    def get_socket(self):
        return self._sock

    def is_close(self):
        bret = True
        self._semaphore.acquire()
        try:
            bret = self._close
        finally:
            self._semaphore.release()
        return bret
    
    def is_shutdown(self):
        bret = True
        self._semaphore.acquire()
        try:
            bret = self._shutdown
        finally:
            self._semaphore.release()
        return bret

    def fire_message(self, msg):
        if self._on_message is not None:
            self._task_pool.execute(self._on_message, msg)
            #self._task_pool.apply_async(self._on_message, [msg])

    def fire_close(self):
        if self._on_close is not None:
            self._on_close()
    
    @staticmethod
    def send_message_append(ardt,s):
        ardt.append(struct.pack('!i',len(s)))
        ardt.append(s)

    def send_message(self,msg):
        if self._sock is None:
            raise Exception('session closed.')
        self._count_send_message+=1
        ardt = []
        Session.send_message_append(ardt,"dataweb.comunication.Message".encode('utf-8'))
        Session.send_message_append(ardt,"java.lang.String".encode('utf-8'))
        Session.send_message_append(ardt,"CUSTOM".encode('utf-8'))
        #Aggiunge numero elementi
        ardt.append(struct.pack('!i',len(msg)))
        #Aggiunge elementi
        for key in msg.iterkeys():
            Session.send_message_append(ardt,"java.lang.String".encode('utf-8'))
            Session.send_message_append(ardt,key.encode('utf-8'))
            Session.send_message_append(ardt,"java.lang.String".encode('utf-8'))
            Session.send_message_append(ardt,msg[key].encode('utf-8'))
        data = zlib.compress(''.join(ardt))
        lendata=len(data)
        pos=0
        lencur=lendata
        while lencur>0:
            lensend=lencur
            if lencur>self.get_buffersize_write():
                lensend=self.get_buffersize_write()
            head = struct.pack('!qchhq',self._count_send_message,_TYPE_MESSAGE,0,0,lendata)
            self._semaphore_send.acquire()
            try:
                self._send_ws_data(self,self._sock,''.join([head,data[pos:pos+lensend]]))
            finally:
                self._semaphore_send.release()
            self._tdalive.reset()
            lencur-=lensend
            pos+=lensend
    
    def _send_ws_data(self,chl,sock,data):
        bf = []
        b0 = 0;
        b0 |= 1 << 7;
        b0 |= 0x2 % 128;
        length = len(data);
        if length <= 125:
            bf.append(chr(b0))
            bf.append(chr(0x80 | length))
        elif length <= 0xFFFF:
            bf.append(chr(b0))
            bf.append(chr(0xFE))
            bf.append(chr(length >> 8 & 0xFF))
            bf.append(chr(length & 0xFF))
        else: 
            bf.append(chr(b0))
            bf.append(chr(0xFF))
            bf.append(struct.pack('!I', length))

        rnd=0;
        mask = struct.pack('!I',rnd)
        bf.append(mask)
        bf.append(data);
        
        ssnd=''.join(bf);
        while len(ssnd)>0:
            sz=chl.get_buffersize_write()
            if sz>=len(ssnd):
                appdt=ssnd
                ssnd="" 
            else:
                appdt=ssnd[:sz]
                ssnd=ssnd[sz:]
            sock.sendall(appdt)
            tm=0
            if chl._band_limiter_write is not None:
                tm = chl._band_limiter_write.get_wait_time(len(appdt))
            if tm>0:
                time.sleep(float(tm)/float(1000))
        
            
    def _send_ws_close(self,sock):
        bf = []
        b0 = 0;
        b0 |= 1 << 7;
        b0 |= 0x8 % 128;
        bf.append(chr(b0))
        bf.append(chr(0x80 | 0))
        rnd=0 #random.randint(0,2147483647)
        mask = struct.pack('!I',rnd)
        bf.append(mask)
        sock.sendall(''.join(bf))
    
    def _send_ws_ping(self,sock):
        bf = []
        b0 = 0
        b0 |= 1 << 7;
        b0 |= 0x9 % 128;
        bf.append(chr(b0))
        bf.append(chr(0x80 | 0))
        rnd=0 #random.randint(0,2147483647)
        mask = struct.pack('!I',rnd)
        bf.append(mask)
        sock.sendall(''.join(bf))
    
    def _close_all_stream(self):
        #Chiude tutti gli stream
        self._semaphore.acquire()
        try:
            keys = self._streams.keys()
        finally:
            self._semaphore.release()
        for sid in keys:
            try:
                self._streams[sid].close()
            except:
                if sid in self._streams:
                    del self._streams[sid]
    
    def close(self):
        if not self.is_close():
            self._close_all_stream()
            try:
                self._semaphore_send.acquire()
                try:
                    self._close=True
                    self._send_ws_close(self._sock);
                    #print "session send stream close."
                finally:
                    self._semaphore_send.release()
                #Attende lo shutdown
                while not self._shutdown:
                    time.sleep(0.2)
            except:
                None
    
    def shutdown(self):
        
        self._semaphore.acquire()
        try:
            self._close=True
        finally:
            self._semaphore.release()
        
        self._close_all_stream()
        if self._sock is not None:
            #Chiude thread alive
            #if (self._tdalive is not None) and (not self._tdalive.is_close()):
            #    self._tdalive.join(5000)
            self._tdalive = None

            #Chiude thread read
            #if (self._tdread is not None) and (not self._tdread.is_close()):
            #   self._tdread.join(5000)
            self._tdread = None
            try:
                self._sock.shutdown(1)
            except:
                None
            try:
                self._sock.close()
            except:
                None
            self._sock = None
            self._prop = None
            self._proxy_info = None
            self._idsession = None
        
        self._semaphore.acquire()
        try:
            self._shutdown=True
        finally:
            self._semaphore.release()
        
            #print "close session"


class StreamAlive ():
    _STREAM_KEEPALIVE_INTERVALL = 60
    _STREAM_KEEPALIVE_THRESHOLD = 5
    
    def __init__(self, stream):
        self._stream = stream
        self._counter=Counter()
        self._stream_keepalive_send=False
        self._semaphore = threading.Condition()

    def _send_keep_alive(self):
        try:
            if not self._stream.is_close():
                self._stream._semaphore_send.acquire()
                try:
                    #self._stream._session._send_ws_ping(self._stream._sock)
                    ardt = []
                    ardt.append(_TYPE_REQUEST_KEEP_ALIVE)
                    self._stream._session._send_ws_data(self._stream, self._stream._sock,''.join(ardt))
                    #print "STREAM - PING INVIATO!"
                finally:
                    self._stream._semaphore_send.release()
        except Exception:
            #traceback.print_exc()
            None

    def reset(self):
        self._semaphore.acquire()
        try:
            self._counter.reset()
            self._stream_keepalive_send = False
        finally:
            self._semaphore.release()
        
            
    def on_tick(self):
        bfireclose=False
        if not self._stream.is_shutdown():
            self._semaphore.acquire()
            try:
                #Verifica alive
                if not self._stream_keepalive_send:
                    if self._counter.is_elapsed((StreamAlive._STREAM_KEEPALIVE_INTERVALL-StreamAlive._STREAM_KEEPALIVE_THRESHOLD)*1000):
                        self._stream_keepalive_send=True
                        self._stream._session._task_pool.execute(self._send_keep_alive)                        
                else:
                    if self._counter.is_elapsed(StreamAlive._STREAM_KEEPALIVE_INTERVALL*1000):
                        bfireclose=not self._stream.is_close()
            finally:
                self._semaphore.release()
        if bfireclose is True:
            try:
                self._stream.close();
            except:
                None                        
            self._stream.fire_close()

class StreamRead (threading.Thread):
    
    def __init__(self, stream, init_data):
        threading.Thread.__init__(self, name="StreamRead")
        self.daemon=True
        self._stream = stream
        self._init_data=init_data
    
    
    def _read_fully(self, sock, ln):
        data = []
        cnt=0
        while ln > cnt:
            if self._init_data is not None:
                appln=ln
                if ln>len(self._init_data):
                    appln=len(self._init_data)                
                s=self._init_data[0:appln]
                self._init_data=self._init_data[appln:]
                if len(self._init_data)==0:
                    self._init_data=None
            else:    
                s = sock.recv(ln-cnt)
            if s is None or len(s) == 0:
                return ''
            self._stream._tdalive.reset();
            data.append(s)
            cnt+=len(s)
        return ''.join(data)
    
    def run(self):
        #print "Thread read started"
        bfireclose=False
        sock = self._stream.get_socket()
        try:
            data = None
            while not self._stream.is_shutdown():
                data = self._read_fully(sock, 2)
                if len(data) == 0:
                    bfireclose=not self._stream.is_close()
                    break
                else:
                    lendt=0;
                    if ord(data[1]) <= 125:
                        if ord(data[1]) > 0:
                            lendt = ord(data[1]);
                        else:
                            if ord(data[0]) == 136: #CLOSE
                                bfireclose=not self._stream.is_close()
                                break
                            elif ord(data[0]) == 138: #PONG
                                #self._stream._tdalive.reset()
                                #print "STREAM - PONG RICEVUTO!"
                                continue
                            else:
                                continue
                    elif ord(data[1]) == 126:
                        data = self._read_fully(sock, 2)
                        if len(data) == 0:
                            bfireclose=not self._stream.is_close()
                            break
                        lendt=struct.unpack('!H',data)[0]
                    elif ord(data[1]) == 127:
                        data = self._read_fully(sock, 4)
                        if len(data) == 0:
                            bfireclose=not self._stream.is_close()
                            break
                        lendt=struct.unpack('!I',data)[0]
                    #Legge data
                    data = self._read_fully(sock, lendt)
                    if len(data) == 0:
                        bfireclose=not self._stream.is_close()
                        break
                    else:
                        if data[0] == _TYPE_STREAM_DATA:
                            #self._stream._tdalive.reset()
                            if not self._stream._inizialize:
                                ipos=1
                                #Legge IDStream
                                l = struct.unpack('!i', data[ipos:ipos+4])[0]
                                ipos+=4
                                self._stream._idstream = data[ipos:ipos+l]
                                ipos+=l
                                #Legge bandLimit
                                l = struct.unpack('!i', data[ipos:ipos+4])[0]
                                ipos+=4
                                blid = data[ipos:ipos+l]
                                ipos+=l
                                blbps = struct.unpack('!i', data[ipos:ipos+4])[0]
                                ipos+=4
                                self._stream._session._set_band_limiter_write(self._stream, blid, blbps)
                                self._stream._inizialize=True
                                extradata=data[ipos+l:]
                                if len(extradata)>0:
                                    self._stream.fire_data(extradata)
                            else:
                                self._stream.fire_data(data[1:])
                        elif (data[0] == _TYPE_REQUEST_OK_ALIVE):
                            #print "STREAM - PONG RICEVUTO!"
                            None
                        else:
                            bfireclose=not self._stream.is_close()
                            break
        except Exception:
            bfireclose=not self._stream.is_close()
            #traceback.print_exc()
        self._stream.shutdown()
        if bfireclose is True:
            self._stream.fire_close()
        #print "Thread StreamRead read stopped"


class Stream:
    def __init__(self, session, events,  props):
        self._semaphore = threading.Condition()
        self._semaphore_send = threading.Condition()
        self._session = session
        self._close=True
        self._inizialize=False
        self._shutdown=False
        self._idstream=None
        self._band_limiter_write = None
        if props is not None:
            self._properties=props
        else:
            self._properties = {}
        self._tdread = None
        self._on_close=None
        self._on_data=None
        self._tdalive = StreamAlive(self)
        if events is not None:
            if "on_close" in events:
                self._on_close = events["on_close"]
            if "on_data" in events:
                self._on_data = events["on_data"]
        
        #Apre socket
        self._sock = _connect_socket(self._session._prop['host'], int(self._session._prop['port']), self._session._proxy_info)
        try:
            '''method_connect_port = self._session._prop['methodConnectPort']
            if not method_connect_port is None and method_connect_port!="0": 
                req = Request("CONNECT", self._session._prop['host'] + ":" + method_connect_port ,  {'Host' : self._session._prop['host'] + ':' + method_connect_port,  'Proxy-Connection' :  'Keep-Alive'})
                self._sock.sendall(req.to_message())
                resp = Response(self._sock)
                if resp.get_code() != '200':
                    raise Exception("Connect method error.")    
        
            prpresp = self._send_openstream()'''
            
            init_data=self._send_openstream()
            
            self._close=False
            
            self._sock.settimeout(None)
            
            #Avvia thread lettura
            self._tdread = StreamRead(self,init_data)
            self._tdread.start()
        
            #Attende ID Sessione
            cnt = 0;
            while not self._inizialize:
                time.sleep(0.2)
                cnt+=0.2
                if self._close:
                    raise Exception("Connection closed.");
                if cnt >= 15:
                    raise Exception("Connection timeout.");
        except Exception as e:
            self.shutdown()
            raise e
    
    
    def get_properties(self):
        return self._properties
    
    def _send_openstream(self):
        #Invia richiesta
        appprp = {}
        for k in self._session._prop:
            if self._session._prop[k] is not None:
                appprp["dw_" + k]=self._session._prop[k]
        appprp["dw_compressType"]='zlib';
        appprp["dw_idSession"]=self._session._idsession
        
        appprp["host"] = self._session._prop['host'] + ":" + self._session._prop['port']
        appprp["Connection"] = 'keep-alive, Upgrade'
        appprp["Upgrade"] = 'websocket'
        appprp["Sec-WebSocket-Key"] = 'XV3+Fd9KMg54tXP7Tsrl8Q=='
        appprp["Sec-WebSocket-Version"] = '13'
                
        req = Request("GET", "/openstream.dw", appprp)
        self._sock.sendall(req.to_message())

        #Legge risposta
        resp = Response(self._sock);
        if resp.get_code() == '101':
            return resp.get_extra_data()
        else:
            if resp.get_body() is not None:
                raise Exception(resp.get_body())
            else:
                raise Exception("Server error.")
        
    
    def get_socket(self):
        return self._sock
    
    def get_idstream(self):
        return self._idstream
    
    def fire_data(self, data):
        if self._on_data is not None:
            self._on_data(self,  data)
    

    def get_buffersize_write(self):
        if self._band_limiter_write is None:
            return 32*1024
        else:
            return self._band_limiter_write.get_buffer_size();
    
    def send_data(self, data):
        if not self.is_close():
            self._semaphore_send.acquire()
            try:
                ardt = []
                ardt.append(_TYPE_STREAM_DATA)
                ardt.append(data)     
                self._session._send_ws_data(self, self._sock,''.join(ardt))
            finally:
                self._semaphore_send.release()
            self._tdalive.reset();
            
   
    
    def is_close(self):
        bret = True
        self._semaphore.acquire()
        try:
            bret = self._close
        finally:
            self._semaphore.release()
        return bret
        
    def is_shutdown(self):
        bret = True
        self._semaphore.acquire()
        try:
            bret = self._shutdown
        finally:
            self._semaphore.release()
        return bret
    
    def fire_close(self):
        if self._on_close is not None:
            self._on_close()
    
    def close(self):
        try:
            self._semaphore_send.acquire()
            try:
                if not self._close:
                    self._close=True
                    self._session._remove_stream(self._idstream)
                    self._session._send_ws_close(self._sock)
                #print "stream send stream close."
            finally:
                self._semaphore_send.release()
        except:
            None
    
    def shutdown(self):
        self._semaphore.acquire()
        try:
            self._close=True
        finally:
            self._semaphore.release()
        if self._idstream is not None:
            self._session._remove_stream(self._idstream)
        if self._sock is not None: 
            #Chiude thread read
            #if (self._tdread is not None) and (not self._tdread.is_close()):
            #    self._tdread.join(5000)
            self._tdread = None
            try:
                self._close.shutdown(1)
            except:
                None
            try:
                self._close.close()
            except:
                None
            self._sock=None
        
        self._semaphore.acquire()
        try:
            self._shutdown=True
        finally:
            self._semaphore.release()
        
        #print "close stream"

class WebSocketSimulate:
    DATA_RESP_SIZE = 32*1024
    
    def __init__(self, session, props):
        self._session=session
        self._props=props
        self._baccept=False
        self._bclose=False
    
    def accept(self, events):
        self._semaphore = threading.Condition()
        self._stream = self._session.new_stream({"on_close": self._on_close_stream,"on_data":self._on_data_stream})
        self._idstream = self._stream.get_idstream()
        self._on_close=None
        self._on_data=None
        if events is not None:
            if "on_close" in events:
                self._on_close = events["on_close"]
            if "on_data" in events:
                self._on_data = events["on_data"]
        self._qry_len=-1
        self._qry_data=""
        self._pst_len=-1
        self._pst_data=""
        self._qry_or_pst="qry"
        self._send_list=[]
        self._baccept=True
    
    def is_accept(self):
        return self._baccept
    
    def get_idstream(self):
        return self._idstream
    
    def get_properties(self):
        return self._props
    
    def _on_data_stream(self,stream,data):
        if self._idstream is not None:
            try:
                if self._qry_or_pst=="qry":
                    self._qry_data = "".join([self._qry_data,data])
                else:
                    self._pst_data = "".join([self._pst_data,data])
                if self._qry_or_pst=="qry":
                    if self._qry_len==-1:
                        if len(self._qry_data)>=4:
                            self._qry_len = struct.unpack('!i', self._qry_data[0:4])[0]
                            self._qry_data = self._qry_data[4:]
                    if self._qry_len!=-1 and len(self._qry_data)>=self._qry_len:
                        self._pst_data=self._qry_data[self._qry_len:]
                        self._qry_data=self._qry_data[0:self._qry_len]
                        self._qry_or_pst="pst"
                if self._qry_or_pst=="pst":
                    if self._pst_len==-1:
                        if len(self._pst_data)>=4:
                            self._pst_len = struct.unpack('!i', self._pst_data[0:4])[0]
                            self._pst_data = self._pst_data[4:]      
                    if self._pst_len!=-1 and len(self._pst_data)>=self._pst_len:
                        prpqry=None
                        if self._qry_len>0:
                            prpqry=xml_to_prop(self._qry_data)
                        self._qry_data=self._pst_data[self._pst_len:]
                        self._pst_data=self._pst_data[0:self._pst_len]
                        prppst=None
                        if self._pst_len>0:
                            prppst=xml_to_prop(self._pst_data)
                        self._qry_or_pst="qry"
                        self._qry_len=-1
                        self._pst_len=-1
                        self._pst_data=""
                        
                        if self._on_data is not None:
                            cnt = int(prppst["count"])
                            for i in range(cnt):
                                tpdata = prppst["type_" + str(i)]
                                prprequest = prppst["data_" + str(i)]
                                if tpdata==WEBSOCKET_DATA_BYTEARRAY:
                                    prprequest = base64.b64decode(prprequest)
                                self._on_data(self, tpdata, prprequest);
                        #Invia risposte
                        self._semaphore.acquire()
                        try:
                            if len(self._send_list)==0 and "destroy" not in prppst:
                                appwt=250
                                if "wait" in prppst:
                                    appwt=int(prppst["wait"])
                                if appwt==0:
                                    self._semaphore.wait()
                                else:
                                    appwt=appwt/1000.0
                                    self._semaphore.wait(appwt)
                            if self._idstream is not None: # non chiuso
                                if len(self._send_list)>0:
                                    arsend = {}
                                    arcnt = 0
                                    lensend = 0
                                    app_send_list=[]
                                    for i in range(len(self._send_list)):
                                        if (len(app_send_list)>0) or (i>0 and (lensend + len(self._send_list[i]["data"])) > WebSocketSimulate.DATA_RESP_SIZE):
                                            app_send_list.append(self._send_list[i])
                                        else:
                                            arsend["type_" + str(i)]=self._send_list[i]["type"]
                                            arsend["data_" + str(i)]=self._send_list[i]["data"]
                                            lensend += len(self._send_list[i])
                                            arcnt+=1
                                    arsend["count"]=arcnt
                                    arsend["otherdata"]=len(app_send_list)>0
                                    self._send_response(json.dumps(arsend))
                                    self._send_list=app_send_list
                                else:
                                    self._send_response("")
                        finally:
                            self._semaphore.release()
                        if "destroy" in prppst:
                            self.close();
                            if self._on_close is not None:
                                self._on_close()
            except:
                self._bclose=True
                self.close();
                if self._on_close is not None:
                    self._on_close()
                    
    
    def _send_response(self,sdata):
        prop = {}
        prop["Cache-Control"] = "no-cache, must-revalidate"
        prop["Pragma"] = "no-cache"
        prop["Expires"] = "Sat, 26 Jul 1997 05:00:00 GMT"
        prop["Content-Encoding"] = "gzip"
        prop["Content-Type"] = "application/json; charset=utf-8"
        
        
        ardt = []
        #AGGIUNGE HEADER
        shead = prop_to_xml(prop)
        ardt.append(struct.pack('!i', len(shead)))
        ardt.append(shead)
        
        appout = StringIO.StringIO()
        f = gzip.GzipFile(fileobj=appout, mode='w', compresslevel=5)
        f.write(sdata)
        f.close()
        dt = appout.getvalue()
        
        #BODY LEN
        ln=len(dt)
        ardt.append(struct.pack('!i', ln))
        if ln>0:
            ardt.append(dt)
        sresp="".join(ardt)        
        while len(sresp)>0:
            appdata=None
            bf=self._stream.get_buffersize_write() 
            if len(sresp)>bf:
                appdata=sresp[0:bf]
                sresp=sresp[bf:]
            else:
                appdata=sresp
                sresp=""
            self._stream.send_data(appdata)
    
    def send(self,tpdata,data): 
        if self._idstream is not None:
            self._semaphore.acquire()
            try:
                if type(data).__name__ == 'list':
                    for i in range(len(data)):
                        dt=data[i];
                        if tpdata==WEBSOCKET_DATA_BYTEARRAY:
                            dt=base64.b64encode(dt);
                        #print("LEN: " + str(len(data[i])) + " LEN B64: " + str(len(dt)))
                        self._send_list.append({"type": tpdata, "data": dt})
                else:
                    dt=data;
                    if tpdata==WEBSOCKET_DATA_BYTEARRAY:
                        dt=base64.b64encode(dt)
                    #print("LEN: " + str(len(data)) + " LEN B64: " + str(len(dt)))
                    self._send_list.append({"type": tpdata, "data": dt})
                self._semaphore.notifyAll()
            finally:
                self._semaphore.release()
    
    def _on_close_stream(self):
        self._bclose=True
        self.close();
        if self._on_close is not None:
            self._on_close()
    
    def is_close(self):
        return self._bclose
    
    def close(self):
        self._bclose=True
        if self._idstream is not None:
            self._semaphore.acquire()
            try:
                self._stream.close()
                self._idstream = None
                self._send_list=[]
                self._semaphore.notifyAll()
            finally:
                self._semaphore.release()
            
class WebSocket:
    
    def __init__(self, session, props):
        self._session=session
        self._props=props
        self._baccept=False
        self._bclose=False
        self._stream = None
        self._idstream = None
            
    def accept(self, events):
        self._stream = self._session.new_stream({"on_close": self._on_close_stream,"on_data":self._on_data_stream})
        self._idstream = self._stream.get_idstream()
        self._on_close=None
        self._on_data=None
        if events is not None:
            if "on_close" in events:
                self._on_close = events["on_close"]
            if "on_data" in events:
                self._on_data = events["on_data"]
        self._len=-1
        self._data=""
        #Avvia thread scrittura
        self._baccept=True
                
    
    def is_accept(self):
        return self._baccept
    
    def get_idstream(self):
        return self._idstream
    
    def get_properties(self):
        return self._props
    
    def _on_data_stream(self,stream,data):
        if self._idstream is not None:
            if self._data == "":
                self._data=data
            else:
                self._data="".join([self._data,data])
            try:
                while True:
                    if self._len==-1:
                        if len(self._data)>=4:
                            self._len = struct.unpack('!i', self._data[0:4])[0]
                        else:
                            break
                    if self._len>=0 and len(self._data)-4>=self._len:
                        apps = self._data[4:4+self._len]
                        self._data=self._data[4+self._len:]
                        self._len=-1;
                        if self._on_data is not None:
                            self._on_data(self,apps[0],apps[1:]);
                    else:
                        break
            except:
                self._bclose=True
                self.close();
                if self._on_close is not None:
                    self._on_close()
    
    def send(self,tpdata,data):
        if self._idstream is not None:
            dtsend=[]
            lnsend=0
            if type(data).__name__ == 'list':
                for i in range(len(data)):
                    dt = zlib.compress(data[i])
                    dt = "".join([struct.pack('!i', len(dt)+1),tpdata,dt])
                    if lnsend+len(dt)>self._stream.get_buffersize_write():
                        dtsend.insert(0,struct.pack('!i', lnsend))
                        self._stream.send_data("".join(dtsend))
                        dtsend=[]
                        lnsend=0
                    dtsend.append(dt)
                    lnsend+=len(dt)
            else:
                dt = zlib.compress(data)
                dt = "".join([struct.pack('!i', len(dt)+1),tpdata,dt])
                dtsend.append(dt)
                lnsend+=len(dt)            
            dtsend.insert(0,struct.pack('!i', lnsend))
            self._stream.send_data("".join(dtsend))
       
    def _on_close_stream(self):
        self._destroy(True)
        if self._on_close is not None:
            self._on_close()
            
    def is_close(self):
        return self._bclose
    
    def close(self):
        self._destroy(False)
    
    def _destroy(self,bnow):
        if not self._bclose:
            self._bclose=True
            if self._idstream is not None:
                self._stream.close()
                self._idstream = None
    

class Calcbps():
    
    def __init__(self):
        self._semaphore = threading.Condition()
        self._bps=float(0)
        self._curbyte=-1
        self._curtime=-1
        self._transfered=0l
        self._blength=0l
        self._arbps=[]
        
    def calc_bps(self):
        ret = float(0)
        for v in self._arbps:
            ret += v
        return ret / float(len(self._arbps))
    
    def data_transfered(self, cnt): 
        self._semaphore.acquire()
        try:
            self._transfered+=cnt
            if self._curbyte==-1:
                self._curbyte = 0
                self._curtime = time.time()
            else:
                self._curbyte+= cnt
                apptime = time.time()
                if apptime-self._curtime<0: #Potrebbe essere cambiato l'orario del pc
                    self._curbyte = 0
                    self._curtime = time.time()
                elif apptime-self._curtime>=0.5:
                    appbps=float(self._curbyte)/float(apptime-self._curtime)
                    self._curbyte = 0
                    self._curtime = apptime
                    self._arbps.append(appbps)
                    if len(self._arbps)>5:
                        self._arbps.remove(self._arbps[0])
                    self._bps = self.calc_bps()
        finally:
                self._semaphore.release()
                
    def get_transfered(self):
        ret = 0l
        self._semaphore.acquire()
        try:
            ret=self._transfered
        finally:
            self._semaphore.release()
        return ret
    
    def get_bps(self):
        ret = float(0)
        self._semaphore.acquire()
        try:
            ret=self._bps
        finally:
            self._semaphore.release()
        return ret
    

class FileDownload(threading.Thread):

    def __init__(self, session, props):
        threading.Thread.__init__(self)
        self._session=session
        self._props=props
        self._baccept=False

    def accept(self, path):
        self._path=path
        self._name=os.path.basename(self._path)
        self._length=os.path.getsize(self._path)
        self._calcbps=Calcbps()
        self._stream = self._session.new_stream({"on_data": self._on_data, "on_close": self._on_close})
        self._idstream = self._stream.get_idstream()
        self._bclose = False
        self._status="T"
        self._semaphore = threading.Condition()
        self._baccept=True
        #self._bytes_send=0
        #self._remote_bytes_received=0
    
    def is_accept(self):
        return self._baccept
    
    def get_idstream(self):
        return self._idstream
    
    def get_properties(self):
        return self._props
    
    def get_name(self):
        return self._name
        
    def get_path(self):
        return self._path
    
    def get_transfered(self):
        return self._calcbps.get_transfered()
    
    def get_length(self):
        return self._length
    
    def get_bps(self):
        return self._calcbps.get_bps()
    
    def get_status(self):
        return self._status   
    
    def run(self):
        fl = open(self._path, 'rb')
        try:
            while not self.is_close():
                bsz=self._stream.get_buffersize_write()
                s = fl.read(bsz)
                ln = len(s)
                if ln==0:
                    self._status="C"
                    break
                self._stream.send_data(s)
                self._calcbps.data_transfered(ln)
                '''
                self._semaphore.acquire()
                try:
                    self._bytes_send+=ln
                    while (self._bytes_send-self._remote_bytes_received>=bsz*3):
                        self._semaphore.wait(1)
                        if self._bclose:
                            break                    
                finally:
                    self._semaphore.release()
                '''
                #print "DOWNLOAD - NAME:" + self._name + " LEN: " + str(self._calcbps.get_transfered()) +  "  BPS: " + str(self._calcbps.get_bps())
                
        except Exception:
            self._status="E"
        finally:
            self.close()
            fl.close()
        self._stream.close()
    
    def _on_data(self, stream, data):
        '''
        dtrim=None
        newrc=-1
        p=0
        while (p<len(data)):
            if dtrim is not None:
                cneeds = 8-len(dtrim)
                if cneeds>len(data):
                    dtrim=dtrim+data
                    break
                else:
                    dtrim=dtrim+data[p:cneeds]
                    newrc=struct.unpack('!q',dtrim)[0]
                    dtrim=None;
                    p+=cneeds
            else:
                if len(data)-p<8:
                    break
                newrc=struct.unpack('!q',data[p:p+8])[0]
                p=p+8
            
        df = len(data)-p
        if df>0:
            dtrim=data[p:]
        
        if newrc>0:
            self._semaphore.acquire()
            try:
                if not self._bclose:
                    self._remote_bytes_received=newrc
                    bsz=self._stream.get_buffersize_write()
                    if self._bytes_send-self._remote_bytes_received<=bsz*1.5:
                        self._semaphore.notify_all()
                    #print "DWN RCV: " + str(self._remote_bytes_received)
            finally:
                self._semaphore.release()
            '''
        None
    
    def is_close(self):
        ret = True
        self._semaphore.acquire()
        try:
            ret=self._bclose
        finally:
            self._semaphore.release()
        return ret
        
    def _on_close(self):
        if not self._bclose:
            self._semaphore.acquire()
            try:
                if self._status=="T":
                    self._status="E"
                self._bclose=True
            finally:
                self._semaphore.release()
    
    def close(self):
        if not self._bclose:
            self._semaphore.acquire()
            try:
                if self._status=="T":
                    self._status="C"
                self._bclose=True
            finally:
                self._semaphore.release()


class FileUpload():

    def __init__(self, session, props):
        self._session=session
        self._props=props
        self._baccept=False

    def accept(self, path):
        self._path=path
        self._name=os.path.basename(self._path)
        if 'length' not in self._props:
            raise Exception("upload file length in none.")
        self._length=long(self._props['length'])
        self._calcbps=Calcbps()
            
        sprnpath=os.path.dirname(path);    
        while True:
            r="".join([random.choice("0123456789") for x in xrange(6)])            
            self._tmpname=sprnpath + os.sep + "temporary" + r + ".dwsupload";
            if not os.path.exists(self._tmpname):
                open(self._tmpname, 'wb').close() #Crea il file per imposta i permessi
                self._session._agent_main.get_osmodule().fix_file_permissions("CREATE_FILE",self._tmpname)
                self._fltmp = open(self._tmpname, 'wb')
                break
        try:
            self._stream = self._session.new_stream({"on_data": self._on_data, "on_close": self._on_close})
            self._idstream = self._stream.get_idstream()
            self._bclose = False
            self._status="T"
            self._semaphore = threading.Condition()
            self._enddatafile=False
            self._baccept=True
            self._last_time_transfered = 0
        except Exception as e:
            self._remove_temp_file()
            raise e
        
    def _remove_temp_file(self):
        try:
            self._fltmp.close()
        except:
            None
        try:
            if os.path.exists(self._tmpname):
                os.remove(self._tmpname)
        except:
            None
        
    
    def is_accept(self):
        return self._baccept
    
    def get_idstream(self):
        return self._idstream
    
    def get_properties(self):
        return self._props
    
    def get_name(self):
        return self._name
        
    def get_path(self):
        return self._path
    
    def get_transfered(self):
        return self._calcbps.get_transfered()
    
    def get_length(self):
        return self._length
    
    def get_bps(self):
        return self._calcbps.get_bps()
    
    def get_status(self):
        return self._status  
    
    #def _send_transfered(self):
    #    self._stream.send_data(struct.pack('!q', self._calcbps.get_transfered()));
    
    def _on_data(self, stream, data):
        self._semaphore.acquire()
        try:
            if not self._bclose:
                if self._status == "T":
                    if len(data)==0: #Considerato come fine data
                        self._enddatafile=True;
                        #SCRIVE FILE
                        try:
                            self._fltmp.close()
                            if os.path.exists(self._path):
                                if os.path.isdir(self._path):
                                    raise Exception("")
                                else:
                                    os.remove(self._path)
                            shutil.move(self._tmpname, self._path)
                            self._status = "C"
                            self._stream.send_data(struct.pack('!b', 1));
                        except Exception:
                            self._status = "E"
                            self._stream.send_data(struct.pack('!b', 0));
                    else:
                        self._fltmp.write(data)
                        self._calcbps.data_transfered(len(data))
                        #self._send_transfered()
                        #print "UPLOAD - NAME:" + self._name + " LEN: " + str(self._calcbps.get_transfered()) +  "  BPS: " + str(self._calcbps.get_bps())
                        
        except:
            self._status  = "E"
        finally:
            self._semaphore.release()
        
    def is_close(self):
        ret = True
        self._semaphore.acquire()
        try:
            ret=self._bclose
        finally:
            self._semaphore.release()
        return ret
        
    def _on_close(self):
        if not self._bclose:
            self._semaphore.acquire()
            try:
                #print "UPLOAD - ONCLOSE"
                self._bclose=True
                self._remove_temp_file()
                if not self._enddatafile:
                    self._status = "E"
            finally:
                self._semaphore.release()
            self._stream.close()
    
    def close(self):
        if not self._bclose:
            #print "UPLOAD - CLOSE"
            self._semaphore.acquire()
            try:
                self._bclose=True
                self._remove_temp_file()
                self._status  = "C"
            finally:
                self._semaphore.release()
            self._stream.close()
            