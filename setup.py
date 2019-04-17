#!/usr/bin/env python3

import os
from setuptools import setup, find_packages


here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.md')) as f:
    README = f.read()

if __name__ == "__main__":
    setup(
        name = 'jasmin-cloud',
        setup_requires = ['setuptools_scm'],
        use_scm_version = True,
        description = 'API for management of tenancies in the JASMIN Cloud.',
        long_description = README,
        classifiers = [
            "Programming Language :: Python",
            "Framework :: Django",
            "Topic :: Internet :: WWW/HTTP",
            "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
        ],
        author = 'Matt Pryor',
        author_email = 'matt.pryor@stfc.ac.uk',
        url = 'https://github.com/cedadev/jasmin-cloud',
        keywords = 'web django jasmin cloud api',
        packages = find_packages(),
        include_package_data = True,
        zip_safe = False,
        install_requires = [
            'docutils',
            'python-dateutil',
            'requests',
            'openstacksdk',
            'django',
            'djangorestframework',
            'psycopg2-binary',
            'django-settings-object',
            'jasmin-ldap',
        ],
    )
