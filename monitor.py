# -*- coding: utf-8 -*-

'''
This Source Code Form is subject to the terms of the Mozilla
Public License, v. 2.0. If a copy of the MPL was not distributed
with this file, You can obtain one at http://mozilla.org/MPL/2.0/.
'''

import os
import resources
import platform
import json
import sys
import subprocess
import agent
import threading
import agent_status_config
import gdi
import time

_WIDTH=360
_HEIGHT=140
#_HEIGHT_BOTTOM=45
#_CONTENT_HEIGHT=_HEIGHT-_HEIGHT_BOTTOM
_WIDTH_RIGHT=140
_CONTENT_WIDTH=_WIDTH-_WIDTH_RIGHT
_HEIGHT_STATUS=30

MENU_SHOW = 1
MENU_HIDE = 2
MENU_ENABLE = 11
MENU_DISABLE = 12
MENU_CONFIGURE = 21

COLOR_NOSERVICE="949494"
COLOR_ONLINE="259126"
COLOR_OFFLINE="949494"
COLOR_UPDATING="bfba34"
COLOR_DISABLE="c21b1a"

TIMEOUT_REQ=5

def is_windows():
    return (platform.system().lower().find("window") > -1)

def is_linux():
    return (platform.system().lower().find("linux") > -1)

def is_mac():
    return (platform.system().lower().find("darwin") > -1)

def get_user_dir():
    try:
        from win32com.shell import shellcon, shell
        return shell.SHGetFolderPath(0, shellcon.CSIDL_APPDATA, 0, 0)
    except:
        return os.path.expanduser("~")

       
