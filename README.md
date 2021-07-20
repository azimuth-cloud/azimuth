# jasmin-cloud

The `jasmin-cloud` project provides a portal for the administration of tenancies in an
[OpenStack](https://www.openstack.org/) cloud.

It has two sub-components  - a REST API written in [Python](https://www.python.org/) using
the [Django REST framework](https://www.django-rest-framework.org/) and a UI written in
[React](https://reactjs.org/).

The code for both components, along with artifacts for building [Docker](https://www.docker.com/)
images and a [Helm chart](https://helm.sh/) for deploying to [Kubernetes](https://kubernetes.io/)
are included in this repository.

## Using the Helm chart

The Helm chart is stored in an OCI repository, which requires experimental features in
Helm 3 to be enabled. See https://helm.sh/docs/topics/registries/ for more information.

To see the available versions, please consult the repository on
[GitHub packages](https://github.com/orgs/stackhpc/packages/container/package/jasmin-cloud-chart).

```sh
helm chart pull ghcr.io/stackhpc/jasmin-cloud-chart:<version>
helm chart export ghcr.io/stackhpc/jasmin-cloud-chart:<version>
helm upgrade -i jasmin-cloud ./jasmin-cloud -f values.yaml
```

To see the available options, check the [chart's values.yaml](./chart/values.yaml).

## Setting up a local development environment

First, check out the code:

```sh
git clone https://github.com/stackhpc/jasmin-cloud.git
cd jasmin-cloud
# Switch to the required branch
```

### REST API

The API requires a recent version of Python 3, which you must first install.

Then create and activate a new virtual environment and install the API project:

```sh
python -m venv ./venv
source ./venv/bin/activate
pip install git+https://github.com/cedadev/django-settings-object.git#egg=settings_object
pip install git+https://github.com/cedadev/jasmin-ldap.git#egg=jasmin_ldap
pip install git+https://github.com/cedadev/rackit.git#egg=rackit
pip install -e ./api
```

Install the local settings:

```sh
cp api/jasmin_cloud_site/settings.py-local api/jasmin_cloud_site/settings.py
```

Modify the settings to match your cloud, then run the development server:

```sh
python api/manage.py runserver
```

The API will then be available at http://localhost:8000/api.

## React UI

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

This will start the JASMIN Cloud UI at `http://localhost:3000`. The development server will
proxy API requests to `http://localhost:8000` so that the UI and API appear at the same
address, as they will when deployed in production.
