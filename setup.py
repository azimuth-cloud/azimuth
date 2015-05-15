#!/usr/bin/env python3
import os

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.md')) as f:
    README = f.read()
with open(os.path.join(here, 'CHANGES.md')) as f:
    CHANGES = f.read()
with open(os.path.join(here, 'VERSION')) as f:
    VERSION = f.read().split()[0]

requires = [
    'pyramid',
    'pyramid_chameleon',
    'pyramid_debugtoolbar',
    'waitress',
    'requests',
    'webtest',     # Needed to run the tests
    ]

if __name__ == "__main__":

    setup(name='eos_portal',
          version=VERSION,
          description='eos_portal',
          long_description=README + '\n\n' + CHANGES,
          classifiers=[
            "Programming Language :: Python",
            "Framework :: Pyramid",
            "Topic :: Internet :: WWW/HTTP",
            "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
            ],
          author='Benjamin Collier, Tim Booth',
          author_email='bmcollier@gmail.com, tbooth@ceh.ac.uk',
          url='http://eoscloud.nerc.ac.uk',
          keywords='web pyramid pylons',
          packages=find_packages(),
          include_package_data=True,
          zip_safe=False,
          install_requires=requires,
          tests_require=requires,
          test_suite="eos_portal.test",
          entry_points="""\
          [paste.app_factory]
          main = eos_portal:main
          """,
          )
