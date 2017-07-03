==========
SuckleSync
==========
Sucklesync allows you to subscribe to one or more remote directories,
using rsync to synchronize the remote directories locally. It only
synchronizes directories that don't contain actively changing files.
This prevents synchronizing corrupt files and then re-synchronizing
them later when the remote changes are complete.

Sucklesync (currently) requires Python 2.

============
Installation
============
Run:
  pip install sucklesync

Or:
  sudo ./setup.py install

To configure sucklesync, save the configuration template to any of
the following paths, as preferred for your local configuration:
 * /etc/sucklesync.cfg
 * /usr/local/etc/sucklesync.cfg
 * ~/.sucklesync.cfg
 * ./sucklesync.cfg

=============
Configuration
=============
In /usr/local/etc/sucklesync.cfg or /etc/sucklesync.cfg define the
following sections. (Use template.sucklesync.cfg from this package
for a quick starting place.)

- [Sucklepaths]

Define one or more sucklepath pairs. Every pair requires a matching
source and destination, and numbers must be incremented sequentally.
Sucklesync currently requires the source to be remote, and the
destination to be local. For example:

	[Sucklepaths]
	source1 = /the/remote/path
	destination1 = /the/local/path
	source2 = /another/remote/path
	destination2 = /another/local/path

- [Local]

Sucklesync needs to know the full path to rsync and ssh on your
local server. It also currently assumes the "-a --verbose" flags
on rsync, it is not recommended you change this or things will
very likely break.

By default, rsync will delete local files that don't exist on the
remote server. To disable this feature, set "delete = no".

	[Local]
	rsync = /usr/bin/rsync
	rsync_flags = -a --delete
	ssh = /usr/bin/ssh
	ssh_flags = -C
	delete = yes

- [Remote]

Sucklesync needs to know the full path to find on your remote
server. Don't change the find_flags unless you're certain your
new flags will work with Sucklesync's assumptions (learned through
reading the code). By default, it builds a list of directories
that have not been modified in the past 5 minutes, and syncs them
one at a time.

Key-based ssh access is currently required to the remote host
specified. The ssh_timeout is specified in seconds.

	[Remote]
	find = /usr/bin/find
	find_flags = ! -mmin -5 -print
	hostname = example.com
	ssh_timeout = 5

- [Logging]

As Sucklesync runs as a daemon, it writes to a log and maintains a
pidfile to track the running process. Whatever user you run
sucklesync as will require read-write access to both files.

	[Logging]
	filename = /var/log/sucklesync/sucklesync.log
	pidfile = /var/run/sucklesync.pid
	level = WARNING

- [Email]

TBD: Not yet implemented.

	[Email]
	enabled = yes
	; Email addresses can optionally include a human readable name, just addresses,
	; or a combination. For example:
	; NAME ONE | ADDRESS1, NAME TWO | ADDRESS2, ADDRESS3
	to = User 1|user1@example.com, User 2|user2@example.com, user3@example.com
	from = SuckleSync|sucklesync@example.com
	smtp_hostname = example.com
	smtp_port = 587
	; Supported smtp modes are: default, ssl, tls
	smtp_mode = tls
	smtp_username = username
	smtp_password = password

- [Frequency]

Sucklesync polls a remote server looking for new files to sync that haven't
changed recently. If it hasn't found new files recently, it polls less
frequently. If it has found new files recently, it polls more frequently.

It will poll at least minimum_poll_delay seconds for new files when it's
not actively syncing. If no new files are found, it will increment the
poll_delay by minimum_poll_delay until it reaches the maximum_poll_delay.

	[Frequency]
	minimum_poll_delay = 60
	maximum_poll_delay = 900
