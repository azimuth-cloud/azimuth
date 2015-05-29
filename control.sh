#!/bin/bash

set -u

## Control script for the EOS Cloud boost controller portal. ##

# While the components of the system all run separately as good little
# microservices, we want a master controller script to start and stop them
# and ensure that they are all set up in concert.

# This script lives in the eos-portal code as it's as good a place as any.

# You may configure settings in a file pointed to by $CONTROL_CONF, or else just
# use the defaults.  See deployment_notes.txt.

_WD="`dirname $0`"
_CONTROL_CONF="$_WD/control.conf"

CONTROL_CONF=${CONTROL_CONF:-$_CONTROL_CONF}
[ -e "$CONTROL_CONF" ] && source "$CONTROL_CONF"
WD="${WORKING_DIR:-$_WD/..}"
WD="`readlink -e "$WD"`"

# So assuming you just check out eos-db, eos-portal and eos-agents in the same folder
# and run with the default settings:
PY3VENV="`readlink -e "${PY3VENV:-$WD/py3venv}"`"
AGENT_WORKING_DIR="${AGENT_WORKING_DIR:-$WD/var/eos-agents}"
DB_WORKING_DIR="${DB_WORKING_DIR:-$WD/var/eos-db}"
PORTAL_WORKING_DIR="${PORTAL_WORKING_DIR:-$WD/var/eos-portal}"

# And assume we want to run production.ini for web services unless you say otherwise
INI_FLAVOUR="${INI_FLAVOUR:-production}"

# Start the services as whatever user owns their respective working
# directories.
for X in AGENT DB PORTAL ; do
    eval X_WORKING_DIR="\$${X}_WORKING_DIR"
    X_USER=`stat -c '%U' "$X_WORKING_DIR/."`
    eval ${X}_USER="$X_USER"

    # Ensure this is a real non-root user
    if [[ $(( 0`id -u $X_USER 2>/dev/null` + 0 )) == 0 ]] ; then
	echo "$X_WORKING_DIR must exist as a directory and not be owned by root."
	exit 1
    fi
done

# Some utility functions
check_root()
{
    if ! [ `id -u` = 0 ] ; then
	echo "This script probably needs to run as root"
	return 0
    fi
    return 0
}

make_shared_secret()
{
    #urandom is theoretically not as secure as random, but we're not doing
    #on-line banking here.
    head -c 42 /dev/urandom | base64
}

# A shared secret that the agents use to prove to the database they are legit.
# If 2-way verification is needed make a double secret.
make_secrets()
{
    a_ss=`make_shared_secret`
    t_ss=`make_shared_secret`

    ( umask 077

      #Database makes secure authtkt tokens
      #rm -f "$DB_WORKING_DIR"/token_secret
      echo "$t_ss" > "$DB_WORKING_DIR"/token_secret
      chown $DB_USER "$DB_WORKING_DIR"/token_secret

      #Database knows how to recognise agents
      #rm -f "$DB_WORKING_DIR"/agent_secret
      echo "$a_ss" > "$DB_WORKING_DIR"/agent_secret
      chown $DB_USER "$DB_WORKING_DIR"/agent_secret

      #Agents know how to talk to database
      rm -f "$AGENT_WORKING_DIR"/agent_secret
      echo "$a_ss" > "$AGENT_WORKING_DIR"/agent_secret
      chown $AGENT_USER "$AGENT_WORKING_DIR"/agent_secret

    )

    #echo "Starting with shared secret $a_ss and $d_ss"
}

clear_logs()
{
    for l in "${DB_WORKING_DIR}/server.log" "${PORTAL_WORKING_DIR}/server.log" \
	     "${AGENT_WORKING_DIR}/agents.log" ; do
	if [ -e "$l" ] ; then
	    true > "$l"
	fi
    done
    true
}

clear_pids()
{
    for p in "${DB_WORKING_DIR}/server.pid" "${PORTAL_WORKING_DIR}/server.pid" \
	     "${AGENT_WORKING_DIR}/controller.pid" ; do
	rm -f "$p"
    done
    true
}

