#!/bin/sh
# Loads config.json and exports every key as an environment variable.
# String values are exported directly. Object/array values are exported
# as compact JSON strings (e.g. MODEL_ALIASES='{"haiku":"claude-haiku-4-5-20251001",...}').
# Source this from other scripts: . "$SCRIPT_DIR/load_config.sh"

CONFIG_FILE="$(cd "$(dirname "$0")/.." && pwd)/config.json"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "ERROR: config.json not found. Copy config.example.json to config.json and set your keys." >&2
    exit 1
fi

eval "$(jq -r 'to_entries[] | "export \(.key)=\(.value | if type == "string" then @sh else (tojson | @sh) end)"' "$CONFIG_FILE")"
