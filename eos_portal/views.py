"""EOS Cloud Views

vw_home
vw_login
vw_servers
vw_configure
vw_stop
vw_account

logout
forbidden_view

"""
from pyramid.view import view_config, forbidden_view_config
from pyramid.security import remember, forget
from pyramid.httpexceptions import HTTPFound, HTTPForbidden
import json, requests

from pyramid.renderers import render_to_response

##############################################################################
#                                                                            #
# Supporting Functions - load universal session variables et al.             #
#                                                                            #
##############################################################################

# FIXME - maybe don't need this?
def api_request_string(request_string, request):
    """Process the request string based on request.registry.settings['db_endpoint_i']
       to work out how to make a server-side call to the eos-db server.
    """
    db_endpoint = request.registry.settings.get('db_endpoint_i')

    #Ensure the request string is just a base URL
    assert('://' not in request_string)

    return db_endpoint + '/' + request_string

def api_get(request_string, request):
    """Run an API call and handle exceptions.
    """
    rs = request.registry.settings.get('db_endpoint_i') + '/' + request_string

    cookie = {'auth_tkt':request.session['token']}
    r = requests.get(rs, cookies=cookie)
    if r.status_code == 200:
        return json.loads(r.text)
    else:
        raise ValueError(r.text)

def api_post(request_string, request):
    rs = request.registry.settings.get('db_endpoint_i') + '/' + request_string

    cookie = {'auth_tkt':request.session['token']}
    r = requests.post(rs, cookies=cookie)
    if r.status_code == 200:
        return json.loads(r.text)
    else:
        raise ValueError

def account_details(request):
    if 'token' in request.session:
        result = api_get('user', request)
        account_details = json.loads(result)
        if account_details['credits'] is None:
            account_details['credits'] = 0
        return account_details

def user_credit(request):
    credit = account_details(request)['credits']
    return credit

def server_list(request):
    """Loads all servers for the logged-in user.
    """
    # return api_get('http://localhost:6543/servers?actor_id=' + request.session['username'], request)
    return api_get('servers', request)

def server_data(server_name, request):
    """Loads details of a specific server.
    """
    return api_get('servers/' + server_name, request)

def server_touches(server_name, request):
    """Loads log entries for a given server.
    """
    return api_get('servers/' + server_name + '/touches', request)

##############################################################################
#                                                                            #
# Pages Views - Actual pages on the portal                                   #
#                                                                            #
##############################################################################

@view_config(route_name='home', renderer='templates/home.pt')
def vw_home(request):
    """Main landing page for the portal. Contains reference information.
    """
    account = account_details(request)
    if account is None:
        return {"logged_in": False}
    username = account['username']
    session = request.session
    return dict(values=server_list(request), logged_in=username, credit=user_credit(request), token=request.session['token'])

@view_config(route_name='servers')
def vw_servers(request):
    """Server View - Lists all servers available to the logged-in user.
    """
    session = request.session
    account = account_details(request)
    db_endpoint = request.registry.settings.get('db_endpoint_x')
    response = render_to_response('templates/servers.pt',
                              dict(logged_in   = account['username'],
                                   user        = account['username'],
                                   values      = server_list(request),
                                   credit      = account['credits'],
                                   token       = request.session['token'],
                                   db_endpoint = db_endpoint),
                              request=request)
    response.set_cookie('auth_tkt', request.session['token'])  #!!!!!! SORT THIS
    return response

@view_config(route_name='configure')
def vw_configure(request):
    """Config View - List details of a specific server.
    """
    session = request.session
    account = account_details(request)
    server_name = request.matchdict['name']
    db_endpoint = request.registry.settings.get('db_endpoint_x')
    response = render_to_response('templates/configure.pt',
                              dict(logged_in = account['username'],
                                   values    = server_list(request),
                                   server    = server_data(server_name, request),
                                   touches   = server_touches(server_name, request),
                                   credit    = account['credits'],
                                   token     = request.session['token'],
                                   db_endpoint = db_endpoint),
                              request=request)
    response.set_cookie('auth_tkt', request.session['token'])  #!!!!!! SORT THIS
    return response

@view_config(route_name='account', renderer='templates/account.pt')
def vw_account(request):
    session = request.session
    account = account_details(request)
    if not account['username']:
        return HTTPFound(location=request.registry.settings.get('portal_endpoint') + '/logout')
    return dict(logged_in=account['username'], values=server_list(request), account=account_details(request), credit=user_credit(request), token=request.session['token'])

##############################################################################
#                                                                            #
# Login and logout methods with redirects                                    #
#                                                                            #
##############################################################################

@view_config(route_name='login', renderer='templates/login.pt')
def login(request):
    """??? What exactly does this do ???
    """
    session = request.session
    account = account_details(request)
    if account:
        username = account['username']
    else:
        username = None
    error_flag = False
    if 'submit' in request.POST:
        rs = request.registry.settings.get('db_endpoint_i') + '/user'
        r = requests.get(rs, auth=(request.POST['username'], request.POST['password']))
        login = request.params['username']
        if r.status_code == 200:
            headers = remember(request, login)  # , tokens=[json.loads(r.text)])
            request.session['token'] = r.headers['Set-Cookie'].split(";")[0].split("=")[1][1:-1]
            print ("Session token from DB: " + request.session['token'])
            return HTTPFound(location=request.registry.settings.get('portal_endpoint') + '/servers', headers=headers)
        else:
            error_flag = True
    return dict(project='eos_portal', values=error_flag, logged_in=username)

@view_config(route_name='logout')
def logout(request):
    """Forget the login credentials and redirect to the front page.
    """
    headers = forget(request)
    if 'token' in request.session:
        request.session.pop('token')
    return HTTPFound(location=request.registry.settings.get('portal_endpoint'), headers=headers)
