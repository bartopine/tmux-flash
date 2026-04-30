#!/usr/bin/env bash
# tmux-flash plugin file for TPM
# Entry point: registers the keybinding and points it at the launcher.

PLUGIN_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

get_tmux_option() {
    local option="${1}"
    local default_value="${2}"
    local option_override
    option_override="$(tmux show-option -gqv "${option}")"
    if [ -z "${option_override}" ]; then
        echo "${default_value}"
    else
        echo "${option_override}"
    fi
}

bind_key=$(get_tmux_option "@flash-bind-key" "s")

tmux bind-key "${bind_key}" run-shell "${PLUGIN_DIR}/bin/tmux-flash.py"
