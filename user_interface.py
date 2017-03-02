# -*- coding: utf-8 -*-

'''
This Source Code Form is subject to the terms of the Mozilla
Public License, v. 2.0. If a copy of the MPL was not distributed
with this file, You can obtain one at http://mozilla.org/MPL/2.0/.
'''

import resources
import platform
import os
import shutil
import sys
import threading
import gdi
from gdi import DIALOGMESSAGE_LEVEL_ERROR
#from Queue import Queue

_WIDTH=760
_HEIGHT=480
_HEIGHT_BOTTOM=55
_WIDTH_LEFT=90
_CONTENT_WIDTH=_WIDTH-_WIDTH_LEFT
_CONTENT_HEIGHT=_HEIGHT-_HEIGHT_BOTTOM

class VarString:
        
    def __init__(self, value = None,  password= False):
        self._value=value
        self._password=password
    
    def is_password(self):
        return self._password
    
    def set(self, v):
        self._value=v
    
    def get(self):
        return self._value

class UI:
    def __init__(self):
        self._cancel=False
        self._prev_step=None
        self._next_step=None
        self._key=None
        self._params={}
  
    def set_key(self,  k):
        self._key=k
        
    def get_key(self):
        return self._key
    
    def set_param(self,  k, v):
        self._params[k]=v
        
    def get_param(self, k, d=None):
        if k in self._params:
            return self._params[k]
        else:
            return d
        
    def is_next_enabled(self):
        return self._next_step is not None
    
    def is_back_enabled(self):
        return self._prev_step is not None
    
    def prev_step(self, np):
        self._prev_step=np
    
    def next_step(self, np):
        self._next_step=np
    
    def fire_prev_step(self):
        if self._prev_step is not None:
            return self._prev_step(self)
        return None
        
    def fire_next_step(self):
        if self._next_step is not None:
            return self._next_step(self)
        return None

class Message(UI):
    def __init__(self, msg=''):
        UI.__init__(self)
        self._message=msg
    
    def set_message(self, msg):
        self._message=msg
        
    def get_message(self):
        return self._message
    
class Inputs(UI):
   
    def __init__(self):
        UI.__init__(self)
        self._message=None
        self._arinputs=[]
    
    def set_message(self, msg):
        self._message=msg
        
    def get_message(self):
        return self._message
    
    def add(self, key, label, variable, mandatory):
        self._arinputs.append({'key':key,  'label':label,  'variable':variable,  'mandatory':mandatory })
    
    def get_inputs(self):
        return self._arinputs
    
    def fire_next_step(self):
        #Verifica mandatory
        for i in range(len(self._arinputs)):
            inp = self._arinputs[i]
            if inp['mandatory'] is True and inp['variable'].get().strip()=="":
                return ErrorDialog(resources.get_message("fieldRequired").format(inp['label']))
        return UI.fire_next_step(self)

    def on_validate(self,e):
        for i in range(len(self._arinputs)):
            inp = self._arinputs[i]
            if inp["key"]==e["source"].get_name():
                inp["variable"].set(e["source"].get_text())
                break
        
class Chooser(UI):
        
    def __init__(self):
        UI.__init__(self)
        self._archooser=[]
        self._selected_key=None
        self._variable=None
        self._message=None
        self._message_height=100
        self._accept_key=None
        self._main=None
        self._selected=None
        
        
    def set_message(self, m):
        self._message=m
    
    def set_message_height(self, h):
        self._message_height=h
    
    def get_message_height(self):
        return self._message_height
    
    def get_message(self):
        return self._message
    
    def set_accept_key(self, k):
        self._accept_key=k
    
    def get_accept_key(self):
        return self._accept_key
    
    def is_accept_key(self,s):
        if self._accept_key is not None:
            ar = self._accept_key.split(";")
            for i in ar:
                if i==s:
                    return True
        return False
    
    def add(self, key, label):
        self._archooser.append({'key':key,  'label':label})
    
    def get_choices(self):
        return self._archooser
    
    def get_variable(self):
        return self._variable
        
    def set_variable(self, v):
        self._variable=v
    
    def fire_next_step(self):
        #Verifica se selezionato
        bok = False
        for i in range(len(self._archooser)):
            inp = self._archooser[i]
            if self._variable.get()==inp["key"]:
                bok = True
                break
        if not bok:
            return ErrorDialog(resources.get_message("mustSelectOptions"))
        return UI.fire_next_step(self)
    
    def set_main(self, main):
        self._main=main
        self._disble_next_button()

    def on_selected(self,e):
        self.get_variable().set(e["source"].get_name())
        self._disble_next_button()
    
    def _disble_next_button(self):
        None
        if self._main is not None and self.get_accept_key() is not None:
            if self.is_accept_key(self.get_variable().get()):
                self._main._enable_next_button()
            else:
                self._main._disable_next_button()
                
