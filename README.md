# digitalmarketplace-api

[![Build Status](https://travis-ci.org/alphagov/digitalmarketplace-api.svg?branch=master)](https://travis-ci.org/alphagov/digitalmarketplace-api)
[![Coverage Status](https://coveralls.io/repos/alphagov/digitalmarketplace-api/badge.svg?branch=master&service=github)](https://coveralls.io/github/alphagov/digitalmarketplace-api?branch=master)
[![Requirements Status](https://requires.io/github/alphagov/digitalmarketplace-api/requirements.svg?branch=master)](https://requires.io/github/alphagov/digitalmarketplace-api/requirements/?branch=master)

API tier for Digital Marketplace.

- Python app, based on the [Flask framework](http://flask.pocoo.org/)

## Setup

Install [Virtualenv](https://virtualenv.pypa.io/en/latest/)

```
sudo easy_install virtualenv
```

Ensure you have Postgres running locally, and then bootstrap your development
environment

```
./scripts/bootstrap.sh
```

### Activate the virtual environment

```
source ./venv/bin/activate
```

### Upgrade database schema

When new database migrations are added you can bring your local database schema
up to date by running upgrade.

```python application.py db upgrade```

### Upgrade dependencies

Install new Python dependencies with pip

```pip install -r requirements_for_test.txt```

### Run the tests

```
./scripts/run_tests.sh
```

### Run the development server

To run the API for local development you can use the convenient run script, 
which sets the environment variables required for local development: 

```
./scripts/run_app.sh
```

More generally, the command to start the server is:

```
python application.py runserver
```

## Using the API locally

By default the API runs on port 5000. Calls to the API require a valid bearer 
token. Tokens to be accepted can be set using the DM_AUTH_TOKENS environment
variable (a colon-separated list), e.g.:

```export DM_API_AUTH_TOKENS=myToken1:myToken2```

If ``DM_API_AUTH_TOKENS`` is not explicitly set then the run_api.sh script sets
it to ``myToken``. You should include a valid token in your request headers, 
e.g.:

```
curl -i -H "Authorization: Bearer myToken" 127.0.0.1:5000/services/123456789
```

## Using FeatureFlags

To use feature flags, check out the documentation in (the README of)
[digitalmarketplace-utils](https://github.com/alphagov/digitalmarketplace-utils#using-featureflags).


## Utility scripts

### Getting a list of migration versions

`./scripts/list_migrations.py` checks that there are no branches in the DB migrations and prints a
list of migration versions

### Getting a list of application URLs

`python application.py list_routes` prints a full list of registered application URLs with supported HTTP methods
