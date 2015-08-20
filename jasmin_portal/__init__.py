"""
WSGI app definition for the JASMIN cloud portal
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"


from pyramid.config import Configurator
from pyramid.session import SignedCookieSessionFactory
from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy

from .auth import RootFactory, RequestFactory, check_session


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
    config.add_route('login',  '/login')
    config.add_route('logout', '/logout')
    
    # Catalogue routes
    config.add_route('catalogue',      '/catalogue')
    config.add_route('catalogue_item', '/catalogue_item/{id}')
    
    # VM routes
    config.add_route('machines',       '/machines')
    config.add_route('new_machine',    '/machine/new')
    config.add_route('machine',        '/machine/{id}')
    config.add_route('machine_action', '/machine/{id}/action')

    config.scan()
    return config.make_wsgi_app()
