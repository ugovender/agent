# -*- coding: utf-8 -*-

'''
This Source Code Form is subject to the terms of the Mozilla
Public License, v. 2.0. If a copy of the MPL was not distributed
with this file, You can obtain one at http://mozilla.org/MPL/2.0/.
'''

import os
import mmap
import struct
import time
import string
import random
import threading
import json

#Il file di n KB e diviso in 2 parti
# SIDE 1 scrive sulla parte 1 e legge sulla parte 2
# SIDE 2 scrive sulla parte 2 e legge sulla parte 1
#
#
#
# SIDE 1 parte da 0
# 1 byte stato= C:Connesso X:Chiuso T:Terminato
# 1 byte keepalive= A:Is Alive K:Ok Aliva
# 4 byte identificano posizione write side 1    
# 4 byte identificano posizione read side 2
# SIDE 2 parte da pos n/2
# 1 byte stato= C:Connesso W:Attesa connessione X:Chiuso T:Terminato
# 1 byte keepalive= A:Is Alive K:Ok Aliva
# 4 byte pid
# 4 byte identificano posizione write side 2    
# 4 byte identificano posizione read side 1
#
# SIDE 1 CREA IL FILE


SHAREDMEM_PATH="sharedmem"
STREAM_WAIT=0.005

def init_path():
    if not os.path.exists(SHAREDMEM_PATH):
        os.mkdir(SHAREDMEM_PATH)
    else:
        #Elimina tutti i file
        lst=os.listdir(SHAREDMEM_PATH);
        for fname in lst:
            try:
                if fname[0:7]=="stream_":
                    if os.path.exists(SHAREDMEM_PATH + os.sep + fname):
                        os.remove(SHAREDMEM_PATH + os.sep + fname)
            except:
                None

