# -*- coding: utf-8 -*-

'''
This Source Code Form is subject to the terms of the Mozilla
Public License, v. 2.0. If a copy of the MPL was not distributed
with this file, You can obtain one at http://mozilla.org/MPL/2.0/.
'''

import BaseHTTPServer
import threading
from urlparse import urlparse, parse_qs

#CREATO PER USI FUTURI
class ConfigHandler(BaseHTTPServer.BaseHTTPRequestHandler):

    def do_GET(self):
        #Legge richiesta
        o = urlparse(self.path)
        nm = o.path
        qs = parse_qs(o.query)
        #Invia risposta
        resp={}
        resp['code']=404
        if 'code' in resp:
            self.send_response(resp['code'])
        else:
            self.send_response(200)
        if 'headers' in resp:
            hds = resp['headers']
            for k in hds.keys():
                self.send_header(k, hds[k])
            self.end_headers()
        if 'data' in resp:
            self.wfile.write(resp['data'])
        
    def do_HEAD(self):
        self.send_response(404)

    def do_POST(self):
        self.send_response(404)

    
    def log_message(self, format, *args):
        return

class ConfigServer(BaseHTTPServer.HTTPServer):
    
    def __init__(self, port, agent):
        server_address = ('127.0.0.1', port)
        BaseHTTPServer.HTTPServer.__init__(self, server_address, ConfigHandler)
        self._agent = agent
    
    def get_agent(self):
        return self._agent
    

class Main(threading.Thread):
    
    def __init__(self, port,  agent):
        threading.Thread.__init__(self, name="AgentListener")
        self.daemon=True
        self._agent = agent
        self._port = port
        self._close=False
        self._httpd = None
    
    def run(self):        
        self._httpd = ConfigServer(self._port,  self._agent)
        self._close=False
        while not self._close:
            self._httpd.handle_request()

    def close(self):
        if  not self._close:
            self._close=True
            try:
                self._httpd.server_close()
            except:
                None
            self._httpd = None

if __name__ == "__main__":
    ac = Main(9000, None)
    ac.start()
    ac.join()
    
    
    
    
