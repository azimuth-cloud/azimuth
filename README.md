# jasmin-portal

Web portal for administration of organisations in the JASMIN Scientific Cloud.


## Requirements

The reference platform is a fully patched CentOS 6.x installation with Python 3.3.

The reason we use Python 3.3 is that it is the latest version for which a `mod_wsgi`
package currently exists in the IUS Community repository.

To install Python 3.3 and pip in CentOS 6.x, the following can be used:

```sh
sudo yum install https://dl.iuscommunity.org/pub/ius/stable/CentOS/6/x86_64/ius-release-1.0-14.ius.centos6.noarch.rpm
sudo yum install python33 python33-devel
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
$PYENV/bin/pip install -e jasmin-portal
```

To run the portal, you first need to copy `application.ini.example` to `application.ini`
and adjust the settings for your platform (see
http://docs.pylonsproject.org/docs/pyramid/en/1.5-branch/narr/environment.html).

You also need to copy `catalogue.json.example` to `catalogue.json` and populate it with
information for the catalogue items in your vCloud Director instance. You should then point
to this file in `application.ini`. If a catalogue item is in vCloud Director but not in
`catalogue.json`, you can still deploy a VM from it, but the portal will never attempt
to apply any NAT or firewall rules for the machine.

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

First, freeze the code and dependencies from the development venv:

```sh
# Freeze the dependencies, omitting the jasmin portal project
$PYENV/bin/pip freeze | grep -v jasmin > requirements.txt

# Create a release tarball
#   This will create a tarball in the dist folder
$PYENV/bin/python setup.py sdist
```

Create the required directories under `/var/www/jasmin-portal` and install the code and dependencies:

```sh
# Create a basic directory structure
sudo mkdir -p /var/www/jasmin-portal/conf /var/www/jasmin-portal/wsgi

# Create a venv (if you need to use a proxy, remember to use it)
sudo python3.3 -m venv --clear /var/www/jasmin-portal/venv
wget https://bootstrap.pypa.io/get-pip.py -O - | sudo /var/www/jasmin-portal/venv/bin/python

# Install the requirements from requirements.txt
sudo /var/www/jasmin-portal/venv/bin/pip install -r /path/to/requirements.txt

# Install the jasmin portal code
sudo /var/www/jasmin-portal/venv/bin/pip install --no-deps /path/to/jasmin_portal-*.tar.gz
```

Create `/var/www/jasmin-portal/conf/application.ini` and `/var/www/jasmin-portal/conf/catalogue.json`
and adjust the settings for your environment (see
http://docs.pylonsproject.org/docs/pyramid/en/1.5-branch/narr/environment.html and above).

Next, create the WSGI entry point at `/var/www/jasmin-portal/wsgi/portal.wsgi` containing the following:

```python
from pyramid.paster import get_app, setup_logging
ini_path = '/var/www/jasmin-portal/conf/application.ini'
setup_logging(ini_path)
application = get_app(ini_path, 'main')
```

Then add the following to your Apache config file:

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
WSGIDaemonProcess jasmin processes=2 threads=15 display-name=%{GROUP} python-path=/var/www/jasmin-portal/venv/lib/python3.3/site-packages:/var/www/jasmin-portal/venv/lib64/python3.3/site-packages

WSGIScriptAlias / /var/www/jasmin-portal/wsgi/portal.wsgi
```

Then restart Apache:

```sh
sudo service httpd restart
```
