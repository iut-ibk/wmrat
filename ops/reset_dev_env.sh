#!/bin/bash

export DJANGO_SETTINGS_MODULE=httpd.settings.dev
export DJANGO_SUPERUSER_PASSWORD=pass

set -euxo pipefail

# clean data
rm -rf appdata/*

# clean migrations
rm -rf ./httpd/hub/migrations

# delete DB
rm -f httpd/db.sqlite3

# migrate
python3 httpd/manage.py makemigrations hub
python3 httpd/manage.py migrate
python3 httpd/manage.py createsuperuser --noinput --username admin --email admin@example.com

