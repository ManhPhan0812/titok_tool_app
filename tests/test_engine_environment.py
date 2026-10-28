"""Source launches must share their runtime with packaged resource engines."""

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from haizflow.core import paths


@pytest.mark.parametrize("storage", ["default", "custom", "moved-resources", "external-models"])
def test_source_environment_bootstraps_frozen_engine(tmp_path, storage):
    checkout = tmp_path / "mã nguồn"
    engine = tmp_path / "resource-pack" / "HaizFlowEngine.exe"
    engine.parent.mkdir()
    environment = {"HAIZFLOW_ENGINE_APP_ROOT": str(tmp_path / "stale-install"), "UNRELATED_SETTING": "keep"}
    if storage == "custom":
        environment.update({
            "HAIZFLOW_INSTALL_ROOT": str(checkout),
            "HAIZFLOW_HOME": str(tmp_path / "app-data"),
            "RUNTIME_DATA_DIR": str(tmp_path / "app-data" / "custom-data"),
            "HAIZFLOW_RESOURCE_ROOT": str(tmp_path / "moved-resources"),
            "MODELS_DIR": str(tmp_path / "app-data" / "custom-models"),
            "BIN_DIR": str(tmp_path / "media-tools"),
        })
    elif storage == "moved-resources":
        environment["HAIZFLOW_HOME"] = str(tmp_path / "app-data")
        environment["HAIZFLOW_RESOURCE_ROOT"] = str(tmp_path / "moved-resources")
    elif storage == "external-models":
        environment["MODELS_DIR"] = str(tmp_path / "external-models")
        environment["RUNTIME_DATA_DIR"] = "relative-data"
    # Unlike pytest's global fixture, the user's .bat launch has no smoke flag
    # or explicit runtime overrides by default.
    with patch.dict(os.environ, environment, clear=True), \
         patch.object(paths, "is_frozen", return_value=False), \
         patch.object(paths, "project_root", return_value=checkout):
        expected = [str(path.resolve()) for path in (
            paths.install_root(), paths.app_data_dir(), paths.runtime_data_dir(),
            paths.resource_storage_dir(), paths.models_dir(), paths.bin_dir(), paths.cache_dir(),
        )]
        worker = paths.engine_environment()
        assert "HAIZFLOW_SMOKE_TEST" not in os.environ
        assert os.environ["HAIZFLOW_ENGINE_APP_ROOT"] == environment["HAIZFLOW_ENGINE_APP_ROOT"]

    assert worker["HAIZFLOW_SMOKE_TEST"] == "1"
    assert worker["UNRELATED_SETTING"] == "keep"
    assert "HAIZFLOW_ENGINE_APP_ROOT" not in worker
    worker["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    # Exercise config import from a frozen engine's cwd; this is where the
    # original failure occurred, before inference or rendering could begin.
    script = (
        "import sys, json; sys.frozen = True; "
        f"sys.executable = {str(engine)!r}; "
        "import haizflow.config as c; from haizflow.core import paths; "
        "print(json.dumps([c.INSTALL_ROOT, c.APP_DATA_DIR, c.RUNTIME_DATA_DIR, "
        "str(paths.resource_storage_dir()), c.MODELS_DIR, c.BIN_DIR, c.CACHE_DIR]))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=engine.parent, env=worker,
        capture_output=True, text=True, encoding="utf-8", timeout=30,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected
    assert not (engine.parent / "runtime").exists()
