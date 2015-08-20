"""
Pyramid view callables for the JASMIN cloud portal
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"


from pyramid.view import view_config, forbidden_view_config, notfound_view_config
from pyramid.security import remember, forget
from pyramid.httpexceptions import (
    HTTPSeeOther, HTTPNotFound, HTTPUnauthorized, HTTPForbidden, HTTPBadRequest
)

import jasmin_portal.cloudservices as cloud
import jasmin_portal.cloudservices.vcloud as vcloud


@forbidden_view_config(renderer = 'templates/forbidden.jinja2')
def forbidden(request):
    """
    Handler for 403 errors
    """
    return {}


@notfound_view_config(renderer = 'templates/notfound.jinja2')
def notfound(request):
    """
    Handler for 404 errors
    """
    return {}


@view_config(route_name = 'home',
             request_method = 'GET',
             renderer = 'templates/home.jinja2')
def home(request):
    """
    Handler for /
    
    If the user is logged in, this redirects to /machines
    If the user is not logged in, this shows a splash page
    """
    if request.vcd_session and request.vcd_session.is_active():
        return HTTPSeeOther(location = request.route_url('machines'))
    return {}


@view_config(route_name = 'login', request_method = 'POST')
def login(request):
    """
    Handler for /login
    
    Attempt to authenticate the user with vCD
    Redirect to /machines on success
    Show homepage with error on failure
    """
    username = request.params['username']
    password = request.params['password']
    try:
        provider = vcloud.VCloudProvider(request.registry.settings['vcloud_endpoint'])
        request.vcd_session = provider.new_session(username, password)
        return HTTPSeeOther(location = request.route_url('machines'),
                            headers  = remember(request, username))
    except cloud.CloudServiceError as e:
        request.session.flash(str(e), 'error')
        request.vcd_session = None
    return HTTPSeeOther(location = request.route_url('home'))
            

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
    return HTTPSeeOther(location = request.route_url('home'),
                        headers = forget(request))

   
@view_config(route_name = 'catalogue',
             request_method = 'GET',
             renderer = 'templates/catalogue.jinja2', permission = 'view')
def catalogue(request):
    """
    Handler for /catalogue
    
    User must be logged in
    
    Shows the catalogue items available to the user
    """
    items = []
    try:
        items = request.vcd_session.list_images()
    # Convert some of the cloud service errors to appropriate HTTP errors
    except cloud.AuthenticationError:
        return HTTPUnauthorized()
    except cloud.PermissionsError:
        return HTTPForbidden()
    except cloud.NoSuchResourceError:
        return HTTPNotFound()
    except cloud.CloudServiceError as e:
        request.session.flash(str(e), 'error')
    return { 'items' : items }


@view_config(route_name = 'catalogue_item',
             request_method = 'GET',
             renderer = 'templates/catalogue_item.jinja2', permission = 'view')
def catalogue_item(request):
    """
    Handler for /catalogue_item/{id}
    
    User must be logged in
    
    Shows the details for the catalogue item
    """
    try:
        item = request.vcd_session.get_image(request.matchdict['id'])
    # Convert some of the cloud service errors to appropriate HTTP errors
    except cloud.AuthenticationError:
        return HTTPUnauthorized()
    except cloud.PermissionsError:
        return HTTPForbidden()
    except cloud.NoSuchResourceError:
        return HTTPNotFound()
    except cloud.CloudServiceError as e:
        request.session.flash(str(e), 'error')
        return HTTPSeeOther(location = request.route_url('catalogue'))
    return { 'item' : item }
   

@view_config(route_name = 'machines',
             request_method = 'GET',
             renderer = 'templates/machines.jinja2', permission = 'view')
def machines(request):
    """
    Handler for /machines
    
    User must be logged in
    
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
    Handler for /machine/new
    
    User must be logged in
    
    GET: Shows a form to gather information required for provisioning
         image_id may be given as a request parameter, and is the ID of the catalog item to use
         If image_id is not given, user selects from a dropdown
    
    POST: Attempts to provision a machine with the given details
          If the provisioning is successful, redirect to /machines with a success message
          If the provisioning is successful but NATing fails, redirect to /machines
          with an error message
          If the provisioning fails, show form with error message
    """
    try:
        # For the form fields, we use dict objects to capture error info
        # image id can be given as a get parameter, so we fetch it here
        image_id = request.params.get('image_id', '')
        image_field = { 'value' : image_id, 'error' : False }
        name_field  = { 'value' : '', 'error' : False }
        desc_field  = { 'value' : '', 'error' : False }
        # If we have a POST request, try and provision a machine with the info
        if request.method == 'POST':
            name = request.params.get('name', '')
            name_field['value'] = name
            description = request.params.get('description', '')
            desc_field['value'] = description
            try:
                machine = request.vcd_session.provision_machine(image_id, name, description)
                request.session.flash('Machine provisioned successfully', 'success')
                return HTTPSeeOther(location = request.route_url('machines'))
            # Catch more specific provisioning errors here
            except (cloud.DuplicateNameError, cloud.BadRequestError) as e:
                # Assume bad request errors are down to the name, since it is the only
                # required field
                request.session.flash(str(e), 'error')
                name_field['error'] = True
            except cloud.ProvisioningError as e:
                request.session.flash(str(e), 'error')
        # Inject the items from the catalogue as choices for image
        image_field['choices'] = request.vcd_session.list_images()
        return {
            'image'       : image_field,
            'name'        : name_field,
            'description' : desc_field,
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


@view_config(route_name = 'machine',
             request_method = 'GET',
             renderer = 'templates/machine.jinja2', permission = 'view')
def machine(request):
    """
    Handler for /machine/{id}
    
    User must be logged in
    
    Shows details for the machine
    """
    try:
        machine = request.vcd_session.get_machine(request.matchdict['id'])
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
    return { 'machine' : machine }


@view_config(route_name = 'machine_action',
             request_method = 'POST', permission = 'edit')
def machine_action(request):
    """
    Handler for /machine/{id}/action
    
    User must be logged in
    
    Attempt to perform the specified action
    Redirect to machines with a suitable success or failure message
    """
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
