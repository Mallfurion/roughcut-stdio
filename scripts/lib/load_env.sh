#!/usr/bin/env bash

load_env_file() {
  local env_file="$1"

  [ -f "$env_file" ] || return 0

  while IFS= read -r raw_line || [ -n "$raw_line" ]; do
    local line="$raw_line"
    line="${line#"${line%%[![:space:]]*}"}"

    if [ -z "$line" ] || [ "${line#\#}" != "$line" ]; then
      continue
    fi

    if [[ "$line" != *=* ]]; then
      continue
    fi

    local key="${line%%=*}"
    local value="${line#*=}"

    key="${key%"${key##*[![:space:]]}"}"
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"

    if [ -n "${!key+x}" ]; then
      continue
    fi

    export "${key}=${value}"
  done < "$env_file"
}

load_env_file "${ROOT_DIR}/.env"
load_env_file "${ROOT_DIR}/.env.local"
