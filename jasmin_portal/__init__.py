"""
WSGI app definition for the JASMIN cloud portal
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"


from pyramid.config import Configurator
from pyramid.session import SignedCookieSessionFactory
from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy

from jasmin_portal.auth import RootFactory, RequestFactory, check_session


def main(global_config, **settings):
    """
    Builds and returns the portal WSGI application
    """

    config = Configurator(
        settings = settings,
        # TODO: Provide a better secret
        session_factory = SignedCookieSessionFactory('FIXME')
    )

    # We want to use Jinja2 templates
    config.include('pyramid_jinja2')
    
    ###############################################################################################
    ## Define the security configuration using vCD helpers
    ###############################################################################################
    config.set_request_factory(RequestFactory)
    # We want to use token based authentication, with a check on the vCD session
    config.set_authentication_policy(AuthTktAuthenticationPolicy(
        'MY_SECRET', hashalg = 'sha512', callback = check_session
    ))
    # We use a basic ACL policy for authorisation
    config.set_authorization_policy(ACLAuthorizationPolicy())
    config.set_root_factory(RootFactory)
        
    
    ###############################################################################################
    ## Define routes
    ###############################################################################################
    # Define a pass-through route for static content with caching
    config.add_static_view(name = 'static', path = 'static', cache_max_age = 3600)
    
    config.add_route('home',   '/')
    
    # Single logout URI - just clears the current session
    config.add_route('logout',         '/logout')
    
    # All other routes are org-specific
    config.add_route('org_home',       '/{org}')
    config.add_route('login',          '/{org}/login')
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
