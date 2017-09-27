#!/bin/bash

# Copyright (c) Microsoft Corporation. All Rights Reserved.
# Licensed under the MIT license. See LICENSE file on the project webpage for details.

# Rotates big logs

set -x

# Settings
    file_size_threshold=700000000     # Default to 700 megabytes
    mysql_user=root
    mysql_pass=
    large_partition=/datadisks/disk1
# Paths and file names.
    current_script_path="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

mysql_command_wrapper()
{
    command="$1"

    echo "`mysql -u $mysql_user -p$mysql_pass -se "$command"`"
}

invalid_mysql_settings()
{
    [[ -z $file_size_threshold ]] && return
    [[ -z $mysql_user ]] && return
    [[ -z $mysql_pass ]] && return
    [[ -z $large_partition ]] && return

    false
}

rotate_mysql_slow_log()
{
    # Disable slow logs before rotation.
    mysql_command_wrapper "set global slow_query_log=off"

    # Flush slow logs before rotation.
    mysql_command_wrapper "flush slow logs"

    # Compress
    file_suffix=$(date +"%Y-%m-%d_%Hh-%Mm-%Ss").tar.gz
    sudo tar -zcvf "$large_partition/$slowLogPath.$file_suffix" "$slowLogPath"

    # Truncate log
    echo -n > $slowLogPath

    # Enable slow logs after rotation.
    mysql_command_wrapper "set global slow_query_log=on"
}

needs_rotation()
{
    if invalid_mysql_settings ; then
        log "Missing mysql settings on $HOSTNAME"
        #todo:exit on error
        false
    fi

    # Is slow log enabled?
    # This will also prevent execution on machines without mysql
    isLoggingSlow=`mysql_command_wrapper "select @@slow_query_log" | tail -1`
    if (( $isLoggingSlow == 1 )) ; then
        # Get path mysql is writing the slow log to
        slowLogPath=`mysql_command_wrapper "select @@slow_query_log_file" | tail -1`

        # Get size of slow log
        slowLogSizeInBytes=`du $slowLogPath | tr '\t' '\n' | head -1`

        if [[ -n $slowLogSizeInBytes ]] && (( $slowLogSizeInBytes > $file_size_threshold )) ; then
            true
        else
            log "Nothing to do. Slow query logs are not large enough to rotate out yet."
            false
        fi
    else
        log "Nothing to do. MySql either isn't installed or slow query logs are not enabled on $HOSTNAME."
        false
    fi
}

###############################################
# START CORE EXECUTION
###############################################

# Update working directory
pushd $current_script_path

if [[ -z $mysql_pass ]] ; then
    shared="sharedOperations.sh"
    echo "Sourcing file $shared"
    source $shared || exit 1

    # Source utilities. Exit on failure.
    source_utilities || exit 1

    # Parse commandline arguments
    parse_args "$@"
fi

log "Starting mysql slow logs rotation."

# Script self-idenfitication
print_script_header

# Pre-conditionals
exit_if_limited_user

if needs_rotation ; then
    rotate_mysql_slow_log
    #todo: exit on error
    needs_rotation && exit 1
fi

# Restore working directory
popd
