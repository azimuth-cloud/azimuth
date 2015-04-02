from pyramid.config import Configurator
from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy
from pyramid.session import UnencryptedCookieSessionFactoryConfig
from pyramid.events import NewRequest, NewResponse

from eos_portal.security import groupfinder

my_session_factory = UnencryptedCookieSessionFactoryConfig('asdfasdfas')

def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application.
    """
    config = Configurator(settings=settings, session_factory=my_session_factory)

    config.include('pyramid_chameleon')
    config.add_static_view('static', 'static', cache_max_age=3600)
    config.add_route('home', '/')
    config.add_route('login', '/login')
    config.add_route('logout', '/logout')
    config.add_route('servers', '/servers')
    config.add_route('configure', '/servers/{name}')
    config.add_route('stop', '/stop')
    config.add_route('account', '/account')
    config.add_route('forbidden', '/forbidden')

    config.scan()
    return config.make_wsgi_app()
