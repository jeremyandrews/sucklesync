==========
SuckleSync
==========
Sucklesync allows you to subscribe to remote directories, using rsync to
synchronize the directories locally. It only synchronizes files that
aren't actively changing.

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
