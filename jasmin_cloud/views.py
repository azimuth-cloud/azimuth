"""
This module contains Pyramid view callables for the JASMIN cloud portal.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"

import logging

from pyramid.view import view_config, forbidden_view_config, notfound_view_config
from pyramid.security import remember, forget
from pyramid.session import check_csrf_token
from pyramid.httpexceptions import HTTPForbidden, HTTPSeeOther, HTTPBadRequest

from . import cloudservices
from .cloudservices import NATPolicy
from .cloudservices.vcloud import VCloudSession
from .util import validate_ssh_key


_log = logging.getLogger(__name__)


################################################################################
## Exception views
##
##   Executed if an exception occurs during regular view handling
################################################################################

def _exception_redirect(request):
    """
    Returns a redirect to the most specific page accessible to the current user:
    
      * Current org machines page if user is logged in and belongs to org in URL
      * Dashboard if user is logged in but doesn't belong to org in URL
      * Login page if user is not logged in
    """
    if request.authenticated_user:
        user_orgs = request.memberships.orgs_for_user(request.authenticated_user.username)
        if request.current_org and (request.current_org in user_orgs):
            return HTTPSeeOther(location = request.route_path('machines'))
        else:
            return HTTPSeeOther(location = request.route_path('dashboard'))
    else:
        return HTTPSeeOther(location = request.route_path('login'))
    

@forbidden_view_config()
def forbidden(request):
    """
    Handler for 403 forbidden errors.
    
    Shows a suitable error on the most specific page possible.
    """
    if request.authenticated_user:
        request.session.flash('Insufficient permissions', 'error')
    else:
        request.session.flash('Log in to access this resource', 'error')
    return _exception_redirect(request)


@notfound_view_config()
def notfound(request):
    """
    Handler for 404 not found errors.
    
    Shows a suitable error on the most specific page possible.
    """
    request.session.flash('Resource not found', 'error')
    return _exception_redirect(request)


@view_config(context = cloudservices.CloudServiceError)
def cloud_service_error(ctx, request):
    """
    Handler for cloud service errors.
    
    If the error is an "expected" error (e.g. not found, permissions), then convert
    to the HTTP equivalent.
    
    Otherwise, show a suitable error on the most specific page possible and log
    the complete error for sysadmins.
    """
    if isinstance(ctx, (cloudservices.AuthenticationError,
                        cloudservices.PermissionsError)):
        return forbidden(request)
    if isinstance(ctx, cloudservices.NoSuchResourceError):
        return notfound(request)
    request.session.flash(str(ctx), 'error')
    _log.error('Unhandled cloud service error', exc_info=(type(ctx), ctx, ctx.__traceback__))
    return _exception_redirect(request)


################################################################################
## Regular views
##
##   Executed when the request matches a route
################################################################################

@view_config(route_name = 'home',
             request_method = 'GET',
             renderer = 'templates/home.jinja2')
def home(request):
    """
    Handler for GET requests to ``/``.
    
    If the user is logged in, redirect to the dashboard, otherwise show a splash page.
    """
    if request.authenticated_user:
        return HTTPSeeOther(location = request.route_url('dashboard'))
    return {}


@view_config(route_name = 'login',
             request_method = ('GET', 'POST'),
             renderer = 'templates/login.jinja2')
def login(request):
    """
    Handler for ``/login``.
    
    GET request
        Show a login form.
        
    POST request
        Attempt to authenticate the user.
        
        If authentication is successful, try to start a vCloud Director session
        for each organisation that the user belongs to. Login is only considered
        successful if we successfully obtain a session for every organisation.
        
        Redirect to the dashboard on success, otherwise show the login form with
        errors.
    """
    if request.method == 'POST':
        # When we get a POST request, clear any existing cloud sessions
        request.cloud_sessions.clear()
        # Try to authenticate the user
        username = request.params['username']
        password = request.params['password']
        if request.users.authenticate(username, password):
            # Try to create a session for each of the user's orgs
            # If any of them fail, bail with the error message
            try:
                for org in request.memberships.orgs_for_user(username):
                    request.cloud_sessions[org] = VCloudSession(
                        request.registry.settings['vcloud.endpoint'],
                        '{}@{}'.format(username, org), password
                    )
            except cloudservices.CloudServiceError:
                request.cloud_sessions.clear()
                raise
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
    Handler for ``/logout``.
    
    If the user is logged in, forget them and redirect to splash page.
    """
    request.cloud_sessions.clear()
    request.session.flash('Logged out successfully', 'success')
    return HTTPSeeOther(location = request.route_url('home'),
                        headers = forget(request))
    
    
@view_config(route_name = 'dashboard',
             request_method = 'GET',
             renderer = 'templates/dashboard.jinja2', permission = 'view')
def dashboard(request):
    """
    Handler for GET requests to ``/dashboard``.
    
    The user must be authenticated to reach here, which means that there should be
    a cloud session for each organisation that the user belongs to.
    
    Shows a list of organisations available to the user with the number of
    machines in each.
    """
    # Pass the per-org counts to the template
    return {
        'machine_counts' : {
            org : sess.count_machines() for org, sess in request.cloud_sessions.items()
        }
    }
    

