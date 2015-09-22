"""
This module provides catalogue management functionality for the JASMIN cloud portal.

It uses a combination of cloud services and an SQL database for management of
catalogue items and metadata. `SQLAlchemy <http://www.sqlalchemy.org/>`_ is used
for database access.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"


from sqlalchemy import Column, String, Text, Boolean
from sqlalchemy.orm.exc import NoResultFound
from pyramid_sqlalchemy import BaseObject, Session, metadata
import transaction


def setup(config, settings):
    """
    Configures the Pyramid application for catalogue management.
    
    :param config: Pyramid configurator
    :param settings: Settings array passed to Pyramid main function
    :returns: The updated configurator
    """
    # Make sure the database tables exist if not already present
    metadata.create_all()
    return config


class CatalogueItem(BaseObject):
    """
    SQLAlchemy model representing a catalogue item in the system.
    """
    __tablename__ = "catalogue_items"
    
    #: Uuid of catalogue item with the cloud provider.
    uuid          = Column('uuid', String(50), primary_key = True)
    #: Name of the catalogue item.
    name          = Column('name', String(200), nullable = False, unique = True)
    #: Extended description of the catalogue item. Can contain HTML, or be empty.
    description   = Column('description', Text())
    #: Flag indicating whether machines provisioned using the catalogue item should
    #: have NAT and firewall rules applied to allow inbound traffic from the internet.
    allow_inbound = Column('allow_inbound', Boolean(), nullable = False)
    
    
def catalogue_item_from_machine(request, machine, name, description, allow_inbound):
    """
    Adds a catalogue item using the given machine as a template.
    
    :param request: Pyramid request
    :param machine: The machine to use as a template
    :param name: The name of the new catalogue item
    :param description: Extended description of the new template
    :param allow_inbound: True if the template should allow inbound traffic from
                          the internet, False otherwise
    :returns: The created ``CatalogueItem``
    """ 
    # First, create the catalogue item in the cloud provider
    image = request.active_cloud_session.image_from_machine(machine.id, name, description)
    # Then create and save a the catalogue item in the database
    item = CatalogueItem(uuid = image.id, name = name,
                         description = description, allow_inbound = allow_inbound)
    with transaction.manager as tx:
        sess = Session()
        sess.add(item)
    return item


def available_catalogue_items(request):
    """
    Retrieves the catalogue items available to the active organisation for the
    given request.
    
    Access to the catalogue items is controlled by the cloud service (i.e. the
    cloud service is queried for the items available to the active organisation),
    but only catalogue items with an entry in the database are returned.
    
    :param request: Pyramid request
    :returns: List of catalogue items
    """
    # Get the images from the cloud session (let errors bubble)
    images = request.active_cloud_session.list_images()
    # Get the corresponding database records
    # Use an IN query so we get them all with one database call
    return Session().query(CatalogueItem).\
               filter(CatalogueItem.uuid.in_([im.id for im in images])).\
               all()


def find_by_uuid(request, uuid):
    """
    Finds a catalogue item by uuid, assuming that the active organisation for the
    given request has access.
    
    If no item can be found or the active organisation does not have access,
    ``None`` is returned.
    
    :param request: Pyramid request
    :param uuid: Uuid of the catalogue item to find
    :returns: Catalogue item or ``None``
    """
    try:
        return Session().query(CatalogueItem).\
                   filter(CatalogueItem.uuid == uuid).\
                   one()
    except NoResultFound:
        return None
