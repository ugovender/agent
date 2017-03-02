# -*- coding: utf-8 -*-

'''
This Source Code Form is subject to the terms of the Mozilla
Public License, v. 2.0. If a copy of the MPL was not distributed
with this file, You can obtain one at http://mozilla.org/MPL/2.0/.
'''

import locale
import subprocess
import messages.default
import messages.it
import gdi
import threading
import json

_resourcesmap={}
_resourcesmap["semaphore"]=threading.Condition()

def set_locale(lng):
    _resourcesmap["semaphore"].acquire()
    try:
        _set_locale(lng)
    finally:
        _resourcesmap["semaphore"].release()

def _set_locale(lng):
    #SE AGGIUNGI LINGUA VERIFICA IN MACOS APP I FILE __boot__.py
    if lng is not None and lng.lower().startswith("it"):
        _resourcesmap["lang"]="it"
        _resourcesmap["lang_module"]=messages.it
    else:
        _resourcesmap["lang"]="default"
        _resourcesmap["lang_module"]=messages.default

def get_message(key):
    try:
        _resourcesmap["semaphore"].acquire()
        try:
            if "lang_module" not in _resourcesmap:
                applng=None
                try:
                    l = locale.getdefaultlocale()
                    if l is None or l[0] is None:
                        if gdi.is_mac():
                            p = subprocess.Popen(['defaults', 'read', '-g', 'AppleLocale'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                            sout, serr = p.communicate()
                            if sout is not None:
                                applng = sout.replace("\n","").replace(" ","_")[:10]
                    else:
                        applng=l[0]
                except:
                    None
                
                _set_locale(applng)
                
        finally:
            _resourcesmap["semaphore"].release()
        
        if key in _resourcesmap["lang_module"].data:
            return _resourcesmap["lang_module"].data[key]
        elif key in messages.default.data:
            return messages.default.data[key]
        else:
            return "RES_MISSING#" + key
    except:
        return "RES_ERROR#" + key

