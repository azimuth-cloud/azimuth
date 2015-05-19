from pyramid.config import Configurator
from pyramid.session import SignedCookieSessionFactory
from pyramid.events import NewRequest, NewResponse

#from eos_portal.security import groupfinder

#FIXME - while the portal does not 'do' security a weak signing key will
#potentially allow a CSRF attack to be made (I think).
my_session_factory = SignedCookieSessionFactory('FIXME')

def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application.
    """

    #Default settings for portal_endpoint and db_endpoint
    if "portal_endpoint" not in settings:
        settings['portal_endpoint'] = "http://localhost:6542"
    if "db_endpoint_x" not in settings:
        settings['db_endpoint_x'] = settings.get('db_endpoint', "http://localhost:6543")
    if "db_endpoint_i" not in settings:
        settings['db_endpoint_i'] = settings.get('db_endpoint', "http://localhost:6543")

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
