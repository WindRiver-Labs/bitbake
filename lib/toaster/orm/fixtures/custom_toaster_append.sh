#!/bin/sh

# Copyright (C) 2017 Wind River Systems, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA

# This extends Toaster startup/shutdown to manage the anspass environment

verbose=0
if [ $verbose -ne 0 ] ; then
    echo "custom_toaster_append.sh:$*"
fi

CWD=`pwd`
TOASTER_ANSPASS=${TOASTER_DIR}/.toaster_anspass

if [ -z `which anspass` ] ; then
    echo "ERROR: environment is missing anspass tools"
    return 1
fi

if [ "web_start_postpend" = "$1" ] ; then
    # is there an anspass environment?
    if [  ! -d $TOASTER_DIR/bin/.anspass ] ; then
        return 0
    fi
    cd $TOASTER_DIR
    . wrlinux-9/data/environment.d/setup_anspass
    anspass_setup
    if [ -z "$ANSPASS_TOKEN" ] ; then
        echo "...retry anspass setup..."
        sleep 5
        anspass_setup
    fi
    cd $CWD
    if [ -z "$ANSPASS_TOKEN" ] ; then
        echo "ERROR: could not start anspass. Restart Toaster in a moment."
        return 1
    fi
    echo "ANSPASS_TOKEN=$ANSPASS_TOKEN"  > $TOASTER_ANSPASS
    echo "ANSPASS_PATH=$ANSPASS_PATH"   >> $TOASTER_ANSPASS
    echo "SSH_ASKPASS=$SSH_ASKPASS"     >> $TOASTER_ANSPASS
    echo "GIT_ASKPASS=$GIT_ASKPASS"     >> $TOASTER_ANSPASS
    return 0
fi

if [ "web_stop_postpend" = "$1" ] ; then
    # is there an active Toaster anspass environment?
    if [  ! -d $TOASTER_DIR/bin/.anspass -o ! -f $TOASTER_ANSPASS ] ; then
        return 0
    fi
    cd $TOASTER_DIR
    . $TOASTER_ANSPASS
    export ANSPASS_TOKEN
    export ANSPASS_PATH
    . wrlinux-9/data/environment.d/setup_anspass
    anspass_stop
    rc=$?
    cd $CWD
    rm -f $TOASTER_ANSPASS
    return $rc
fi

