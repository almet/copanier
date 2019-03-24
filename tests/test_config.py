import os
from pathlib import Path

from copanier import config


def test_config_should_read_from_env():
    old_root = os.environ.get("COPANIER_DATA_ROOT", "")
    old_secret = os.environ.get("COPANIER_SECRET", "")
    assert config.SECRET == "sikretfordevonly"
    assert isinstance(config.DATA_ROOT, Path)
    os.environ["COPANIER_DATA_ROOT"] = "changeme"
    os.environ["COPANIER_SECRET"] = "ultrasecret"
    config.init()
    assert config.SECRET == "ultrasecret"
    assert isinstance(config.DATA_ROOT, Path)
    assert str(config.DATA_ROOT) == "changeme"
    if old_root:
        os.environ["COPANIER_DATA_ROOT"] = old_root
    else:
        del os.environ["COPANIER_DATA_ROOT"]
    if old_secret:
        os.environ["COPANIER_SECRET"] = old_secret
    else:
        del os.environ["COPANIER_SECRET"]
    config.init()
