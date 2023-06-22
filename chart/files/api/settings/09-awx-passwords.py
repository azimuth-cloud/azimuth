import os

# Read the AWX password from an environment variable that is populated from the specified secret
AZIMUTH['AWX']['PASSWORD'] = os.environ['AWX_PASSWORD']
if 'AWX_ADMIN_PASSWORD' in os.environ:
    AZIMUTH['AWX']['ADMIN_PASSWORD'] = os.environ['AWX_ADMIN_PASSWORD']