@view_config(route_name = 'org_home', request_method = 'GET', permission = 'org_view')
def org_home(request):
    """
    Handler for GET requests to ``/{org}``.
    
    The user must be authenticated for the organisation in the URL to reach here.
    
    Just redirect the user to ``/{org}/machines``.
    """
    return HTTPSeeOther(location = request.route_url('machines'))


@view_config(route_name = 'users',
             request_method = 'GET',
             renderer = 'templates/users.jinja2', permission = 'org_view')
def users(request):
    """
    Handler for GET requests to ``/{org}/users``.
    
    The user must be authenticated for the organisation in the URL to reach here.
    
    Show the users belonging to the organisation in the URL.
    """
    # Get the users for the org
    member_ids = request.memberships.members_for_org(request.current_org)
    # Convert the usernames to user objects
    return { 'users' : [request.users.find_by_username(uid) for uid in member_ids] }

   
@view_config(route_name = 'catalogue',
             request_method = 'GET',
             renderer = 'templates/catalogue.jinja2', permission = 'org_view')
def catalogue(request):
    """
    Handler for GET requests to ``/{org}/catalogue``.
    
    The user must be authenticated for the organisation in the URL to reach here.
    
    Show the catalogue items available to the organisation in the URL.
    """
    # Get the available catalogue items
    # Sort the items so that the public items appear first, and then by name
    items = request.active_cloud_session.list_images()
    return { 'items' : sorted(items, key = lambda i: (not i.is_public, i.name)) }


@view_config(route_name = 'catalogue_new',
             request_method = ('GET', 'POST'),
             renderer = 'templates/catalogue_new.jinja2', permission = 'org_edit')
def catalogue_new(request):
    """
    Handler for ``/{org}/catalogue/new/{id}``
    
    The user must be authenticated for the organisation in the URL to reach here.
    
    ``{id}`` is the uuid of the machine to use as a template.
    
    GET request
        Show a form to gather information required to create a new catalogue item.
        
    POST request
        Attempt to create a new catalogue item using the provided information.
        
        On success, redirect the user to ``/{org}/catalogue`` with a success message.
        
        On a duplicate name error, show the form with an error message.        
    """
    # Get the cloud session for the current org
    cloud_session = request.active_cloud_session
    # Check if the session has permission to create templates
    if not cloud_session.has_permission('CAN_CREATE_TEMPLATES'):
        raise HTTPForbidden()
    # Get the machine details from the id
    machine = cloud_session.get_machine(request.matchdict['id'])
    # On a POST request, we must try to create the catalogue item
    if request.method == 'POST':
        # All POST requests need a csrf token
        check_csrf_token(request)
        item_info = {
            'name'          : request.params.get('name', ''),
            'description'   : request.params.get('description', ''),
        }
        try:
            # Create the catalogue item
            cloud_session.image_from_machine(
                machine.id, item_info['name'], item_info['description']
            )
            request.session.flash('Catalogue item created successfully', 'success')
        except cloudservices.DuplicateNameError:
            request.session.flash('There are errors with one or more fields', 'error')
            return {
                'machine' : machine,
                'item'    : item_info,
                'errors'  : { 'name' : ['Catalogue item name is already in use'] }
            }
        return HTTPSeeOther(location = request.route_url('catalogue'))
    # Only a get request should get this far
    return {
        'machine'       : machine,
        'item' : {
            'name'          : '',
            'description'   : '',
        },
        'errors' : {}
    }
    
    
@view_config(route_name = 'catalogue_delete',
             request_method = 'POST', permission = 'org_edit')
def catalogue_delete(request):
    """
    Handler for ``/{org}/catalogue/delete/{id}``
    
    The user must be authenticated for the organisation in the URL to reach here.
    
    Attempts to delete a catalogue item and redirects to the catalogue page with
    a success message.
    
    ``{id}`` is the id of the catalogue item to delete.    
    """
    # Request must pass a CSRF test
    check_csrf_token(request)
    request.active_cloud_session.delete_image(request.matchdict['id'])
    request.session.flash('Catalogue item deleted', 'success')
    return HTTPSeeOther(location = request.route_url('catalogue'))


@view_config(route_name = 'machines',
             request_method = 'GET',
             renderer = 'templates/machines.jinja2', permission = 'org_view')
def machines(request):
    """
    Handler for GET requests to ``/{org}/machines``.
    
    The user must be authenticated for the organisation in the URL to reach here.
    
    Show the machines available to the organisation in the URL.
    """
    return { 'machines'  : request.active_cloud_session.list_machines() }


@view_config(route_name = 'new_machine',
             request_method = ('GET', 'POST'),
             renderer = 'templates/new_machine.jinja2', permission = 'org_edit')
