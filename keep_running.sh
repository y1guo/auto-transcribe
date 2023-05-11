#!/bin/bash

# Help message function
print_help() {
    echo "Usage: $0 \"<command>\" [sleep_interval]"
    echo
    echo "Keep the given command running. If it finishes or exits with an error, restart it after the specified sleep interval."
    echo
    echo "Arguments:"
    echo "  <command>        The command to keep running, enclosed in quotes."
    echo "  sleep_interval   The sleep interval (in seconds) between restarts. Default: 10 seconds."
}

# Check if help is requested or if the command is not provided
if [[ "$1" == "-h" ]] || [[ "$1" == "--help" ]] || [[ -z "$1" ]]; then
    print_help
    exit 0
fi

# Set the command and the sleep interval (use default value if not provided)
command_to_run="$1"
sleep_interval=${2:-10}

# Check if sleep_interval is a valid number
if ! [[ "$sleep_interval" =~ ^[0-9]+$ ]]; then
    echo "Error: sleep_interval must be a positive integer."
    print_help
    exit 1
fi

echo "Running the command: $command_to_run"
echo "Sleep interval: $sleep_interval seconds"

while true; do
    # Run the command and store its exit status
    eval "$command_to_run"
    exit_status=$?

    # Check if the command exited with an error
    if [ $exit_status -ne 0 ]; then
        echo "Command exited with status $exit_status (error). Restarting in $sleep_interval seconds..."
    fi

    # Sleep for the specified interval
    sleep $sleep_interval
done
