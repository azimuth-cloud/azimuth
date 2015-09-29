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

from jasmin_portal import auth, identity, catalogue, cloud


def main(global_config, **settings):
    """
    `PasteDeploy app factory <http://pythonpaste.org/deploy/#paste-app-factory>`_
    for the JASMIN portal.
    """

    config = Configurator(
        settings = settings,
        session_factory = SignedCookieSessionFactory(settings['session.secret'])
    )

    # We want to use Jinja2 templates
    config.include('pyramid_jinja2')
    
    # We want to use SQLAlchemy with transaction management
    config.include('pyramid_tm')
    config.include('pyramid_sqlalchemy')
    
    # Set up the integration for the portal services
    config = auth.setup(config, settings)
    config = identity.setup(config, settings)
    config = cloud.setup(config, settings)
    config = catalogue.setup(config, settings)
    
    
    ############################################################################
    ## Define routes
    ############################################################################
    # Define a pass-through route for static content with caching
    config.add_static_view(name = 'static', path = 'static', cache_max_age = 3600)
    
    config.add_route('home',   '/')
    
    # Single login and logout for all orgs
    config.add_route('login',  '/login')
    config.add_route('logout', '/logout')
    
    # User-specific routes
    config.add_route('dashboard', '/dashboard')
    config.add_route('profile', '/profile')
    
    # Org-specific routes
    config.add_route('org_home',         '/{org}')
    config.add_route('catalogue',        '/{org}/catalogue')
    config.add_route('catalogue_new',    '/{org}/catalogue/new/{id}')
    config.add_route('catalogue_delete', '/{org}/catalogue/delete/{id}')
    config.add_route('machines',         '/{org}/machines')
    config.add_route('new_machine',      '/{org}/machine/new/{id}')
    config.add_route('machine_action',   '/{org}/machine/{id}/action')

    config.scan(ignore = ['.test'])
    return config.make_wsgi_app()


# For debugging, you can just run this script instead of pserve
if __name__ == "__main__":
    import sys
    from pkg_resources import load_entry_point

    sys.exit(
        load_entry_point('pyramid', 'console_scripts', 'pserve')()
    )
