#!/bin/bash

export DJANGO_SETTINGS_MODULE=httpd.settings.dev

set -euxo pipefail

# Django dev server, 3 crunch 'workers' and a 'delete' and 'cancel' worker
(trap 'kill 0' SIGINT;
    python3 httpd/manage.py rqworker crunch &
    python3 httpd/manage.py rqworker crunch &
    python3 httpd/manage.py rqworker crunch &
    python3 httpd/manage.py rqworker delete &
    python3 httpd/manage.py rqworker cancel &
    python3 httpd/manage.py runserver
)

