import json

from trimmy import config


def test_load_returns_defaults_when_no_file(tmp_config_dir):
    result = config.load()
    assert result == config._DEFAULTS


def test_load_reads_existing_config(tmp_config_dir):
    tmp_config_dir.parent.mkdir(parents=True, exist_ok=True)
    data = {"selected_platform": "tiktok", "selected_quality": "optimized"}
    tmp_config_dir.write_text(json.dumps(data), encoding="utf-8")
    result = config.load()
    assert result["selected_platform"] == "tiktok"
    assert result["selected_quality"] == "optimized"


def test_load_returns_defaults_on_corrupt_json(tmp_config_dir):
    tmp_config_dir.parent.mkdir(parents=True, exist_ok=True)
    tmp_config_dir.write_text("{not valid json!!!", encoding="utf-8")
    result = config.load()
    assert result == config._DEFAULTS


def test_load_merges_partial_config(tmp_config_dir):
    tmp_config_dir.parent.mkdir(parents=True, exist_ok=True)
    data = {"selected_platform": "whatsapp"}
    tmp_config_dir.write_text(json.dumps(data), encoding="utf-8")
    result = config.load()
    assert result["selected_platform"] == "whatsapp"
    assert result["selected_quality"] == "max"
    assert result["split_ratio"] == 0.5


def test_save_creates_directory_and_file(tmp_config_dir):
    state = {"selected_platform": "telegram", "selected_quality": "optimized"}
    config.save(state)
    assert tmp_config_dir.exists()
    loaded = json.loads(tmp_config_dir.read_text(encoding="utf-8"))
    assert loaded["selected_platform"] == "telegram"


def test_save_and_load_roundtrip(tmp_config_dir):
    state = {
        "selected_platform": "twitter",
        "selected_format": "post",
        "selected_quality": "optimized",
        "split_ratio": 0.7,
        "crops": {
            "top": {"x": 10.0, "y": 20.0, "w": 500.0, "h": 400.0},
            "bottom": {"x": 30.0, "y": 40.0, "w": 600.0, "h": 500.0},
        },
    }
    config.save(state)
    result = config.load()
    assert result["selected_platform"] == "twitter"
    assert result["split_ratio"] == 0.7
    assert result["crops"]["top"]["x"] == 10.0
