# jasmin-portal

Web portal for administration of organisations in the JASMIN Scientific Cloud.


## Requirements

The reference platform is a fully patched CentOS 6.x installation with Python 3.4.

To install Python 3.4 in CentOS 6.x, the following can be used:

    $ yum install https://dl.iuscommunity.org/pub/ius/stable/CentOS/6/x86_64/ius-release-1.0-14.ius.centos6.noarch.rpm
    $ yum install python34u python34u-devel python34u-pip
    

## Creating a venv

To ensure that you are using the correct Python version and libraries, it is recommended to
use a [Python virtual environment (venv)](https://docs.python.org/3/library/venv.html).

    $ python3.4 -m venv --clear $PYENV
    
where `$PYENV` is the directory where the created venv will live (e.g. `~/jasmin-venv`).


## Developing

Installing the portal in development mode, via setuptools, ensures that dependencies are installed
and entry points are set up properly in the venv, but instead of copying files to `site-packages`
it creates `egg-link` files that act like symbolic links. This ensures that changes we make to
the source code are instantly picked up by the venv.

    # Activate the venv
    $ source $PYENV/bin/activate
    
    # Install the portal project in development mode
    ($PYENV) $ python setup.py develop

To run the portal, you first need to copy `example.ini` to `development.ini` and adjust the
settings for your platform. You can then launch the portal using a development server:

    # Activate the venv
    $ source $PYENV/bin/activate
    
    # Start the portal web server
    ($PYENV) $ pserve development.ini
    
The portal will then be available in a web browser at `127.0.0.1:6543`.


## Running the tests

To run the integration tests for the vCloud Director client, first copy `jasmin_portal/test/vcd_settings.py.example` to `jasmin_portal/test/vcd_settings.py` and insert some credentials for a user in a test vCloud Director organisation (not a production one!). Then run:

    # Activate venv
    $ source $PYENV/bin/activate
    
    # Run the tests
    ($PYENV) $ python setup.py -q test

If the tests fail, you will need to log into vCloud Director manually and clean up any partially created machines and any NAT and firewall rules associated with the machine.
