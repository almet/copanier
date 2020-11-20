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

![Login screen](/screenshots/place-order.png?raw=true)
![Login screen](/screenshots/payments.png?raw=true)
![Login screen](/screenshots/order-confirmation.png?raw=true)
![Login screen](/screenshots/login.png?raw=true)
![Login screen](/screenshots/groups.png?raw=true)

## Philosophy

- Keep things simple
- Do not rely on JavaScript (or the less possible)
- Lower the cost of maintainance of the project

## FAQ

### How is it different from cagette?

[Cagette](https://www.cagette.net) is a free software which aims at solving a larger problem that what we're solving. Cagette has a more general approach, providing a tool that can be used by groups of producers, AMAPs, people having a physical store, and group of consumers.

In copanier, we only focus on groups of consumers. We want to keep things as straightforward and effective as possible, by keeping the problem small. We do one thing and we try to do it the best way we can! We believe copanier is better suited for people who want to organise the way we do, but if copanier doesn't fit your needs, cagette might :-)

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

## Fork

This project is a continuation of the work done by
[Alexis](https://framagit.org/almet/copanier), itself took from the work
[Yohan](https://framagit.org/ybon/copanier) did in the first place.