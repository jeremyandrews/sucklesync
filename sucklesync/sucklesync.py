""" 
    SuckleSync - A wrapper around rsync to simplify continuous synchronization of remote directories.
"""

import logging

from utils import debug
from config import config

__version__ = "0.1"

DEFAULT_CONFIG    = ["/etc/sucklesync.cfg", "/usr/local/etc/sucklesync.cfg", "~/.sucklesync.cfg", "./sucklesync.cfg"]
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

        try:
            self.logger = logging.getLogger(__name__)
            self.debugger = debug.Debugger(self.verbose, self.logger, debug.FILE)
            # start by logging to stdout
            self.debugger.handler = logging.StreamHandler()
            formatter = logging.Formatter(DEFAULT_LOGFORMAT)
            self.debugger.handler.setFormatter(formatter)
            self.logger.addHandler(self.debugger.handler)

        except Exception as e:
            self.debugger.dump_exception("_load_debugger() caught exception")

    def _enable_debugger(self):
        import logging.handlers

        try:
            if self.daemonize:
                self.debugger.handler = logging.FileHandler(self.logging["filename"])
            else:
                self.debugger.handler = logging.StreamHandler()
            formatter = logging.Formatter(DEFAULT_LOGFORMAT)
            self.debugger.handler.setFormatter(formatter)
            self.logger.addHandler(self.debugger.handler)
            self.logger.setLevel(self.logging["level"])
        except Exception as e:
            self.debugger.dump_exception("_enable_debugger() caught exception")

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
        self.logging["filename"] = self.configuration.GetText("Logging", "filename", DEFAULT_LOGFILE, False)
        self.logging["pidfile"] = self.configuration.GetText("Logging", "filename", DEFAULT_PIDFILE, False)
        self.logging["level"] = self.configuration.GetText("Logging", "level", DEFAULT_LOGLEVEL, False)

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

def start(ss):
    ss.debugger.warning("starting sucklesync")

def stop(ss):
    ss.debugger.warning("stopping sucklesync")

def restart(ss):
    ss.debugger.warning("restarting sucklesync")

def status(ss):
    print "sucklesync status ..."
