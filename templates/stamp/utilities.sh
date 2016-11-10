#!/bin/bash

# Copyright (c) Microsoft Corporation. All Rights Reserved.
# Licensed under the MIT license. See LICENSE file on the project webpage for details.

#############################################################################
# Log a message
#############################################################################

log()
{
    # By default, we'd like logged messages to be sent to syslog. 
    # We also want to enable logging for error messages
    
    # $1 - the message to log
    # $2 - flag for error message = 1 (only presence test)
    
    TIMESTAMP=`date +"%D %T"`
    
    # check if this is an error message
    LOG_MESSAGE="${TIMESTAMP} :: $1"
    
    if [ ! -z $2 ]; then
        # stderr logging
        LOG_MESSAGE="${TIMESTAMP} :: [ERROR] $1"
        echo $LOG_MESSAGE >&2
    else
        echo $LOG_MESSAGE
    fi
    
    # send the message to syslog
    logger $1
}

#############################################################################
# Apply memory configuration for the current server 
#############################################################################

tune_memory()
{
    log "Disabling THP (transparent huge pages)"

    # Disable THP on a running system
    echo never > /sys/kernel/mm/transparent_hugepage/enabled
    echo never > /sys/kernel/mm/transparent_hugepage/defrag

    # Disable THP upon reboot
    cp -p /etc/rc.local /etc/rc.local.`date +%Y%m%d-%H:%M`
    sed -i -e '$i \ if test -f /sys/kernel/mm/transparent_hugepage/enabled; then \
              echo never > /sys/kernel/mm/transparent_hugepage/enabled \
          fi \ \
        if test -f /sys/kernel/mm/transparent_hugepage/defrag; then \
           echo never > /sys/kernel/mm/transparent_hugepage/defrag \
        fi \
        \n' /etc/rc.local
}

#############################################################################
# Apply system tuning for the current server 
#############################################################################

tune_system()
{
    log "Adding local machine for IP address resolution"

    # Add local machine name to the hosts file to facilitate IP address resolution
    if grep -q "${HOSTNAME}" /etc/hosts
    then
      log "${HOSTNAME} was found in /etc/hosts"
    else
      log "${HOSTNAME} was not found in and will be added to /etc/hosts"
      # Append it to the hosts file if not there
      echo "127.0.0.1 ${HOSTNAME}" >> /etc/hosts
      log "Hostname ${HOSTNAME} added to /etc/hosts"
    fi    
}

#############################################################################
# Configure Blob storage attached to current server 
#############################################################################

configure_datadisks()
{
    # Stripe all of the data 
    log "Formatting and configuring the data disks"

    # vm-disk-utils-0.1 can install mdadm which installs postfix. The postfix
    # installation cannot be made silent using the techniques that keep the
    # mdadm installation quiet: a) -y AND b) DEBIAN_FRONTEND=noninteractive.
    # Therefore, we'll install postfix early with the "No configuration" option.
    echo "postfix postfix/main_mailer_type select No configuration" | sudo debconf-set-selections
    sudo apt-get install -y postfix

    bash ./vm-disk-utils-0.1.sh -b $DATA_DISKS -s
}

#############################################################################
# Install GIT client
#############################################################################

install-git()
{
    if type git >/dev/null 2>&1; then
        log "Git already installed"
    else
        log "Installing Git Client"
        apt-get install -y git
    fi
}

#############################################################################
# Install Mongo Shell
#############################################################################

install-mongodb-shell()
{
    if type mongo >/dev/null 2>&1; then
        log "MongoDB Shell is already installed"
    else
        log "Installing MongoDB Shell"
        
        PACKAGE_URL=http://repo.mongodb.org/apt/ubuntu
        SHORT_RELEASE_NUMBER=$(lsb_release -rs)
        SHORT_CODENAME=`lsb_release -sc`

        if (( $(echo "$SHORT_RELEASE_NUMBER > 16" |bc -l) ))
        then
            apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv EA312927
            echo "deb ${PACKAGE_URL} "${SHORT_CODENAME}"/mongodb-org/3.2 multiverse" | tee /etc/apt/sources.list.d/mongodb-org-3.2.list
        else
            apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv 7F0CEB10
            echo "deb ${PACKAGE_URL} "${SHORT_CODENAME}"/mongodb-org/3.0 multiverse" | tee /etc/apt/sources.list.d/mongodb-org-3.0.list
        fi

        apt-get update
        apt-get install -y mongodb-org-shell
    fi
}

#############################################################################
# Install Mysql Client
#############################################################################

install-mysql-client()
{
    if type mysql >/dev/null 2>&1; then
        log "Mysql Client is already installed"
    else
        log "Installing Mysql Client"
        apt-get install -y mysql-client-core*
    fi
}