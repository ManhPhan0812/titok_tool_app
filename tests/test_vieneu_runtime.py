"""Recover extracted SDK caches using verified wheels, preserving originals."""

import hashlib
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from haizflow.core.model_integrity import ModelIntegrityError
from haizflow.pipeline import vieneu_tts as voice


@pytest.fixture
def sdk(tmp_path, monkeypatch):
    root = tmp_path / "models"
    directory = root / "sdk"
    directory.mkdir(parents=True)
    wheel = directory / "fixture.whl"
    files = ("vieneu/__init__.py", "vieneu/v3turbo.py", "vieneu/assets/voices_v3_turbo.json",
             "sea_g2p/__init__.py", "sea_g2p/sea_g2p_rs.pyd", "kaldi_native_fbank/__init__.py",
             "_kaldi_native_fbank.cp313-win_amd64.pyd", "kaldi-native-fbank-core.dll")
    with zipfile.ZipFile(wheel, "w") as archive:
        for name in files:
            archive.writestr(name, b"verified fixture")
    manifest = {"sdk_version": "3.8.3", "assets": [{
        "path": "sdk/fixture.whl", "size": wheel.stat().st_size,
        "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
    }]}
    monkeypatch.setattr(voice, "MANIFEST", manifest)
    weights = root / "weights.bin"
    weights.write_bytes(b"model weights must not change")
    return root, wheel, weights, manifest


def test_extracts_verified_sdk_and_reuses_complete_runtime(sdk):
    root, _wheel, weights, _manifest = sdk
    runtime = voice.prepare_runtime(root)
    marker = runtime / ".ready"
    assert marker.read_text(encoding="ascii") == voice.CACHE_VERSION
    identity = marker.stat().st_ino
    assert voice.prepare_runtime(root) == runtime
    assert marker.stat().st_ino == identity
    assert not list(root.glob("sdk-old-*")) and not list(runtime.parent.glob("runtime-*-old-*"))
    assert weights.read_bytes() == b"model weights must not change"


@pytest.mark.parametrize("damage", ["denied", "invalid-encoding", "missing-library"])
def test_rebuilds_unreadable_or_incomplete_runtime_and_preserves_backup(sdk, monkeypatch, damage):
    root, _wheel, _weights, _manifest = sdk
    runtime = voice.prepare_runtime(root)
    marker = runtime / ".ready"
    if damage == "denied":
        read_text = Path.read_text

        def read(path, *args, **kwargs):
            if path == marker:
                raise PermissionError("SDK marker is inaccessible")
            return read_text(path, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", read)
    elif damage == "invalid-encoding":
        marker.write_bytes(b"\xff")
    else:
        (runtime / "vieneu/v3turbo.py").unlink()
    assert voice.prepare_runtime(root) == runtime
    # Bypass only the injected marker read failure when checking rebuilt data.
    assert marker.read_bytes().decode("ascii") == voice.CACHE_VERSION
    assert (runtime / "vieneu/v3turbo.py").is_file()
    assert len(list(runtime.parent.glob("runtime-*-old-*"))) == 1


@pytest.mark.parametrize("fail_commit", [False, True])
def test_replaces_sdk_parent_when_windows_denies_runtime_rename(sdk, monkeypatch, fail_commit):
    root, wheel, weights, _manifest = sdk
    runtime = voice.prepare_runtime(root)
    (runtime / ".ready").write_text("stale", encoding="ascii")
    original_wheel = wheel.read_bytes()
    replace = os.replace

    def publish(source, target):
        source, target = Path(source), Path(target)
        if source == runtime:
            raise PermissionError("Windows denies access to extracted runtime")
        if fail_commit and target == root / "sdk" and source.name == "sdk":
            raise OSError("Publication failed")
        return replace(source, target)

    monkeypatch.setattr(voice.os, "replace", publish)
    if fail_commit:
        with pytest.raises(OSError, match="Publication failed"):
            voice.prepare_runtime(root)
        assert (runtime / ".ready").read_text(encoding="ascii") == "stale"
    else:
        assert voice.prepare_runtime(root) == runtime
        assert (runtime / ".ready").read_text(encoding="ascii") == voice.CACHE_VERSION
        backup, = root.glob("sdk-old-*")
        assert (backup / runtime.name / ".ready").read_text(encoding="ascii") == "stale"
        assert (backup / wheel.name).read_bytes() == original_wheel
    assert wheel.read_bytes() == original_wheel
    assert weights.read_bytes() == b"model weights must not change"


def test_runtime_publication_failure_restores_original_cache(sdk, monkeypatch):
    root, _wheel, _weights, _manifest = sdk
    runtime = voice.prepare_runtime(root)
    (runtime / ".ready").write_text("stale", encoding="ascii")
    replace = os.replace

    def publish(source, target):
        if Path(source).name == "site-packages" and Path(target) == runtime:
            raise OSError("Publication failed")
        return replace(source, target)

    monkeypatch.setattr(voice.os, "replace", publish)
    with pytest.raises(OSError, match="Publication failed"):
        voice.prepare_runtime(root)
    assert (runtime / ".ready").read_text(encoding="ascii") == "stale"


def test_tampered_wheel_is_rejected_before_cache_replacement(sdk):
    root, wheel, _weights, _manifest = sdk
    runtime = voice.prepare_runtime(root)
    (runtime / ".ready").write_text("stale", encoding="ascii")
    wheel.write_bytes(b"x" * wheel.stat().st_size)
    with pytest.raises(ModelIntegrityError, match="checksum"):
        voice.prepare_runtime(root)
    assert (runtime / ".ready").read_text(encoding="ascii") == "stale"
    assert not list(root.glob("sdk-old-*"))


def test_separate_processes_share_one_sdk_preparation(sdk, tmp_path):
    root, _wheel, _weights, manifest = sdk
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    script = '''import json, sys, time, zipfile
from pathlib import Path
from haizflow.pipeline import vieneu_tts as voice
voice.MANIFEST = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
original = zipfile.ZipFile.open
def slow_open(self, *args, **kwargs):
    time.sleep(.05)
    return original(self, *args, **kwargs)
zipfile.ZipFile.open = slow_open
print(voice.prepare_runtime(Path(sys.argv[2])))
'''
    workers = [subprocess.Popen(
        [sys.executable, "-c", script, str(path), str(root)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    ) for _ in range(2)]
    try:
        for worker in workers:
            stdout, stderr = worker.communicate(timeout=15)
            assert worker.returncode == 0, stderr
            assert Path(stdout.strip()) == root / "sdk/runtime-3.8.3"
    finally:
        for worker in workers:
            if worker.poll() is None:
                worker.kill()
                worker.communicate()
    assert not list(root.glob("sdk-old-*"))
    assert not list((root / "sdk").glob("runtime-*-old-*"))
