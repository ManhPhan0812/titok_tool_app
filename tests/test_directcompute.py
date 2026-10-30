"""Legacy GPU routing, pinned executables and CPU phase hand-off."""

import hashlib
import json
import wave
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from haizflow.core import directcompute as dc
from haizflow.core.hardware import HardwareCapabilities
from haizflow.core.model_choices import gpu_choice_blocked, models_for_device, recognition_context
from haizflow.desktop.qml_controller import HaizFlowController
from haizflow.desktop.resource_pack_controller import ResourcePackController
from haizflow.pipeline import directcompute_transcribe as backend
from haizflow.schemas.video import VideoConfig
from haizflow.services.recognition_progress import RecognitionProgress
from haizflow.services.resource_packs import ResourcePackManager, built_in_pack_definitions


def quadro(**overrides):
    values = dict(cuda_available=True, cuda_name="NVIDIA Quadro K1000M",
        total_vram_bytes=2 * 1024**3, free_vram_bytes=1024**3,
        total_ram_bytes=int(7.8 * 1024**3), installed_ram_bytes=8 * 1024**3,
        logical_cpu_count=8, ac_powered=True, battery_percent=100)
    return HardwareCapabilities(**(values | overrides))


def test_k1000m_can_use_directcompute_without_unlocking_modern_cuda():
    caps = quadro()
    assert not caps.gpu_supported
    assert dc.validate_hardware(caps)[0]
    assert not gpu_choice_blocked("cpu", recognition=dc.MODEL_CHOICE, translation="q4", voice="vieneu")
    assert recognition_context(dc.MODEL_CHOICE, "gpu") == {"model": dc.MODEL_CHOICE, "device": "cpu"}
    assert models_for_device("cpu", recognition=dc.MODEL_CHOICE, translation="full", voice="vieneu-gpu") == {
        "speech_recognition_model": dc.MODEL_CHOICE, "translation_model": "q4", "tts_provider": "vieneu"}


def test_old_driver_needs_no_nvidia_smi_but_ram_minimum_still_applies():
    caps = quadro(cuda_available=False, cuda_name="", total_vram_bytes=0,
                  detected_graphics=("Intel HD 4000", "NVIDIA Quadro K1000M"))
    assert dc.validate_hardware(caps)[0]
    assert "K1000M" in dc.adapter_hint(caps)
    assert not dc.validate_hardware(quadro(total_ram_bytes=4 * 1024**3, installed_ram_bytes=4 * 1024**3))[0]
    assert not dc.validate_hardware(None)[0]


def test_choice_persists_and_picker_does_not_require_global_gpu():
    config = VideoConfig(input_path="example.mp4", speech_recognition_model=dc.MODEL_CHOICE)
    assert VideoConfig.model_validate_json(config.model_dump_json()).speech_recognition_model == dc.MODEL_CHOICE
    host = SimpleNamespace(_hardware_capabilities=quadro(), _settings_processing_device="cpu",
        _settings_language="vi", _speech_recognition_model=dc.MODEL_CHOICE, _startup_hardware_resolved=True)
    options = HaizFlowController.speechRecognitionModelOptions.fget(host)
    assert options[3]["value"] == dc.MODEL_CHOICE and options[3]["available"]
    assert not options[1]["available"] and not options[2]["available"]
    assert HaizFlowController.speechRecognitionModelIndex.fget(host) == 3


def test_resource_plan_uses_cpu_engine_and_shared_language_alignment_assets():
    manager = ResourcePackManager.__new__(ResourcePackManager)
    assert manager.required_packs("recognition", {"device": "gpu", "model": dc.MODEL_CHOICE}) == [
        "engine-cpu-py313", "model-whisper-small", dc.PACK_ID]
    pack = next(item for item in built_in_pack_definitions() if item.pack_id == dc.PACK_ID)
    assert pack.assets == dc.assets()
    assert pack.dependencies == ("engine-cpu-py313", "model-whisper-small")
    assert all(len(item.sha256) == 64 and item.url.startswith("https://") for item in pack.assets)
    host = SimpleNamespace(_hardware_capabilities=quadro(), _startup_hardware_resolved=True, _settings_language="vi")
    controller = ResourcePackController.__new__(ResourcePackController)
    controller._host = host
    assert controller._hardware_compatibility(dc.PACK_ID)[0]
    assert not controller._hardware_compatibility("engine-cuda128-py313")[0]


def test_native_adapter_must_match_k1000m_even_on_dual_gpu_machine():
    with patch.object(backend, "_run", return_value=(1,
        'Available adapters:\n"Intel HD 4000"\n"NVIDIA Quadro K1000M"\n', "")):
        assert backend._adapter(Path("main.exe"), "Quadro K1000M", "fixture") == "NVIDIA Quadro K1000M"
    with patch.object(backend, "_run", return_value=(1, '"Intel HD 4000"\n"Microsoft Basic Render Driver"', "")):
        with pytest.raises(RuntimeError, match="K1000M"):
            backend._adapter(Path("main.exe"), "NVIDIA Quadro K1000M", "fixture")