class Stream():
    
    def __init__(self):
        self._semaphore = threading.Condition()
        self._binit=False
    
    def _is_init(self):
        self._semaphore.acquire()
        try:
            return self._binit
        finally:
            self._semaphore.release()
    
    def create(self,size=512*1024):
        self._semaphore.acquire()
        try:
            if self._binit==True:
                raise Exception("Shared file already initialized.")
            self._side=1
            self._size=size
            fname = sharedmem_manager.getStreamFile(self._size)
            self._path=sharedmem_manager.getPath(fname)
            self._initialize()
            return fname
        finally:
            self._semaphore.release() 
        
    def connect(self,fname):
        self._semaphore.acquire()
        try:
            if self._binit==True:
                raise Exception("Shared file already initialized.")
            self._side=2
            self._path=sharedmem_manager.getPath(fname)
            if not os.path.exists(self._path):
                raise Exception("Shared file not found.")
            self._size=os.path.getsize(self._path)
            self._initialize()
        finally:
            self._semaphore.release() 
    
    def _get_local_state(self):
        self._semaphore.acquire()
        try:
            self._mmap.seek(self._state_pos)
            return self._mmap.read(1)
        finally:
            self._semaphore.release()

    def _get_other_state(self):
        self._semaphore.acquire()
        try:
            self._mmap.seek(self._state_other_pos)
            return self._mmap.read(1)
        finally:
            self._semaphore.release()
    
    def _set_other_state(self,v):
        self._semaphore.acquire()
        try:
            self._mmap.seek(self._state_other_pos)
            self._mmap.write(v)
        finally:
            self._semaphore.release()

    def _get_local_alive(self):
        self._semaphore.acquire()
        try:
            self._mmap.seek(self._alive_pos)
            return self._mmap.read(1)
        finally:
            self._semaphore.release()
    
    def _set_local_alive(self,v):
        self._semaphore.acquire()
        try:
            self._mmap.seek(self._alive_pos)
            self._mmap.write(v)
        finally:
            self._semaphore.release()

    def _get_other_alive(self):
        self._semaphore.acquire()
        try:
            self._mmap.seek(self._alive_other_pos)
            return self._mmap.read(1)
        finally:
            self._semaphore.release()
            
    def _set_other_alive(self,v):
        self._semaphore.acquire()
        try:
            self._mmap.seek(self._alive_other_pos)
            self._mmap.write(v)
        finally:
            self._semaphore.release()
            
    
    def _get_pointer(self,pos):
        self._semaphore.acquire()
        try:
            self._mmap.seek(pos)
            return struct.unpack('!i', self._mmap.read(4))[0]
        finally:
            self._semaphore.release()
    
    def _initialize(self):
        self._binit=True
        self._side_size=self._size/2;
        if self._side==1:
            self._state_pos=0
            self._alive_pos=1
            self._write_pnt_pos=2;
            self._write_data_pos=10;
            self._state_other_pos=self._side_size
            self._alive_other_pos=self._side_size+1
            self._read_pnt_pos=self._side_size+6;
            self._read_data_pos=self._side_size+10
            self._write_limit=self._side_size
            self._read_limit=self._size
        elif self._side==2:
            self._state_pos=self._side_size
            self._alive_pos=self._side_size+1
            self._write_pnt_pos=self._side_size+2
            self._write_data_pos=self._side_size+10
            self._state_other_pos=0
            self._alive_other_pos=1
            self._read_pnt_pos=6
            self._read_data_pos=10
            self._write_limit=self._size
            self._read_limit=self._side_size
        self._last_read_time=long(time.time() * 1000)
        self._last_write_time=long(time.time() * 1000)
        self._file=open(self._path, "r+b")
        self._mmap = mmap.mmap(self._file.fileno(), 0)
        if self._side==1:
            #Inserisce le posizioni
            self._mmap.seek(0)
            self._mmap.write(struct.pack('!ccii','C','K',0,0))
            self._mmap.seek(self._side_size)
            self._mmap.write(struct.pack('!ccii','W','K',0,0))
            self._waitconn_tm=long(time.time() * 1000)
        elif self._side==2:
            self._mmap.seek(self._side_size)
            self._mmap.write(struct.pack('!ccii','C','K',0,0))
        sharedmem_manager.add(self);
    
    def _terminate(self):
        if self._binit==True:
            self._binit=False
            err=""
            try:
                self._mmap.seek(self._state_pos)
                self._mmap.write('T')
                self._mmap.close()
            except Exception as e:
                err+="Error map close:" + str(e) + "; ";
            try:
                self._file.close()
            except Exception as e:
                err+="Error shared file close:" + str(e) + ";"
            if self._side==1:
                if os.path.exists(self._path):
                    try:
                        os.remove(self._path)
                    except Exception as e:
                        err+="Error shared file close:" + str(e) + ";"
            if (err!=""):
                raise Exception(err)
            
    def _close(self):
        if self._binit==True:
            self._mmap.seek(self._state_pos)
            self._mmap.write('X')
    
    def close(self):
        self._semaphore.acquire()
        try:
            self._close()
        finally:
            self._semaphore.release()
    
    def is_closed(self):
        self._semaphore.acquire()
        try:
            if self._binit:
                locstate=self._get_local_state()
                return locstate=="X" or locstate=="T"
            return True
        finally:
            self._semaphore.release()
    
    def _check_close(self):
        if self._is_init():
            locstate=self._get_local_state()
            othstate=self._get_other_state()
            if self._side==1:
                if (locstate=="X" or locstate=="T") \
                       and othstate=="T":
                    self._terminate()
                else:
                    return False
            else:
                if (locstate=="X" or locstate=="T") \
                       and (othstate=="X" or othstate=="T"):
                    self._terminate()
                else:
                    return False
        return True
    
    
    def _check_alive(self):
        if self._is_init():
            #Verifica se l'altro lato mi ha chiesto un keep alive
            appalive=self._get_local_alive()
            if appalive=="A":
                self._set_local_alive("K")
            #Verifica se devo richiedere il keep alive all'altro lato
            othstate=self._get_other_state()
            if othstate=="W":
                elapsed=long(time.time() * 1000)-self._waitconn_tm
                if elapsed<0: #Cambiato orario pc
                    self._waitconn_tm=long(time.time() * 1000)
                elif elapsed>=2000:
                    self._terminate()
            elif othstate!="T":
                appalive=self._get_other_alive()
                if appalive=="K":
                    self._alive_tm=long(time.time() * 1000)
                    self._set_other_alive("A")
                elif appalive=="A":
                    #Verifica se timeout
                    elapsed=long(time.time() * 1000)-self._alive_tm
                    if elapsed<0: #Cambiato orario pc
                        self._alive_tm=long(time.time() * 1000)
                    elif elapsed>=1000:
                        self._set_other_state("T")
                else:
                    self._set_other_state("T")
                    raise Exception("Invalid other alive (" + str(self._side) + ").")  
                    
    
    def write(self,s):
        if not self._is_init():
            raise Exception("Shared file closed. (1)");
        locstate=self._get_local_state()
        othstate=self._get_other_state()
        if locstate=="X" or othstate=="X" or othstate=="T":
            self._close()
            raise Exception("Shared file closed. (2)")
        while othstate=="W":
            time.sleep(STREAM_WAIT)
            if not self._is_init():
                raise Exception("Shared file closed. (3)");
            locstate=self._get_local_state()
            othstate=self._get_other_state()
            if locstate=="X" or othstate=="X" or othstate=="T":
                self._close()
                raise Exception("Shared file closed. (4)")             
        pw=self._get_pointer(self._write_pnt_pos)
        apps=s
        while len(apps)>0:
            #Attende lettura da parte dell'altro side
            while True:
                pr=self._get_pointer(self._write_pnt_pos+4)
                if pr==pw:
                    break  
                elif pr>pw:
                    if pr-pw>1:
                        break
                elif pr<pw:
                    if self._write_limit-self._write_data_pos-pw+pr>1:
                        break
                time.sleep(STREAM_WAIT)
                #VERIFICA CHIUSURA
                if not self._is_init():
                    raise Exception("Shared file closed. (5)");
                locstate=self._get_local_state()
                othstate=self._get_other_state()
                if locstate=="X" or othstate=="X" or othstate=="T":
                    self._close()
                    raise Exception("Shared file closed. (6)")       
            
            self._semaphore.acquire()
            try:
                #Cursore write si trova dopo Cursore read
                rpw=self._write_data_pos+pw
                self._mmap.seek(rpw)
                if pw>=pr: 
                    ln = len(apps)
                    if ln<self._write_limit-rpw:
                        self._mmap.write(apps)
                        pw+=len(apps)
                        apps=""
                    else:
                        if pr>0:
                            appsz=self._write_limit-rpw
                            self._mmap.write(apps[0:appsz])
                            pw=0
                        else:
                            appsz=self._write_limit-rpw-1
                            self._mmap.write(apps[0:appsz])
                            pw+=appsz
                        apps=apps[appsz:]
                #Cursore write si trova prima Cursore read
                rpw=self._write_data_pos+pw
                self._mmap.seek(rpw)
                if pw<pr: 
                    ln = len(apps)
                    if ln<=pr-pw-1:
                        self._mmap.write(apps)
                        pw+=len(apps)
                        apps=""
                    else:
                        appsz=pr-pw-1
                        self._mmap.write(apps[0:appsz])
                        pw=pr-1
                        apps=apps[appsz:]
                
                self._mmap.seek(self._write_pnt_pos)
                self._mmap.write(struct.pack('!i', pw))
            finally:
                self._semaphore.release()
                
    def read(self,timeout=0,maxbyte=0): #0 infinite
        if not self._is_init():
            return None
        pr=self._get_pointer(self._read_pnt_pos)
        tm=long(time.time() * 1000)
        while True:
            appstate=self._get_other_state()
            pw=self._get_pointer(self._read_pnt_pos-4)
            if pr!=pw:
                break
            #VERIFICA CHIUSURA
            if not self._is_init() or appstate=="X" or appstate=="T":
                self._close();
                return None
            time.sleep(STREAM_WAIT)
            
            #VERIFICA TIMEOUT
            elapsed=long(time.time() * 1000)-tm
            if timeout>0:
                if elapsed<0: #Cambiato orario pc
                    tm=long(time.time() * 1000)
                elif elapsed>=timeout:
                    return ""
        
        self._semaphore.acquire()
        try:
            arret=[]
            bread=0
            if pw<pr:
                bfullread=True
                appsz=self._read_limit-self._read_data_pos-pr;
                if maxbyte>0 and appsz>maxbyte:
                    appsz=maxbyte
                    bfullread=False
                rpr=self._read_data_pos+pr
                self._mmap.seek(rpr)
                arret.append(self._mmap.read(appsz))
                if bfullread:
                    pr=0
                else:
                    pr+=appsz
                bread+=appsz
            if pw>pr:
                if maxbyte==0 or bread<maxbyte:
                    bfullread=True
                    appsz=pw-pr
                    if maxbyte>0 and appsz>maxbyte-bread:
                        appsz=maxbyte-bread
                        bfullread=False
                    rpr=self._read_data_pos+pr
                    self._mmap.seek(rpr)
                    arret.append(self._mmap.read(appsz))
                    if bfullread:
                        pr=pw
                    else:
                        pr+=appsz
            self._mmap.seek(self._read_pnt_pos)
            self._mmap.write(struct.pack('!i', pr))
            self._last_read_time=long(time.time() * 1000) 
            return "".join(arret);
        finally:
            self._semaphore.release()
    
    def write_token(self,s):
        ar=[]
        ar.append(struct.pack('!i', len(s)))
        ar.append(s)
        self.write("".join(ar))
    
    def read_token(self):
        sln=""
        while len(sln)<4:
            s=self.read(maxbyte=4-len(sln))
            if s==None:
                return None
            sln+=s
        ln=struct.unpack('!i', sln)[0]
        ar=[]
        cnt=0
        while cnt<ln:
            s=self.read(maxbyte=ln-cnt)
            if s==None:
                return None
            ar.append(s)
            cnt+=len(s)
        return "".join(ar)

