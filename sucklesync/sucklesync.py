""" 
    SuckleSync - A wrapper around rsync to simplify continuous synchronization of remote directories.
"""

import logging
from easyprocess import EasyProcess

import sucklesync
from utils import debug
from config import config

sucklesync_instance = None

__version__ = "0.1"

DEFAULT_CONFIG    = ["/etc/sucklesync.cfg", "/usr/local/etc/sucklesync.cfg", "~/.sucklesync.cfg", "./sucklesync.cfg"]
DEFAULT_LOGLEVEL  = logging.WARNING
DEFAULT_LOGFILE   = "/var/log/sucklesync/sucklesync.log"
DEFAULT_LOGFORMAT = "%(asctime)s [%(levelname)s/%(processName)s] %(message)s"
DEFAULT_PIDFILE   = "/var/run/sucklesync.pid"

class SuckleSync:
    def __init__(self, config):
        self.config = config
        self.local = {}
        self.remote = {}
        self.paths = []
        self.logging = {}
        self.mail = {}
        self.ssh = {}

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
        try:
            from shlex import quote as cmd_quote
        except ImportError:
            from pipes import quote as cmd_quote

        self.configuration = config.Config(self.debugger)

        # load binary paths and associated flags
        self.local["rsync"] = cmd_quote(self.configuration.GetText("Local", "rsync", "/usr/bin/rsync"))
        self.local["rsync_flags"] = cmd_quote(self.configuration.GetText("Local", "rsync_flags", "-aP"))
        self.local["ssh"] = cmd_quote(self.configuration.GetText("Local", "ssh", "/usr/bin/ssh"))
        self.local["ssh_flags"] = cmd_quote(self.configuration.GetText("Local", "ssh_flags", "-C"))
        self.remote["find"] = cmd_quote(self.configuration.GetText("Remote", "find", "/usr/bin/find"))
        self.remote["find_flags"] = cmd_quote(self.configuration.GetText("Remote", "find_flags", "-mmin -5 -print"))

        # load SSH configuration
        self.remote["hostname"] = self.configuration.GetText("Remote", "hostname")
        self.remote["port"] = self.configuration.GetInt("Remote", "port", 22, False)
        self.remote["timeout"] = self.configuration.GetInt("Remote", "timeout", 5, False)
        self.remote["username"] = self.configuration.GetText("Remote", "username", False, False)

        # load paths that will be suckle-synced
        self.paths = self.configuration.GetItemPairs("Sucklepaths", ["source", "destination"])

        # load logging preferences
        self.logging["filename"] = self.configuration.GetText("Logging", "filename", DEFAULT_LOGFILE, False)
        self.logging["pidfile"] = self.configuration.GetText("Logging", "pidfile", DEFAULT_PIDFILE, False)
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
    import sys
    import os
    import subprocess

    ss.debugger.warning("starting sucklesync")
    sucklesync.sucklesync_instance = ss

    # test that we can write to the log
    try:
        with open(ss.logging["filename"], "w"):
            ss.debugger.info("successfully writing to logfile")
    except IOError:
        ss.debugger.critical("failed to write to logfile: %s", (ss.logging["filename"],))

    # test rsync -- run a NOP
    try:
        subprocess.call([ss.local["rsync"], "-qh"])
        ss.debugger.info("successfully tested local rsync: %s -qh", (ss.local["rsync"],))
    except OSError as e:
        if e.errno == os.errno.ENOENT:
            ss.debugger.critical("failed to find local rsync: %s", (ss.local["rsync"],))
        else:
            ss.debugger.critical("failed to execute local rsync: %s -qh", (ss.local["rsync"],))

    # test ssh -- run a NOP find
    command = ss.local["ssh"] + " " + ss.remote["hostname"] + " " + ss.local["ssh_flags"] + " " + ss.remote["find"] + " " + ss.remote["find"] + " -type d"
    try:
        output = EasyProcess(command).call(timeout=ss.remote["timeout"])
        if output.timeout_happened:
            ss.debugger.critical("failed to ssh to remote server, took longer than %d seconds. Command tried: %s", (ss.remote["timeout"], command))
        elif output.return_code:
            ss.debugger.critical("ssh to remote server returned error code (%d), error (%s). Command tried: %s", (output.return_code, output.stderr, command))
        elif output.oserror:
            ss.debugger.critical("failed to ssh to remote server, error (%s). Command tried: %s", (output.oserror, command))
        else:
            ss.debugger.info("successfully tested ssh to remote server: %s", (command,))
    except Exception as e:
        ss.debugger.critical("failed to ssh to remote server, unexpected error (%s). Command tried: %s", (e, command))

    if ss.daemonize:
        try:
            import daemonize
        except Exception as e:
            ss.debugger.error("fatal exception: %s", (e,))
            ss.debugger.critical("failed to import daemonize (as user %s), try 'pip install daemonize', exiting", (ss.debugger.whoami()))
        ss.debugger.info("successfully imported daemonize")

        # test that we can write to the pidfile
        try:
            with open(ss.logging["pidfile"], "w"):
                ss.debugger.info("successfully writing to pidfile")
        except IOError:
            ss.debugger.critical("failed to write to pidfile: %s", (ss.logging["pidfile"],))

        ss.debugger.warning("daemonizing, output redirected to log file: %s", (ss.logging["filename"],))

        try:
            daemon = daemonize.Daemonize(app="sucklesync", pid=ss.logging["pidfile"], action=sucklesync, keep_fds=[ss.debugger.handler.stream.fileno()], logger=ss.logger, verbose=True)
            daemon.start()
        except Exception as e:
            ss.debugger.critical("Failed to daemonize: %s, exiting", (e,))
    else:
        sucklesync()

def stop(ss):
    ss.debugger.warning("stopping sucklesync")

def restart(ss):
    ss.debugger.warning("restarting sucklesync")

def status(ss):
    print "sucklesync status ..."

def sucklesync():
    ss = sucklesync.sucklesync_instance

    ss.debugger.warning("daemonized")

    for source in ss.paths["source"]:
        ss.debugger.warning("%s", (source,))

#    # test ssh -- run a NOP find
#    command = ss.local["ssh"] + " " + ss.remote["hostname"] + " " + ss.local["ssh_flags"] + " " + ss.remote["find"] + " " + ss.remote["find"] + " -type d"
#    try:
#        output = EasyProcess(command).call(timeout=ss.remote["timeout"])
#        if output.timeout_happened:
#            ss.debugger.critical("failed to ssh to remote server, took longer than %d seconds. Command tried: %s", (ss.remote["timeout"], command))
#        elif output.return_code:
#            ss.debugger.critical("ssh to remote server returned error code (%d), error (%s). Command tried: %s", (output.return_code, output.stderr, command))
#        elif output.oserror:
#            ss.debugger.critical("failed to ssh to remote server, error (%s). Command tried: %s", (output.oserror, command))
#        else:
#            ss.debugger.info("successfully tested ssh to remote server: %s", (command,))
#    except Exception as e:
#        ss.debugger.critical("failed to ssh to remote server, unexpected error (%s). Command tried: %s", (e, command))
