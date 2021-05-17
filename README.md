# jasmin-cloud

The `jasmin-cloud` project provides an API for administration of tenancies in the JASMIN Cloud.

## Setting up a development environment

`jasmin-cloud` requires at least Python 3.7, so you must first ensure a suitable Python version is installed.

First, check out the code:

```sh
git clone https://github.com/cedadev/jasmin-cloud.git
cd jasmin-cloud
```

Create and activate a new virtual environment and install:

```sh
python -m venv ./venv
source ./venv/bin/activate
pip install git+https://github.com/cedadev/django-settings-object.git#egg=settings_object
pip install git+https://github.com/cedadev/jasmin-ldap.git#egg=jasmin_ldap
pip install git+https://github.com/cedadev/rackit.git#egg=rackit
pip install -e .
```

Install the local settings:

```sh
cp jasmin_cloud_site/settings.py-local jasmin_cloud_site/settings.py
```

Modify the settings to match your cloud, then run the development server:

```sh
python manage.py runserver
```

The API will then be available at http://localhost:8000/api.
