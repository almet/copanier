# Copanier

Copanier is a software to make grouped orders. It's generally used by small groups
who want to buy food supplies directly from producers, without requiring each
individual to see each producer.

It helps people to order a set of defined products, and provide a few helpers
to ease the life of everyone involved :-)

## How does it work?

1. A new delivery is created ;
2. Producers and products are created in the software (or copied from a past delivery) ;
3. (Optional : prices are checked with the producers to be sure they are still okay) ;
4. Individuals place their orders for their groups ;
5. Referents ask their producers for the products and pay them ;
6. There is a delivery - the tool provides summary of who ordered what ;
7. A dispatch of who has to pay whom is done ;
8. XXX
9. ... Profit !

## Features

- Handles groups of people (useful for people sharing a house) ;
- Handles multiple producers in one delivery ;
- Intelligent dispatching of payments, without any central bank account ;
- Support for shipping fees ;

## Screenshots

![Login screen](/screenshots/login.png?raw=true)
![Login screen](/screenshots/groups.png?raw=true)
![Login screen](/screenshots/place-order.png?raw=true)
![Login screen](/screenshots/order-confirmation.png?raw=true)
![Login screen](/screenshots/payments.png?raw=true)

## Philosophy

- Keep things simple.
- Do not rely on JavaScript (or the less possible)
- Lower the cost of maintainance of the project

## FAQ

### How files are stored? Does this rely on a database?

The current implementation of copanier doesn't need an external database, and relies on YAML files instead. It's done to keep things simple and easy to work with / backup, and we believe the needs for a database are very little, since we would very rarely have multiple writes at the same time.

### How is it different from cagette?

[Cagette](https://www.cagette.net) is a free software which aims at solving a larger problem that what we're solving. Cagette has a more general approach, providing a tool that can be used by groups of producers, AMAPs, people having a physical store, and group of consumers.

In copanier, we only focus on groups of consumers. We want to keep things as straightforward and effective as possible, by keeping the problem small. We do one thing and we try to do it the best way we can! We believe copanier is better suited for people who want to organise the way we do, but if copanier doesn't fit your needs, cagette might :-)

## Install copanier locally

### Get the system dependencies

You might need to install some system dependencies. On
[Debian-based](https://www.debian.org) systems, you can install the
dependencies with this command:

```bash
sudo apt install python3-dev python3-venv python3-pip libcairo-dev libpango1.0-dev
```

The project relies on Python 3.7+, so if you don't have it yet, here's your
chance!

One way to install it is to use [pyenv](https://github.com/pyenv/pyenv):

```bash
pyenv install 3.7.1
pyenv global 3.7.1
```

### Install copanier

We recommend to use virtualenv so everything is installed separately from the
rest of the system:

```bash
# Get the source code locally
git clone https://github.com/spiral-project/copanier.git
cd copanier

# Create the virtualenv
python -m venv venv
# On some systems, you might need to specify "python3.7 -m venv venv"

# Activate it!
source venv/bin/activate

# install everything!
pip install -e .
```

### Running in docker

For this, you need to have [docker](https://docs.docker.com/engine/install/) and [docker-compose](https://docs.docker.com/compose/install/) installed.

To give a try to Copanier quickly, you can use docker:

```bash
cd docker
sudo docker-compose -p copanier up
```

The app will be available at http://localhost:2244.

Database is saved under `db` folder. This folder is mounted in `app` container to persist data changes on host disk.

For development purpose, you can use both `docker-compose.yml` and `docker-compose-dev.yml` which allows you to work on copanier source code and make gunicorn automatically reload workers when code changes:

```bash
sudo docker-compose -p copanier -f docker-compose.yml -f docker-compose-dev.yml up
```

## Run local server

Once everything is installed, you can use the `copanier` command to run the server.

Make sure venv is active, then:

```bash
copanier serve
```

Optionally autoreload the server when you change a python file (needs `hupper`):

```bash
copanier serve --reload
```

Then browse to [http://localhost:2244](http://localhost:2244)

## Run the tests

If you want to contribute, don't hesitate! In this case, it might be helpful to
install a few other dependencies.

```bash
pip instal -e .[test]
```

Then, to run the tests:

```bash
# install the required dependencies for dev
pip install -r requirements-dev.txt
# run the tests
py.test tests
```

## Configuration

Copanier uses environment variables to configure its behaviour. All the configuration flags are specified in [this config.py file](https://github.com/spiral-project/copanier/blob/master/copanier/config.py) and in order to use them, you will need to set them, considering their name starts with `COPANIER_`.

One simple way to handle this behaviour, is to have a `config.env` file and source it (with `source config.env`) before starting the server. Here is how this file could look like:

```bash
export COPANIER_SITE_URL="https://yourdomain.com"
export COPANIER_SITE_NAME="Your site name"
export COPANIER_SITE_DESCRIPTION="Site long description"
export COPANIER_XLSX_FILENAME="crac-produits"
export COPANIER_SEND_EMAILS=True
export COPANIER_SMTP_HOST="mail.gandi.net"
export COPANIER_SMTP_PASSWORD="something"
export COPANIER_SMTP_LOGIN="yourlogin"
export COPANIER_FROM_EMAIL="youremail@tld.com"
export COPANIER_EMAIL_SIGNATURE="The team"
export COPANIER_STAFF="staff@email.com another@staff.com"
```

## Deployment

If you're running the application locally, then just running it with `copanier serve` might be enough, but if you want to deploy it in production, the best way to make this run is to rely on a WSGI server. One good option is [gunicorn](https://gunicorn.org).

You can run it with this command:

```bash
gunicorn -k roll.worker.Worker copanier:app --bind [$IP]:$PORT
```

## Installation on AlwaysData

[AlwaysData](https://alwaysdata.net) has a free plan capable of hosting copanier. Here are the steps to install there :

1. Create a free account
1. Connect via ssh
1. `git clone https://github.com/spiral-project/copanier.git`
1. Create the venv with `python3.9 -m venv venv` (using python 3.9 right now to avoid issues with cython)
1. Create a `copanier.env` and `runserver.sh` file with the contents below

```env
export COPANIER_SITE_NAME="Copanier"
export COPANIER_SITE_URL="https://xxx.alwaysdata.net"
export COPANIER_SITE_DESCRIPTION="Copanier"
export COPANIER_XLSX_FILENAME="produits"
export COPANIER_SEND_EMAILS=True

export COPANIER_SMTP_HOST="xxx"
export COPANIER_SMTP_PASSWORD="xxx"
export COPANIER_SMTP_LOGIN="xxx"

export COPANIER_FROM_EMAIL="xxx"
export COPANIER_EMAIL_SIGNATURE="Copanier"
export COPANIER_STAFF=""
```

```bash
#!/bin/bash
source copanier.env && /home/copanier/venv/bin/gunicorn -k roll.worker.Worker copanier:app --bind [$IP]:$PORT
```

Then in the admin pannel create a website with a custom script that runs
`/runserver.sh` and another site which points to the static files. You should
be good to go.

## Fork

This project is a continuation of the work done by [Yohan](https://framagit.org/ybon/copanier),
on top of which we added the notion of groups, multiple producers, payment repartition etc.
