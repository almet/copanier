# Copanier

Copanier is a minimalist grouped-command management software.

It helps people to order a set of defined products, and provide a few helpers
to ease the life of everyone involved :-)

## Fork

This project is a modified version [of the project started by Yohan](https://framagit.org/ybon/copanier).

The main differences are :

- Support for multiple producers (and persons to handle these producers)
- A concept of groups was added : multiple persons can belong to the same group (and create / edit orders).
- A minimal interface to add  / remove / update products from the website.
- Support for out of stock products.
- Automatically compute a settlement plan (using the [debts library](https://framagit.org/almet/debts))
- A special page with tools to ease delivery management
- Drop support for CSV files
- Send emails to producers referents, with an order summary
- Generation of PDF files rather than XLS files (for order summary, signing sheet and paiements repartition)

## Philosophy

- Keep things simple
- Do not rely on JavaScript (or the less possible)
- Lower the cost of maintainance of the project

## Install copanier locally

The project relies on Python 3.7+, so if you don't have it yet, here's your
chance!

One way to install it, is to use [pyenv](https://github.com/pyenv/pyenv):

```bash
$ pyenv install 3.7.1
$ pyenv global 3.7.1
```

And then create a virtualenv so everything is installed separately from the
rest of the system:

```bash
$ # Get the source code locally
$ git clone https://framagit.org/almet/copanier.git
$ cd copanier

$ # Create the virtualenv
$ python -m venv venv

$ # Activate it!
$ source venv/bin/activate

$ # install everything!
$ pip install -e .
```

## Run local server

Once everything is installed, you can use the `copanier` command to run the server.

Make sure venv is active, then:

```bash
$ copanier serve
```

Optionally autoreload the server when you change a python file (needs `hupper`):

```bash
$ copanier serve --reload
```

Then browse to [http://localhost:2244](http://localhost:2244)

## Run the tests

If you want to contribute, don't hesitate! In this case, it might be helpful to
install a few other dependencies.

```bash
$ pip instal -e .[test]
```

Then, to run the tests:

```bash
$ # install the required dependencies for dev
$ pip install -r requirements-dev.txt
$ # run the tests
$ py.test tests
```
