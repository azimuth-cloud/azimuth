"""
Application-specific settings.
"""

# Remove unnecessary context processors to maybe reduce some overhead
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
            ],
        },
    },
]

INSTALLED_APPS = [
    'django.contrib.staticfiles',
    'cloud_auth',
    'jasmin_cloud',
    'rest_framework',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'cloud_auth.middleware.SessionTokenMiddleware',
    'jasmin_cloud.middleware.CleanupProviderMiddleware',
]

ROOT_URLCONF = 'jasmin_cloud_site.urls'

WSGI_APPLICATION = 'jasmin_cloud_site.wsgi.application'

# Use cookie sessions so that we don't need a database
SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'

REST_FRAMEWORK = {
    'VIEW_DESCRIPTION_FUNCTION': 'jasmin_cloud.views.get_view_description',
    'DEFAULT_AUTHENTICATION_CLASSES': ['jasmin_cloud.authentication.TokenHeaderAuthentication'],
    'UNAUTHENTICATED_USER': None,
}

# Javascript must be able to access the CSRF cookie
CSRF_COOKIE_HTTPONLY = False
