"""Tests for the portal.  This is a bit tricky because the portal needs to
   call to the DB for most functions, but we can still test some basics.
"""

import os
import unittest
from webtest import TestApp
from unittest.mock import Mock, patch
from pyramid.paster import get_app
from http.cookiejar import DefaultCookiePolicy

#Not called directly, but patched:
import requests

# Expect a sample .ini file in the same folder as this test.
test_ini = os.path.join(os.path.dirname(__file__), 'test.ini')

class TestPortal(unittest.TestCase):

    def setUp(self):
        """Launch pserve/waitress using webtest with test settings.
           Fresh for every test, though it shouldn't matter.
        """
        self.myapp = get_app(test_ini)
        self.testapp = TestApp(self.myapp)

        #No auth, no cookies
        self.testapp.authorization = None
        self.testapp.cookiejar.set_policy(DefaultCookiePolicy(allowed_domains=[]))

    def test_homepage(self):
        """Homepage load
        """
        #Look how simple this test is.  I love webtest.
        self.testapp.get("/")

    def test_logout(self):
        """Even if we are not logged in, logout should generate a redirect to
           http://localhost:6542
        """
        res = self.testapp.get("/logout", status=302)

        self.assertEqual(res.headers['Location'], 'http://localhost:6542')

    @patch('requests.post', return_value=None)
    @patch('requests.get', return_value=None)
    def test_nologin(self, mock_get, mock_post):
        """A login request with no username and password should return the login
           form without making any requests.get or requests.post calls.
        """
        res = self.testapp.get("/login", status=200)

        res = self.testapp.post("/login", status=200)

        self.assertEqual(mock_get.call_count, 0)
        self.assertEqual(mock_post.call_count, 0)

    @patch('requests.post', return_value=None)
    @patch('requests.get', return_value=Mock(status_code=404))
    def test_login(self, mock_get, mock_post):
        """A login request with a username and password should result in an
           internal query to http://endpoint_i.example.com/user
        """
        res = self.testapp.post("/login", [
                                    ('submit', '1'),
                                    ('username', 'foo'),
                                    ('password', 'bar'),
                                    ], expect_errors=True)

        self.assertEqual(mock_post.call_count, 0)
        self.assertEqual(mock_get.call_count, 1)

        #Note this test is dependent on how exactly requests.get is called.
        self.assertEqual(mock_get.call_args, (
                            ('http://endpoint_i.example.com/user',),
                            { 'auth': ('foo', 'bar',) }
                        ))
