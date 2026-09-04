#!/bin/sh
set -eu

psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
SELECT 'CREATE DATABASE evogo_users'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'evogo_users')\gexec
SQL
