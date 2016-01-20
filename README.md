# jasmin-cloud

Web portal for administration of virtual organisations in the JASMIN Scientific Cloud.


## Requirements

The reference platform is a fully patched CentOS 6.x installation with Python 3.5.

To install Python 3.5 in CentOS 6.x, the following can be used:

```sh
sudo yum install https://centos6.iuscommunity.org/ius-release.rpm
sudo yum install python35u python35u-devel
```

The JASMIN Cloud Portal uses metadata attached to items in vCloud Director to determine
the allowed operations. More information on this will follow in due course...


## Creating a venv

To ensure that you are using the correct Python version and libraries, it is recommended to
use a [Python virtual environment (venv)](https://docs.python.org/3/library/venv.html).

```sh
python3.5 -m venv --clear $PYENV
```

where `$PYENV` is the directory where the created venv will live (e.g. `~/jasmin-account-venv`).

`jasmin-cloud` uses [pip](https://pypi.python.org/pypi/pip), which is included
by default from Python 3.4, to manage dependencies and installation.


## Developing

Installing `jasmin-cloud` in development mode, via pip, ensures that dependencies are installed
and entry points are set up properly in the venv, but changes we make to the source code are
instantly picked up by the venv.

`jasmin-cloud` uses another JASMIN library - [jasmin-auth](https://github.com/cedadev/jasmin-common) -
for authentication, so we must install that first (note that the repository has been renamed as
`jasmin-common` due to pending changes to the package):

```sh
# Install jasmin-auth
wget -O jasmin-common.tar.gz https://github.com/cedadev/jasmin-common/archive/v0.1.tar.gz
tar -xzf jasmin-common.tar.gz
$PYENV/bin/pip install jasmin-common-0.1
```


```sh
# Clone the jasmin-cloud repository
git clone https://github.com/cedadev/jasmin-cloud.git

# Install in editable (i.e. development) mode
#   NOTE: This will install the LATEST versions of any packages
#         This is what you want for development, as we should be keeping up to date!
$PYENV/bin/pip install -e jasmin-cloud
```

Then copy `application.ini.example` to `application.ini` and adjust the settings
for your platform (see
http://docs.pylonsproject.org/docs/pyramid/en/1.5-branch/narr/environment.html).

You can then launch the portal using a development server:

```sh
$PYENV/bin/pserve application.ini
```

The portal will then be available in a web browser at `localhost:8080`.

**NOTE:** The example configuration uses `wsgiref.simple_server`, which is not suitable for
anything other than development. However, because it is single-threaded, it can be used by the PyDev
debugger.


## Generating the API documentation

Once you have successfully installed the JASMIN cloud portal code, you can generate
and view the API documentation:

```sh
cd doc
make clean html SPHINXBUILD=$PYENV/bin/sphinx-build
firefox _build/html/index.html
```


## Running the tests

To run the integration tests for the vCloud Director client, first copy
`jasmin_cloud/test/vcd_settings.py.example` to `jasmin_cloud/test/vcd_settings.py`
and modify the settings for a test vCloud Director organisation (not a production
one!). Then run:

```sh
$PYENV/bin/python setup.py test
```

If the tests fail, you will need to log into vCloud Director manually and clean
up any partially created machines and any NAT and firewall rules associated with
the machine.
