#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
cd "$SCRIPT_DIR" || exit 1

truncate -s 0 "${SCRIPT_DIR}/inventory.networking"

while read -r line; do
    eval 'echo "'"$line"'"' >> "${SCRIPT_DIR}/inventory.networking"
done < "${SCRIPT_DIR}/inventory.networking.tpl"