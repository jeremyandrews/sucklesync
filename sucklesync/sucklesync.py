""" 
    SuckleSync - A wrapper around rsync to simplify continuous synchronization of remote directories.
"""

import logging

from utils import debug
from config import config

__version__ = "0.1"

DEFAULT_CONFIG    = ["/etc/sucklesync.cfg", "/usr/local/etc/sucklesync.cfg", "~/.sucklesync.cfg", "./sucklesync.cfg"]
DEFAULT_USER      = "daemon"
DEFAULT_GROUP     = "daemon"
DEFAULT_LOGLEVEL  = logging.WARNING
DEFAULT_LOGFILE   = "/var/log/sucklesync/sucklesync.log"
DEFAULT_LOGFORMAT = "%(asctime)s [%(levelname)s/%(processName)s] %(message)s"
DEFAULT_PIDFILE   = "/var/run/sucklesync.pid"

class SuckleSync:
    def __init__(self, config):
        self.config = config
        self.binaries = {}
        self.flags = {}
        self.paths = []
        self.logging = {}
        self.mail = {}

    def _load_debugger(self):
        import logging.handlers

        logger = logging.getLogger(__name__)
        formatter = logging.Formatter(DEFAULT_LOGFORMAT)
        self.debugger = debug.Debugger(self.verbose, logger, debug.FILE)

    def _load_configuration(self):
        self.configuration = config.Config(self.debugger)

        # load binary paths
        self.binaries["local_rsync"] = self.configuration.GetText("Binaries", "local_rsync", "/usr/bin/rsync")
        self.binaries["remote_find"] = self.configuration.GetText("Binaries", "remote_find", "/usr/bin/find")

        # load flags used when launching binaries
        self.flags["rsync_flags"] = self.configuration.GetText("Flags", "rsync_flags", "-aP")
        self.flags["find_flags"] = self.configuration.GetText("Flags", "find_flags", "-mmin -5 -print")

        # load paths that will be suckle-synced
        self.paths = self.configuration.GetItemPairs("Sucklepaths", ["source", "destination"])

        # load logging preferences
        self.logging["filename"] = self.configuration.GetText("Logging", "filename", "/var/log/sucklesync/sucklesync.log", False)
        self.logging["pidfile"] = self.configuration.GetText("Logging", "filename", "/var/run/sucklesync.pid", False)
        self.logging["level"] = self.configuration.GetText("Logging", "level", "WARNING", False)

        # load email preferences
        self.mail["enabled"] = self.configuration.GetBoolean("Email", "enabled", False, False)
        if self.mail["enabled"]:
            required = True
        else:
            required = False
        self.mail["to"] = self.configuration.GetEmailList("Email", "to", None, required)
        self.mail["from"] = self.configuration.GetEmailList("Email", "from", None, required)
        self.mail["hostname"] = self.configuration.GetInt("Email", "smtp_hostname", None, required)
        self.mail["port"] = self.configuration.GetInt("Email", "smtp_port", 587, required)
        self.mail["mode"] = self.configuration.GetText("Email", "smtp_mode", None, required)
        self.mail["username"] = self.configuration.GetText("Email", "smtp_username", None, required)
        self.mail["password"] = self.configuration.GetText("Email", "smtp_password", None, required)

        print self.binaries, self.paths, self.flags, self.mail

def start(ss):
    print "starting sucklesync ..."

def stop(ss):
    print "stopping sucklesync ..."

def restart(ss):
    print "restarting sucklesync ..."

def status(ss):
    print "sucklesync status ..."
