#!/usr/bin/env python

# This script will start HTTP server on specified port and will listen for any requests
# to further send messages via Jabber server using sleekxmpp third party module.
# Example of server start: xmppsenderd.py
# Use settings.py to define defaults
# Use it with: curl "http://localhost:8100/send?msg=tratatatata%20lalalala"
# or: curl "http://localhost:8100/send?to=username@domain.com&msg=tratatatata%20lalalala"

import os
import sys
import sleekxmpp
import logging
import urlparse
import getpass
from optparse import OptionParser
from httplib import OK, NOT_FOUND, FORBIDDEN, CONFLICT, INTERNAL_SERVER_ERROR
from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler

# Setup logging. Raise to debug to find out errors
#loglevel = logging.DEBUG
loglevel = logging.INFO
logging.basicConfig(level=loglevel, format='%(levelname)-8s %(message)s')


class SendMsgBot(sleekxmpp.ClientXMPP):
    """
    A basic SleekXMPP bot that will log in, send a message,
    and then log out.
    """

    def __init__(self, jid, password, recipient, message):
        sleekxmpp.ClientXMPP.__init__(self, jid, password)

        # The message we wish to send, and the JID that
        # will receive it.
        self.recipient = recipient
        self.msg = message

        # The session_start event will be triggered when
        # the bot establishes its connection with the server
        # and the XML streams are ready for use. We want to
        # listen for this event so that we we can initialize
        # our roster.
        self.add_event_handler("session_start", self.start)

    def start(self, event):
        """
        Process the session_start event.

        Typical actions for the session_start event are
        requesting the roster and broadcasting an initial
        presence stanza.

        Arguments:
            event -- An empty dictionary. The session_start
                     event does not provide any additional
                     data.
        """
        self.send_presence()
        self.get_roster()

        self.send_message(mto=self.recipient,
                          mbody=self.msg,
                          mtype='chat')

        # Using wait=True ensures that the send queue will be
        # emptied before ending the session.
        self.disconnect(wait=True)


class DaemonRequestHandler(BaseHTTPRequestHandler):
    """
    Request handler to do all the work.

    Parses the request to send the message or anything else
    """

    def do_GET(self):
        # Parse body
        self.body = urlparse.urlparse(self.path)
        self.passedparams = urlparse.parse_qs(self.body.query)

        if self.body.path == "/send":
            try:
                self.to = self.passedparams["to"][0]
            except:
                self.to = to
            self.message = self.passedparams["msg"][0]
            # Setup the EchoBot and register plugins.
            # Note that while plugins may have interdependencies,
            # the order in which you register them does not matter.
            self.xmpp = SendMsgBot(jid, password, self.to, self.message)
            self.xmpp.register_plugin('xep_0030')  # Service Discovery
            self.xmpp.register_plugin('xep_0199')  # XMPP Ping

            # If you are working with an OpenFire server, you may need
            # to adjust the SSL version used:
            # xmpp.ssl_version = ssl.PROTOCOL_SSLv3

            # If you want to verify the SSL certificates offered by a server:
            # xmpp.ca_certs = "path/to/ca/cert"

            # Connect to the XMPP server and start processing XMPP stanzas.
            if self.xmpp.connect():
                # If you do not have the dnspython library installed,
                # you will need to manually specify the name of the server
                # if it does not match the one in the JID.
                # For example, to use Google Talk you would need to use:
                #
                # if xmpp.connect(('talk.google.com', 5222)):
                #     ...
                self.xmpp.process(block=True)
                logging.info("Done sending the message")
                self.send_response(OK)
            else:
                print("Unable to connect.")
                self.send_response(INTERNAL_SERVER_ERROR)
        else:
            self.send_response(NOT_FOUND)
            return

    def _send_response(self, response, message):
        self.send_response(response)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(message)


def daemon_run(port, server_class=HTTPServer,
               handler_class=DaemonRequestHandler):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    try:
        logging.info("Starting daemon on port %s, "
                     "%s JID will be used to send messages" % (port, jid))
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.server_close()
        pass

if __name__ == '__main__':

    # Import config with variables.
    # Don't put password there, we'll ask for it anyway, but one can always change the code
    parser = OptionParser()
    parser.add_option('-p', '--port', type="int", dest='port', default=8100,
                      help='Service will listen on a port [default %default]')
    parser.add_option('-j', '--jid', dest='jid', default=None,
                      help='The bot JID, e.g. username@domain.com/bot [default %default]')
    parser.add_option('-t', '--to', dest='to', default=None,
                      help='The recipient JID, e.g. username@domain.com [default %default]')
    options, unused_args = parser.parse_args()

    # FIX THIS: ugly
    try:
        import settings
    except:
        pass

    if options.jid:
        jid = options.jid
    else:
        jid = settings.jid

    if options.port:
        port = options.port
    else:
        port = settings.port

    # By default send to this JID. If missing in settings.py - will be send to one from request
    if options.to:
        to = options.to
    else:
        to = settings.to

    password = getpass.getpass("Please type in password for JID %s:" % jid)
    
    # Start daemon, terminate with CTRL-C or put into background
    daemon_run(port)
