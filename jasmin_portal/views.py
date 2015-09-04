"""
Pyramid view callables for the JASMIN cloud portal
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"

import os, tempfile, subprocess, json

from pyramid.view import view_config, forbidden_view_config, notfound_view_config
from pyramid.security import remember, forget
from pyramid.session import check_csrf_token
from pyramid.httpexceptions import (
    HTTPSeeOther, HTTPNotFound, HTTPUnauthorized, HTTPForbidden, HTTPBadRequest
)

import jasmin_portal.cloudservices as cloud
import jasmin_portal.cloudservices.vcloud as vcloud


@forbidden_view_config(renderer = 'templates/login.jinja2')
def forbidden(request):
    """
    Handler for 403 errors
    
    We should only get 403 errors for pages with an org
    """
    if request.vcd_session is not None:
        request.session.flash(
            'You have insufficient permissions to access this resource', 'error'
        )
    else:
        request.session.flash('Please log in to access this resource', 'error')
    return {}


@notfound_view_config(renderer = 'templates/notfound.jinja2')
def notfound(request):
    """
    Handler for 404 errors
    """
    request.session.flash(
        'The resource you requested could not be found', 'error'
    )
    return {}


@view_config(route_name = 'home',
             request_method = 'GET',
             renderer = 'templates/home.jinja2')
def home(request):
    """
    Handler for /
    
    If the user is logged in, this redirects to /{org}/machines using the
    org from their username
    If the user is not logged in, this shows a splash page
    """
    if request.authenticated_userid:
        org = request.authenticated_userid.split('@').pop()
        return HTTPSeeOther(location = request.route_url('machines', org = org))
    return {}


@view_config(route_name = 'login',
             request_method = ('GET', 'POST'),
             renderer = 'templates/login.jinja2')
def login(request):
    """
    Handler for /{org}/login
    
    GET:
        Show a login form for the org
        
    POST:
        Attempt to authenticate the user with vCD
        Redirect to /{org}/machines on success
        Show login form with error on failure
    """
    if request.method == 'POST':
        username = '{}@{}'.format(request.params['username'], request.matchdict['org'])
        password = request.params['password']
        try:
            
            provider = vcloud.VCloudProvider(request.registry.settings['vcloud.endpoint'])
            request.vcd_session = provider.new_session(username, password)
            # When a user logs in, force a refresh of the CSRF token
            request.session.new_csrf_token()
            return HTTPSeeOther(location = request.route_url('machines'),
                                headers  = remember(request, username))
        except cloud.CloudServiceError as e:
            request.session.flash(str(e), 'error')
            request.vcd_session = None
    return {}
            

@view_config(route_name = 'logout')
def logout(request):
    """
    Handler for /logout
    
    If the user is logged in, forget them
    Redirect to /
    """
    if request.vcd_session:
        request.vcd_session.close()
        request.vcd_session = None
    request.session.flash('Logged out successfully', 'success')
    return HTTPSeeOther(location = request.route_url('home'),
                        headers = forget(request))
    

@view_config(route_name = 'org_home', request_method = 'GET')
def org_home(request):
    """
    Handler for /{org}
    
    If the user is authenticated for the org, redirect to /{org}/machines
    Otherwise, redirect to /{org}/login
    """
    if request.matchdict['org'].lower() in request.effective_principals:
        return HTTPSeeOther(location = request.route_url('machines'))
    else:
        return HTTPSeeOther(location = request.route_url('login'))

   
@view_config(route_name = 'catalogue',
             request_method = 'GET',
             renderer = 'templates/catalogue.jinja2', permission = 'view')
def catalogue(request):
    """
    Handler for /{org}/catalogue
    
    User must be logged in to org to reach here
    
    Shows the catalogue items available to the user
    """
    # Get the catalogue items from vCD, then overwrite with values from the
    # config file where present
    # Items from vCD catalogues have no NAT or firewall rules applied unless
    # overridden in the catalogue file
    items = []
    try:
        items = request.vcd_session.list_images()
        # Get items in the same format as the catalogue file
        items = ({
            'uuid'          : i.id,
            'name'          : i.name,
            'description'   : i.description,
            'allow_inbound' : False
        } for i in items)
    # Convert some of the cloud service errors to appropriate HTTP errors
    except cloud.AuthenticationError:
        return HTTPUnauthorized()
    except cloud.PermissionsError:
        return HTTPForbidden()
    except cloud.NoSuchResourceError:
        return HTTPNotFound()
    except cloud.CloudServiceError as e:
        request.session.flash(str(e), 'error')
    if items:
        with open(request.registry.settings['catalogue.file']) as f:
            overrides = json.load(f)
    return {
        'items' : [overrides[i['uuid']] if i['uuid'] in overrides else i for i in items]
    }


@view_config(route_name = 'machines',
             request_method = 'GET',
             renderer = 'templates/machines.jinja2', permission = 'view')
def machines(request):
    """
    Handler for /{org}/machines
    
    User must be logged in to org to reach here
    
    Shows the machines available to the user
    """
    machines = []
    try:
        machines = request.vcd_session.list_machines()
    # Convert some of the cloud service errors to appropriate HTTP errors
    except cloud.AuthenticationError:
        return HTTPUnauthorized()
    except cloud.PermissionsError:
        return HTTPForbidden()
    except cloud.NoSuchResourceError:
        return HTTPNotFound()
    except cloud.CloudServiceError as e:
        request.session.flash(str(e), 'error')
    return { 'machines'  : machines }


@view_config(route_name = 'new_machine',
             request_method = ('GET', 'POST'),
             renderer = 'templates/new_machine.jinja2', permission = 'edit')
def new_machine(request):
    """
    Handler for /{org}/machine/new/{id}
    
    User must be logged in to org to reach here
    
    {id} is the id of the template to use
    
    GET: Shows a form to gather information required for provisioning
         
    POST: Attempts to provision a machine with the given details
          If the provisioning is successful, redirect to /machines with a success message
          If the provisioning is successful but NATing fails, redirect to /machines
          with an error message
          If the provisioning fails, show form with error message
    """
    try:
        image_id = request.matchdict['id']
        # Try to load the image data from the JSON file
        with open(request.registry.settings['catalogue.file']) as f:
            items = json.load(f)
        if image_id in items:
            image = items[image_id]
        else:
            # If that fails, get the image data from vCD in the same format
            image = request.vcd_session.get_image(image_id)
            image = {
                'uuid'          : image.id,
                'name'          : image.name,
                'description'   : image.description,
                'allow_inbound' : False,
            }
        # If we have a POST request, try and provision a machine with the info
        if request.method == 'POST':
            # For a POST request, the request must pass a CSRF test
            check_csrf_token(request)
            name = request.params.get('name', '')
            description = request.params.get('description', '')
            ssh_key = request.params.get('ssh-key', '')
            # Check that the SSH key is valid using ssh-keygen
            fd, temp = tempfile.mkstemp()
            with os.fdopen(fd, mode = 'w') as f:
                f.write(ssh_key)
            try:
                # We don't really care about the content of stdout/err
                # We just care if the command succeeded or not...
                subprocess.check_call(
                    'ssh-keygen -l -f {}'.format(temp), shell = True,
                    stdout = subprocess.DEVNULL, stderr = subprocess.DEVNULL
                )
            except subprocess.CalledProcessError:
                request.session.flash('SSH Key is not valid', 'error')
                return {
                    'image'       : image,
                    'name'        : name,
                    'description' : description,
                    'ssh_key'     : ssh_key,
                }
            try:
                machine = request.vcd_session.provision_machine(image_id, name, description, ssh_key)
                request.session.flash('Machine provisioned successfully', 'success')
            # Catch more specific provisioning errors here
            except (cloud.DuplicateNameError, 
                    cloud.BadRequestError,
                    cloud.ProvisioningError) as e:
                # If provisioning fails, we want to report an error and show the form again
                request.session.flash('Provisioning error - {}'.format(str(e)), 'error')
                return {
                    'image'       : image,
                    'name'        : name,
                    'description' : description,
                    'ssh_key'     : ssh_key,
                }
            # Now see if we need to apply NAT and firewall rules
            if image['allow_inbound']:
                try:
                    machine = request.vcd_session.expose(machine.id)
                    request.session.flash('Inbound access from internet enabled', 'success')
                except cloud.NetworkingError as e:
                    request.session.flash('Networking error - {}'.format(str(e)), 'error')
            # Whatever happens, if we get this far we are redirecting to machines
            return HTTPSeeOther(location = request.route_url('machines'))
        # Only get requests should get this far
        return {
            'image'       : image,
            'name'        : '',
            'description' : '',
            'ssh_key'     : '',
        }
    except cloud.AuthenticationError:
        return HTTPUnauthorized()
    except cloud.PermissionsError:
        return HTTPForbidden()
    except cloud.NoSuchResourceError:
        return HTTPNotFound()
    except cloud.CloudServiceError as e:
        request.session.flash(str(e), 'error')
        return HTTPSeeOther(location = request.route_url('machines'))


@view_config(route_name = 'machine_action',
             request_method = 'POST', permission = 'edit')
def machine_action(request):
    """
    Handler for /{org}/machine/{id}/action
    
    User must be logged in to org to reach here
    
    Attempt to perform the specified action
    Redirect to machines with a suitable success or failure message
    """
    # Request must pass a CSRF test
    check_csrf_token(request)
    try:
        action = getattr(request.vcd_session,
                         '{}_machine'.format(request.params['action']), None)
        if not callable(action):
            return HTTPBadRequest()
        action(request.matchdict['id'])
        request.session.flash('Action completed successfully', 'success')
    # Convert some of the cloud service errors to appropriate HTTP errors
    except cloud.AuthenticationError:
        return HTTPUnauthorized()
    except cloud.PermissionsError:
        return HTTPForbidden()
    except cloud.NoSuchResourceError:
        return HTTPNotFound()
    except cloud.CloudServiceError as e:
        request.session.flash(str(e), 'error')
    return HTTPSeeOther(location = request.route_url('machines'))
