"""
Modify settings to serve static files using whitenoise.
"""

_SECURITY_MIDDLEWARE = 'django.middleware.security.SecurityMiddleware'
_WHITENOISE_MIDDLEWARE = 'whitenoise.middleware.WhiteNoiseMiddleware'

# Make sure MIDDLEWARE is a list, not a tuple
MIDDLEWARE = list(globals().get('MIDDLEWARE', []))
# As per the docs, inject the whitenoise middleware after the security middleware
try:
    index = MIDDLEWARE.index(_SECURITY_MIDDLEWARE)
except ValueError:
    index = -1
MIDDLEWARE.insert(index + 1, _WHITENOISE_MIDDLEWARE)

# Use the whitenoise static file storage for caching, compression etc.
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
