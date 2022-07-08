from .core import Connection, ServiceNotSupported
# Import the modules for each of the services
from . import block_store, coe, compute, identity, image, network, orchestration
