""" 
    SuckleSync - A wrapper around rsync to simplify continuous synchronization of remote directories.
"""

import logging
from easyprocess import EasyProcess

import sucklesync
from utils import debug
from utils import email
from config import config

sucklesync_instance = None

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
        self.frequency = {}
        self.mail = {}

    def _load_debugger(self):
        import logging.handlers

        try:
            self.logger = logging.getLogger(__name__)
            self.debugger = debug.Debugger(self.verbose, self.logger, debug.PRINT)
            # start by logging to stdout
            self.debugger.handler = logging.StreamHandler()
            formatter = logging.Formatter(DEFAULT_LOGFORMAT)
            self.debugger.handler.setFormatter(formatter)
            self.logger.addHandler(self.debugger.handler)

        except Exception as e:
            self.debugger.dump_exception("_load_debugger() exception")

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
            self.debugger.dump_exception("_enable_debugger() exception")

    def _load_configuration(self):
        try:
            from shlex import quote as cmd_quote
        except ImportError:
            from pipes import quote as cmd_quote

        self.configuration = config.Config(self.debugger)

        # load binary paths and associated flags
        self.local["rsync"] = cmd_quote(self.configuration.GetText("Local", "rsync", "/usr/bin/rsync"))
        self.local["rsync_flags"] = self.configuration.GetText("Local", "rsync_flags", "-aP")
        self.local["ssh"] = cmd_quote(self.configuration.GetText("Local", "ssh", "/usr/bin/ssh"))
        self.local["ssh_flags"] = self.configuration.GetText("Local", "ssh_flags", "-C")
        self.local["delete"] = self.configuration.GetBoolean("Local", "delete")
        self.remote["find"] = cmd_quote(self.configuration.GetText("Remote", "find", "/usr/bin/find"))
        self.remote["find_flags"] = cmd_quote(self.configuration.GetText("Remote", "find_flags", "-mmin -10 -print"))

        # load SSH configuration
        self.remote["hostname"] = self.configuration.GetText("Remote", "hostname")
        self.remote["port"] = self.configuration.GetInt("Remote", "port", 22, False)
        self.remote["ssh_timeout"] = self.configuration.GetInt("Remote", "ssh_timeout", 5, False)
        self.remote["username"] = self.configuration.GetText("Remote", "username", False, False)

        # load paths that will be suckle-synced
        self.paths = self.configuration.GetItemPairs("Sucklepaths", ["source", "destination"])

        # load logging preferences
        self.logging["filename"] = self.configuration.GetText("Logging", "filename", DEFAULT_LOGFILE, False)
        self.logging["pidfile"] = self.configuration.GetText("Logging", "pidfile", DEFAULT_PIDFILE, False)
        self.logging["level"] = self.configuration.GetText("Logging", "level", DEFAULT_LOGLEVEL, False)

        # load frequency preferences
        self.frequency["minimum_poll_delay"] = self.configuration.GetInt("Frequency", "minimum_poll_delay", 60, False)
        self.frequency["maximum_poll_delay"] = self.configuration.GetInt("Frequency", "maximum_poll_delay", 60, False)

        # load email preferences
        self.mail["enabled"] = self.configuration.GetBoolean("Email", "enabled", False, False)
        if self.mail["enabled"]:
            self.mail["to"] = self.configuration.GetEmailList("Email", "to", None)
            self.mail["from"] = self.configuration.GetEmailList("Email", "from", None)
            self.mail["hostname"] = self.configuration.GetText("Email", "smtp_hostname", None)
            self.mail["port"] = self.configuration.GetInt("Email", "smtp_port", 587)
            self.mail["mode"] = self.configuration.GetText("Email", "smtp_mode", None)
            self.mail["username"] = self.configuration.GetText("Email", "smtp_username", None)
            self.mail["password"] = self.configuration.GetText("Email", "smtp_password", None)

    # Determine if pid in pidfile is a running process.
    def is_running(self):
        import os
        import errno

        running = False
        if self.logging["pidfile"]:
            if os.path.isfile(self.logging["pidfile"]):
                f = open(self.logging["pidfile"])
                pid = int(f.readline())
                f.close()
                if pid > 0:
                    self.debugger.info("Found pidfile %s, contained pid %d", (self.logging["pidfile"], pid))
                    try:
                        os.kill(pid, 0)
                    except OSError as e:
                        if e.errno == errno.EPERM:
                            running = pid
                    else:
                        running = pid
        return running

