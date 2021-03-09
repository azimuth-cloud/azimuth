import os
from jasmin_cloud.provider import openstack
from jasmin_cloud.provider.cluster_engine import awx, mock
from jasmin_cloud.keystore import dummy

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if True:
    cluster_engine = awx.Engine(
        url="http://10.60.253.30:8888",
        username="admin",
        password="password",
        credential_type="openstack",
        verify_ssl="false",
    )
else:
    url = "https://raw.githubusercontent.com/cedadev/jasmin-appliances/master/ui-meta/{cluster_type}.yml"
    cluster_types = [
        mock.dto.ClusterType.from_yaml(v, url.format(cluster_type=v.lower()))
        for v in [
            "Identity",
            "Gluster",
            "NFS",
            "BeeGFS",
            "Slurm",
            "Kubernetes",
            "Pangeo",
        ]
    ]
    cluster_engine = Engine(cluster_types, "clusters_file.json")

JASMIN_CLOUD = {
    "AVAILABLE_CLOUDS": {
        "current": {
            "label": "Cloud Dashboard",
            "url": "http://10.60.253.117/dashboard",
        },
    },
    "TOKEN_COOKIE_SECURE": False,
    "CURRENT_CLOUD": "current",
    "PROVIDER": openstack.Provider(
        auth_url="https://cumulus.openstack.hpc.cam.ac.uk:5000/v3",
        cluster_engine=cluster_engine,
        net_device_owner="network:ha_router_replicated_interface",
    ),
    "SSH_KEY_STORE": dummy.KeyStore(
        key="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDQ/+ArQL72tvCFucr0iMezZ2sXgsZ4FTRgx9xdbW4rkoglS7DIw80NfUIx9x9sxo09bMzKMGjwKXR9LmOAsa7jUOfn45ksrUdlAlnmrskCVcC32Gc35lvD11OMke1cvFIaUCkS0VGYWF9aCkmG2yj90xSUf7G4lMpfKn2pjncJ66I/+L50m+DXTim/Zfax4NMMtPRk3O8uXeEk00qISjZevPo0x5XQBRPbLgFBXnkYLrJwu2n00AD5kFUgMELyB8KKFYIUv9KqUAG8OVQKHwgs+M11gxhMy1wEFW5yxROv6tENFCQbFvKjEsd3H9tNH5YNr2nBQfTQaZZIXmp+P6rj brtknr@MacBook"
    ),
}

# SECURITY WARNING: DO NOT USE THIS IN PRODUCTION
SECRET_KEY = "notsecret"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ["127.0.0.1"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "jasmin_cloud",
    "rest_framework",
]

SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"

SESSION_SAVE_EVERY_REQUEST = True

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "jasmin_cloud.middleware.provider_session",
]

ROOT_URLCONF = "jasmin_cloud_site.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "jasmin_cloud_site.wsgi.application"


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(BASE_DIR, "db.sqlite3"),
    }
}


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


LANGUAGE_CODE = "en-gb"

TIME_ZONE = "UTC"

USE_I18N = True

USE_L10N = True

USE_TZ = True


STATIC_URL = "/static/"


INTERNAL_IPS = ("127.0.0.1",)


REST_FRAMEWORK = {
    #'DEFAULT_PERMISSION_CLASSES': [],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "jasmin_cloud.authentication.TokenCookieAuthentication",
    ]
}

SPECTACULAR_SETTINGS = {
    "SCHEMA_PATH_PREFIX": r"/api",
    "SERVE_INCLUDE_SCHEMA": False,
}

LOGGING = {
    "version": 1,
    "formatters": {
        "verbose": {
            "format": "%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s"
        },
        "simple": {"format": "%(levelname)s %(message)s"},
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        "file": {
            "level": "DEBUG",
            "class": "logging.FileHandler",
            "filename": "logging.log",
            "formatter": "simple",
        },
    },
    "loggers": {
        "jasmin_cloud": {
            "handlers": ["file"],
            "level": "DEBUG",
            "propagate": True,
        },
        "jasmin_cloud_site": {
            "handlers": ["file"],
            "level": "DEBUG",
            "propagate": True,
        },
        "django": {
            "handlers": ["file"],
            "level": "INFO",
            "propagate": True,
        },
    },
}

if DEBUG:
    for logger in LOGGING["loggers"]:
        LOGGING["loggers"][logger]["handlers"] = ["console"]