class Property():
    
    def __init__(self):
        self._semaphore = threading.Condition()
        self._binit=False
    
    def create(self, fname, fieldsdef, fixperm=None):
        self._semaphore.acquire()
        try:
            if self._binit:
                raise Exception("Already initialized.")
            self._path = sharedmem_manager.getPath(fname)
            if os.path.exists(self._path):
                if fixperm is not None:
                    fixperm.get_osmodule().set_file_permission_everyone(self._path)
                self.open(fname)
                #Verifica se la struttura è identica
                bok=True
                for f in fieldsdef:
                    if f["name"] in self._fields:
                        if f["size"]!=self._fields[f["name"]]["size"]:
                            bok=False
                            break
                    else:
                        bok=False
                        break
                if not bok:
                    self.close()
                    #Prova a rimuovere il file
                    try:
                        os.remove(self._path)
                    except:
                        raise Exception("Shared file is locked.")
                else:
                    self._binit=True
                    return
            #CREAZIONE DEL FILE
            self._fields={}
            szdata=0
            for f in fieldsdef:
                self._fields[f["name"]]={"pos":szdata,"size":f["size"]}
                szdata+=f["size"]
            shead=json.dumps(self._fields)
            self._len_def=len(shead)
            self._size=4+self._len_def+szdata
            with open(self._path, "wb") as f:
                f.write(" "*self._size)
            if fixperm is not None:
                fixperm.get_osmodule().set_file_permission_everyone(self._path)
            self._file=open(self._path, "r+b")
            self._mmap = mmap.mmap(self._file.fileno(), 0)
            self._mmap.seek(0)
            self._mmap.write(struct.pack('!i', self._len_def))
            self._mmap.write(shead)
            self._binit=True
        finally:
            self._semaphore.release()
                        
    def open(self, fname, bpath=None):
        self._semaphore.acquire()
        try:
            if self._binit:
                raise Exception("Already initialized.")
            self._path = sharedmem_manager.getPath(fname, path=bpath)
            if not os.path.exists(self._path):
                raise Exception("Shared file not found")
            self._file=open(self._path, "r+b")
            self._mmap = mmap.mmap(self._file.fileno(), 0)
            self._mmap.seek(0)
            #Legge struttura
            self._len_def=struct.unpack('!i',self._mmap.read(4))[0]
            shead=self._mmap.read(self._len_def)
            self._fields = json.loads(shead)
            self._binit=True
        finally:
            self._semaphore.release()
    
    def close(self):
        self._semaphore.acquire()
        try:
            if self._binit:
                self._binit=False
                self._fields=None
                err=""
                try:
                    self._mmap.close()
                except Exception as e:
                    err+="Error map close:" + str(e) + "; "
                try:
                    self._file.close()
                except Exception as e:
                    err+="Error shared file close:" + str(e) + ";"
                if (err!=""):
                    raise Exception(err)
        finally:
            self._semaphore.release()
    
    def is_close(self):
        self._semaphore.acquire()
        try:
            return not self._binit;
        finally:
            self._semaphore.release()
    
    def set_property(self, name, val):
        self._semaphore.acquire()
        try:
            if self._binit:
                if name in self._fields:
                    f=self._fields[name];
                    if len(val)<=f["size"]:
                        self._mmap.seek(4+self._len_def+f["pos"])
                        appv=val + " "*(f["size"]-len(val))
                        self._mmap.write(appv)
                    else:
                        raise Exception("Invalid size for property " + name + ".")
                else:
                    raise Exception("Property " + name + " not found.")
            else:
                raise Exception("Not initialized.")
        finally:
            self._semaphore.release()
    
    def get_property(self, name):
        self._semaphore.acquire()
        try:
            if self._binit:
                if name in self._fields:
                    f=self._fields[name];
                    self._mmap.seek(4+self._len_def+f["pos"])
                    sret = self._mmap.read(f["size"])
                    return sret.strip() 
                else:
                    raise Exception("Property " + name + " not found.")
            else:
                raise Exception("Not initialized.")
        finally:
            self._semaphore.release()
        