def start(ss):
    ss.debugger.warning("starting sucklesync")
    sucklesync.sucklesync_instance = ss

    # test that we can write to the log
    try:
        with open(ss.logging["filename"], "w"):
            ss.debugger.info("successfully writing to logfile")
    except IOError:
        ss.debugger.critical("failed to write to logfile: %s", (ss.logging["filename"],))

    # test rsync -- run a NOP, only success returns
    command = ss.local["rsync"] + " -qh"
    _rsync(command)
    ss.debugger.info("successfully tested local rsync: %s", (command,))

    # test ssh -- run a NOP find, only success returns
    command = ss.local["ssh"] + " " + ss.remote["hostname"] + " " + ss.local["ssh_flags"] + " " + ss.remote["find"] + " " + ss.remote["find"] + " -type d"
    _ssh(command, True)
    ss.debugger.info("successfully tested ssh to remote server: %s", (command,))

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
            ss.debugger.logToFile()
            daemon = daemonize.Daemonize(app="sucklesync", pid=ss.logging["pidfile"], action=sucklesync, keep_fds=[ss.debugger.handler.stream.fileno()], logger=ss.logger, verbose=True)
            daemon.start()
        except Exception as e:
            ss.debugger.critical("Failed to daemonize: %s, exiting", (e,))
    else:
        sucklesync()

def stop(ss, must_be_running = True):
    import os
    import signal
    import errno

    pid = ss.is_running()

    if not pid:
        if must_be_running:
            ss.debugger.critical("Sucklesync is not running.")
        else:
            ss.debugger.info("Sucklesync is not running.")
    else:
        ss.debugger.warning("Stopping sucklesync...")

        try:
            os.kill(pid, signal.SIGTERM)
        except OSError as e:
            if e.errno == errno.EPERM:
                ss.debugger.critical("Failed (perhaps try with sudo): %s", (e))
            else:
                ss.debugger.critical("Failed: %s", (e,))

def restart(ss):
    import time

    stop(ss, False)
    running = ss.is_running()
    loops = 0
    while running:
        loops += 1
        if (loops > 15):
            ss.debugger.critical("Failed to stop sucklesync.")
        time.sleep(0.2)
        running = ss.is_running()
    start(ss)

def status(ss):
    pid = ss.is_running()
    if pid:
        ss.debugger.warning("Sucklesync is running with pid %d", (pid,))
    else:
        ss.debugger.warning("Sucklesync is not running.")

def _ssh(command, fail_on_error = False):
    ss = sucklesync.sucklesync_instance
    ss.debugger.debug("_ssh: %s", (command,))

    try:
        output = EasyProcess(command).call(timeout=ss.remote["ssh_timeout"])
        if output.timeout_happened:
            ss.debugger.error("failed to ssh to remote server, took longer than %d seconds. Failed command: %s", (ss.remote["timeout"], command))
        elif output.return_code:
            ss.debugger.error("ssh to remote server returned error code (%d), error (%s). Failed command: %s", (output.return_code, output.stderr, command))
        elif output.oserror:
            ss.debugger.error("failed to ssh to remote server, error (%s). Failed command: %s", (output.oserror, command))

        return output.stdout.splitlines()

    except Exception as e:
        ss.debugger.error("_ssh exception, failed command: %s", (command,))
        ss.debugger.dump_exception("_ssh() exception")

def _rsync(command):
    ss = sucklesync.sucklesync_instance
    ss.debugger.debug("_rsync: %s", (command,))

    try:
        output = EasyProcess(command).call()
        if output.return_code:
            ss.debugger.error("rsync returned error code (%d), error (%s). Failed command: %s", (output.return_code, output.stderr, command))
        elif output.oserror:
            ss.debugger.error("rsync failed, error (%s). Failed command: %s", (output.oserror, command))

        return output.stdout.splitlines()

    except Exception as e:
        ss.debugger.error("_rsync exception, failed command: %s", (command,))
        ss.debugger.dump_exception("_rsync() exception")

def _cleanup(source, key):
    import re

    ss = sucklesync.sucklesync_instance
    ss.debugger.debug("_cleanup: %s (%d)", (source, key))

    try:
        deleted = []
        if ss.local["delete"]:
            # Delete files/directories that were deleted on the source.
            cleanup = ss.local["rsync"] + " --recursive --delete --ignore-existing --existing --prune-empty-dirs --verbose"
            cleanup += " " + ss.remote["hostname"] + ':"' + source + '/"'
            cleanup += " " + ss.paths["destination"][key]
            output = _rsync(cleanup)

            prefix = True
            for line in output:
                if prefix:
                    if re.search("receiving file list", line):
                        prefix = False
                    else:
                        ss.debugger.debug("PREFIX: %s", (line,))
                else:
                    try:
                        if re.search("sent (.*) bytes", line):
                            # All done with the information we care about.
                            break
                        ss.debugger.debug(" %s ...", (line,))
                        deleted.append(line)
                    except:
                        # This shouldn't happen during file deletion.
                        continue
        else:
            ss.debugger.debug("local delete disabled")

        return deleted

    except Exception as e:
        ss.debugger.dump_exception("_cleanup() exception")