def test_missing_shared_models_do_not_disable_directcompute_install_button():
    manager = ResourcePackManager()
    host = SimpleNamespace(_hardware_capabilities=quadro(), _startup_hardware_resolved=True,
        _settings_processing_device="cpu", _speech_recognition_model=dc.MODEL_CHOICE,
        _settings_language="vi")
    controller = ResourcePackController.__new__(ResourcePackController)
    controller._host, controller.manager = host, manager
    controller.model = SimpleNamespace(_rows=manager.snapshot())
    controller._storage_mutating = Mock(return_value=False)
    with patch.object(manager, "status", return_value="missing"), \
         patch.object(manager, "archive_available", side_effect=lambda pack: pack == "engine-cpu-py313"):
        row = next(row for row in controller.displayRows if row["packId"] == dc.PACK_ID)
    assert row["canInstall"]
    assert row["hardwareCompatible"]


@pytest.mark.parametrize("content", ["", "1\n00:00:02,000 --> 00:00:03,000\nLate\n",
    "1\n00:00:01,600 --> 00:00:01,700\nPast audio\n",
    "1\n00:00:00,000 --> 00:00:00,000\nEmpty\n",
    "1\n00:00:00,000 --> 00:00:01,000\nOne\n\n2\n00:00:00,500 --> 00:00:01,000\nOverlap\n"])
def test_invalid_native_subtitles_are_not_published(tmp_path, content):
    path = tmp_path / "speech.srt"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(RuntimeError):
        backend._segments(path, 1.5, "vi")


def test_verified_cli_extraction_rejects_same_size_rewrite_and_ignores_archive_paths(tmp_path):
    payload = tmp_path / "payload"
    payload.mkdir()
    output = tmp_path / "output"
    output.mkdir()
    pinned = {"main.exe": (4, hashlib.sha256(b"safe").hexdigest())}
    with zipfile.ZipFile(payload / "cli.zip", "w") as archive:
        archive.writestr("main.exe", b"evil")
        archive.writestr("../outside.txt", b"escape")
    with patch.object(backend, "CLI_FILES", pinned), pytest.raises(RuntimeError, match="checksum"):
        backend._extract_cli(payload, output)
    assert not (tmp_path / "outside.txt").exists()
    assert not (output / "main.exe").exists()


def test_language_probe_reads_only_30_seconds_and_preserves_format(tmp_path):
    audio = tmp_path / "audio.wav"
    with wave.open(str(audio), "wb") as stream:
        stream.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        stream.writeframes(b"\0" * 16000 * 2 * 35)
    def cpu(path, *_args, **kwargs):
        with wave.open(path, "rb") as stream:
            assert stream.getnframes() == 30 * 16000
        assert kwargs["model_name"] == "small-cpu"
        return [], "zh"
    assert backend._language_probe(str(audio), tmp_path, "fixture", cpu) == ("zh", 35.0)


def test_gpu_checkpoint_is_only_a_transcribed_phase_then_cpu_publishes(tmp_path, monkeypatch):
    audio = tmp_path / "source.mp4"
    audio.write_bytes(b"source video fixture")
    checkpoint = tmp_path / "recognition.json"
    output = tmp_path / "final.json"
    directory = tmp_path / "temp"
    monkeypatch.setattr("haizflow.config.TMP_DIR", str(directory))
    monkeypatch.setattr("haizflow.core.hardware.detect_hardware_capabilities", lambda: quadro())
    monkeypatch.setattr("haizflow.services.video_store.log_to_video", Mock())
    monkeypatch.setattr(backend, "verify_payload", lambda _: tmp_path)
    monkeypatch.setattr(backend, "_extract_cli", lambda _payload, root: root / "main.exe")
    monkeypatch.setattr(backend, "_adapter", lambda *_: "NVIDIA Quadro K1000M")
    monkeypatch.setattr(backend, "_language_probe", lambda *_: ("vi", 2.0))
    calls = []
    def run(command, *_args, **_kwargs):
        calls.append(command)
        if "--output-srt" in command:
            Path(command[-1]).with_suffix(".srt").write_text(
                "1\n00:00:00,100 --> 00:00:01,500\nXin chào\n", encoding="utf-8")
        return 0, "", ""
    monkeypatch.setattr(backend, "_run", run)
    def cpu(path, destination, language, video_id, **kwargs):
        phase = RecognitionProgress(kwargs["checkpoint_path"], path, model="small",
                                     language=language, key=kwargs["checkpoint_key"])
        assert phase.stage in {"transcribed", "complete"}
        assert phase.language == "vi" and phase.segments[0]["text"] == "Xin chào"
        assert kwargs["model_name"] == "small-cpu"
        assert not output.exists()  # Native SRT was never final output.
        phase.save("complete", phase.segments, "vi")
        return phase.segments, "vi"
    result = backend.transcribe(str(audio), str(output), "auto", "fixture",
        checkpoint_path=str(checkpoint), checkpoint_key="project-model-signature", cpu_transcribe=cpu)
    assert result[1] == "vi" and len(calls) == 2
    assert "--use-gpu" in calls[-1] and "NVIDIA Quadro K1000M" in calls[-1]
    assert "-i" in calls[0] and str(audio) in calls[0]
    # A pause after GPU completion never reruns inference or adapter discovery.
    monkeypatch.setattr(backend, "verify_payload", Mock(side_effect=AssertionError("must resume")))
    backend.transcribe(str(audio), str(output), "auto", "fixture",
        checkpoint_path=str(checkpoint), checkpoint_key="project-model-signature", cpu_transcribe=cpu)
    assert len(calls) == 2
    stored = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert stored["payload"]["stage"] == "complete"


