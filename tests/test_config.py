import os
from pathlib import Path

from kaba import config


def test_config_should_read_from_env():
    old_root = os.environ.get("KABA_DATA_ROOT", "")
    old_secret = os.environ.get("KABA_SECRET", "")
    assert config.SECRET == "sikretfordevonly"
    assert isinstance(config.DATA_ROOT, Path)
    os.environ["KABA_DATA_ROOT"] = "changeme"
    os.environ["KABA_SECRET"] = "ultrasecret"
    config.init()
    assert config.SECRET == "ultrasecret"
    assert isinstance(config.DATA_ROOT, Path)
    assert str(config.DATA_ROOT) == "changeme"
    if old_root:
        os.environ["KABA_DATA_ROOT"] = old_root
    else:
        del os.environ["KABA_DATA_ROOT"]
    if old_secret:
        os.environ["KABA_SECRET"] = old_secret
    else:
        del os.environ["KABA_SECRET"]
    config.init()
