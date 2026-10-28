"""Real media exports for each Auto caption/dubbing combination."""

import json
import queue
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

import test_batch_pipeline_simulation as batch_support
from haizflow.desktop.project_commands_controller import ProjectCommandsController
from haizflow.desktop.processing_lifecycle_controller import ProcessingLifecycleController
from haizflow.desktop.qml_controller import HaizFlowController
from haizflow.pipeline import process_video
from haizflow.schemas.video import VideoConfig, automatic_outputs
from haizflow.services import project_store, video_export, video_store
from haizflow.utils.ffmpeg import _binary, validate_video_integrity


MODES = [("subtitles_and_voice", True, True), ("subtitles_only", True, False),
         ("voice_only", False, True), ("original", False, False)]
media = batch_support.media
simulation = batch_support.simulation


def create_auto(simulation, **settings):
    project = project_store.create_project("Auto outputs", simulation.project["project_directory"], "single")
    return simulation.create(project_type="single", project_key=project["key"], project_id=project["project_id"],
                             project_name=project["project_name"], **settings)


@pytest.mark.parametrize("mode,subtitles,dubbing", MODES)
def test_real_auto_output_skips_disabled_stages_and_publishes_video(simulation, mode, subtitles, dubbing):
    identifier = create_auto(simulation, automatic_output_mode=mode, enable_audio_separation=True)
    video = simulation.run(identifier)
    assert video.status == "done", video.error
    assert automatic_outputs(video) == (subtitles, dubbing)
    assert simulation.calls[identifier, "recognition"] == int(subtitles or dubbing)
    assert simulation.calls[identifier, "translation"] == int(subtitles or dubbing)
    assert simulation.calls[identifier, "voice"] == int(dubbing)
    assert simulation.calls[identifier, "separation"] == int(dubbing)
    assert Path(video.files["srt_output"]).is_file() == subtitles
    record = video_export.current_render(video)
    assert record
    output = record["resolved_outputs"]["video"]
    validate_video_integrity(output)
    pixels = subprocess.run([
        _binary("ffmpeg"), "-v", "error", "-ss", "0.3", "-i", output, "-frames:v", "1",
        "-vf", "scale=160:90", "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1",
    ], capture_output=True, check=True, timeout=20,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    image = np.frombuffer(pixels, dtype=np.uint8).reshape(-1, 3)
    # The source is a solid navy frame. Captions are the only visual addition.
    variation = int(np.ptp(image, axis=0).max())
    assert variation > 32 if subtitles else variation < 8
    if not dubbing:
        # Original speech/audio must survive; disabled dubbing is not a mute.
        audio = subprocess.run([
            _binary("ffmpeg"), "-v", "error", "-i", output, "-vn", "-ac", "1", "-ar", "8000",
            "-f", "s16le", "pipe:1",
        ], capture_output=True, check=True, timeout=20,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
        samples = np.frombuffer(audio, dtype="<i2")
        assert np.sqrt(np.mean(samples.astype(float) ** 2)) > 100
        spectrum = np.abs(np.fft.rfft(samples))
        frequency = np.fft.rfftfreq(len(samples), 1 / 8000)[spectrum.argmax()]
        assert abs(frequency - 200) < 2


def test_disabling_both_outputs_never_reuses_old_voices_or_captions(simulation):
    identifier = create_auto(simulation)
    first = simulation.run(identifier)
    assert first.status == "done", first.error
    old_signature = first.active_artifacts["export"]
    video_store.update_video(identifier, automatic_output_mode="original")
    assert video_export.current_render(video_store.get_video(identifier)) is None
    final = simulation.run(identifier)
    assert final.status == "done", final.error
    assert final.active_artifacts["export"] != old_signature
    assert simulation.calls[identifier, "recognition"] == 1
    assert simulation.calls[identifier, "voice"] == 1
    assert simulation.calls[identifier, "render"] == 2
    mix_rows = Path(video_store.get_video_dir(identifier)) / "temp/original_audio_segments.json"
    assert json.loads(mix_rows.read_text(encoding="utf-8")) == []


def test_original_mode_accepts_video_without_audio(simulation, tmp_path):
    identifier = create_auto(simulation, automatic_output_mode="original")
    video = video_store.get_video(identifier)
    temporary = tmp_path / "silent.mp4"
    subprocess.run([_binary("ffmpeg"), "-v", "error", "-y", "-i", video.files["video_input"],
                    "-an", "-c:v", "copy", str(temporary)], check=True, capture_output=True, timeout=20,
                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    temporary.replace(video.files["video_input"])
    final = simulation.run(identifier)
    assert final.status == "done", final.error
    assert video_export.current_render(final)
    assert simulation.calls[identifier, "recognition"] == 0


def test_original_mode_queues_and_executes_without_model_setup_or_gemini_key(simulation, monkeypatch):
    identifier = create_auto(simulation, automatic_output_mode="original")
    monkeypatch.setattr("haizflow.services.gemini_translation.key_configured", lambda: False)
    host = SimpleNamespace(_model_setup_state="missing", _runtime_probe_error="No inference engine installed",
        _deleted_video_ids=set(), _shutdown_started=False, _settings_processing_device="cpu", _smart_warmup=None,
        _processing_queue=SimpleNamespace(contains=lambda _: False, enqueue=lambda _: True, pending_ids=lambda: []),
        _log_queue=queue.Queue(), processingChanged=SimpleNamespace(emit=Mock()),
        selectedVideoChanged=SimpleNamespace(emit=Mock()))
    lifecycle = ProcessingLifecycleController(host)
    assert lifecycle.enqueue_video(identifier)
    lifecycle.execute_pipeline(identifier)
    final = video_store.get_video(identifier)
    assert final.status == "done", final.error
    assert video_export.current_render(final)


@pytest.mark.parametrize("mode,subtitles,dubbing", MODES)
def test_output_choice_is_saved_reopened_and_undoable(simulation, mode, subtitles, dubbing):
    identifier = create_auto(simulation, automatic_output_mode=mode)
    video_store._VIDEO_METADATA_CACHE.clear()
    reopened = video_store.get_video(identifier)
    assert reopened.automatic_output_mode == mode
    snapshot = HaizFlowController._video_settings_snapshot(reopened)
    assert snapshot["automatic_output_mode"] == mode
    restored = HaizFlowController._video_config_from_snapshot(reopened, {"automatic_output_mode": "original"})
    assert restored.automatic_output_mode == "original"


@pytest.mark.parametrize("mode,subtitles,dubbing", MODES)
def test_resource_gate_requests_only_active_branches(monkeypatch, mode, subtitles, dubbing):
    monkeypatch.setattr("haizflow.services.gemini_translation.key_configured", lambda: subtitles or dubbing)
    config = VideoConfig(automatic_output_mode=mode, tts_provider="edge", translation_model="gemini-3.1-flash-lite",
                         speech_recognition_model="small-cpu", enable_audio_separation=True,
                         remove_original_subtitles=False)
    video = SimpleNamespace(**config.model_dump(), video_id="test", status="pending", files={})
    requested = []
    manager = SimpleNamespace(required_packs=lambda capability, _context: requested.append(capability) or [],
                              missing_packs=lambda *_: [])
    host = SimpleNamespace(_settings_processing_device="cpu", appAlertRequested=SimpleNamespace(emit=Mock()),
                           _processing_queue=SimpleNamespace(contains=lambda _: False),
                           _resource_packs=SimpleNamespace(storageMoving=False, manager=manager))
    assert ProjectCommandsController._resources_ready_for_videos(host, [video])
    assert set(requested) == (({"recognition", "translation"} if subtitles or dubbing else set())
                              | ({"voice", "separation"} if dubbing else set()))
    host.appAlertRequested.emit.assert_not_called()


def test_disabled_voice_ignores_incompatible_provider_and_missing_clone_reference(monkeypatch):
    config = VideoConfig(automatic_output_mode="subtitles_only", tts_provider="vieneu-gpu",
                         tts_voice="vieneu:clone", target_language="zh", speech_recognition_model="small-cpu")
    video = SimpleNamespace(**config.model_dump(), video_id="test", status="processing", files={})
    host = SimpleNamespace(_settings_processing_device="cpu", appAlertRequested=SimpleNamespace(emit=Mock()))
    assert ProjectCommandsController._resources_ready_for_videos(host, [video])
    host.appAlertRequested.emit.assert_not_called()


def test_foreground_prediction_does_not_load_disabled_models():
    video = SimpleNamespace(project_type="single", automatic_output_mode="original", remove_original_subtitles=False)
    assert process_video.foreground_capability(video) == ""
    video.remove_original_subtitles = True
    assert process_video.foreground_capability(video) == "ocr"


def test_existing_projects_and_other_workspaces_keep_current_outputs():
    assert automatic_outputs(VideoConfig()) == (True, True)
    for kind in ("manual", "batch"):
        assert automatic_outputs(VideoConfig(project_type=kind, automatic_output_mode="original")) == (True, True)
