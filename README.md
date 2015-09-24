# jasmin-portal

Web portal for administration of organisations in the JASMIN Scientific Cloud.


## Requirements

The reference platform is a fully patched CentOS 6.x installation with Python 3.3
and PostgreSQL.

The reason we use Python 3.3 is that it is the latest version for which a `mod_wsgi`
package currently exists in the IUS Community repository.

To install Python 3.3 in CentOS 6.x, the following can be used:

```sh
sudo yum install https://dl.iuscommunity.org/pub/ius/stable/CentOS/6/x86_64/ius-release-1.0-14.ius.centos6.noarch.rpm
sudo yum install python33 python33-devel
```

To install and configure PostgreSQL, use the following:

```sh
sudo yum install postgresql postgresql-devel postgresql-server
sudo service postgresql initdb
sudo chkconfig postgresql on
sudo service postgresql start
```
    

## Creating a venv

To ensure that you are using the correct Python version and libraries, it is recommended to
use a [Python virtual environment (venv)](https://docs.python.org/3/library/venv.html).

```sh
python3.3 -m venv --clear $PYENV
```
    
where `$PYENV` is the directory where the created venv will live (e.g. `~/jasmin-venv`).

`jasmin-portal` uses [pip](https://pypi.python.org/pypi/pip) to manage dependencies and installation.
To install pip in the venv, run:

```sh
wget https://bootstrap.pypa.io/get-pip.py -O - | $PYENV/bin/python
```

If you are behind a proxy, you need to tell pip about it so that it can fetch packages:

```sh
wget https://bootstrap.pypa.io/get-pip.py -O - | $PYENV/bin/python - --proxy="my-proxy.com:8080"
```

Once pip is installed, you can tell it about the proxy server via a configuration file:

```sh
cat <<EOF >> $PYENV/pip.conf
[global]
proxy = my-proxy.com:8080
EOF
```


## Developing

Installing the portal in development mode, via pip, ensures that dependencies are installed
and entry points are set up properly in the venv, but changes we make to the source code are
instantly picked up by the venv.

```sh
# Clone the repository
git clone https://github.com/cedadev/eos-portal.git jasmin-portal

# Install in editable (i.e. development) mode
#   NOTE: This will install the LATEST versions of any packages
#         This is what you want for development, as we should be keeping up to date!
$PYENV/bin/pip install -e jasmin-portal
```

Next, create a PostgreSQL database that is accessible by the user that you are
doing your development with:

```sh
sudo -Hi -u postgres createuser -DRS -w $USER
sudo -Hi -u postgres createdb -E UTF8 -O $USER -w jasminportal
```

This database should be populated with information for the catalogue items in your
vCloud Director instance.

Then copy `application.ini.example` to `application.ini` and adjust the settings
for your platform (see
http://docs.pylonsproject.org/docs/pyramid/en/1.5-branch/narr/environment.html).

You can then launch the portal using a development server. The following two lines are
equivalent, but the latter has the advantage that it can be used as a debug configuration
in PyDev, allowing breakpoints etc.

```sh
$PYENV/bin/pserve application.ini
$PYENV/bin/python jasmin_portal/__init__.py application.ini
```
    
The portal will then be available in a web browser at `127.0.0.1:6543`.

**NOTE:** The example configuration uses `wsgiref.simple_server`, which is not suitable for
anything other than development. However, because it is single-threaded, it can be used by the PyDev
debugger.


## Generating the API documentation

Once you have successfully installed the JASMIN portal code, you can generate and
view the API documentation:

```sh
cd doc
make clean html SPHINXBUILD=$PYENV/bin/sphinx-build
firefox _build/html/index.html
```


## Running the tests

To run the integration tests for the vCloud Director client, first copy `jasmin_portal/test/vcd_settings.py.example`
to `jasmin_portal/test/vcd_settings.py` and insert some credentials for a user in a test
vCloud Director organisation (not a production one!). Then run:

```sh
$PYENV/bin/python setup.py test
```

If the tests fail, you will need to log into vCloud Director manually and clean up any partially
created machines and any NAT and firewall rules associated with the machine.


## Deploying using Apache

CentOS 6.x comes with Apache pre-installed, but not activated. To run `jasmin-portal`, we will use `mod_wsgi`.
This can be installed from the IUS Community repository using:

```sh
sudo yum install python33-mod_wsgi
```

First, on your dev box, freeze the code and dependencies:

```sh
# Freeze the dependencies, omitting the jasmin portal project, and commit the requirements.txt
$PYENV/bin/pip freeze | grep -v jasmin > requirements.txt
git add requirements.txt
git commit -m "Freezing dependencies"
git push -u origin  # If you want to push the changes to Github

# Create a release tarball containing wheels for all the dependencies
$PYENV/bin/pip wheel --no-deps -r requirements.txt
$PYENV/bin/pip wheel --no-deps .
tar -czf jasmin-portal-bundle.tar.gz wheelhouse
rm -rf wheelhouse
```

Then move `jasmin-portal-bundle.tar.gz` to the server.

On the server, first create a new user to run the portal and own the PostgreSQL
database:

```sh
# Create the user with no home directory but with a group of their own
useradd -U -s /bin/bash jasminportal

# Add the user to PostgreSQL and create a database
sudo -Hi -u postgres createuser -DRS -w jasminportal
sudo -Hi -u postgres createdb -E UTF8 -O jasminportal -w jasminportal
```

Then create the required directories under `/var/www/jasmin-portal` and install the portal:

```sh
# Create a basic directory structure
sudo mkdir -p /var/www/jasmin-portal/conf /var/www/jasmin-portal/wsgi

# Create a venv (if you need to use a proxy, remember to use it)
sudo python3.3 -m venv --clear /var/www/jasmin-portal/venv
wget https://bootstrap.pypa.io/get-pip.py -O - | sudo /var/www/jasmin-portal/venv/bin/python

# Install the jasmin portal code and dependencies
tar -xzf jasmin-portal-bundle.tar.gz
sudo /var/www/jasmin-portal/venv/bin/pip install --force-reinstall --ignore-installed --upgrade --no-index --no-deps wheelhouse/*
```

Create `/var/www/jasmin-portal/conf/application.ini` and adjust the settings for your environment (see
http://docs.pylonsproject.org/docs/pyramid/en/1.5-branch/narr/environment.html and above).

Next, create the WSGI entry point at `/var/www/jasmin-portal/wsgi/portal.wsgi` containing the following:

```python
from pyramid.paster import get_app, setup_logging
ini_path = '/var/www/jasmin-portal/conf/application.ini'
setup_logging(ini_path)
application = get_app(ini_path, 'main')
```

Add the following to your Apache config file:

```
# This line should be outside any virtual hosts
WSGISocketPrefix /var/run/wsgi

# The following lines should be *inside* a virtual host
<Directory "/var/www/jasmin-portal/wsgi">
    Order allow,deny
    Allow from all
</Directory>

# Ensure HTTP authorisation header gets passed to WSGI app
WSGIPassAuthorization On

WSGIApplicationGroup %{GLOBAL}

WSGIProcessGroup jasmin

# Since we are using long-polling to connect to vCD, we need to specify a long timeout
WSGIDaemonProcess jasmin user=jasminportal group=jasminportal processes=2 threads=15 display-name=%{GROUP} shutdown-timeout=60 python-path=/var/www/jasmin-portal/venv/lib/python3.3/site-packages:/var/www/jasmin-portal/venv/lib64/python3.3/site-packages

WSGIScriptAlias / /var/www/jasmin-portal/wsgi/portal.wsgi
```

Then restart Apache:

```sh
sudo service httpd restart
```
