# Copanier

Copanier is a minimalist grouped-command management software.

It helps people to order a set of defined products, and provide a few helpers
to ease the life of everyone involved :-)

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
$ git clone https://framagit.org/ybon/copanier.git
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
