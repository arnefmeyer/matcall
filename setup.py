#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Author: Arne F. Meyer <arne.f.meyer@gmail.com>
# License: GPLv2

from os import path
from distutils.core import setup


def read(fname):
    return open(path.join(path.dirname(__file__), fname)).read()


setup(name='matcall',
      version='0.1',
      description='Call Matlab code from Python',
      author='Arne F Meyer',
      author_email='arne.f.meyer@gmail.com',
      license='GPLv2',
      url='https://github.com/arnefmeyer/matcall',
      packages=['matcall'],
      long_description=read('README.md'),
      )
