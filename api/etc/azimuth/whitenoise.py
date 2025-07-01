"""
Modify settings to serve static files using whitenoise.
"""

_SECURITY_MIDDLEWARE = "django.middleware.security.SecurityMiddleware"
_WHITENOISE_MIDDLEWARE = "whitenoise.middleware.WhiteNoiseMiddleware"

# Make sure MIDDLEWARE is a list, not a tuple
MIDDLEWARE = list(globals().get("MIDDLEWARE", []))
# As per the docs, inject the whitenoise middleware after the security middleware
try:
    index = MIDDLEWARE.index(_SECURITY_MIDDLEWARE)
except ValueError:
    index = -1
MIDDLEWARE.insert(index + 1, _WHITENOISE_MIDDLEWARE)

# Always use the staticfiles location rather than using finders, even when DEBUG is True
WHITENOISE_USE_FINDERS = False
