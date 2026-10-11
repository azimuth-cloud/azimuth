# Import the modules for each of the services
from . import (
    block_store,  # noqa: F401
    coe,  # noqa: F401
    compute,  # noqa: F401
    identity,  # noqa: F401
    image,  # noqa: F401
    network,  # noqa: F401
    orchestration,  # noqa: F401
    share,  # noqa: F401
)
from .core import Connection, ServiceNotSupported  # noqa: F401
