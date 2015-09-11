"""
WSGI app definition for the JASMIN cloud portal
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"


from pyramid.config import Configurator
from pyramid.session import SignedCookieSessionFactory
from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy

from jasmin_portal.auth import RootFactory, check_cloud_sessions
from jasmin_portal import identity, cloud


def main(global_config, **settings):
    """
    Builds and returns the portal WSGI application
    """

    config = Configurator(
        settings = settings,
        session_factory = SignedCookieSessionFactory(settings['session.secret'])
    )

    # We want to use Jinja2 templates
    config.include('pyramid_jinja2')
    
    ###############################################################################################
    ## Define the security configuration
    ###############################################################################################
    # We want to use token based authentication, with a check on the cloud sessions
    config.set_authentication_policy(AuthTktAuthenticationPolicy(
        settings['auth.secret'], hashalg = 'sha512', callback = check_cloud_sessions
    ))
    # We use a basic ACL policy for authorisation
    config.set_authorization_policy(ACLAuthorizationPolicy())
    config.set_root_factory(RootFactory)
    
    
    # Set up the identity management and cloud integration
    config = identity.setup(config, settings)
    config = cloud.setup(config, settings)
    
    
    ###############################################################################################
    ## Define routes
    ###############################################################################################
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
    config.add_route('org_home',       '/{org}')
    config.add_route('catalogue',      '/{org}/catalogue')
    config.add_route('machines',       '/{org}/machines')
    config.add_route('new_machine',    '/{org}/machine/new/{id}')
    config.add_route('machine_action', '/{org}/machine/{id}/action')

    config.scan(ignore = ['.test'])
    return config.make_wsgi_app()


# For debugging, you can just run this script instead of pserve
if __name__ == "__main__":
    import sys
    from pkg_resources import load_entry_point

    sys.exit(
        load_entry_point('pyramid', 'console_scripts', 'pserve')()
    )
