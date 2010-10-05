
# mirrorcast - mirrorcast.py
# Copyright 2010 Robert Grupp (robert.grupp@gmail.com)

# This file is part of mirrorcast.
# 
# mirrorcast is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# mirrorcast is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with mirrorcast.  If not, see <http://www.gnu.org/licenses/>.

import BaseHTTPServer
import SocketServer
import urllib2
import urllib
import sys
import time
import functools
import ConfigParser

# TODO:
# - Add ability to send HTTP server debug to log file
# - Support x-audiocast-udpport

class MirrorCastParams(object):
    def __init__(self):
        self.port = 8080
        self.mirror_action = 'mirror'
        self.chunk_size = 64 * 1024 # 64 K
        self.no_data_delay = 0.05 # 50 ms
        object.__init__(self)

def ReadMirrorCastParams(path):
    parser = ConfigParser.SafeConfigParser()
    params = MirrorCastParams()
    kPARAMS_SECTION = 'mirrorcast'
    try:
        parser.read(path)
        params.port = parser.getint(kPARAMS_SECTION,'port')
        params.mirror_action = parser.get(kPARAMS_SECTION,'mirror_action')
        params.chunk_size = parser.getint(kPARAMS_SECTION,'chunk_size')
        params.no_data_delay = parser.getfloat(kPARAMS_SECTION,'no_data_delay')
    except:
        params = None
    return params

class RadioForwarderHttpHandler(
                      BaseHTTPServer.BaseHTTPRequestHandler):
    """Handler class for a HTTPServer, inherits from
    BaseHTTPServer.BaseHTTPRequestHandler. HTTP POST requests
    are not supported and just return HTTP error 404. HTTP GET
    requests are used to send streaming data to a client."""

    def __init__(self,params,request,client_address,server):
        self.params = params
        BaseHTTPServer.BaseHTTPRequestHandler.__init__(
            self,request,client_address,server)
    
    def do_POST(self):
        """Does nothing; always responds with HTTP error 404."""
        self.send_error(404)

    def do_GET(self):
        # requests to mirror take the form /mirror/<radio URL>
        # eg. /mirror/http://75.102.43.202/live
        path_str = self.path[1:]
        kMIRROR_ACTION_W_SLASH = '%s/' % self.params.mirror_action
        path_entries = path_str.split('/')
        if (path_str and (path_entries[0].lower() ==
                          self.params.mirror_action)
            and (len(path_str) > len(kMIRROR_ACTION_W_SLASH))):
            # make sure it has a / followed by an address
            if path_str.find(kMIRROR_ACTION_W_SLASH) == 0:
                srv_url = urllib.unquote(
                    path_str[len(kMIRROR_ACTION_W_SLASH):])
                # retreive the client's headers
                cli_hdrs = {}
                # for k,v in self.headers does not work, yields
                # the following error:
                # ValueError: too many values to unpack
                # solution is to just to do for k in self.headers
                # and then lookup the value.
                for cli_hdr_key in self.headers:
                    # currently no support for 'x-audiocast-udpport'
                    cli_hdr_val = self.headers[cli_hdr_key]
                    if cli_hdr_val.lower() != 'x-audiocast-udpport':
                        cli_hdrs[cli_hdr_key] = cli_hdr_val
                try:
                    # make the connection to the real radio server
                    u = urllib2.urlopen(urllib2.Request(srv_url,
                                                  headers=cli_hdrs))
                    # send back header
                    self.send_response(200)
                    u_info = u.info()
                    for srv_hdr_key in u_info:
                        self.send_header(srv_hdr_key,u_info[srv_hdr_key])
                    self.end_headers()
                    # now start writing the audio stream
                    while True:
                        chunk = u.read(self.params.chunk_size)
                        if chunk and (len(chunk) > 0):
                            try:
                                self.wfile.write(chunk)
                            except:
                                # exception will be thrown on client exit
                                break
                        else:
                            time.sleep(self.params.no_data_delay)
                except (ValueError,urllib2.URLError,urllib2.HTTPError):
                    self.send_error(404)
            else:
                self.send_error(404)
        else:
            self.send_error(404)

class ThreadedHTTPServer(SocketServer.ThreadingMixIn,
                         BaseHTTPServer.HTTPServer):
    """Threaded HTTP server class. Each connection is
    handled by a separate thread. Inherits from:
    SocketServer.ThreadingMixIn and BaseHTTPServer.HTTPServer."""
    pass

class RadioHTTPServer(ThreadedHTTPServer):
    def __init__(self,params):
        self.params = params
        ThreadedHTTPServer.__init__(self,('',self.params.port),
                   functools.partial(RadioForwarderHttpHandler,
                                     self.params))

def main_fn():
    if len(sys.argv) >= 2:
        params = ReadMirrorCastParams(sys.argv[1])
        if params:
            try:
                RadioHTTPServer(params).serve_forever()
            except KeyboardInterrupt:
                pass
        else:
            sys.stderr.write('Error initializing from ini file\n')
            sys.exit(2)
    else:
        sys.stderr.write('Usage: %s <path to param ini file>\n'
                         % sys.argv[0])
        sys.exit(1)
    sys.exit(0)

if __name__ == '__main__':
   main_fn()
