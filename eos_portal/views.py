from pyramid.view import view_config, forbidden_view_config
from pyramid.security import remember, forget, authenticated_userid
from pyramid.httpexceptions import HTTPFound, HTTPForbidden
import json, requests

@view_config(route_name='home', renderer='templates/home.pt')
def vw_home(request):
    return {'project': 'eos_portal', "logged_in": request.authenticated_userid}

def forbidden_view(request):
    # do not allow a user to login if they are already logged in
    if authenticated_userid(request):
        return HTTPForbidden()
    loc = request.route_url('login', _query=(('next', request.path),))
    return HTTPFound(location=loc)

@view_config(route_name='login', renderer='templates/login.pt')
def vw_login(request):
    session = request.session
    error_flag=False
    if 'submit' in request.POST:
        r = requests.get('http://localhost:6543/users/asdf/password?actor_id=' + request.POST['username'] + '&password=' + request.POST['password'])
        login = request.params['username']
        if r.status_code == 200:
            headers = remember(request, login)
            request.session['token'] = r.text
            
            q = requests.get('http://localhost:6543/users/asdf?actor_id=' + request.POST['username'])
            if q.status_code == 200:
                credit = json.loads(json.loads(q.text))['credits']
                if credit is None:
                    credit = 0
                session['credit'] = credit
            
            return HTTPFound(location='http://localhost:6542/servers', headers=headers)
        else:
            error_flag = True
    return {"project": 'eos_portal', "values": error_flag, "logged_in": request.authenticated_userid}

@view_config(route_name='servers', renderer='templates/servers.pt')
def vw_servers(request):
    owner = authenticated_userid(request)
    session = request.session
    if ('credit' in session) == False:
        return HTTPFound(location='http://localhost:6542/logout') #Turn this into a decorator
    server_list = "gah"
    r = requests.get('http://localhost:6543/servers?actor_id='+ request.authenticated_userid )
    if r.status_code == 200:
        server_list = json.loads(r.text)
    else:
        server_list = "Request Failed"
    return dict(logged_in = request.authenticated_userid, values=server_list, credit=session['credit'])

@view_config(route_name='configure', renderer='templates/configure.pt')
def vw_configure(request):
    owner = authenticated_userid(request)
    session = request.session
    if ('credit' in session) == False:
        return HTTPFound(location='http://localhost:6542/logout') #Turn this into a decorator
    
    # Need to call retrieve_server and retrieve_server_touches
    # /servers/{name}/touches and /servers/{name}/
    
    server_name = request.matchdict['name']
        
    # Abstract this block out and add more error checking
    
    r = requests.get('http://localhost:6543/servers/' + server_name)
    if r.status_code == 200:
        server_data = json.loads(r.text)
    else:
        server_data = "Request Failed" 
    
    p = requests.get('http://localhost:6543/servers/' + server_name + '/touches' )    
    if p.status_code == 200:
        server_touches = json.loads(p.text)
    else:
        server_touches = "Request Failed"
    
    return dict(logged_in = request.authenticated_userid, values=server_data, touches = server_touches, credit=session['credit'])
    

@view_config(route_name='stop', renderer='templates/main.pt')
def vw_stop(request):
    session = request.session
    r = requests.put('http://localhost:6543/servers/aasdf/stop')
    return HTTPFound(location='/main', headers=headers)

@view_config(route_name='account', renderer='templates/account.pt')
def vw_account(request):
    session = request.session
    headers = request.headers
    account_details = {}
    r = requests.get('http://localhost:6543/users/asdf?actor_id=' + request.authenticated_userid)
    if r.status_code == 200:
        account_details = json.loads(json.loads(r.text))
        if account_details['credits'] is None:
            account_details['credits'] = 0
    return dict(logged_in = request.authenticated_userid, values=account_details, credit=session['credit'])

@view_config(route_name='logout')
def logout(request):
    headers = forget(request)
    return HTTPFound(location = request.resource_url(request.context), headers=headers)
