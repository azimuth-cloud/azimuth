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
from pyramid.security import remember, forget, authenticated_userid
from pyramid.httpexceptions import HTTPFound, HTTPForbidden
import json, requests

username = 'agent'
password = 'sharedsecret'

##############################################################################
#                                                                            #
# Supporting Functions - load universal session variables et al.             #
#                                                                            #
##############################################################################

def api_get(request_string):
    """Run an API call and handle exceptions.
    """
    r = requests.get(request_string, auth=(username, password))
    if r.status_code == 200:
        return json.loads(r.text)
    else:
        raise ValueError

def api_post(request_string):
    r = requests.post(request_string, auth=(username, password))
    if r.status_code == 200:
        return json.loads(r.text)
    else:
        raise ValueError

def account_details(request):
    result = api_get('http://localhost:6543/users/asdf?actor_id=' + request.authenticated_userid)
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
    return api_get('http://localhost:6543/servers?actor_id=' + request.authenticated_userid)

def server_data(server_name):
    """Loads details of a specific server.
    """
    return api_get('http://localhost:6543/servers/' + server_name)

def server_touches(server_name):
    """Loads log entries for a given server.
    """
    return api_get('http://localhost:6543/servers/' + server_name + '/touches')

##############################################################################
#                                                                            #
# Pages Views - Actual pages on the portal                                   #
#                                                                            #
##############################################################################

@view_config(route_name='home', renderer='templates/home.pt')
def vw_home(request):
    """Main landing page for the portal. Contains reference information.
    """
    if not request.authenticated_userid:
        return {"logged_in": False}

    session = request.session
    return dict(values=server_list(request), logged_in=request.authenticated_userid, credit=user_credit(request), token=request.session['token'])

@view_config(route_name='servers', renderer='templates/servers.pt')
def vw_servers(request):
    """Server View - Lists all servers available to the logged-in user.
    """
    session = request.session
    if not request.authenticated_userid:
        return HTTPFound(location='http://localhost:6542/logout')
    return dict(logged_in=request.authenticated_userid, values=server_list(request), credit=user_credit(request), token=request.session['token'])

@view_config(route_name='configure', renderer='templates/configure.pt')
def vw_configure(request):
    """Config View - List details of a specific server.
    """
    session = request.session
    if not request.authenticated_userid:
        return HTTPFound(location='http://localhost:6542/logout')
    server_name = request.matchdict['name']
    return dict(logged_in=request.authenticated_userid, server=server_data(server_name), values=server_list(request), token=request.session['token'], touches=server_touches(server_name), credit=user_credit(request))

@view_config(route_name='account', renderer='templates/account.pt')
def vw_account(request):
    session = request.session
    if not request.authenticated_userid:
        return HTTPFound(location='http://localhost:6542/logout')
    return dict(logged_in=request.authenticated_userid, values=server_list(request), account=account_details(request), credit=user_credit(request), token=request.session['token'])

##############################################################################
#                                                                            #
# Login and logout methods with redirects                                    #
#                                                                            #
##############################################################################

@view_config(route_name='login', renderer='templates/login.pt')
def login(request):
    session = request.session
    error_flag = False
    if 'submit' in request.POST:
        r = requests.get('http://localhost:6543/users/asdf/password?actor_id=' + request.POST['username'] + '&password=' + request.POST['password'], auth=(username, password))
        login = request.params['username']
        if r.status_code == 200:
            headers = remember(request, login)
            request.session['token'] = r.text
            return HTTPFound(location='http://localhost:6542/servers', headers=headers)
        else:
            error_flag = True
    return {"project": 'eos_portal', "values": error_flag, "logged_in": request.authenticated_userid}

@view_config(route_name='logout')
def logout(request):
    headers = forget(request)
    return HTTPFound(location=request.resource_url(request.context), headers=headers)
