"""
Default settings, including security best practices.
"""

# All logging should go to stdout/stderr to be collected
import logging
import os

from django.core.management.utils import get_random_secret_key

# By default, don't run in DEBUG mode
DEBUG = False

# In a Docker container, ALLOWED_HOSTS is always '*' - let the proxy worry about hosts
ALLOWED_HOSTS = ['*']

# Make sure Django interprets the script name correctly if set
if 'SCRIPT_NAME' in os.environ:
    FORCE_SCRIPT_NAME = os.environ['SCRIPT_NAME']

# Security settings
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = 'DENY'
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Set a default random secret key
# This can be overridden by files included later if desired
SECRET_KEY = get_random_secret_key()

LOG_FORMAT = '[%(levelname)s] [%(asctime)s] [%(name)s:%(lineno)s] [%(threadName)s] %(message)s'
LOGGING = {
    'version' : 1,
    'disable_existing_loggers' : False,
    'formatters' : {
        'default' : {
            'format' : LOG_FORMAT,
        },
    },
    'filters' : {
        # Logging filter that only accepts records with a level < WARNING
        # This allows us to log level >= WARNING to stderr and level < WARNING to stdout
        'less_than_warning' : {
            '()': 'django.utils.log.CallbackFilter',
            'callback': lambda record: record.levelno < logging.WARNING,
        },
    },
    'handlers' : {
        'stdout' : {
            'class' : 'logging.StreamHandler',
            'stream' : 'ext://sys.stdout',
            'formatter' : 'default',
            'filters': ['less_than_warning'],
        },
        'stderr' : {
            'class' : 'logging.StreamHandler',
            'stream' : 'ext://sys.stderr',
            'formatter' : 'default',
            'level' : 'WARNING',
        },
    },
    'loggers' : {
        '' : {
            'handlers' : ['stdout', 'stderr'],
            'level' : 'DEBUG' if DEBUG else 'INFO',
            'propogate' : True,
        },
    },
}

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# By default, no databases are defined
DATABASES = {}

# Authentication settings
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# IMPORTANT: CookieStorage (and hence FallbackStorage, which is the default) interacts
#            badly with Chrome's prefetching, causing messages to be rendered twice
#            or not at all...!
MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'

# Default internationalization settings
LANGUAGE_CODE = 'en-gb'
TIME_ZONE = 'Europe/London'
USE_I18N = True
USE_L10N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
# Make sure to include the WSGI script name in the static URL
STATIC_URL = '{}/static/'.format(os.environ.get('SCRIPT_NAME', ''))
STATIC_ROOT = '/var/azimuth/staticfiles'