@pytest.mark.parametrize("exit_code", [0, 4])
def test_native_failure_or_missing_srt_cannot_publish_a_cpu_result(tmp_path, monkeypatch, exit_code):
    audio, output = tmp_path / "source.wav", tmp_path / "final.json"
    audio.write_bytes(b"source")
    checkpoint = tmp_path / "recognition.json"
    monkeypatch.setattr("haizflow.config.TMP_DIR", str(tmp_path / "temp"))
    monkeypatch.setattr("haizflow.core.hardware.detect_hardware_capabilities", lambda: quadro())
    monkeypatch.setattr("haizflow.services.video_store.log_to_video", Mock())
    monkeypatch.setattr(backend, "verify_payload", lambda _: tmp_path)
    monkeypatch.setattr(backend, "_extract_cli", lambda _payload, root: root / "main.exe")
    monkeypatch.setattr(backend, "_adapter", lambda *_: "NVIDIA Quadro K1000M")
    monkeypatch.setattr(backend, "_language_probe", lambda *_: ("vi", 2.0))
    monkeypatch.setattr(backend, "_run", lambda command, *_: (
        exit_code if "--output-srt" in command else 0, "", "D3D device failure"))
    cpu = Mock(side_effect=AssertionError("failed GPU output must not be published"))
    with pytest.raises(RuntimeError, match="Whisper DirectCompute"):
        backend.transcribe(str(audio), str(output), "auto", "fixture",
            checkpoint_path=str(checkpoint), cpu_transcribe=cpu)
    cpu.assert_not_called()
    assert not output.exists() and not checkpoint.exists()


def test_cancelled_task_does_not_start_a_native_child():
    with patch.object(backend, "check_cancellation", side_effect=RuntimeError("Video cancelled by user.")), \
         patch.object(backend.subprocess, "Popen") as start:
        with pytest.raises(RuntimeError, match="cancelled"):
            backend._run(["main.exe"], "fixture")
    start.assert_not_called()


def test_frozen_acceptance_requires_isolation(monkeypatch):
    from haizflow.core.release_smoke import run_directcompute_smoke

    monkeypatch.delenv("HAIZFLOW_SMOKE_TEST", raising=False)
    with pytest.raises(RuntimeError, match="isolated"):
        run_directcompute_smoke("unused.wav", "Intel GPU")


def test_frozen_acceptance_restores_adapter_and_closes_cpu_workers(monkeypatch, tmp_path):
    from haizflow.core import release_smoke
    from haizflow.pipeline.timing_contract import TIMING_SOURCE

    manager = Mock()
    manager.missing_packs.return_value = []
    manager.external_engine_pack.return_value = "engine-cpu-py313"
    rows = [{"start": 0, "end": 1, "text": "Hello", "timing_source": TIMING_SOURCE}]
    original = backend.adapter_hint
    monkeypatch.setattr("haizflow.services.resource_packs.ResourcePackManager", lambda: manager)
    monkeypatch.setattr("haizflow.core.paths.runtime_data_dir", lambda: tmp_path)
    close = Mock()
    monkeypatch.setattr("haizflow.services.external_engine.close_shared_external_engine_pool", close)
    run = Mock(return_value=(rows, "en"))
    monkeypatch.setattr("haizflow.pipeline.manual_tools.transcribe", run)
    result = release_smoke.run_directcompute_smoke("fixture.wav", "Intel GPU")
    assert result["ok"] and result["adapter"] == "Intel GPU"
    assert result["cpu_engine"] == "engine-cpu-py313" and not result["physical_k1000m_tested"]
    assert backend.adapter_hint is original
    close.assert_called_once()