class Manager(threading.Thread):
    def __init__(self,fname=None):
        threading.Thread.__init__(self,name="SharedMemManager")
        self.daemon=True
        
        
        self._semaphore = threading.Condition()
        self._list=[]
    
    def add(self,sm):
        self._semaphore.acquire()
        try:
            self._list.append(sm)
        finally:
            self._semaphore.release()
    
    def getStreamFile(self,size):
        fname=None
        self._semaphore.acquire()
        try:
            while True:
                ar=[]
                for x in range(8):
                    if x==0:
                        ar.append(random.choice(string.ascii_lowercase))
                    else:
                        ar.append(random.choice(string.ascii_lowercase + string.digits))
                fname = "stream_" + ''.join(ar)
                fpath=SHAREDMEM_PATH + os.sep + fname + ".shm"
                if not os.path.exists(fpath):
                    with open(fpath, "wb") as f:
                        f.write(" "*size)
                    break
            
        finally:
            self._semaphore.release()    
        return fname
    
    def getPath(self,name,path=None):
        if path is None:
            return SHAREDMEM_PATH + os.sep + name + ".shm"
        else:
            return path + os.sep + SHAREDMEM_PATH + os.sep + name + ".shm"
    
    
    def run(self):
        while True:
            time.sleep(0.5)
            self._semaphore.acquire()
            try:
                remlist=[]
                for sm in self._list:
                    try:
                        sm._check_alive()
                    except Exception as e:
                        print("SharedMem manager check alive error: " + str(e))
                    try:
                        #Verifica se e chiuso
                        if sm._check_close():
                            remlist.append(sm)
                    except Exception as e:
                        print("SharedMem manager check close error: " + str(e))
                #RIMUOVE
                for sm in remlist:
                    self._list.remove(sm)
            finally:
                self._semaphore.release()
               
        
