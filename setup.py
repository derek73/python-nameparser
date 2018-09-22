#!/usr/bin/env python
try:
  from setuptools import setup
except ImportError:
  from distutils.core import setup
import nameparser
import os

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

README = read('README.rst')

setup(name='nameparser',
      packages      = ['nameparser','nameparser.config'],
      description   = 'A simple Python module for parsing human names into their individual components.',
      long_description = README,
      version       = nameparser.__version__,
      url           = nameparser.__url__,
      author        = nameparser.__author__,
      author_email  = nameparser.__author_email__,
      license       = nameparser.__license__,
      keywords      = ['names','parser'],
      classifiers = [
          'Intended Audience :: Developers',
          'Operating System :: OS Independent',
          "License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)",
          'Programming Language :: Python',
          'Programming Language :: Python :: 2',
          'Programming Language :: Python :: 3',
          'Development Status :: 5 - Production/Stable',
          'Natural Language :: English',
          "Topic :: Software Development :: Libraries :: Python Modules",
          'Topic :: Text Processing :: Linguistic',
      ]
      )