class ErrorDialog():
    
    def __init__(self, msg):
        self._message=msg
    
    def get_message(self):
        return self._message

class AsyncInvoke(threading.Thread):
    def __init__(self, main, func, callback):
        threading.Thread.__init__(self, name="User_Interface")
        self._func=func
        self._callback=callback
        self._main=main
    
    def run(self):
        try:
            self._main._wait_ui=None
            self._main.wait_message(resources.get_message("waiting"))
            ret=self._func()  
        except SystemExit:
            self._main._action=None
            gdi.add_scheduler(0.1, self._main.close)
            return         
        except Exception as e:
            msg = e.__class__.__name__
            if e.args is not None and len(e.args)>0 and e.args[0] != '':
                msg = e.args[0]
            ret=ErrorDialog(resources.get_message('unexpectedError').format(msg))
        self._main._guimode_execute(self._callback,  ret)

class Main():
    def __init__(self, title, step_init):
        self._title = title
        self._step_init=step_init
        self._cur_step_ui=None
        self._wait_ui=None
        self._action=None
    
    def set_action(self,f):
        self._action=f
    
    def _copy_msvc_file(self,nm):
        src="runtime" + os.sep + nm;
        dst="runtime" + os.sep + "DLLs" + os.sep + nm
        if os.path.exists(src) and not os.path.exists(dst):
            shutil.copy2(src,dst)
    
    def start(self, bgui=True):
        if bgui:
            try:
                #Copia le librerie msvc90
                if gdi.is_windows():
                    self._copy_msvc_file("msvcm90.dll");
                    self._copy_msvc_file("msvcp90.dll");
                    self._copy_msvc_file("msvcr90.dll");
                    self._copy_msvc_file("Microsoft.VC90.CRT.manifest");
                elif gdi.is_linux():
                    if not "DISPLAY" in os.environ:
                        raise("NODIPLAY") 
                    d = os.environ["DISPLAY"]
                    if d is None or d=="":
                        raise("NODIPLAY")    
                self._gui_enable=True
                self._guimode_start()
            except Exception as e:
                self._gui_enable=False
                self._clmode_start()
        else:
            self._gui_enable=False
            self._clmode_start()
    
    def _prepare_step(self, stp):
        self._prev_msg_wait=""
        self._prepare_buttons(stp)
        func = getattr(self,  '_show_' + stp.__class__.__name__ .lower())
        func(stp)
    
    def next(self):
        if self._gui_enable==True:
            self._guimode_next()
        else:
            self._clmode_next()
            
    def back(self):
        if self._gui_enable==True:
            self._guimode_back()
        else:
            self._clmode_back()
    
    def _op_complete(self, app):
        if app is None and self._wait_ui is not None:
            self._prepare_step(self._cur_step_ui)
        elif app.__class__.__name__ .lower()=='errordialog':
            self._show_error(app.get_message())
        else:
            self._cur_step_ui = app
            self._prepare_step(self._cur_step_ui)
            
    def _signal_close(self, signal, frame):
        self.close()
    
    def close(self):
        if self._gui_enable is True:
            self._app.destroy()
        if self._action is not None:
            self._action({"action":"CLOSE"})        
        
    def _clmode_next(self):
        try:
            self.wait_message(resources.get_message("waiting"))
            ret=self._cur_step_ui.fire_next_step()
        except Exception as e:
            msg = e.__class__.__name__
            if e.args is not None and len(e.args)>0 and e.args[0] != '':
                msg = e.args[0]
            ret=ErrorDialog(resources.get_message('unexpectedError').format(msg))
        self._op_complete(ret)
    
    def _clmode_back(self):
        try:
            self.wait_message(resources.get_message("waiting"))
            ret=self._cur_step_ui.fire_prev_step()
        except Exception as e:
            msg = e.__class__.__name__
            if e.args is not None and len(e.args)>0 and e.args[0] != '':
                msg = e.args[0]
            ret=ErrorDialog(resources.get_message('unexpectedError').format(msg))
        self._op_complete(ret)
     
    def _clmode_start(self):
        try:
            import signal 
            signal.signal(signal.SIGINT, self._signal_close)
        except:
            None            
        
        print("")
        print("*********************************************")
        print(resources.get_message('commands') + ":")
        print("  #B <" + resources.get_message('enter')  + "> " + resources.get_message('toBack'))
        print("  #E <" + resources.get_message('enter')  + "> " + resources.get_message('toExit'))
        print("*********************************************")
        try:
            self._cur_step_ui=self._step_init(UI())
            if isinstance(self._cur_step_ui,ErrorDialog):
                self._cur_step_ui=Message(self._cur_step_ui.get_message())
        except Exception as e:            
            self._cur_step_ui=Message("Error: " + str(e))        
        self._prepare_step(self._cur_step_ui)
        print("")
    
    def _guimode_next(self, e):
        ac = AsyncInvoke(self, self._cur_step_ui.fire_next_step, self._op_complete)
        ac.start()
    
    def _guimode_back(self, e):
        ac = AsyncInvoke(self, self._cur_step_ui.fire_prev_step, self._op_complete)
        ac.start()
    
    def _guimode_close_action(self, e):
        if e["action"]=="DIALOG_YES":
            self.close()
    
    def _guimode_close(self, e):
        if self._cur_step_ui is None or (self._cur_step_ui.is_next_enabled() or self._cur_step_ui.is_back_enabled()) :
            dlgerr = gdi.DialogMessage(gdi.DIALOGMESSAGE_ACTIONS_YESNO,gdi.DIALOGMESSAGE_LEVEL_INFO,self._app)
            dlgerr.set_title(self._title)
            dlgerr.set_message(resources.get_message('confirmExit'))
            dlgerr.set_action(self._guimode_close_action)
            dlgerr.show();
        else:
            self.close()
    
    def _guimode_action(self, e):
        if e["action"]==u"ONCLOSE":
            e["cancel"]=True
            if self._btclose.is_enable():
                self._guimode_close(e)
    
    def _guimode_step_init_start(self):
        ac = AsyncInvoke(self, self._guimode_step_init, self._guimode_step_init_callback)
        ac.start()
    
    def _guimode_step_init(self):
        ui=None
        try:
            ui=self._step_init(UI())
            if isinstance(ui,ErrorDialog):
                ui=Message(ui.get_message())
        except Exception as e:            
            ui=Message("Error: " + str(e))
        return ui
    
    def _guimode_step_init_callback(self,ui):
        self._cur_step_ui=ui
        self._prepare_step(self._cur_step_ui)
    
    def _guimode_start(self):
        self._app = gdi.Window(gdi.WINDOW_TYPE_NORMAL_NOT_RESIZABLE);
        self._app.set_title(U"DWAgent")
        self._app.set_size(_WIDTH, _HEIGHT)
        self._app.set_show_position(gdi.WINDOW_POSITION_CENTER_SCREEN)
        self._app.set_action(self._guimode_action)
        
        pnl_left = gdi.Panel();
        pnl_left.set_position(0, 0)
        pnl_left.set_size(_WIDTH_LEFT,_HEIGHT)
        pnl_left.set_background_gradient("83e5ff", "FFFFFF", gdi.GRADIENT_DIRECTION_LEFTRIGHT)
        self._app.add_component(pnl_left)
                
        pnl_bottom = gdi.Panel();
        pnl_bottom.set_position(0, _CONTENT_HEIGHT)
        pnl_bottom.set_size(_WIDTH,_HEIGHT_BOTTOM)
        self._app.add_component(pnl_bottom)
        
        wbtn=140
        hbtn=36
        
        self._btback = gdi.Button();
        self._btback.set_position(10, 10)
        self._btback.set_size(wbtn, hbtn)
        self._btback.set_text(resources.get_message('back'))
        self._btback.set_enable(False);
        self._btback.set_action(self._guimode_back)
        pnl_bottom.add_component(self._btback)
                
        self._btnext = gdi.Button();
        self._btnext.set_position(10+wbtn+5, 10)
        self._btnext.set_size(wbtn, hbtn)
        self._btnext.set_text(resources.get_message('next'))
        self._btnext.set_enable(False);
        self._btnext.set_action(self._guimode_next)
        pnl_bottom.add_component(self._btnext)
        
        self._btclose = gdi.Button();
        self._btclose.set_position(_WIDTH-wbtn-10, 10)
        self._btclose.set_size(wbtn, hbtn)
        self._btclose.set_text(resources.get_message('close'))
        self._btclose.set_enable(False);
        self._btclose.set_action(self._guimode_close)
        pnl_bottom.add_component(self._btclose)
        
        self._pnlmain=None
        self._cur_step_ui=None
        self._step_init_run=False
        
        gdi.add_scheduler(0.1,self._guimode_step_init_start)
        
        #self._queue = Queue()
        #gdi.add_scheduler(0.1, self._guimode_update)
        
        gdi.loop(self._app,True)
        
    
    def _guimode_execute(self, func, *args, **kargs):
        func(*args, **kargs)
        #self._queue.put([func, args, kargs])
    
    '''def _guimode_update(self):
        while not self._queue.empty():
            func, args, kargs = self._queue.get()
            try: 
                func(*args, **kargs)
            except Exception as e:
                import traceback 
                msg = str(e)
                msg += "\n" + traceback.format_exc()
                print(msg)
            self._queue.task_done()
        gdi.add_scheduler(0.1, self._guimode_update)'''

    def _prepare_main_panel(self):
        if self._gui_enable is True:
            if (self._pnlmain is not None):
                self._pnlmain.remove_all_components()
            else:
                self._pnlmain = gdi.Panel();
                self._pnlmain.set_background("ffffff")
                self._pnlmain.set_position(_WIDTH_LEFT, 0)
                self._pnlmain.set_size(_CONTENT_WIDTH,_CONTENT_HEIGHT)
                self._app.add_component(self._pnlmain)

    def _prepare_buttons(self,  ui):
        if self._gui_enable is True:
            self._btnext.set_enable(ui.is_next_enabled())
            self._btback.set_enable(ui.is_back_enabled())
            self._btclose.set_enable(True)
    
    def _disable_next_button(self):
        if self._gui_enable is True:
            self._btnext.set_enable(False)
    
    def _enable_next_button(self):
        if self._gui_enable is True:
            self._btnext.set_enable(True)
    
    def _show_error_gui_ok(self,e):
        if self._wait_ui is not None:
            self._prepare_step(self._cur_step_ui)
            
    def _show_error(self,  msg):
        if self._gui_enable is True:
            dlgerr = gdi.DialogMessage(gdi.DIALOGMESSAGE_ACTIONS_OK,gdi.DIALOGMESSAGE_LEVEL_ERROR,self._app)
            dlgerr.set_title(self._title)
            dlgerr.set_message(msg)
            dlgerr.set_action(self._show_error_gui_ok)
            dlgerr.show();
        else:
            print("")
            print(resources.get_message('error') + ": " + msg)
            try:
                raw_input(resources.get_message('pressEnter'))
                self._prepare_step(self._cur_step_ui)
            except:
                None
    
    def wait_message(self, msg, perc=None, progr=None, allowclose=False):
        if self._gui_enable is True:
            if perc is not None:
                msg=msg + "     (" + str(perc) + "%)"
            self._guimode_execute(self._wait_message_gui, msg, progr, allowclose)
        else:
            if self._prev_msg_wait!=msg:
                self._prev_msg_wait=msg
                print msg
    
    def _wait_message_gui(self, msg, progr=None, allowclose=False):
        gap=20
        if self._wait_ui is None:
            self._btnext.set_enable(False)
            self._btback.set_enable(False)
            self._btclose.set_enable(allowclose)
            self._prepare_main_panel()
            lbl=gdi.Label()
            lbl.set_wordwrap(True)
            lbl.set_position(gap,(_CONTENT_HEIGHT/2)-60)
            lbl.set_size(_CONTENT_WIDTH-(2*gap),60)
            lbl.set_text_align(gdi.TEXT_ALIGN_LEFTTOP)
            self._pnlmain.add_component(lbl)
            pbar = gdi.ProgressBar()
            pbar.set_position(gap,_CONTENT_HEIGHT/2)
            pbar.set_size(_CONTENT_WIDTH-(2*gap),24)
            self._pnlmain.add_component(pbar)
            self._wait_ui={'label':lbl,  'progress':pbar}
        else:
            self._btclose.set_enable(allowclose)
            lbl=self._wait_ui['label']
            pbar=self._wait_ui['progress']
        
        if 'label_value' not in self._wait_ui or self._wait_ui['label_value'] !=msg:
            lbl.set_text(msg)
        self._wait_ui['label_value']=msg
        if progr is None:
            if 'progress_value' not in self._wait_ui or self._wait_ui['progress_value'] is not None:
                pbar.set_y(-100)
                lbl.set_y(0)
                lbl.set_height(_CONTENT_HEIGHT)
                lbl.set_text_align(gdi.TEXT_ALIGN_LEFTMIDDLE)
            self._wait_ui['progress_value']=None
        else:
            if 'progress_value' not in self._wait_ui  or self._wait_ui['progress_value'] is None or self._wait_ui['progress_value']!=progr:
                lbl.set_y((_CONTENT_HEIGHT/2)-40)
                lbl.set_height(30)
                lbl.set_text_align(gdi.TEXT_ALIGN_LEFTTOP)
                pbar.set_y(_CONTENT_HEIGHT/2)
                pbar.set_percent(progr)                
            self._wait_ui['progress_value']=progr
            
            
        
    def _clmode_read(self, msg,  bpwd=False):
        ui = self._cur_step_ui;
        if not ui.is_next_enabled() and not ui.is_back_enabled():
            self.close()
            return None #Termina Installazione
        if not bpwd:
            try:
                sr = raw_input(msg + " ")
                if sr!="":
                    if sr=="#E" or sr=="#e":
                        self.close()
                        return None
                    elif sr=="#B" or sr=="#b":
                        if ui.is_back_enabled():
                            self._clmode_back()
                            return None      
                        else:
                            sr=""
                return sr
            except:
                self.close()
                return None #Termina Installazione
        else:
            import getpass
            pw = getpass.getpass(msg + " ")
            return pw
    
    def _show_message(self,  msg):
        if self._gui_enable is True:
            self._prepare_main_panel()
            gap=20
            w=_CONTENT_WIDTH-(2*gap)
            h=_CONTENT_HEIGHT-(2*gap)
            
            l = gdi.Label()
            l.set_position(gap,gap)
            l.set_size(w,h)
            l.set_wordwrap(True)
            l.set_text(msg.get_message())
            self._pnlmain.add_component(l)
        else:
            print("")
            print(msg.get_message())
            rd = self._clmode_read(resources.get_message('pressEnter'))
            if rd is not None:
                self._clmode_next()

    def _show_inputs(self,  inps):
        if self._gui_enable is True:
            self._prepare_main_panel()
            gap=20
            w=_CONTENT_WIDTH-(2*gap)
            h=100
            
            l = gdi.Label()
            l.set_position(gap,gap)
            l.set_size(w,h)
            l.set_wordwrap(True)
            l.set_text_align(gdi.TEXT_ALIGN_LEFTTOP)
            l.set_text(inps.get_message())
            self._pnlmain.add_component(l)

            lblw=170
            ar = inps.get_inputs()
            p=120
            for i in range(len(ar)):
                inp=ar[i]
                #LABEL
                l = gdi.Label()
                l.set_position(gap,p)
                l.set_size(lblw-1,30)
                l.set_text(inp['label'])
                self._pnlmain.add_component(l)
                
                #TEXTBOX
                t = gdi.TextBox()
                t.set_name(inp['key'])
                t.set_position(gap+lblw,p)
                t.set_size(_CONTENT_WIDTH-(4*gap)-lblw,30)
                t.set_text(inp['variable'].get())
                if inp['variable'].is_password():
                    t.set_password_mask(True)
                self._pnlmain.add_component(t)
                t.set_validate(inps.on_validate)
                if i==0:
                    t.focus()
                p+=36
        else:
            print("")
            print(inps.get_message())
            ar = inps.get_inputs()
            for i in range(len(ar)):
                inp=ar[i]
                v=inp['variable'].get()
                if v is None:
                    v=""
                if v!="" and not inp['variable'].is_password():
                    v=" (" + v + ")"
                rd = self._clmode_read(inp['label']  +  v + ":", inp['variable'].is_password())
                if rd is not None:
                    if rd.strip()!="":
                        inp['variable'].set(rd)
                else:
                    return
            self._clmode_next()
                            
            
    def _show_chooser(self,  chs):
        if self._gui_enable is True:
            self._prepare_main_panel()
            gap=20
            h=chs.get_message_height()
            w=_CONTENT_WIDTH-(2*gap)
            l = gdi.Label() 
            l.set_wordwrap(True)
            l.set_text_align(gdi.TEXT_ALIGN_LEFTTOP)
            l.set_text(chs.get_message())
            l.set_position(gap, gap)
            l.set_size(w, h)
            
            self._pnlmain.add_component(l)
        
            ar = chs.get_choices()
            p=h
            for i in range(len(ar)):
                inp=ar[i]
                rb = gdi.RadioButton()
                rb.set_text(inp['label'])
                rb.set_position(gap, p)
                rb.set_size(_CONTENT_WIDTH-(2*gap), 30)
                rb.set_name(inp['key'])
                rb.set_group("RADIOBUTTON")
                if chs.get_variable().get()==inp['key']:
                    rb.set_selected(True);
                rb.set_action(chs.on_selected)
                self._pnlmain.add_component(rb)
                p+=30
            chs.set_main(self)
        else:
            print("")
            print(chs.get_message())
            print("")
            ar = chs.get_choices()
            df = ""
            ar_idx_accept=[]
            idx_default=None
            for i in range(len(ar)):
                inp=ar[i]
                print(str(i+1) + ". " + inp['label'])
                if chs.get_variable().get()==inp['key']:
                    idx_default=i+1
                    df = " (" + str(idx_default) + ")"
                if chs.is_accept_key(inp['key']):
                    ar_idx_accept.append(i+1)
            rd = self._clmode_read(resources.get_message('option') + df + ":")
            if rd is not None:
                if rd=="":
                    rd=str(idx_default)
                try:
                    ird=int(rd)
                    if (ird>len(ar)):
                        raise Exception("")
                    if len(ar_idx_accept) > 0:
                        serr=[]
                        berr=True
                        for idxcur in ar_idx_accept:
                            serr.append(str(idxcur))
                            if ird==idxcur:
                                berr=False
                        if berr:
                            self._show_error(resources.get_message('mustAccept').format((' ' + resources.get_message('or') + ' ').join(serr)))
                            return
                    inp=ar[ird-1]
                except:
                    self._show_error(resources.get_message('optionNotValid'))
                    return
                chs.get_variable().set(inp['key'])
                self._clmode_next()
                
            
