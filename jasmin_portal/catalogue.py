"""
Catalogue management functionality for the JASMIN cloud portal

Uses a combination of cloud services and an SQL database for management of catalogue
items and metadata
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"


from sqlalchemy import Column, String, Text, Boolean
from sqlalchemy.orm.exc import NoResultFound
from pyramid_sqlalchemy import BaseObject, Session, metadata


def setup(config, settings):
    """
    Given a pyramid configurator and a settings dictionary, configure the app
    for catalogue management
    
    :param config: Pyramid configurator
    :param settings: Settings array passed to Pyramid main function
    """
    # Make sure the database tables exist if not already present
    metadata.create_all()
    return config


class CatalogueItem(BaseObject):
    """
    Represents a catalogue item in the system
    
    The uuid is the uuid of the catalogue item in the cloud provider
    
    Access is controlled via the cloud provider, i.e. a user can only retrieve
    items that they can access via the cloud provider, so there are no explicit
    links to organisations in this model
    """
    __tablename__ = "catalogue_items"
    
    uuid          = Column('uuid', String(50), primary_key = True)
    name          = Column('name', String(200), nullable = False, unique = True)
    description   = Column('description', Text())
    allow_inbound = Column('allow_inbound', Boolean(), nullable = False)


def available_catalogue_items(request):
    """
    Gets the catalogue items available to the active organisation for the given
    request
    
    :param request: Pyramid request
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
    given request has access
    
    If no item can be found, None is returned
    
    :param request: Pyramid request
    :param uuid: Uuid of the catalogue item to find
    """
    try:
        return Session().query(CatalogueItem).\
                   filter(CatalogueItem.uuid == uuid).\
                   one()
    except NoResultFound:
        return None
