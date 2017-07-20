#!/usr/bin/env python2

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

setup(name="sucklesync",
      version="0.3.8",
      author="Jeremy Andrews",
      author_email="jeremy@tag1consulting.com",
      maintainer="Jeremy Andrews",
      maintainer_email="jeremy@tag1consulting.com",
      url="https://github.com/jeremyandrews/sucklesync",
      packages=["sucklesync", "sucklesync.config", "sucklesync.utils"],
      license="2-clause BSD",
      description="A wrapper around rsync to simplify continuous sychnronization of remote directories",
      long_description=open("README.txt").read(),
      scripts=["bin/sucklesync"],
      download_url = "https://github.com/jeremyandrews/sucklesync/archive/v0.3.8-alpha.tar.gz",
      include_package_data=True,
      install_requires=["daemonize>=2.4.7", "pyzmail", "easyprocess"],
     )
