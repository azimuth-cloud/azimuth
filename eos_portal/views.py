from pyramid.view import view_config, forbidden_view_config
from pyramid.security import remember, forget
from pyramid.httpexceptions import HTTPFound
import json, requests

@view_config(route_name='home', renderer='templates/test.pt')
def vw_home(request):
    return {'project': 'eos_portal', "logged_in": request.authenticated_userid}

@view_config(route_name='login', renderer='templates/login.pt')
@forbidden_view_config(renderer='templates/login.pt')
def vw_login(request):
    session = request.session
    error_flag=False
    if 'submit' in request.POST:
        r = requests.get('http://localhost:6543/user/asdf/password?actor_id=' + request.POST['username'] + '&password=' + request.POST['password'])
        login = request.params['username']
        # Verify
        if r.status_code == 200:
            headers = remember(request, login)
            request.session['token'] = r.text
            return HTTPFound(location='http://localhost:7590', headers=headers)
        else:
            error_flag = True
    return {"project": 'eos_portal', "values": error_flag, "logged_in": request.authenticated_userid}

@view_config(route_name='main', renderer='templates/main.pt', permission='user')
def vw_main(request):
    session = request.session
    server_list = "gah"
    r = requests.get('http://localhost:6543/servers?actor_id='+ request.authenticated_userid )
    if r.status_code == 200:
        server_list = json.loads(r.text)
        #server_list = {'sdffsdf':'sdfsdf'}
    else:
        server_list = "Request Failed"
    return HTTPFound(location='http://localhost:7590/', headers=headers)

@view_config(route_name='main', renderer='templates/main.pt', permission='user')
def vw_stop(request):
    session = request.session
    r = requests.put('http://localhost:6543/servers/aasdf/stop')
    return HTTPFound(location='http://localhost:7590/main', headers=headers)

@view_config(route_name='logout')
def logout(request):
    headers = forget(request)
    return HTTPFound(location = request.resource_url(request.context), headers=headers)
