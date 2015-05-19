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
import requests

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

    #Pass auth_tkt in cookie rather than header.
    cookie = {'auth_tkt':request.session['auth_tkt']}
    r = requests.get(rs, cookies=cookie)
    if r.status_code == 200:
        return r.json()
    else:
        #FIXME - ensure return to login form on receipt of a 401
        raise ValueError(r.text)

def api_post(request_string, request):
    rs = request.registry.settings.get('db_endpoint_i') + '/' + request_string

    #Pass auth_tkt in cookie rather than header.
    cookie = {'auth_tkt':request.session['auth_tkt']}
    r = requests.post(rs, headers=cookie)
    if r.status_code == 200:
        return r.json()
    else:
        #FIXME - ensure return to login form on receipt of a 401
        raise ValueError

def user_credit(request):
    return api_get('user', request)['credits']

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

#FIXME - home page should be login page.  This should be the /about page or summat.
@view_config(route_name='home', renderer='templates/home.pt')
def vw_home(request):
    """Main landing page for the portal. Contains reference information.
    """
    account = None
    try:
        account = api_get('user', request)
    except:
        #We need to be able to look at this page even if not logged in.
        account = dict()
    return dict(values      = [],
                logged_in   = account.get('username'),
                credit      = account.get('credits'))

@view_config(route_name='servers', renderer='templates/servers.pt')
def vw_servers(request):
    """Server View - Lists all servers available to the logged-in user.
    """
    account = None
    try:
        account = api_get('user', request)
    except:
        return logout(request)
    #Tell the browser how to query the database via the external endpoint.
    db_endpoint = request.registry.settings.get('db_endpoint_x')
    return dict(   logged_in   = account['username'],
                   user        = account['username'],
                   values      = server_list(request),
                   credit      = account['credits'],
                   token       = request.session['auth_tkt'],
                   db_endpoint = db_endpoint)

@view_config(route_name='configure', renderer='templates/configure.pt')
def vw_configure(request):
    """Config View - List details of a specific server.
    """
    #FIXME - this boilerplate could be made into a handle_logout decorator,
    #as well as adding token, db_endpoint, logged_in, credit to all templates.
    account = None
    try:
        account = api_get('user', request)
    except:
        return logout(request)
    server_name = request.matchdict['name']
    db_endpoint = request.registry.settings.get('db_endpoint_x')
    return dict(   logged_in    = account['username'],
                   values       = server_list(request),
                   server       = server_data(server_name, request),
                   touches      = server_touches(server_name, request),
                   credit       = account['credits'],
                   token        = request.session['auth_tkt'],
                   db_endpoint  = db_endpoint)

@view_config(route_name='account', renderer='templates/account.pt')
def vw_account(request):
    account = None
    try:
        account = api_get('user', request)
    except:
        return logout(request)
    return dict( logged_in = account['username'],
                 values    = server_list(request),
                 account   = account_details(request),
                 credit    = user_credit(request),
                 token     = request.session['auth_tkt'])

##############################################################################
#                                                                            #
# Login and logout methods with redirects                                    #
#                                                                            #
##############################################################################

@view_config(route_name='login', renderer='templates/login.pt')
def login(request):
    """Either log the user in or show the login page.
    """
    username = request.POST.get('username')
    account = None
    error_msg = None

    #1) If the user submitted the form, try to log in.
    if 'submit' in request.POST:
        user_url = request.registry.settings.get('db_endpoint_i') + '/user'
        r = requests.get(user_url, auth=(request.POST['username'], request.POST['password']))
        if r.status_code == 200:
            headers = remember(request, r.json()['username'])
            #FIXME - must be a nicer way to read this!
            request.session['auth_tkt'] = r.headers['Set-Cookie'].split(";")[0].split("=")[1][1:-1]
            print ("Session token from DB: " + request.session['auth_tkt'])
            return HTTPFound(location=request.registry.settings.get('portal_endpoint') + '/servers', headers=headers)
        if r.status_code == 401:
            error_msg = "Username or password not recognised"
        else:
            error_msg = "Server error"
    #2) Already logged in, maybe?  See if any of the following raise an exception...
    else:
        try:
            auth_tkt = request.session['auth_tkt']
            #If that didn't raise an exception, try using it...
            error_msg = "Session has expired"
            account = api_get('user', request)
            username = account['username']
            print("Already logged in")
            headers = remember(request, username)
            return HTTPFound(location=request.registry.settings.get('portal_endpoint') + '/servers', headers=headers)
        except:
            pass #Continue to show login form.

    #FIXME - make use of error_msg and username if set.
    return dict(project='eos_portal', values=[], logged_in=None)

@view_config(route_name='logout')
def logout(request):
    """Forget the login credentials and redirect to the front page.
       Note that other methods rely on this to always return an HTTPFound instance.
    """
    headers = forget(request)
    if 'auth_tkt' in request.session:
        request.session.pop('auth_tkt')
    return HTTPFound(location=request.registry.settings.get('portal_endpoint'), headers=headers)
