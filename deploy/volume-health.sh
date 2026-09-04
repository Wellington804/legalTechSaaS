#!/bin/sh
set -eu

project=${COMPOSE_PROJECT_NAME:-legaltech-production}
for suffix in pgdata redisdata caddy_data caddy_config evolution_data evolution_pgdata clamav_data; do
  docker volume inspect "${project}_${suffix}" >/dev/null 2>&1 || {
    printf 'volume-health: missing %s\n' "${project}_${suffix}" >&2
    exit 1
  }
done

# Docker reports actual usage. This script deliberately makes no guessed capacity claim.
docker system df -v