def new_machine(request):
    """
    Handler for ``/{org}/machine/new/{id}``.
    
    The user must be authenticated for the organisation in the URL to reach here.
    
    ``{id}`` is the id of the catalogue item to use for the new machine.
    
    GET request
        Show a form to gather information required for provisioning.
         
    POST request
        Attempt to provision a machine with the given details.
        
        If the provisioning is successful, redirect the user to ``/{org}/machines``
        with a success message.
        
        If the provisioning fails with an error that the user can correct, show
        the form with an error message.
        
        If the provisioning fails with a cloud error, show an error on ``/{org}/machines``.
    """
    # Try to load the catalogue item
    item = request.active_cloud_session.get_image(request.matchdict['id'])
    # If we have a POST request, try and provision a machine with the info
    if request.method == 'POST':
        # For a POST request, the request must pass a CSRF test
        check_csrf_token(request)
        machine_info = {
            'template'    : item,
            'name'        : request.params.get('name', ''),
            'description' : request.params.get('description', ''),
            'expose'      : request.params.get('expose', 'false'),
            'ssh_key'     : request.params.get('ssh_key', ''),
            'errors'      : {}
        }
        # Check that the SSH key is valid
        try:
            machine_info['ssh_key'] = validate_ssh_key(machine_info['ssh_key'])
        except ValueError as e:
            request.session.flash('There are errors with one or more fields', 'error')
            machine_info['errors']['ssh_key'] = [str(e)]
            return machine_info
        try:
            machine = request.active_cloud_session.provision_machine(
                item.id, machine_info['name'],
                machine_info['description'], machine_info['ssh_key'],
                machine_info['expose'] == 'true'
            )
            request.session.flash('Machine provisioned successfully', 'success')
            if machine.external_ip:
                request.session.flash('Inbound access from internet enabled', 'success')
        except cloudservices.DuplicateNameError:
            # If there is an error with a duplicate name, the user can correct that
            request.session.flash('There are errors with one or more fields', 'error')
            machine_info['errors']['name'] = ['Machine name is already in use']
            return machine_info
        except cloudservices.NetworkingError:
            # Networking doesn't happen until the machine has been provisioned
            # So we report that provisioning was successful before propagating
            request.session.flash('Machine provisioned successfully', 'success')
            raise
        # If we get this far, redirect to machines
        return HTTPSeeOther(location = request.route_url('machines'))
    # Only get requests should get this far
    return {
        'template'    : item,
        'name'        : '',
        'description' : '',
        # The default value for expose is based on the NAT policy
        'expose'      : 'true' if item.nat_policy == NATPolicy.ALWAYS else 'false',
        # Use the current user's SSH key as the default
        'ssh_key'     : request.authenticated_user.ssh_key or '',
        'errors'      : {}
    }
    
    
@view_config(route_name = 'machine_reconfigure',
             request_method = 'POST', permission = 'org_edit')
def machine_reconfigure(request):
    """
    Handler for POST requests to ``/{org}/machine/{id}/reconfigure``.
    
    The user must be authenticated for the organisation in the URL to reach here.
    
    Attempt to reconfigure the specified machine with the given amount of CPU
    and RAM.
    """
    # Request must pass a CSRF test
    check_csrf_token(request)
    try:
        cpus = int(request.params['cpus'])
        ram = int(request.params['ram'])
        if cpus < 1 or ram < 1:
            raise ValueError('CPU and RAM must be at least 1')
    except (ValueError, KeyError):
        # If the user has used the UI without modification, this should never happen
        request.session.flash('Error with inputs', 'error')
        return HTTPSeeOther(location = request.route_url('machines'))
    # Reconfigure the machine
    machine_id = request.matchdict['id']
    request.active_cloud_session.reconfigure_machine(machine_id, cpus, ram)
    request.session.flash('Machine reconfigured successfully', 'success')
    return HTTPSeeOther(location = request.route_url('machines'))


@view_config(route_name = 'machine_action',
             request_method = 'POST', permission = 'org_edit')
def machine_action(request):
    """
    Handler for POST requests to ``/{org}/machine/{id}/action``.
    
    The user must be authenticated for the organisation in the URL to reach here.
    
    Attempt to perform the specified action and redirect to ``/{org}/machines``
    with a success message.
    """
    # Request must pass a CSRF test
    check_csrf_token(request)
    action = getattr(request.active_cloud_session,
                     '{}_machine'.format(request.params['action']), None)
    if not callable(action):
        raise HTTPBadRequest()
    action(request.matchdict['id'])
    request.session.flash('Action completed successfully', 'success')
    return HTTPSeeOther(location = request.route_url('machines'))


@view_config(route_name = 'markdown_preview',
             request_method = 'POST', xhr = True, permission = 'view',
             renderer = 'templates/markdown_preview.jinja2')
def markdown_preview(request):
    """
    Handler for POST requests via XMLHttpRequest to ``/markdown_preview``.
    
    The user must be authenticated to reach here.
    
    Renders the specified markdown to HTML using the same filter used in templates.
    """
    return { 'value' : request.params['markdown'] }