class Main():
    
    
    @staticmethod
    def get_instance():
        return Main._instance_monitor
    
    @staticmethod
    def set_instance(i):
        Main._instance_monitor=i
    
    def lock(self):
        self._homedir = get_user_dir() + os.sep + ".dwagent"
        if not os.path.exists(self._homedir):
            os.makedirs(self._homedir)
        self._lockfilename = self._homedir + os.sep + "monitor.lock"
        try:
            if is_linux():
                import fcntl
                self._lockfile = open(self._lockfilename , "w")
                fcntl.lockf(self._lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
            else:
                if os.path.exists(self._lockfilename ):
                    os.remove(self._lockfilename ) 
                self._lockfile = open(self._lockfilename , "w")
                self._lockfile.write("\x00")
        except:
            try:
                self._lockfile.close()
            except:
                None
            if self._mode=="systray":
                print ("An Instance is already running.")
            else:
                self.add_show_file()
            return False
        
        #self.remove_show_file()
        return True

    def unlock(self):
        self._lockfile.close()  
        try:
            os.remove(self._lockfilename ) 
        except:
            None
        #self.remove_show_file()
        
    def check_stop(self):
        stopfilename = "monitor.stop"
        return os.path.exists(stopfilename)
    
    def check_update(self):
        stopfilename = "monitor.update"
        return os.path.exists(stopfilename)
    
    def add_show_file(self):
        showfilename  = self._homedir + os.sep + "monitor.show"
        if not os.path.exists(showfilename):
            f = open(showfilename, "w")
            f.write("\x00")
            f.close()
        
    def remove_show_file(self):
        showfilename  = self._homedir + os.sep + "monitor.show"        
        try:
            os.remove(showfilename  )
        except:
            None
    
    def check_show(self):
        showfilename = self._homedir + os.sep + "monitor.show"
        return os.path.exists(showfilename)
    
    def get_ico_file(self, name):
        return unicode("images" + os.sep + name + ".ico")
       
    def get_info(self):
        ret={"state": "-1","connections":"0"}
        self._semaphore.acquire()
        try:
            if self._prop==None or self._prop.is_close():
                self._prop=agent_status_config.open_property()
                self._status_cnt=-1

            cnt=long(self._prop.get_property("counter"))
            if self._status_cnt!=cnt:
                self._status_cnt=cnt
                ret["state"] = self._prop.get_property("state")
                try:
                    ret["connections"] = self._prop.get_property("connections")
                except:
                    None
                return ret;
            else:
                return ret
        except Exception as e:
            print str(e)
            return ret
        finally:
            self._semaphore.release()
            
    def check_events(self):
        if self.check_stop():
            self._app.destroy()
            return
        if self.check_update():
            self._update=True
            self._app.destroy()
            return
        if self.check_show():
            self._app.show()
            self.remove_show_file()
        gdi.add_scheduler(0.5, self.check_events)
    
    def update_status(self):
        bground=""
        self.msgst=""
        self.icofile=""
        stateBtnEnDis=True
        msgBtnEnDis="monitorDisable"
        appar = self.get_info()
        s=appar["state"]
        newst=""
        if s=='0': #STATUS_OFFLINE 
            newst="OFFLINE"
            self.msgst=resources.get_message('monitorStatusOffline')
            bground=COLOR_OFFLINE
            self.icofile="monitor_grey"
        elif s=='1': #STATUS_ONLINE 
            newst="ONLINE"
            self.msgst=resources.get_message('monitorStatusOnline')
            bground=COLOR_ONLINE
            self.icofile="monitor_green"
        elif s=='3': #STATUS_DISABLE 
            newst="DISABLE"
            self.msgst=resources.get_message('monitorStatusDisabled')
            bground=COLOR_DISABLE
            msgBtnEnDis="monitorEnable"
            self.icofile="monitor_red"
        elif s=='10': #STATUS_UPDATING 
            newst="UPDATING"
            self.msgst=resources.get_message('monitorStatusUpdating')
            bground=COLOR_UPDATING
            self.icofile="monitor_yellow"
        else:
            newst="NOSERVICE"
            stateBtnEnDis=False
            self.msgst=resources.get_message('monitorStatusNoService')
            bground=COLOR_NOSERVICE
            self.icofile="monitor_warning"
        
        if newst != self._cur_status or appar["connections"] != self._cur_connections:
            self._cur_status=newst 
            self._cur_connections=appar["connections"]
            self.update_systray(self.icofile, self.msgst)
            self._img_status_top.set_background_gradient(bground,"ffffff",gdi.GRADIENT_DIRECTION_TOPBOTTON)
            self._img_status_bottom.set_background_gradient(bground,"ffffff",gdi.GRADIENT_DIRECTION_BOTTONTOP)
            apptx=[]
            apptx.append(resources.get_message("monitorStatus"))
            apptx.append(u": ")
            apptx.append(self.msgst)
            apptx.append(u"\n")
            apptx.append(resources.get_message("monitorConnections"))
            apptx.append(u": ")
            apptx.append(self._cur_connections)
            self._lbl_status.set_text(u"".join(apptx))
            self._btconfig.set_enable(stateBtnEnDis)
            self._btends.set_text(resources.get_message(msgBtnEnDis))
            self._btends.set_enable(stateBtnEnDis)
        
        gdi.add_scheduler(2, self.update_status)
    
    def invoke_req(self, usr, pwd, req, prms=None):
        self._semaphore.acquire()
        try:
            if self._prop==None or self._prop.is_close():
                self._prop=agent_status_config.open_property()
            return agent_status_config.invoke_request(self._prop, usr, pwd, req, prms);
        except: 
            return 'ERROR:REQUEST_TIMEOUT'
        finally:
            self._semaphore.release()
            
    def set_config(self, pwd,  key, val):
        sret=self.invoke_req("admin", pwd, 'set_config',  {'key':key, 'value':val})
        if sret!="OK":
            raise Exception(sret[6:])

    
    def check_auth(self, pwd):
        sret=self.invoke_req("admin", pwd, "check_auth", None)
        if sret=="OK":
            return True
        elif sret=="ERROR:FORBIDDEN":
            return False
        else:
            raise Exception(sret[6:])
    
    def _enable_disable_action_pwd(self,e):
        pwd = ""
        for c in e["window"].get_components():
            if c.get_name()=="txtPassword":
                pwd=c.get_text()
        
        e["window"].destroy()        
        val = "false"
        mess_ok='monitorAgentDisabled'
        if self._cur_status=="DISABLE":
            val="true"
            mess_ok='monitorAgentEnabled'
        if not self.check_auth(pwd):
            self.set_config(pwd, "enabled", val)
            dlg = gdi.DialogMessage(gdi.DIALOGMESSAGE_ACTIONS_OK,gdi.DIALOGMESSAGE_LEVEL_INFO,self._app)
            dlg.set_title(resources.get_message('monitorTitle'))
            dlg.set_message(resources.get_message(mess_ok))
            dlg.show();
        else:
            dlg = gdi.DialogMessage(gdi.DIALOGMESSAGE_ACTIONS_OK,gdi.DIALOGMESSAGE_LEVEL_ERROR,self._app)
            dlg.set_title(resources.get_message('monitorTitle'))
            dlg.set_message(resources.get_message('monitorInvalidPassword'))
            dlg.show();            
    
    def _enable_disable_action(self,e):
        if e["action"]=="DIALOG_YES":
            try:
                val = "false"
                mess_ok='monitorAgentDisabled'
                if self._cur_status=="DISABLE":
                    val="true"
                    mess_ok='monitorAgentEnabled'
                pwd = ""
                if self.check_auth(pwd):
                    self.set_config(pwd, "enabled", val)
                    dlg = gdi.DialogMessage(gdi.DIALOGMESSAGE_ACTIONS_OK,gdi.DIALOGMESSAGE_LEVEL_INFO,self._app)
                    dlg.set_title(resources.get_message('monitorTitle'))
                    dlg.set_message(resources.get_message(mess_ok))
                    dlg.show();
                else:
                    #RICHIEDE PASSWORD
                    dlg = gdi.Window(gdi.WINDOW_TYPE_DIALOG, self._app)
                    dlg.set_title(resources.get_message('monitorTitle'))
                    dlg.set_size(220, 140)
                    dlg.set_show_position(gdi.WINDOW_POSITION_CENTER_SCREEN)
                    lbl = gdi.Label()
                    lbl.set_text(resources.get_message('monitorEnterPassword'))
                    lbl.set_position(10, 10)
                    lbl.set_width(200)
                    dlg.add_component(lbl)
                    txt = gdi.TextBox()
                    txt.set_name("txtPassword");
                    txt.set_password_mask(True)
                    txt.set_position(10, 10+lbl.get_height())
                    txt.set_width(200)
                    dlg.add_component(txt)
                    pnlBottomH=55
                    pnl = gdi.Panel();
                    pnl.set_position(0, dlg.get_height()-pnlBottomH)
                    pnl.set_size(dlg.get_width(),pnlBottomH)
                    dlg.add_component(pnl)
                    bt = gdi.Button();
                    bt.set_position(int((dlg.get_width()/2)-(bt.get_width()/2)), 10)
                    bt.set_text(resources.get_message('ok'))
                    bt.set_action(self._enable_disable_action_pwd)
                    pnl.add_component(bt)
                    dlg.show()
            except Exception as e:
                dlg = gdi.DialogMessage(gdi.DIALOGMESSAGE_ACTIONS_OK,gdi.DIALOGMESSAGE_LEVEL_ERROR,self._app)
                dlg.set_title(resources.get_message('monitorTitle'))
                dlg.set_message(str(e))
                dlg.show();
    
    def enable_disable(self, e):
        msg=resources.get_message('monitorDisableAgentQuestion')
        if self._cur_status=="DISABLE":
            msg=resources.get_message('monitorEnableAgentQuestion')
        
        dlg = gdi.DialogMessage(gdi.DIALOGMESSAGE_ACTIONS_YESNO,gdi.DIALOGMESSAGE_LEVEL_INFO,self._app)
        dlg.set_title(resources.get_message('monitorTitle'))
        dlg.set_message(msg)
        dlg.set_action(self._enable_disable_action)
        dlg.show();
    
    def configure(self, e):
        if is_windows():
            subprocess.call(["native" + os.sep + "dwaglnc.exe" , "configure"]) 
        elif is_linux():
            subprocess.Popen(["native" + os.sep + "configure"])
        elif is_mac():
            subprocess.Popen(["native/Configure.app/Contents/MacOS/Configure"])
    
    def run_update(self):
        #Lancia se stesso perche con il file monitor.update attende che le librerie si aggiornano
        if is_windows():
            subprocess.call(["native" + os.sep + "dwaglnc.exe" , "systray"]) 
        elif is_linux():
            None
            #subprocess.Popen(["native" + os.sep + "configure"])
        elif is_mac():
            None
            #subprocess.Popen(["native/Configure.app/Contents/MacOS/Configure"])
    
    def unistall(self, e):
        if is_windows():
            subprocess.call(["native" + os.sep + "dwaglnc.exe" , "uninstall"]) 
        elif is_linux():
            sucmd=None
            if self._which("gksu"):
                sucmd="gksu"
            elif self._which("kdesu"):
                sucmd="kdesu"
            if sucmd is not None:
                subprocess.Popen([sucmd , os.path.abspath("native" + os.sep + "uninstall")])
            else:
                dlg = gdi.DialogMessage(gdi.DIALOGMESSAGE_ACTIONS_OK,gdi.DIALOGMESSAGE_LEVEL_ERROR,self._app)
                dlg.set_title(resources.get_message('monitorTitle'))
                dlg.set_message(resources.get_message('monitorUninstallNotRun'))
                dlg.show();
        elif is_mac():
            subprocess.Popen(["native/Uninstall.app/Contents/MacOS/Uninstall"])      
    
    def _which(self, name):
        p = subprocess.Popen("which " + name, stdout=subprocess.PIPE, shell=True)
        (po, pe) = p.communicate()
        p.wait()
        return len(po) > 0     
    
    def printInfo(self):
        msgst=""
        appar = self.get_info()
        s=appar["state"]
        if s=='0': #STATUS_OFFLINE 
            msgst=resources.get_message('monitorStatusOffline')
        elif s=='1': #STATUS_ONLINE 
            msgst=resources.get_message('monitorStatusOnline')
        elif s=='3': #STATUS_DISABLE 
            msgst=resources.get_message('monitorStatusDisabled')
        elif s=='10': #STATUS_UPDATING 
            msgst=resources.get_message('monitorStatusUpdating')
        else:
            msgst=resources.get_message('monitorStatusNoService')
        print("Status: " + msgst)
        print("Connections: " + appar["connections"])
    
    
    def _actions_systray(self,e):
        if e["action"]=="show":
            self._app.show()
            self._app.to_front()
        elif e["action"]=="hide":
            self._app.hide()
        elif e["action"]=="enable":
            self.enable_disable(e)
        elif e["action"]=="disable":
            self.enable_disable(e)
        elif e["action"]=="configure":
            self.configure(e)
    
    def _window_action(self,e):
        if e["action"]==u"ONCLOSE":
            if self._monitor_tray_icon:
                e["source"].hide()
                e["cancel"]=True
        if e["action"]==u"NOTIFYICON_ACTIVATE":
            e["source"].show()
            e["source"].to_front()
        elif e["action"]==u"NOTIFYICON_CONTEXTMENU":
            pp=gdi.PopupMenu()
            pp.set_show_position(gdi.POPUP_POSITION_TOPLEFT)
            if not self._app.is_show():
                pp.add_item("show",resources.get_message('monitorShow'))
            else:
                pp.add_item("hide",resources.get_message('monitorHide'))
            
            if self._cur_status!="NOSERVICE":
                if self._cur_status=="DISABLE":
                    pp.add_item("enable",resources.get_message('monitorEnable'))
                else:
                    pp.add_item("disable",resources.get_message('monitorDisable'))
                pp.add_item("configure",resources.get_message('monitorConfigure'))
            pp.set_action(self._actions_systray);
            pp.show()
    
    def update_systray(self,icon,msg):
        if self._monitor_tray_icon:
            self._app.update_notifyicon(self.get_ico_file(icon), "DWAgent - " + msg)
        
    def prepare_systray(self):
        ti=True
        try:
            f = open('config.json')
            prop= json.loads(f.read())
            f.close()
            if 'monitor_tray_icon' in prop:
                ti=prop['monitor_tray_icon']
        except Exception:
            None
        if self._monitor_tray_icon!=ti:
            msgst=resources.get_message('monitorStatusNoService')
            self._app.show_notifyicon(self.get_ico_file(u"monitor_warning"), "DWAgent - " + msgst)
            self._monitor_tray_icon=ti
    
    def prepare_window(self):
        self._cur_status="NOSERVICE"
        self._cur_connections=0
        #msgst=resources.get_message('monitorStatusNoService')
        
        
        self._app = gdi.Window(gdi.WINDOW_TYPE_NORMAL_NOT_RESIZABLE);
        self._app.set_title(resources.get_message('monitorTitle'))
        self._app.set_size(_WIDTH, _HEIGHT)
        self._app.set_show_position(gdi.WINDOW_POSITION_CENTER_SCREEN)
        self._app.set_action(self._window_action)
        
        self._img_status_top = gdi.Panel()
        self._img_status_top.set_position(0, 0)
        self._img_status_top.set_size(_CONTENT_WIDTH, _HEIGHT_STATUS)
        self._img_status_top.set_background_gradient("ffffff", "ffffff", gdi.GRADIENT_DIRECTION_TOPBOTTON)
        self._app.add_component(self._img_status_top)
        
        self._img_status_bottom = gdi.Panel()
        self._img_status_bottom.set_position(0, _HEIGHT-_HEIGHT_STATUS)
        self._img_status_bottom.set_size(_CONTENT_WIDTH,_HEIGHT_STATUS)
        self._img_status_bottom.set_background_gradient("ffffff", "ffffff", gdi.GRADIENT_DIRECTION_BOTTONTOP)
        self._app.add_component(self._img_status_bottom)
        
        
        self._lbl_status = gdi.Label()
        self._lbl_status.set_text_align(gdi.TEXT_ALIGN_CENTERMIDDLE)
        self._lbl_status.set_text(resources.get_message('waiting'))
        self._lbl_status.set_position(0, _HEIGHT_STATUS)
        self._lbl_status.set_size(_CONTENT_WIDTH,_HEIGHT-(2*_HEIGHT_STATUS))
        self._app.add_component(self._lbl_status)
        
        
        self._pnl_bottom = gdi.Panel()
        self._pnl_bottom.set_position(_CONTENT_WIDTH, 0)
        self._pnl_bottom.set_size(_WIDTH_RIGHT, _HEIGHT)
        self._app.add_component(self._pnl_bottom)
        
        wbtn=_WIDTH_RIGHT-20
        hbtn=36
        appy=10
        
        self._btends = gdi.Button()
        self._btends.set_position(10, appy)
        self._btends.set_size(wbtn, hbtn)
        self._btends.set_text(resources.get_message('monitorDisable'))
        self._btends.set_action(self.enable_disable)
        self._btends.set_enable(False)
        self._pnl_bottom.add_component(self._btends)
        appy+=hbtn+6        
        
        self._btconfig = gdi.Button()
        self._btconfig.set_position(10, appy)
        self._btconfig.set_size(wbtn, hbtn)
        self._btconfig.set_text(resources.get_message('monitorConfigure'))
        self._btconfig.set_action(self.configure)
        self._btconfig.set_enable(False)
        self._pnl_bottom.add_component(self._btconfig)
        appy+=hbtn+6
        
        self._btunistall = gdi.Button()
        self._btunistall.set_position(10, appy)
        self._btunistall.set_size(wbtn, hbtn)
        self._btunistall.set_text(resources.get_message('monitorUninstall'))
        self._btunistall.set_action(self.unistall)
        self._pnl_bottom.add_component(self._btunistall)
        appy+=hbtn+6
        
    def start(self, mode):
        self._semaphore = threading.Condition()
        self._prop = None
        self._mode=mode
        self._monitor_tray_icon=False
        self._update=False
        if mode=="info":
            self.printInfo()
        else:
            if not self.lock():
                if mode=="window":
                    self._add_show_file()
                return            
            
            while self.check_update() or self.check_stop():
                time.sleep(2) #Attende finché il server non cancella l'update file o lo stop file
        
            #Carica Maschera 
            self.prepare_window()
            
            #Attiva Eventi
            gdi.add_scheduler(0.5, self.update_status)
            #self._event=None
            gdi.add_scheduler(1, self.check_events)
            
            bshow=True
            if mode=="systray":
                self.prepare_systray()
                bshow=False
            
            gdi.loop(self._app, bshow)
            self.unlock()
            if self._update:
                self.run_update()

def fmain(args): #SERVE PER MACOS APP
    try:
        mode = None
        for arg in args: 
            if arg.lower() == "systray":
                mode = "systray"
                break
            elif arg.lower() == "window":
                mode = "window"
                break
            elif arg.lower() == "info":
                mode = "info"
                break
        if mode is not None:
            main = Main()
            Main.set_instance(main)
            main.start(mode)
        else:
            try:
                main = Main()
                Main.set_instance(main)
                main.start("window")
            except:
                main = Main()
                Main.set_instance(main)
                main.start("info")
        sys.exit(0)
    except Exception as e:
        print str(e)
        sys.exit(1)

if __name__ == "__main__":
    fmain(sys.argv)