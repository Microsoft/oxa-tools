#!/bin/bash

# Copyright (c) Microsoft Corporation. All Rights Reserved.
# Licensed under the MIT license. See LICENSE file on the project webpage for details.

set -x

# Path to settings file provided as an argument to this script.
SETTINGS_FILE=

# From settings file
    USAGE_THRESHOLD_PERCENT=33 # Default, but updated later on.
# Paths and file names.
    CURRENT_SCRIPT_PATH="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
    UTILITIES_FILE=$CURRENT_SCRIPT_PATH/../../templates/stamp/utilities.sh
    SCRIPT_NAME=`basename "$0"`

help()
{
    echo
    echo "This script $SCRIPT_NAME will alert when a partition\'s"
    echo "usage percentage exceeds a threshold"
    echo
    echo "Options:"
    echo "  -s|--settings-file  Path to settings"
    echo
}

# Parse script parameters
parse_args()
{
    while [[ "$#" -gt 0 ]]
        do

        # Output parameters to facilitate troubleshooting
        echo "Option $1 set with value $2"

        case "$1" in
            -s|--settings-file)
                SETTINGS_FILE=$2
                shift # argument
                ;;
            -h|--help)
                help
                exit 2
                ;;
            *) # unknown option
                echo "ERROR. Option -${BOLD}$2${NORM} not allowed."
                help
                exit 2
                ;;
        esac

        shift # argument
    done
}

check_usage_threshold()
{
    # List of <usage>%<path>
    # for example:
    #   "4%/"
    #   "1%/datadisks/disk1"
    diskUsages=`df --output=ipcent,target | grep -v -i "use%\|mounted on" | tr -d ' '`

    # Iterate over list of <usage>%<path> pairs.
    while read diskUsage; do
        # Split usage and path
        diskUsageArray=(`echo "$diskUsage" | tr '%' ' '`)
        percentUsed=${diskUsageArray[0]}
        directoryPath=${diskUsageArray[1]}

        log "Directory $directoryPath on machine $HOSTNAME is using $percentUsed percent of available space"

        # Alert for unexpected values (indicative of possible errors in script and/or unexpected cases)
        if [[ -n ${diskUsageArray[2]} ]]; then
            log "Error in script $SCRIPT_NAME. Too many values"
            log "Extraneous value: ${diskUsageArray[2]}"

            continue
        fi
        if [[ -z $percentUsed ]] || [[ -z $directoryPath ]]; then
            log "Error in script $SCRIPT_NAME. Missing disk usage percentage or file system path"

            continue
        fi

        # Alert when threshold is exceeded.
        if (( $(echo "$percentUsed > $USAGE_THRESHOLD_PERCENT" | bc -l) )); then

            # Help clarify messaging by appending trailing slash to directory.
            if [[ $directoryPath != '/' ]] ; then
                directoryPath="${directoryPath}/"
            fi

            # Message
            
            log "Please cleanup this directory at your earliest convenience."
            log "The top subfolders or subfiles in $directoryPath are:"
            # Get list of subitems and filesize, sort them, grab top five, indent, newline.
            printf "`du -sh $directoryPath* 2> /dev/null | sort -h -r | head -n 5 | sed -e 's/^/  /'`"
            echo

        fi

        # Newline between exections
        echo

    done <<< "$diskUsages"
}

# Parse script argument(s)
parse_args $@

# log() and other functions
source_wrapper $UTILITIES_FILE

# Script self-idenfitication
print_script_header

log "Checking for low disk space"

# Settings. Will update $USAGE_THRESHOLD_PERCENT
source_wrapper $SETTINGS_FILE

# Pre-conditionals
exit_if_limited_user

check_usage_threshold
