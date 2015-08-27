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
    'pyramid_debugtoolbar',
    'pyramid_jinja2',
    'waitress',
    'requests',
]

if __name__ == "__main__":

    setup(
        name = 'jasmin_portal',
        version = VERSION,
        description = 'jasmin_portal',
        long_description = README + '\n\n' + CHANGES,
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
        test_suite = "jasmin_portal.test",
        entry_points = """\
        [paste.app_factory]
        main = jasmin_portal:main
        """,
    )
