"""
This is the main module for the JASMIN cloud portal. It contains a single function
that creates a WSGI app for the portal.

It is also possible to launch the portal using a development server by running
this file and passing an ``application.ini`` file. This can be useful for creating
an Eclipse Debug configuration.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"

__version__ = "0.1"


from pyramid.config import Configurator
from pyramid.session import SignedCookieSessionFactory

from . import jinja2_ext


def main(global_config, **settings):
    """
    `PasteDeploy app factory <http://pythonpaste.org/deploy/#paste-app-factory>`_
    for the JASMIN cloud portal.
    """

    config = Configurator(
        settings = settings,
        session_factory = SignedCookieSessionFactory(settings['session.secret'])
    )

    # We want to use Jinja2 templates
    config.include('pyramid_jinja2')
    # Force the creation of the environment
    config.commit()
    # Add our custom filters
    config.get_jinja2_environment().filters.update({
        'markdown' : jinja2_ext.markdown_filter,
    })
    
    # Set up the integration for the portal services
    config.include('jasmin_cloud.auth')
    config.include('jasmin_cloud.membership')
    config.include('jasmin_cloud.cloud')
    
    
    ############################################################################
    ## Define routes
    ############################################################################
    # Define a pass-through route for static content with caching
    config.add_static_view(name = 'static', path = 'static', cache_max_age = 3600)
    
    config.add_route('home',   '/')
    
    # Route for XMLHttpRequest calls to get markdown preview
    config.add_route('markdown_preview', '/markdown_preview')
    
    # Single login and logout for all orgs
    config.add_route('login',  '/login')
    config.add_route('logout', '/logout')
    
    # User-specific routes
    config.add_route('dashboard', '/dashboard')
    
    # Org-specific routes
    config.add_route('org_home',         '/{org}')
    config.add_route('users',            '/{org}/users')
    config.add_route('catalogue',        '/{org}/catalogue')
    config.add_route('catalogue_new',    '/{org}/catalogue/new/{id}')
    config.add_route('catalogue_delete', '/{org}/catalogue/delete/{id}')
    config.add_route('machines',         '/{org}/machines')
    config.add_route('new_machine',      '/{org}/machine/new/{id}')
    config.add_route('machine_action',   '/{org}/machine/{id}/action')

    config.scan(ignore = ['.test'])
    return config.make_wsgi_app()
