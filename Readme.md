# Overview

WMRAT (Water Management Resilience Analysis Toolkit) is a proof-of-concept web
application that showcases and implements several scenarios in the context of
urban water management resilience analysis. It is part of the project RESIST.

# Development

This section explains how to start the local development server in a virtual
Python environemtn ("venv"). Make sure that you also have Redis installed and
running (`systemctl start redis`). The following third party dependencies are
used and are installed into the virtual environment:

- Django
- Django RQ
- WNTR

Pre-installations needed:

- python 3.8 (link: https://www.python.org/downloads/release/python-380/)
- Ubuntu (link: https://ubuntu.com/download) 

Check out this repository switch into it:

    $ git clone git@github.com:iut-ibk/wmrat.git
    $ cd wmrat

Make the environment:

    $ python -m venv venv # required by WNTR

Activate it (observe how your shell prompt changes):

    $ source venv/bin/activate

Install dependencies (we will use requirements later):

    $ pip install django django_rq wntr

If everything went well you have now successfully installed the (Django) web
application in your virtual environment. There is a script to reset the database
(NOTE: this deletes all files, but is useful for debugging):

    $ ./ops/reset_dev_env.sh

The login credentials for the test admin are `admin` and `pass`. Then use the
following command to run the development enviroment:

    $ ./ops/run_dev_env.sh

This starts the Django development server on `localhost:8000` (the Django
default port) and runs the required workers (that run the actual analyses).

# Usage

This section is under construction.

# License

AGPLv3