def sucklesync():
    from utils import simple_timer
    import re
    import time

    ss = sucklesync.sucklesync_instance

    run = True
    timer = None

    sleep_delay = 0

    if ss.mail["enabled"]:
        ss.mail["email"] = email.Email(ss)

    try:
        while run:
            if timer:
                # When no files are being transferred, sleep for greater and greater
                # periods of time, up to a maximum.
                if (timer.elapsed() < ss.frequency["minimum_poll_delay"]):
                    if sleep_delay < ss.frequency["maximum_poll_delay"]:
                        sleep_delay += ss.frequency["minimum_poll_delay"]
                    if sleep_delay > ss.frequency["maximum_poll_delay"]:
                        sleep_delay = ss.frequency["maximum_poll_delay"]
                    ss.debugger.debug("sleeping %d seconds", (sleep_delay,))
                    time.sleep(sleep_delay)
                else:
                    ss.debugger.info("last loop took %d seconds, resetting sleep_delay", (timer.elapsed(),))
                    sleep_delay = 0
            timer = simple_timer.Timer()

            key = 0
            for source in ss.paths["source"]:
                # Build a list of files to transfer.
                ss.debugger.info("polling %s ...", (source,))
                initial_queue = []
                queue = []
                transferred = False
                include_flags = "! " + ss.remote["find_flags"]
                command = ss.local["ssh"] + " " + ss.remote["hostname"] + " " + ss.local["ssh_flags"] + " " + ss.remote["find"] + " " + source + " " + include_flags
                include = _ssh(command)
                command = ss.local["ssh"] + " " + ss.remote["hostname"] + " " + ss.local["ssh_flags"] + " " + ss.remote["find"] + " " + source + " " + ss.remote["find_flags"]
                exclude = _ssh(command)

                # We may be having connectivity issues, try again later.
                if not include:
                    break

                for line in include:
                    subpath = re.sub(r"^" + re.escape(source), "", line)
                    try:
                        directory = subpath.split("/")[1]
                        if directory[0] == ".":
                            continue
                        elif directory not in initial_queue:
                            ss.debugger.info(" queueing %s ...", (directory,))
                            initial_queue.append(directory)
                    except:
                        continue

                if exclude:
                    exclude_from_queue = []
                    for line in exclude:
                        subpath = re.sub(r"^" + re.escape(source), "", line)
                        try:
                            directory = subpath.split("/")[1]
                            if directory[0] == ".":
                                continue
                            elif directory not in exclude_from_queue:
                                exclude_from_queue.append(directory)
                        except:
                            continue
                    for line in initial_queue:
                        if line in exclude_from_queue:
                            ss.debugger.info(" excluding from queue %s ...", (directory,))
                        else:
                            queue.append(line)
                else:
                    queue = initial_queue

                # Now rsync the list one by one, allowing for useful emails.
                subkey = 0
                for directory in queue:
                    # Sync queued list of directories.
                    sync = ss.local["rsync"] + " " + ss.local["rsync_flags"]
                    sync += " " + ss.remote["hostname"] + ':"' + source + "/"
                    sync +=  re.escape(directory) + '"'
                    sync += " " + ss.paths["destination"][key]
                    output = _rsync(sync)

                    synced = []
                    transferred = False
                    mail_text = "Successfully synchronized:\n"
                    mail_html = "<html><title>successfully synchronized</title><body><p>Successfully synchronized:</p><ul>"
                    prefix = True
                    suffix = False
                    for line in output:
                        if prefix:
                            if re.search("receiving(.*)file list", line):
                                prefix = False
                        elif suffix:
                            mail_text += line
                            mail_html += "<br />" + line
                            ss.debugger.debug("stats: %s", (line,))
                        else:
                            try:
                                if re.search("sent (.*) bytes", line):
                                    suffix = True
                                    mail_text += "\n" + line
                                    mail_html += "</ul><p>" + line
                                    continue
                                directory_synced = line.split("/")[0]
                                if directory_synced and directory_synced not in synced:
                                    transferred = True
                                    mail_text += " - " + directory_synced + "\n"
                                    mail_html += "<li>" + directory_synced
                                    ss.debugger.debug(" synced %s ...", (directory_synced,))
                                    synced.append(directory_synced)
                            except:
                                # rsync suffix starts with a blank line
                                suffix = True
                                continue

                    if transferred:
                        mail_html += "</p>"

                    # List up to three queued items.
                    in_list = False
                    if len(queue) > subkey + 1:
                        in_list = True
                        mail_text += "Next download:\n - " + queue[subkey + 1] + "\n"
                        mail_html += "<hr /><p>Next download:<ul><li>" + queue[subkey + 1] + "</li>"
                        ss.debugger.debug(" next up %s ... [%d of %d]", (queue[subkey + 1], len(queue), subkey))
                    if in_list and len(queue) > subkey + 2:
                        mail_text += queue[subkey + 2] + "\n"
                        mail_html += "<li>" + queue[subkey + 2] + "</li>"
                    if in_list and len(queue) > subkey + 3:
                        mail_text += queue[subkey + 3] + "\n"
                        mail_html += "<li>" + queue[subkey + 3] + "</li>"
                    if in_list:
                        mail_html += "</ul></p>"

                    if transferred:
                        mail_html += "</body></html>"
                        ss.mail["email"].MailSend("[sucklesync] file copied", mail_text, mail_html)
                        _cleanup(source, key)
                    subkey += 1
                if not transferred:
                    _cleanup(source, key)
                key += 1

    except Exception as e:
        ss.debugger.dump_exception("sucklesync() exception")
