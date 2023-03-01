# Setting up a local development environment

First, check out the code:

```sh
git clone https://github.com/stackhpc/azimuth.git
cd azimuth
# Switch to the required branch
```

### REST API

The API requires a recent version of Python 3, which you must first install.

Then create and activate a new virtual environment and install the API project:

```sh
python -m venv ./venv
source ./venv/bin/activate
pip install git+https://github.com/cedadev/django-settings-object.git
pip install git+https://github.com/stackhpc/easykube.git
pip install git+https://github.com/cedadev/jasmin-ldap.git
pip install git+https://github.com/stackhpc/rackit.git
pip install -e ./api
```

Install the local settings:

```sh
cp api/azimuth_site/settings.py-local api/azimuth_site/settings.py
```

Modify the settings to match your cloud, then run the development server:

```sh
python api/manage.py runserver
```

The API will then be available at http://localhost:8000/api.

### React UI

Once you have the development version of the API up, you can install a development version
of the UI.

To install and run the UI, you will need recent versions of [Node](https://nodejs.dev/) and
[yarn](https://yarnpkg.com/) installed.

Install the dependencies using `yarn`:

```sh
yarn --cwd ./ui install --frozen-lockfile
```

Then start the development server:

```sh
yarn --cwd ./ui serve 
```

This will start the Azimuth UI at `http://localhost:3000`. The development server will
proxy API requests to `http://localhost:8000` so that the UI and API appear at the same
address, as they will when deployed in production.
