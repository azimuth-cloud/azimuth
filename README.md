# eos-portal
Portal server for Cloudhands-EOS system.

# Quickstart for Ubuntu 14.04

 $ virtualenv ~/eoscloud/py3venv -p /usr/bin/python3

 $ ~/eoscloud-venv/bin/python setup.py develop

 $ ~/eoscloud-venv/bin/pserve development.ini
 
# Notes

This assumes you want to develop the system.  For production, follow a
similar path but do it in a dedicated account and use '... setup.py install'.

