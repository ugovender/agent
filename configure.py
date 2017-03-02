# -*- coding: utf-8 -*-

'''
This Source Code Form is subject to the terms of the Mozilla
Public License, v. 2.0. If a copy of the MPL was not distributed
with this file, You can obtain one at http://mozilla.org/MPL/2.0/.
'''

import resources
import user_interface
import sys
import agent_status_config

class Configure:
    
    def __init__(self):
        #self._config_port = 7950
        #self._path_config='config.json'
        self._prop=None
        self._install_code=user_interface.VarString()
        self._proxy_type=user_interface.VarString("SYSTEM")
        self._proxy_host=user_interface.VarString("")
        self._proxy_port=user_interface.VarString("")
        self._proxy_user=user_interface.VarString("")
        self._proxy_password=user_interface.VarString("", True)
        self._password=""
        self._main_menu_sel=user_interface.VarString("configureExit")
        self._agent_menu_sel=user_interface.VarString("configureChangeInstallKey")
        self._password_menu_sel=user_interface.VarString("configureSetPassword")
        
    def invoke_req(self, req, prms=None):
        try:
            if self._prop==None or self._prop.is_close():
                self._prop=agent_status_config.open_property()
            return agent_status_config.invoke_request(self._prop, "admin", self._password, req, prms);
        except: 
            return 'ERROR:REQUEST_TIMEOUT'
    
    def close_req(self):
        if self._prop!=None and not self._prop.is_close():
            self._prop.close()
            
    def check_auth(self):
        sret=self.invoke_req("check_auth", None)
        if sret=="OK":
            return True
        elif sret=="ERROR:FORBIDDEN":
            return False
        else:
            raise Exception(sret[6:])
    
    def get_config(self, key):
        sret=self.invoke_req("get_config", {'key':key})
        if sret[0:2]=="OK":
            return sret[3:]
        else:
            raise Exception(sret[6:])
        return sret     
    
    def set_config(self, key, val):
        sret=self.invoke_req("set_config", {'key':key, 'value':val})
        if sret!="OK":
            raise Exception(sret[6:])
            
    def uninstall_key(self):
        sret=self.invoke_req("remove_key", None)
        if sret!="OK":
            raise Exception(sret[6:])
        return sret  
    
    def install_key(self, code):
        sret=self.invoke_req("install_key", {'code':code})
        if sret!="OK":
            raise Exception(sret[6:])
        return sret  
    
    def change_pwd(self, pwd):
        if pwd!="":
            sret=self.invoke_req("change_pwd", {'password':self._change_pwd.get()})
        else:
            sret=self.invoke_req("change_pwd", {'nopassword':'true'})
        if sret!="OK":
            raise Exception(sret[6:])
        return sret  
    
    def is_agent_enable(self):
        s = self.get_config("enabled")
        return s=="True"
    
    def read_proxy_info(self):
        pt = self.get_config("proxy_type")
        self._proxy_type.set(pt)
        if self._proxy_type.get()=='HTTP' or self._proxy_type.get()=='SOCKS4' or self._proxy_type.get()=='SOCKS4A' or self._proxy_type.get()=='SOCKS5':
            self._proxy_host.set(self.get_config("proxy_host"))
            self._proxy_port.set(self.get_config("proxy_port"))
            self._proxy_user.set(self.get_config("proxy_user"))
    
    def start(self, bgui=True):
        self._uinterface = user_interface.Main(resources.get_message('configureTitle'), self.step_init)
        self._uinterface.start(bgui)
        self.close_req();
            

    def step_init(self, ui):
        '''
        try:
            msg = user_interface.Message(resources.get_message('configureWelcome'))
            msg.next_step(self.step_check_password)
        except Exception as e:
            msg = user_interface.Message(str(e))
        return msg
        '''
        return self.step_check_password(ui);
    
    def step_check_password(self, ui):
        try:
            if ui.get_key() is not None and ui.get_key()=='insert_password':
                self._password=self._ins_pwd.get()
            if not self.check_auth():
                if ui.get_key() is not None and ui.get_key()=='insert_password':
                    return user_interface.ErrorDialog(resources.get_message('configureInvalidPassword'))
                return self.step_password(ui)
            else:
                return self.step_menu_main(ui)
        except:
            return user_interface.ErrorDialog(resources.get_message('configureErrorConnection'))
    
    def step_password(self, ui):
        self._ins_pwd=user_interface.VarString("", True)
        ipt = user_interface.Inputs()
        ipt.set_key("insert_password")
        ipt.set_message(resources.get_message('configureInsertPassword'))
        ipt.add('password', resources.get_message('password'), self._ins_pwd,  True)
        ipt.next_step(self.step_check_password)
        return ipt
    
    def step_menu_main(self, ui):
        try:
            self.read_proxy_info()
        except:
            return user_interface.ErrorDialog(resources.get_message('configureErrorConnection'))
        chs = user_interface.Chooser()
        chs.set_message(resources.get_message('configureChooseOperation'))
        chs.add("configureAgent", resources.get_message('configureAgent'))
        chs.add("configureProxy", resources.get_message('configureProxy'))
        #chs.add("configureMonitor", resources.get_message('configureMonitor'))
        chs.add("configurePassword", resources.get_message('configurePassword'))
        chs.add("configureExit", resources.get_message('configureExit'))
        chs.set_variable(self._main_menu_sel)
        chs.next_step(self.step_menu_main_selected)
        return chs

    def step_menu_main_selected(self, ui):
        if ui.get_variable().get()=="configureAgent":
            return self.step_menu_agent(ui)
        elif ui.get_variable().get()=="configureProxy":
            ui.set_key("menuProxy")
            return self.step_configure_proxy_type(ui)
        elif ui.get_variable().get()=="configureMonitor":
            return self.step_menu_monitor(ui)
        elif ui.get_variable().get()=="configurePassword":
            return self.step_menu_password(ui)
        elif ui.get_variable().get()=="configureExit":
            return user_interface.Message(resources.get_message('configureEnd'))
    
    def step_menu_agent(self, ui):
        try:
            self._install_code.set("")
            key = self.get_config("key")
            if key == "":
                return self.step_menu_agent_install_key_selected(ui)
            else:
                chs = user_interface.Chooser()
                chs.set_message(resources.get_message('configureChooseOperation'))
                chs.add("configureChangeInstallKey", resources.get_message('configureChangeInstallKey'))
                if self.is_agent_enable():
                    chs.add("configureDisableAgent", resources.get_message('configureDisableAgent'))
                else:
                    chs.add("configureEnableAgent", resources.get_message('configureEnableAgent'))
                chs.set_variable(self._agent_menu_sel)
                chs.prev_step(self.step_menu_main)
                chs.next_step(self.step_menu_agent_selected)
                return chs
        except:
            return user_interface.ErrorDialog(resources.get_message('configureErrorConnection'))
            
    
    def step_menu_agent_selected(self, ui):
        if ui.get_variable().get()=="configureChangeInstallKey":
            return self.step_menu_agent_install_key(ui)
        elif ui.get_variable().get()=="configureEnableAgent":
            return self.step_menu_agent_enable(ui)
        elif ui.get_variable().get()=="configureDisableAgent":
            return self.step_menu_agent_disable(ui)
            
    def step_menu_agent_install_key(self, ui):
        chs = user_interface.Chooser()
        chs.set_message(resources.get_message('configureUninstallKeyQuestion'))
        chs.add("yes", resources.get_message('yes'))
        chs.add("no", resources.get_message('no'))
        chs.set_variable(user_interface.VarString("no"))
        chs.set_accept_key("yes")
        chs.prev_step(self.step_menu_agent)
        chs.next_step(self.step_menu_agent_remove_key_selected)
        return chs
    
    def step_menu_agent_remove_key_selected(self, ui):
        if ui.get_variable().get()=='yes':
            try:
                self._uinterface.wait_message(resources.get_message('configureUninstallationKey'),  0)
                self.uninstall_key()
            except:
                    return user_interface.ErrorDialog(resources.get_message('configureErrorConnection'))
            return self.step_menu_agent_install_key_selected(ui)
        else:
            return self.step_menu_agent(ui)
    
    def step_menu_agent_install_key_selected(self, ui):
        ipt = user_interface.Inputs()
        ipt.set_message(resources.get_message('enterInstallCode'))
        ipt.add('code', resources.get_message('code'), self._install_code, True)
        ipt.prev_step(self.step_menu_agent)
        ipt.next_step(self.step_check_install_code)
        return ipt
    
    def step_check_install_code(self, ui):
        if ui.get_key() is not None and ui.get_key()=='tryAgain':
            if ui.get_variable().get()=='configureLater':
                return self.step_menu_main(ui)
            elif ui.get_variable().get()=='configProxy':
                ui.set_key("installCode")
                return self.step_configure_proxy_type(ui)
            elif ui.get_variable().get()=='reEnterCode':
                return self.step_menu_agent_install_key_selected(ui)
        msg=resources.get_message('checkInstallCode')
        self._uinterface.wait_message(msg)
        key = self._install_code.get()
        try:
            self.install_key(key)
            msg = user_interface.Message(resources.get_message('configureKeyInstalled'))
            msg.next_step(self.step_menu_main)
            return msg
        except Exception as e:
            s = str(e)
            if s=="INVALID_CODE":
                chs = user_interface.Chooser()
                chs.set_key("tryAgain")
                chs.set_message(resources.get_message('errorInvalidCode'))
                chs.add("reEnterCode", resources.get_message('reEnterCode'))
                chs.add("configureLater", resources.get_message('configureLater'))
                chs.set_variable(user_interface.VarString("reEnterCode"))
                chs.prev_step(self.step_menu_agent_install_key_selected)
                chs.next_step(self.step_check_install_code)
                return chs
            elif s=="CONNECT_ERROR":
                chs = user_interface.Chooser()
                chs.set_key("tryAgain")
                chs.set_message(resources.get_message('errorConnectionQuestion'))
                chs.add("configProxy", resources.get_message('yes'))
                chs.add("noTryAgain", resources.get_message('noTryAgain'))
                chs.add("configureLater", resources.get_message('configureLater'))
                chs.set_variable(user_interface.VarString("noTryAgain"))
                chs.prev_step(self.step_menu_agent_install_key_selected)
                chs.next_step(self.step_check_install_code)
                return chs
            elif s=="REQUEST_TIMEOUT":
                return user_interface.ErrorDialog(resources.get_message('configureErrorConnection'))
            else:
                return user_interface.ErrorDialog(s) 
    
    def step_configure_proxy_type(self, ui):
        chs = user_interface.Chooser()
        chs.set_key(ui.get_key())
        chs.set_message(resources.get_message('chooseProxyType'))
        chs.add("SYSTEM", resources.get_message('proxySystem'))
        chs.add("HTTP", resources.get_message('proxyHttp'))
        chs.add("SOCKS4", resources.get_message('proxySocks4'))
        chs.add("SOCKS4A", resources.get_message('proxySocks4a'))
        chs.add("SOCKS45", resources.get_message('proxySocks5'))
        chs.add("NONE", resources.get_message('proxyNone'))
        chs.set_variable(self._proxy_type)
        
        if ui.get_key()=="menuProxy":
            chs.prev_step(self.step_menu_main)
        elif ui.get_key()=="installCode":
            chs.prev_step(self.step_menu_agent_install_key_selected)
        
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
        ar = ui.get_key().split('_')
        ui.set_key(ar[0]) 
        if len(ar)==2 and ar[1]=='tryAgain':
            if ui.get_variable() is not None and ui.get_variable().get()=='configureLater':
                if ui.get_key()=="menuProxy":
                    return self.step_menu_main(ui)
                elif ui.get_key()=="installCode":
                    return self.step_menu_agent_install_key_selected(ui)
        try:
            if self._proxy_type.get()=='HTTP' or self._proxy_type.get()=='SOCKS4' or self._proxy_type.get()=='SOCKS4A' or self._proxy_type.get()=='SOCKS5':
                try:
                    int(self._proxy_port.get())
                except:
                    return user_interface.ErrorDialog(resources.get_message("validInteger") .format(resources.get_message('proxyPort')))
            sret=self.invoke_req("set_proxy",  {'type': self._proxy_type.get(), 
                                                       'host':  self._proxy_host.get(), 
                                                       'port': self._proxy_port.get(), 
                                                       'user': self._proxy_user.get(), 
                                                       'password': self._proxy_password.get()})
            if sret!="OK":
                raise Exception(sret[6:])
        except:
            chs = user_interface.Chooser()
            chs.set_key(ui.get_key() + "_tryAgain")
            chs.set_message(resources.get_message('errorConnectionConfig'))
            chs.add("noTryAgain", resources.get_message('noTryAgain'))
            chs.add("configureLater", resources.get_message('configureLater'))
            chs.set_variable(user_interface.VarString("noTryAgain"))
            if ui.get_key()=="menuProxy":
                chs.prev_step(self.step_menu_main)
            elif ui.get_key()=="installCode":
                chs.prev_step(self.step_menu_agent_install_key_selected)
            chs.next_step(self.step_configure_proxy_set)
            return chs
        if ui.get_key()=="menuProxy":
            msg = user_interface.Message(resources.get_message('configureProxyEnd'))
            msg.next_step(self.step_menu_main)
            return msg
        elif ui.get_key()=="installCode":
            return self.step_check_install_code(ui)
        
    
    def step_menu_agent_enable(self, ui):
        chs = user_interface.Chooser()
        chs.set_message(resources.get_message('configureEnableAgentQuestion'))
        chs.add("yes", resources.get_message('yes'))
        chs.add("no", resources.get_message('no'))
        chs.set_variable(user_interface.VarString("no"))
        chs.set_accept_key("yes")
        chs.prev_step(self.step_menu_agent)
        chs.next_step(self.step_menu_agent_enable_procede)
        return chs
    
    def step_menu_agent_disable(self, ui):
        chs = user_interface.Chooser()
        chs.set_message(resources.get_message('configureDisableAgentQuestion'))
        chs.add("yes", resources.get_message('yes'))
        chs.add("no", resources.get_message('no'))
        chs.set_variable(user_interface.VarString("no"))
        chs.set_accept_key("yes")
        chs.prev_step(self.step_menu_agent)
        chs.next_step(self.step_menu_agent_disable_procede)
        return chs
        
    def step_menu_agent_enable_procede(self, ui):
        if ui.get_variable().get()=='yes':
            try:
                self.set_config("enabled", "True")
                msg = user_interface.Message(resources.get_message('configureAgentEnabled'))
                msg.next_step(self.step_menu_main)
                return msg
            except:
                    return user_interface.ErrorDialog(resources.get_message('configureErrorConnection'))
        else:
            return self.step_menu_agent(ui)
    
    def step_menu_agent_disable_procede(self, ui):
        if ui.get_variable().get()=='yes':
            try:
                self.set_config("enabled", "False")
                msg = user_interface.Message(resources.get_message('configureAgentDisabled'))
                msg.next_step(self.step_menu_main)
                return msg
            except:
                    return user_interface.ErrorDialog(resources.get_message('configureErrorConnection'))
        else:
            return self.step_menu_agent(ui)
    
    def step_menu_monitor(self, ui):
        chs = user_interface.Chooser()
        chs.set_message(resources.get_message('configureChooseOperation'))
        chs.add("configureTrayIconVisibility", resources.get_message('configureTrayIconVisibility'))
        chs.set_variable(user_interface.VarString("configureTrayIconVisibility"))
        chs.prev_step(self.step_menu_main)
        chs.next_step(self.step_menu_monitor_selected)
        return chs
    
    def step_menu_monitor_selected(self, ui):
        try:
            chs = user_interface.Chooser()
            chs.set_message(resources.get_message('configureChooseMonitorTrayIconVisibility'))
            chs.add("yes", resources.get_message('yes'))
            chs.add("no", resources.get_message('no'))
            if self.get_config("monitor_tray_icon")=="True":
                chs.set_variable(user_interface.VarString("yes"))
            else:
                chs.set_variable(user_interface.VarString("no"))
            chs.prev_step(self.step_menu_monitor)
            chs.next_step(self.step_menu_monitor_procede)
            return chs
        except:
            return user_interface.ErrorDialog(resources.get_message('configureErrorConnection'))
    
    def step_menu_monitor_procede(self, ui):
        try:
            if ui.get_variable().get()=='yes':
                self.set_config("monitor_tray_icon", "True")
            else:
                self.set_config("monitor_tray_icon", "False")
            msg = user_interface.Message(resources.get_message('configureTrayIconOK'))
            msg.next_step(self.step_menu_main)
            return msg
        except:
            return user_interface.ErrorDialog(resources.get_message('configureErrorConnection'))

    def step_menu_password(self, ui):
        chs = user_interface.Chooser()
        chs.set_message(resources.get_message('configureChooseOperation'))
        chs.add("configureSetPassword", resources.get_message('configureSetPassword'))
        chs.add("configureRemovePassword", resources.get_message('configureRemovePassword'))
        chs.set_variable(self._password_menu_sel)
        chs.prev_step(self.step_menu_main)
        chs.next_step(self.step_config_password)
        return chs

    def step_config_password(self, ui):
        if ui.get_variable().get()=='configureSetPassword':
            self._change_pwd=user_interface.VarString("", True)
            self._change_repwd=user_interface.VarString("", True)
            ipt = user_interface.Inputs()
            ipt.set_key("set_password")
            ipt.set_message(resources.get_message('configurePassword'))
            ipt.add('password', resources.get_message('password'), self._change_pwd,  True)
            ipt.add('rePassword', resources.get_message('rePassword'), self._change_repwd,  True)
            ipt.prev_step(self.step_menu_password)
            ipt.next_step(self.step_config_password_procede)
            return ipt
        elif ui.get_variable().get()=='configureRemovePassword':
            chs = user_interface.Chooser()
            chs.set_key("remove_password")
            chs.set_message(resources.get_message('configureRemovePasswordQuestion'))
            chs.add("yes", resources.get_message('yes'))
            chs.add("no", resources.get_message('no'))
            chs.set_variable(user_interface.VarString("no"))
            chs.set_accept_key("yes")
            chs.prev_step(self.step_menu_password)
            chs.next_step(self.step_config_password_procede)
            return chs
    
    def step_config_password_procede(self, ui):
        if ui.get_key() is not None and ui.get_key()=='set_password':
            if self._change_pwd.get()==self._change_repwd.get():
                try:
                    self.change_pwd(self._change_pwd.get())
                    self._password=self._change_pwd.get()
                    msg = user_interface.Message(resources.get_message('configurePasswordUpdated'))
                    msg.next_step(self.step_menu_main)
                    return msg
                except:
                    return user_interface.ErrorDialog(resources.get_message('configureErrorConnection'))
            else:
                return user_interface.ErrorDialog(resources.get_message('configurePasswordErrNoMatch'))
        elif ui.get_key() is not None and ui.get_key()=='remove_password':
            if ui.get_variable().get()=='yes':
                try:
                    self.change_pwd("")
                    self._password=""
                    msg = user_interface.Message(resources.get_message('configurePasswordUpdated'))
                    msg.next_step(self.step_menu_main)
                    return msg
                except:
                    return user_interface.ErrorDialog(resources.get_message('configureErrorConnection'))
                
def fmain(args): #SERVE PER MACOS APP
    bgui=True
    for arg in args: 
        if arg.lower() == "-console":
            bgui=False
    i = Configure()
    i.start(bgui)

if __name__ == "__main__":
    fmain(sys.argv)
    
