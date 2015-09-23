"""
This module provides catalogue management functionality for the JASMIN cloud portal.

It uses a combination of cloud services and an SQL database for management of
catalogue items and metadata. `SQLAlchemy <http://www.sqlalchemy.org/>`_ is used
for database access.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"


from collections import namedtuple

from sqlalchemy import Column, String, Text, Boolean
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.exc import NoResultFound
from pyramid_sqlalchemy import BaseObject, Session, metadata
import transaction as tx

from jasmin_portal.cloudservices import PermissionsError, NoSuchResourceError


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


class CatalogueMeta(BaseObject):
    """
    SQLAlchemy model for catalogue item metadata.
    """
    __tablename__ = "catalogue_meta"
    
    #: Uuid of catalogue item with the cloud provider.
    uuid          = Column('uuid', String(50), primary_key = True)
    #: Extended description of the catalogue item. Can contain HTML, or be empty.
    description   = Column('description', Text())
    #: Flag indicating whether machines provisioned using the catalogue item should
    #: have NAT and firewall rules applied to allow inbound traffic from the internet.
    allow_inbound = Column('allow_inbound', Boolean(), nullable = False)


class CatalogueItem(namedtuple('CatalogueItemProps',
                      ['uuid', 'name', 'description', 'allow_inbound', 'is_public'])):
    """
    Class representing a catalogue item.
    
    Information is aggregated from :py:class:`jasmin_portal.cloudservices.Image`
    and :py:class`CatalogueMeta` instances to form a complete view of a catalogue
    item.
    
    .. py:attribute:: uuid
    
        Uuid of catalogue item with the cloud provider.
        
    .. py:attribute:: name
    
        Name of the catalogue item.

    .. py:attribute:: description
    
        Extended description of the catalogue item. Can contain HTML, or be empty.
    
    .. py:attribute:: allow_inbound
    
        Flag indicating whether machines provisioned using the catalogue item should
        have NAT and firewall rules applied to allow inbound traffic from the internet.
    
    .. py:attribute:: is_public
    
        Flag indicating whether the catalogue item is public (accessible to all
        organisations) or private (accessible to this organisation only)
    """
    
    
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
    # Then create and save a metadata item in the database
    meta = CatalogueMeta(uuid = image.id,
                         description = description, allow_inbound = allow_inbound)
    sess = Session()
    sess.add(meta)
    tx.commit()
    # Construct the item to return
    return CatalogueItem(image.id, name, description, allow_inbound, image.is_public)


def delete_catalogue_item(request, uuid):
    """
    Deletes the catalogue item with the given uuid.
    
    :param request: Pyramid request
    :param uuid: The uuid of the catalogue item to delete
    :returns: True on success (raises on failure)
    """
    # First, delete the image in the cloud provider
    request.active_cloud_session.delete_image(uuid)
    # If that is successful, the image will no longer be available to the portal,
    # even if the metadata is still in the database
    # Hence we consider the operation as successful even if removal from the DB
    # fails
    try:
        Session().query(CatalogueMeta).filter(CatalogueMeta.uuid == uuid).\
            delete()
        tx.commit()
    except SQLAlchemyError:
        pass
    return True


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
    # Get the corresponding metadata records (note that these might not be in
    # the same order as the images...!)
    # Use an IN query so we get them all with one database call
    metas = set(Session().query(CatalogueMeta).\
                  filter(CatalogueMeta.uuid.in_([im.id for im in images])).\
                  all())
    items = []
    for image in images:
        meta = next((m for m in metas if m.uuid == image.id), None)
        # Skip items in the cloud but not in our database
        if not meta:
            continue
        metas.discard(meta)
        items.append(CatalogueItem(
            image.id, image.name, meta.description, meta.allow_inbound, image.is_public
        ))
    return items


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
        image = request.active_cloud_session.get_image(uuid)
        meta = Session().query(CatalogueMeta).\
                 filter(CatalogueMeta.uuid == uuid).one()
        return CatalogueItem(
            image.id, image.name, meta.description, meta.allow_inbound, image.is_public
        )
    except (NoResultFound, PermissionsError, NoSuchResourceError):
        return None
