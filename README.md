# Copanier

Minimalist grouped command management


# Local install

Dependencies:
- python >= 3.7


- Create a venv:

    python -m venv path/to/venv

- Activate it:

    source path/to/venv/bin/activate

- Install python package locally

    python setup.py develop


## Run local server

Make sure venv is active, then:

    copanier serve

Optionally autoreload the server when you change a python file (needs `hupper`):

    copanier serve --reload

Then browse to http://localhost:2244
