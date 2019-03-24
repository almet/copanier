import os
import sys
from io import StringIO

import minicli
from usine import chown, config, connect, env, exists, mkdir, put, run, sudo, template


@minicli.cli
def pip(*command):
    """Run a pip command on the remote server.
    """
    with sudo(user="copanier"):
        run(f"/srv/copanier/venv/bin/pip {' '.join(command)}")


@minicli.cli
def system():
    """Setup the system."""
    with sudo():
        run("apt update")
        run(
            "apt install -y nginx git software-properties-common gcc "
            "python3.7 python3.7-dev python3.7-venv pkg-config"
        )
        mkdir("/srv/copanier/logs")
        run("useradd -N copanier -d /srv/copanier/ || exit 0")
        chown("copanier:users", "/srv/copanier/")
        run("chsh -s /bin/bash copanier")


@minicli.cli
def venv():
    """Setup the python virtualenv."""
    path = "/srv/copanier/venv/"
    if not exists(path):
        with sudo(user="copanier"):
            run(f"python3.7 -m venv {path}")
    pip("install pip -U")


@minicli.cli
def http():
    """Configure Nginx and letsencrypt."""
    # When we'll have a domain.
    put("remote/nginx-snippet.conf", "/etc/nginx/snippets/copanier.conf")
    put("remote/letsencrypt.conf", "/etc/nginx/snippets/letsencrypt.conf")
    put("remote/ssl.conf", "/etc/nginx/snippets/ssl.conf")
    domain = config.domains[0]
    pempath = f"/etc/letsencrypt/live/{domain}/fullchain.pem"
    with sudo():
        if exists(pempath):
            print(f"{pempath} found, using https configuration")
            conf = template(
                "remote/nginx-https.conf",
                domains=" ".join(config.domains),
                domain=domain,
            )
        else:
            print(f"{pempath} not found, using http configuration")
            # Before letsencrypt.
            conf = template(
                "remote/nginx-http.conf",
                domains=" ".join(config.domains),
                domain=domain,
            )
        put(conf, "/etc/nginx/sites-enabled/copanier.conf")
        restart("nginx")


@minicli.cli
def letsencrypt():
    """Configure letsencrypt."""
    with sudo():
        run("add-apt-repository --yes ppa:certbot/certbot")
        run("apt update")
        run("apt install -y certbot")
        mkdir("/var/www/letsencrypt/.well-known/acme-challenge")
        domains = ",".join(list(config.domains))
        certbot_conf = template("remote/certbot.ini", domains=domains)
        put(certbot_conf, "/var/www/certbot.ini")
        run("certbot certonly -c /var/www/certbot.ini --non-interactive " "--agree-tos")


@minicli.cli
def bootstrap():
    """Bootstrap the system."""
    system()
    venv()
    service()
    http()


@minicli.cli
def cli(command):
    """Run the copanier executable on the remote server.
    """
    with sudo(user="copanier"), env(COPANIER_DATA_ROOT="/srv/copanier/data"):
        run(f"/srv/copanier/venv/bin/copanier {command}")


@minicli.cli
def service():
    """Deploy/update the copanier systemd service."""
    with sudo():
        put("remote/copanier.service", "/etc/systemd/system/copanier.service")
        systemctl("enable copanier.service")


@minicli.cli
def deploy():
    """Deploy/update the copanier code base."""
    with sudo(user="copanier"):
        put("remote/gunicorn.conf", "/srv/copanier/gunicorn.conf")
        pip("install gunicorn")
        base = "https://gitlab.com/ybon/copanier"
        pip(f"install -U git+{base}")
    restart()


@minicli.cli
def restart(*services):
    """Restart the systemd services."""
    services = services or ["copanier", "nginx"]
    with sudo():
        systemctl(f"restart {' '.join(services)}")


@minicli.cli
def systemctl(*args):
    """Run a systemctl command on the remote server.

    :command: the systemctl command to run.
    """
    run(f'systemctl {" ".join(args)}')


@minicli.cli
def logs(lines=50):
    """Display the copanier logs.

    :lines: number of lines to retrieve
    """
    with sudo():
        run(f"journalctl --lines {lines} --unit copanier --follow")


@minicli.cli
def status():
    """Get the services status."""
    systemctl("status nginx copanier")


@minicli.cli
def access_logs():
    """See the nginx access logs."""
    with sudo():
        run("tail -F /var/log/nginx/access.log")


@minicli.cli
def error_logs():
    """See the nginx error logs."""
    with sudo():
        run("tail -F /var/log/nginx/error.log")


@minicli.cli
def upload_env():
    """Upload environment vars to the server.

    Use those to deal with info not commitable.
    """
    vars_ = {
        "COPANIER_DATA_ROOT": "/srv/copanier/data",
        "COPANIER_SEND_MAILS": "1",
        "COPANIER_SMTP_PASSWORD": None,
        "COPANIER_SMTP_LOGIN": None,
    }
    content = ""
    for key, value in vars_.items():
        try:
            content += "{}={}\n".format(key, value or os.environ[key])
        except KeyError:
            sys.exit(f"The {key} environment variable does not exist.")
    path = "/srv/copanier/env"
    if exists(path):
        run(f"cat {path}")
    put(StringIO(content), path)


@minicli.wrap
def wrapper(hostname, configpath):
    with connect(hostname=hostname, configpath=configpath):
        yield


if __name__ == "__main__":
    minicli.run(hostname="qa", configpath="remote/config.yml")