sharedmem_manager=Manager()
sharedmem_manager.start()


######################
######## TEST ########
######################
class TestThread(threading.Thread):
    
    def __init__(self,fname=None):
        threading.Thread.__init__(self)
        self._fname=fname
          
    def run(self):
        num=10000
        m1 = Stream()
        fname=None
        if self._fname==None:
            fname=m1.create()
        else:
            m1.connect(self._fname)
        if self._fname==None:
            t2 = TestThread(fname)
            t2.start()
            try:
                for i in range(num):
                    m1.write("PROVA" + str(i+1) + " ")
                    #m1.write_token("PROVA" + str(i+1) + " ")
                    #time.sleep(STREAM_WAIT)
                m1.write("END")
                #m1.write_token("END")
            except:
                print("Errore write remote closed")
            m1.close()
        else:
            print "INIZIO..."
            ar=[]
            while True:
                s=m1.read()
                #s=m1.read_token()
                if s is None:
                    #time.sleep(8);
                    raise Exception("Errore read remote closed") 
                ar.append(s)
                #print(s)
                if s[len(s)-3:]=="END":
                    break
            #print("***************")
            print("VERIFICA...")
            apps = "".join(ar);
            ar=apps.split(" ");
            bok=True
            for i in range(num):
                if ar[i]!="PROVA" + str(i+1):
                    bok=False
                    print ("ERRORE: " + ar[i] + "  (PROVA" + str(i+1) + ")")
            if bok:
                print "TUTTO OK"
            print "FINE"
            m1.close()
            print "ATTESA RIMOZIONE FILE..."
            time.sleep(8);
            print "VERIFICARE!"
            

if __name__ == "__main__":
    init_path()
    
    '''t1 = Property()
    fieldsdef=[]
    fieldsdef.append({"name":"status","size":1})
    fieldsdef.append({"name":"counter","size":10})
    fieldsdef.append({"name":"prova","size":5})
    t1.create("prova", fieldsdef)
    t1.set_property("status", "2")
    t1.set_property("counter", "0123456789")
    t1.set_property("counter", "012345")
    t1.close()
    
    t2 = Property()
    t2.open("prova")
    print t2.get_property("status")
    print t2.get_property("counter")
    t2.close()'''
    
    t1 = TestThread()
    t1.start()
    
    
    '''m1 = Stream()
    m2 = Stream()
    
    fname=m1.create()
    m2.connect(fname)
    
    
    m2.write_token("TOKEN123")
    m2.write_token("TOKEN999")
    m2.write_token("CIAO")
    m2.write_token("PIPPO")
    
    print(m1.read_token())
    print(m1.read_token())
    print(m1.read_token())
    print(m1.read_token())
    
    m1.close()
    m2.close()
    time.sleep(6)'''
    
        
   

    
    
        
        
        
            
            