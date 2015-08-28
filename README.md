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

To run the portal, you first need to copy `example.ini` to `development.ini` and adjust the
settings for your platform (see http://docs.pylonsproject.org/docs/pyramid/en/1.5-branch/narr/environment.html).

You also need to copy `catalogue.json.example` to `catalogue.json` and populate it with information for the catalogue items in your vCloud Director instance. You should then point to this file in `development.ini`. If a catalogue item is in vCloud Director but not in `catalogue.json`, you can still deploy a VM from it, but the portal will never attempt to apply any NAT or firewall rules for the machine. 

You can then launch the portal using a development server:

```sh
# The following two lines are equivalent
# The latter has the advantage that it can be used as a debug configuration in PyDev, allowing breakpoints etc.
$PYENV/bin/pserve development.ini
$PYENV/bin/python jasmin_portal/__init__.py development.ini
```
    
The portal will then be available in a web browser at `127.0.0.1:6543`.

**NOTE:** The example configuration uses `wsgiref.simple_server`, which is not suitable for
anything other than development. However, because it is single-threaded, it can be used by the PyDev
debugger.


## Running the tests

To run the integration tests for the vCloud Director client, first copy `jasmin_portal/test/vcd_settings.py.example`
 to `jasmin_portal/test/vcd_settings.py` and insert some credentials for a user in a test vCloud Director
organisation(not a production one!). Then run:

```sh
$PYENV/bin/python setup.py test
```

If the tests fail, you will need to log into vCloud Director manually and clean up any partially
created machines and any NAT and firewall rules associated with the machine.


## Deploying into a staging environment using Apache

CentOS 6.x comes with Apache pre-installed, but not activated. To run `jasmin-portal`, we will use `mod_wsgi`.
This can be installed from the IUS Community repository using:

```sh
sudo yum install python33-mod_wsgi
```

The first thing to do is get a frozen list of dependencies from your development venv that you know the current code works with:

```sh
$PYENV/bin/pip freeze | grep -v jasmin > requirements.txt
```

Deploying `jasmin-portal` in production should be done using a dedicated account. To create an account
and a suitable directory structure, use the following:

```sh
# Create a new user
sudo useradd -MU -s /bin/bash jasmin
sudo install -d /home/jasmin -o jasmin -g jasmin -m 755

# Create a venv (if you need to use a proxy, remember to use it)
sudo -iHu jasmin python3.3 -m venv --clear /home/jasmin/venv
wget https://bootstrap.pypa.io/get-pip.py -O - | sudo -iHu jasmin /home/jasmin/venv/bin/python

# Install the requirements from requirements.txt
cat requirements.txt | sudo -iHu jasmin tee requirements.txt > /dev/null
sudo -iHu jasmin /home/jasmin/venv/bin/pip install -r requirements.txt

# Install the HEAD of the master branch of the portal
sudo -iHu jasmin /home/jasmin/venv/bin/pip install --no-deps git+https://github.com/cedadev/eos-portal.git@master

# Create directories to act as the config, document root and WSGI script directories for Apache
sudo -iHu jasmin mkdir -p /home/jasmin/www/conf /home/jasmin/www/root /home/jasmin/www/wsgi
```

Next, create a `production.ini` and a `catalogue.json` and adjust the settings for a production environment on your platform (see http://docs.pylonsproject.org/docs/pyramid/en/1.5-branch/narr/environment.html). See above for more info. Then copy them to `/home/jasmin/www/conf`:

```sh
cat production.ini | sudo -iHu jasmin tee /home/jasmin/www/conf/production.ini > /dev/null
cat catalogue.json | sudo -iHu jasmin tee /home/jasmin/www/conf/catalogue.json > /dev/null
```

Now, we need to set up our WSGI entry point. Create a file called `portal.wsgi` containing the following:

```python
from pyramid.paster import get_app, setup_logging
ini_path = '/path/to/production.ini'
setup_logging(ini_path)
application = get_app(ini_path, 'main')
```