dstart()
{
    echo Starting...
    make_secrets
    export authtkt_secretfile="`readlink -e "$DB_WORKING_DIR"/token_secret`"
    export agent_secretfile="`readlink -e "$DB_WORKING_DIR"/agent_secret`"

    DB_INI="${DB_WORKING_DIR}/${INI_FLAVOUR}.ini"
    if [ ! -e "$DB_INI" ] && [ -e "$WD/eos-db/${INI_FLAVOUR}.ini" ] ; then
       echo "$DB_INI not found - linking to $WD/eos-db/${INI_FLAVOUR}.ini"
       target="`readlink -e "$WD/eos-db/${INI_FLAVOUR}.ini"`"
       #Note this needs the coreutils from 14.04 for ln -r
       ( cd "${DB_WORKING_DIR}" && ln -rs "$target" . )
    fi

    #sudo -Hu "$DB_USER" "$PY3VENV"/bin/pserve ${DB_WORKING_DIR}/${INI_FLAVOUR}.ini &
    #start-stop-daemon -p ${DB_WORKING_DIR}/server.pid -u $DB_USER -c $DB_USER -x "$PY3VENV"/bin/pserve -- "$DB_INI"
    "$PY3VENV"/bin/pserve --daemon --user=$DB_USER \
	--pid-file="${DB_WORKING_DIR}/server.pid" \
	--log-file="${DB_WORKING_DIR}/server.log" \
	"${DB_WORKING_DIR}/${INI_FLAVOUR}.ini"

    ################################
    # Fire up the portal

    PORTAL_INI="${PORTAL_WORKING_DIR}/${INI_FLAVOUR}.ini"
    if [ ! -e "$PORTAL_INI" ] && [ -e "$WD/eos-portal/${INI_FLAVOUR}.ini" ] ; then
       echo "$PORTAL_INI not found - linking to $WD/eos-portal/${INI_FLAVOUR}.ini"
       target="`readlink -e "$WD/eos-portal/${INI_FLAVOUR}.ini"`"
       #Note this needs the coreutils from 14.04 for ln -r
       ( cd "${PORTAL_WORKING_DIR}" && ln -rs "$target" . )
    fi
    "$PY3VENV"/bin/pserve --daemon --user=$PORTAL_USER \
	--pid-file="${PORTAL_WORKING_DIR}/server.pid" \
	--log-file="${PORTAL_WORKING_DIR}/server.log" \
	"${PORTAL_WORKING_DIR}/${INI_FLAVOUR}.ini"

    # Wait 3 seconds.  Yes, I know, horrible hack...
    # But the consequence of not waiting is just a warning in the agent log.
    sleep 3

    #################################
    # Fire up the agent herder.
    # I've not built in daemon functionality to it
    # yet so just use start-stop-daemon with the -b option

    start-stop-daemon -CbS -mp ${AGENT_WORKING_DIR}/controller.pid -u $AGENT_USER -c $AGENT_USER \
	-x "$PY3VENV"/bin/python -- "$WD/eos-agents/eos_agents/controller.py" \
	-s "$AGENT_WORKING_DIR"/agent_secret >>"${AGENT_WORKING_DIR}/agents.log" 2>&1

}

dstop()
{
    echo Stopping...

    # Stop the agents
    start-stop-daemon -K -s TERM -p ${AGENT_WORKING_DIR}/controller.pid -u $AGENT_USER -c $AGENT_USER \
	-x "$PY3VENV"/bin/python

    # Stop the portal
    "$PY3VENV"/bin/pserve --stop-daemon --user=$PORTAL_USER \
	--pid-file="${PORTAL_WORKING_DIR}/server.pid"

    # Stop the DB
    "$PY3VENV"/bin/pserve --stop-daemon --user=$DB_USER \
	--pid-file="${DB_WORKING_DIR}/server.pid"

}


case "${1:-help}" in
    freshstart)
	clear_logs && dstart
	;;
    start | stop )
	check_root && d$1
	;;
    restart)
	check_root && {	dstop ; dstart ; }
	;;
    *)
	echo "Usage: $0 start|stop|restart"
	;;
esac

