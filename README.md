# jasmin-portal

Web portal for administration of organisations in the JASMIN Scientific Cloud.


## Requirements

The reference platform is a fully patched CentOS 6.x installation with Python 3.3.

The reason we use Python 3.3 is that it is the latest version for which a `mod_wsgi`
package currently exists in the IUS Community repository.

To install Python 3.3 and pip in CentOS 6.x, the following can be used:

```sh
$ yum install https://dl.iuscommunity.org/pub/ius/stable/CentOS/6/x86_64/ius-release-1.0-14.ius.centos6.noarch.rpm
$ yum install python33 python33-devel
```
    

## Creating a venv

To ensure that you are using the correct Python version and libraries, it is recommended to
use a [Python virtual environment (venv)](https://docs.python.org/3/library/venv.html).

```sh
$ python3.3 -m venv --clear $PYENV
```
    
where `$PYENV` is the directory where the created venv will live (e.g. `~/jasmin-venv`).

To activate the venv, run:

```sh
$ source $PYENV/bin/activate
```

From now on, all commands in this document will assume that the venv is *active*.

`jasmin-portal` uses [setuptools](https://pypi.python.org/pypi/setuptools) manage dependencies and
installation. To install setuptools in the venv, run:

```sh
($PYENV) $ wget https://bootstrap.pypa.io/ez_setup.py -O - | python
```


## Developing

Installing the portal in development mode, via setuptools, ensures that dependencies are installed
and entry points are set up properly in the venv, but instead of copying files to `site-packages`
it creates `egg-link` files that act like symbolic links. This ensures that changes we make to
the source code are instantly picked up by the venv.

```sh
($PYENV) $ python setup.py develop
```

To run the portal, you first need to copy `example.ini` to `development.ini` and adjust the
settings for your platform. You can then launch the portal using a development server:

```sh
# The following two lines are equivalent
# The latter has the advantage that it can be used as a debug configuration in PyDev, allowing breakpoints etc.
($PYENV) $ pserve development.ini
($PYENV) $ python jasmin_portal/__init__.py development.ini
```
    
The portal will then be available in a web browser at `127.0.0.1:6543`.

**NOTE:** The example configuration uses `wsgiref.simple_server`, which is not suitable for
anything other than development. However, because it is single-threaded, it can be used by the PyDev
debugger.


## Running the tests

To run the integration tests for the vCloud Director client, first copy `jasmin_portal/test/vcd_settings.py.example` to `jasmin_portal/test/vcd_settings.py` and insert some credentials for a user in a test vCloud Director organisation (not a production one!). Then run:

```sh
($PYENV) $ python setup.py test
```

If the tests fail, you will need to log into vCloud Director manually and clean up any partially created machines and any NAT and firewall rules associated with the machine.

