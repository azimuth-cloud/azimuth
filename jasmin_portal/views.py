"""
Pyramid view callables for the JASMIN cloud portal
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"

import os, tempfile, subprocess, json, re

from pyramid.view import view_config, forbidden_view_config, notfound_view_config
from pyramid.security import remember, forget
from pyramid.session import check_csrf_token
from pyramid.httpexceptions import (
    HTTPSeeOther, HTTPNotFound, HTTPUnauthorized, HTTPForbidden, HTTPBadRequest
)

from jasmin_portal.identity import authenticate_user
from jasmin_portal import catalogue as cat
from jasmin_portal import cloudservices
from jasmin_portal.cloudservices.vcloud import VCloudProvider


@forbidden_view_config()
def forbidden(request):
    """
    Handler for 403 forbidden errors
    
    We want to show a suitable error on the most specific page we can
    
    If the user is logged in and are a member of the current org, show the error
    on the machines page
    If the user is logged in but NOT a member of the current org, show the error
    on the dashboard
    If the user is not logged in, show the error on the login page
    """
    if request.authenticated_user:
        request.session.flash('Insufficient permissions to access resource', 'error')
        if request.authenticated_user.belongs_to(request.current_org):
            return HTTPSeeOther(location = request.route_path('machines'))
        else:
            return HTTPSeeOther(location = request.route_path('dashboard'))
    else:
        request.session.flash('Log in to access this resource', 'error')
        return HTTPSeeOther(location = request.route_path('login'))


@notfound_view_config()
def notfound(request):
    """
    Handler for 404 not found errors
    
    We want to show a suitable error on the most specific page we can
    
    If the user is logged in and are a member of the current org, show the error
    on the machines page
    If the user is logged in but NOT a member of the current org, show the error
    on the dashboard
    If the user is not logged in, show the error on the login page
    """
    request.session.flash('Resource not found', 'error')
    if request.authenticated_user:
        if request.authenticated_user.belongs_to(request.current_org):
            return HTTPSeeOther(location = request.route_path('machines'))
        else:
            return HTTPSeeOther(location = request.route_path('dashboard'))
    else:
        return HTTPSeeOther(location = request.route_path('login'))


@view_config(route_name = 'home',
             request_method = 'GET',
             renderer = 'templates/home.jinja2')
def home(request):
    """
    Handler for /
    
    If the user is logged in, this redirects to /dashboard
    If the user is not logged in, this shows a splash page
    """
    if request.authenticated_user:
        return HTTPSeeOther(location = request.route_url('dashboard'))
    return {}


@view_config(route_name = 'login',
             request_method = ('GET', 'POST'),
             renderer = 'templates/login.jinja2')
def login(request):
    """
    Handler for /login
    
    GET:
        Show a login form
        
    POST:
        Attempt to authenticate the user
        If authentication is successful, try to start a vCD session for each org
        Login is only considered successful if we can get a session for every org
        Redirect to /dashboard on success
        Show login form with error on failure
    """
    if request.method == 'POST':
        # When we get a POST request, clear any existing cloud sessions
        request.clear_cloud_sessions()
        # Try to authenticate the user
        username = request.params['username']
        password = request.params['password']
        user = authenticate_user(request, username, password)
        if user:
            # Try to create a session for each of the user's orgs
            # If any of them fail, bail with the error message
            try:
                provider = VCloudProvider(request.registry.settings['vcloud.endpoint'])
                for org in user.organisations:
                    session = provider.new_session('{}@{}'.format(user.userid, org.name), password)
                    request.add_cloud_session(org, session)
            except cloudservices.CloudServiceError as e:
                request.clear_cloud_sessions()
                request.session.flash(str(e), 'error')
                return {}
            # When a user logs in successfully, force a refresh of the CSRF token
            request.session.new_csrf_token()
            return HTTPSeeOther(location = request.route_url('dashboard'),
                                headers  = remember(request, username))
        else:
            request.session.flash('Invalid credentials', 'error')
    return {}
            

@view_config(route_name = 'logout')
def logout(request):
    """
    Handler for /logout
    
    If the user is logged in, forget them
    Redirect to /
    """
    request.clear_cloud_sessions()
    request.session.flash('Logged out successfully', 'success')
    return HTTPSeeOther(location = request.route_url('home'),
                        headers = forget(request))
    
    
@view_config(route_name = 'profile',
             request_method = 'GET',
             renderer = 'templates/profile.jinja2', permission = 'view')
def profile(request):
    request.session.flash('Profile is currently read-only', 'info')
    return { 'user' : request.authenticated_user }
    
    
@view_config(route_name = 'dashboard',
             request_method = 'GET',
             renderer = 'templates/dashboard.jinja2', permission = 'view')
def dashboard(request):
    """
    Handler for /dashboard
    
    The user must be authenticated to reach here, which means that there should be
    a session for each available org
    
    The dashboard will render a list of available orgs with number of machines
    """
    # Pass the per-org counts to the template
    try:
        count_machines = lambda o: request.get_cloud_session(o).count_machines()
        return {
            'machine_counts' : {
                o.name : count_machines(o) for o in request.authenticated_user.organisations
            }
        }
    # Convert some of the cloud service errors to appropriate HTTP errors
    except cloudservices.AuthenticationError:
        raise HTTPUnauthorized()
    except cloudservices.PermissionsError:
        raise HTTPForbidden()
    except cloudservices.NoSuchResourceError:
        raise HTTPNotFound()
    except cloudservices.CloudServiceError as e:
        request.session.flash(str(e), 'error')
    return {}
    

@view_config(route_name = 'org_home', request_method = 'GET', permission = 'org_view')
def org_home(request):
    """
    Handler for /{org}
    
    Users must be authenticated for the org to get to here
    
    Just redirect to /{org}/machines
    """
    return HTTPSeeOther(location = request.route_url('machines'))

   
@view_config(route_name = 'catalogue',
             request_method = 'GET',
             renderer = 'templates/catalogue.jinja2', permission = 'org_view')
def catalogue(request):
    """
    Handler for /{org}/catalogue
    
    User must be authenticated for org to reach here
    
    Shows the catalogue items available to the org
    """
    # Get the available catalogue items
    items = []
    try:
        items = cat.available_catalogue_items(request)
    # Convert some of the cloud service errors to appropriate HTTP errors
    except cloudservices.AuthenticationError:
        raise HTTPUnauthorized()
    except cloudservices.PermissionsError:
        raise HTTPForbidden()
    except cloudservices.NoSuchResourceError:
        raise HTTPNotFound()
    except cloudservices.CloudServiceError as e:
        request.session.flash(str(e), 'error')
    return { 'items' : items }


@view_config(route_name = 'machines',
             request_method = 'GET',
             renderer = 'templates/machines.jinja2', permission = 'org_view')
def machines(request):
    """
    Handler for /{org}/machines
    
    User must be authenticated for org to reach here
    
    Shows the machines available to the org
    """
    machines = []
    try:
        machines = request.active_cloud_session.list_machines()
    # Convert some of the cloud service errors to appropriate HTTP errors
    except cloudservices.AuthenticationError:
        raise HTTPUnauthorized()
    except cloudservices.PermissionsError:
        raise HTTPForbidden()
    except cloudservices.NoSuchResourceError:
        raise HTTPNotFound()
    except cloudservices.CloudServiceError as e:
        request.session.flash(str(e), 'error')
    return { 'machines'  : machines }


@view_config(route_name = 'new_machine',
             request_method = ('GET', 'POST'),
             renderer = 'templates/new_machine.jinja2', permission = 'org_edit')
def new_machine(request):
    """
    Handler for /{org}/machine/new/{id}
    
    User must be authenticated for org to reach here
    
    {id} is the id of the template to use
    
    GET: Shows a form to gather information required for provisioning
         
    POST: Attempts to provision a machine with the given details
          If the provisioning is successful, redirect to machines with a success message
          If the provisioning is successful but NATing fails, redirect to machines
          with an error message
          If the provisioning fails, show form with error message
    """
    try:
        image_id = request.matchdict['id']
        # Try to load the catalogue item
        image = cat.find_by_uuid(request, image_id)
        if not image:
            raise HTTPNotFound()
        # If we have a POST request, try and provision a machine with the info
        if request.method == 'POST':
            # For a POST request, the request must pass a CSRF test
            check_csrf_token(request)
            machine_info = {
                'image'       : image,
                'name'        : request.params.get('name', ''),
                'description' : request.params.get('description', ''),
                'ssh_key'     : request.params.get('ssh-key', ''),
            }
            # Check that the name fulfills the regex
            if not re.match('[a-zA-Z0-9_]+', machine_info['name']):
                request.session.flash('Name is not valid', 'error')
                return machine_info
            # Check that the SSH key is valid using ssh-keygen
            fd, temp = tempfile.mkstemp()
            with os.fdopen(fd, mode = 'w') as f:
                f.write(machine_info['ssh_key'])
            try:
                # We don't really care about the content of stdout/err
                # We just care if the command succeeded or not...
                subprocess.check_call(
                    'ssh-keygen -l -f {}'.format(temp), shell = True,
                    stdout = subprocess.DEVNULL, stderr = subprocess.DEVNULL
                )
            except subprocess.CalledProcessError:
                request.session.flash('SSH Key is not valid', 'error')
                return machine_info
            try:
                machine = request.active_cloud_session.provision_machine(
                    image_id, machine_info['name'],
                    machine_info['description'], machine_info['ssh_key']
                )
                request.session.flash('Machine provisioned successfully', 'success')
            # Catch specific provisioning errors here
            except cloudservices.DuplicateNameError:
                request.session.flash('Name already in use', 'error')
                return machine_info
            except (cloudservices.BadRequestError,
                    cloudservices.ProvisioningError) as e:
                # If provisioning fails, we want to report an error and show the form again
                request.session.flash('Provisioning error: {}'.format(str(e)), 'error')
                return machine_info
            # Now see if we need to apply NAT and firewall rules
            if image.allow_inbound:
                try:
                    machine = request.active_cloud_session.expose(machine.id)
                    request.session.flash('Inbound access from internet enabled', 'success')
                except cloudservices.NetworkingError as e:
                    request.session.flash('Networking error: {}'.format(str(e)), 'error')
            # Whatever happens, if we get this far we are redirecting to machines
            return HTTPSeeOther(location = request.route_url('machines'))
        # Only get requests should get this far
        return {
            'image'       : image,
            'name'        : '',
            'description' : '',
            # Use the current user's SSH key as the default
            'ssh_key'     : request.authenticated_user.ssh_key or '',
        }
    except cloudservices.AuthenticationError:
        raise HTTPUnauthorized()
    except cloudservices.PermissionsError:
        raise HTTPForbidden()
    except cloudservices.NoSuchResourceError:
        raise HTTPNotFound()
    except cloudservices.CloudServiceError as e:
        request.session.flash(str(e), 'error')
        return HTTPSeeOther(location = request.route_url('machines'))


@view_config(route_name = 'machine_action',
             request_method = 'POST', permission = 'org_edit')
def machine_action(request):
    """
    Handler for /{org}/machine/{id}/action
    
    User must be authenticated for org to reach here
    
    Attempt to perform the specified action
    Redirect to machines with a suitable success or failure message
    """
    # Request must pass a CSRF test
    check_csrf_token(request)
    try:
        action = getattr(request.active_cloud_session,
                         '{}_machine'.format(request.params['action']), None)
        if not callable(action):
            raise HTTPBadRequest()
        action(request.matchdict['id'])
        request.session.flash('Action completed successfully', 'success')
    # Convert some of the cloud service errors to appropriate HTTP errors
    except cloudservices.AuthenticationError:
        raise HTTPUnauthorized()
    except cloudservices.PermissionsError:
        raise HTTPForbidden()
    except cloudservices.NoSuchResourceError:
        raise HTTPNotFound()
    except cloudservices.CloudServiceError as e:
        request.session.flash(str(e), 'error')
    return HTTPSeeOther(location = request.route_url('machines'))
