#!/usr/bin/env python

import sys

from setuptools import setup, find_packages

from dgm.main import dgm_version


readme = open('README.textile').read()

v = dgm_version
long_description = """
To find out what's new in this version of dgm, please see `the changelog
<http://www.edgenius.com/dgm/%s/changelog.html>`_.

----

%s

----

For more information, please see the Edgenius website or execute ``dgm -h``.
""" % (v, readme)

setup(
    name='dgm',
    version=dgm_version,
    description='dgm is a simple, Pythonic tool for distribute file management by git.',
    long_description=long_description,
    author='Dapeng Ni',
    author_email='dapeng.ni@edgenius.com',
    url='http://www.edgenius.com',
    packages=find_packages(),
    install_requires=[],
    entry_points={
        'console_scripts': [
            'dgm = dgm.main:main',
        ]
    },
    classifiers=[
          'Development Status :: 0 - Alpha',
          'Environment :: Console',
          'Intended Audience :: Developers',
          'Intended Audience :: System Administrators',
          'License :: OSI Approved :: BSD License',
          'Operating System :: MacOS :: MacOS X',
          'Operating System :: Unix',
          'Operating System :: POSIX',
          'Programming Language :: Python',
          'Programming Language :: Python :: 2.7',
          'Topic :: Software Development',
          'Topic :: Software Development :: Build Tools',
          'Topic :: Software Development :: Libraries',
          'Topic :: Software Development :: Libraries :: Python Modules',
          'Topic :: System :: Clustering',
          'Topic :: System :: Software Distribution',
          'Topic :: System :: Systems Administration',
    ],
)
