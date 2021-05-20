# Application definition
INSTALLED_APPS = [
    'django.contrib.staticfiles',
    'jasmin_cloud',
    'rest_framework',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'jasmin_cloud.middleware.provider_session',
]

ROOT_URLCONF = 'jasmin_cloud_site.urls'

WSGI_APPLICATION = 'jasmin_cloud_site.wsgi.application'

REST_FRAMEWORK = {
    'VIEW_DESCRIPTION_FUNCTION': 'jasmin_cloud.views.get_view_description',
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'jasmin_cloud.authentication.TokenCookieAuthentication',
    ],
    'UNAUTHENTICATED_USER': None,
}

# Javascript must be able to access the CSRF cookie
CSRF_COOKIE_HTTPONLY = False
