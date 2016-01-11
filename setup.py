#!/usr/bin/env python3

import os, re

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))

try:
    import jasmin_cloud.__version__ as version
except ImportError:
    # If we get an import error, find the version string manually from
    # jasmin_cloud/__init__.py
    version = "unknown"
    with open(os.path.join(here, 'jasmin_cloud', '__init__.py')) as f:
        for line in f:
            match = re.search('__version__ *= *[\'"](?P<version>.+)[\'"]', line)
            if match:
                version = match.group('version')
                break

with open(os.path.join(here, 'README.md')) as f:
    README = f.read()

requires = [
    'pyramid',
    'pyramid_debugtoolbar',
    'pyramid_jinja2',
    'pyramid_beaker',
    'jinja2',
    'jasmin-auth',
    'ldap3',
    'requests',
    'bleach',
    'markdown',
    'waitress',
    # Required for docs
    'sphinx',
]

if __name__ == "__main__":

    setup(
        name = 'jasmin-cloud',
        version = version,
        description = 'Portal for management of machines in the JASMIN cloud',
        long_description = README,
        classifiers = [
            "Programming Language :: Python",
            "Framework :: Pyramid",
            "Topic :: Internet :: WWW/HTTP",
            "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
        ],
        author = 'Matt Pryor',
        author_email = 'matt.pryor@stfc.ac.uk',
        url = 'http://jasmin.ac.uk',
        keywords = 'web pyramid cloud jasmin',
        packages = find_packages(),
        include_package_data = True,
        zip_safe = False,
        install_requires = requires,
        tests_require = requires,
        test_suite = "jasmin_cloud.test",
        entry_points = """\
        [paste.app_factory]
        main = jasmin_cloud:main
        """,
    )
