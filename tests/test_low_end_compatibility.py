"""Hardware routing regressions, using simulated telemetry rather than AI inference."""

import queue
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from haizflow.core import hardware, memory
from haizflow.core.model_choices import project_model_defaults
from haizflow.desktop.qml_controller import HaizFlowController
from haizflow.desktop.runtime_device_controller import RuntimeDeviceController
from haizflow.desktop.smart_warmup_controller import SmartWarmupController

GIB = memory.GIB


def quadro():
    return hardware.HardwareCapabilities(True, "NVIDIA Quadro K1000M", 2 * GIB, GIB,
        int(7.8 * GIB), 8, True, 100, installed_ram_bytes=8 * GIB)


@pytest.mark.parametrize("capability", [(0, 0), (3, 0)])
@pytest.mark.parametrize("language", ["vi", "en"])
def test_k1000m_explains_cpu_route_even_when_old_driver_omits_architecture(capability, language):
    caps = replace(quadro(), cuda_compute_capability=capability)
    allowed, message = hardware.validate_processing_device("gpu", caps, language=language)
    assert not allowed
    assert "K1000M" in message and "3.0" in message
    assert "Whisper Small CPU" in message and "HY-MT2 CPU Q4" in message
    assert hardware.validate_processing_device("cpu", caps, language=language)[0]
    assert hardware.recommended_processing_device(caps) == "cpu"


@pytest.mark.parametrize("origin", ["detected", "manual"])
def test_saved_gpu_on_k1000m_switches_to_cpu_and_new_projects_use_cpu_models(origin):
    host = SimpleNamespace(_settings_processing_device="gpu", _processing_device_origin=origin,
        _settings_theme="graphite", _settings_language="vi", _hardware_probe_events=queue.Queue())
    controller = RuntimeDeviceController(host, detect_hardware=Mock(return_value=quadro()))
    with patch("haizflow.desktop.runtime_device_controller.configure_processing_device") as configure, \
         patch("haizflow.desktop.runtime_device_controller.desktop_settings.save_settings") as save:
        assert controller._resolve_startup_processing_device() == "cpu"
    configure.assert_called_once_with("cpu")
    assert save.call_args.args[0]["processing_device"] == "cpu"
    assert host._active_processing_device == "cpu" and host._startup_hardware_resolved
    defaults = project_model_defaults(host._settings_processing_device)
    assert defaults["_speech_recognition_model"] == "small-cpu"
    assert defaults["_translation_model"] == "q4"
    assert defaults["_tts_provider"] == "vieneu"


def test_small_machine_disables_all_speculative_loading_even_with_generous_live_counters():
    profile = hardware.runtime_profile_for(quadro(), "cpu")
    assert profile.whisper_batch_size == 1 and profile.cpu_threads == 2
    assert profile.translation_idle_seconds == 15
    assert not profile.warm_whisper_on_startup and not profile.warm_hymt2_on_startup
    controller = SmartWarmupController.__new__(SmartWarmupController)
    with patch("haizflow.desktop.smart_warmup_controller.runtime_profile", return_value=profile), \
         patch("haizflow.desktop.smart_warmup_controller.available_memory_bytes", return_value=6 * GIB), \
         patch("haizflow.desktop.smart_warmup_controller.available_commit_bytes", return_value=16 * GIB):
        for capability in ("recognition", "translation", "voice", "separation", "ocr"):
            assert not controller._has_warmup_budget(capability, {})


def test_8gb_cpu_admission_preserves_live_memory_checks_for_heavy_models():
    assert hardware.validate_processing_device("cpu", quadro())[0]
    enough = memory.MemorySnapshot(8 * GIB, int(7.8 * GIB), 3 * GIB,
                                  process_commit_available_bytes=7 * GIB)
    memory.require_cpu_memory("recognition", snapshot=enough)
    memory.require_cpu_memory("translation", snapshot=enough)
    memory.require_cpu_memory("voice", snapshot=enough)
    with pytest.raises(RuntimeError, match="OmniVoice"):
        memory.require_cpu_memory("voice", snapshot=replace(enough, process_commit_available_bytes=4 * GIB))


def test_resource_page_exposes_detected_legacy_gpu_and_cpu_guidance():
    host = SimpleNamespace(_hardware_capabilities=quadro(), _active_processing_device="cpu",
        _settings_language="vi", _format_memory_size=lambda value: str(value))
    info = HaizFlowController.hardwareInfo.fget(host)
    assert info["recommendedDevice"] == "cpu" and not info["gpuSafe"]
    assert "K1000M" in info["processingAdvice"]
    assert "Whisper Small CPU" in info["processingAdvice"]


@pytest.mark.parametrize("capability,allowed", [((3, 0), False), ((5, 2), False),
    ((6, 1), False), ((7, 0), True), ((7, 5), True), ((8, 6), True)])
def test_vram_alone_cannot_admit_architectures_missing_from_current_engine(capability, allowed):
    caps = replace(quadro(), cuda_name="Test GPU", cuda_compute_capability=capability,
                   total_vram_bytes=8 * GIB)
    assert hardware.validate_processing_device("gpu", caps)[0] is allowed
    assert caps.gpu_supported is allowed


def test_resource_page_renders_cpu_guidance_inside_small_viewport():
    from pathlib import Path

    from PySide6.QtCore import QObject, Property, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from PySide6.QtQuick import QQuickItem, QQuickWindow
    from shiboken6 import getCppPointer, wrapInstance

    host = SimpleNamespace(_hardware_capabilities=quadro(), _active_processing_device="cpu",
        _settings_language="vi", _format_memory_size=lambda value: str(value))
    info = HaizFlowController.hardwareInfo.fget(host)

    class State(QObject):
        hardwareInfo = Property("QVariantMap", lambda self: info, constant=True)
        processingDevice = Property(str, lambda self: "cpu", constant=True)
        selectedVideoId = Property(str, lambda self: "", constant=True)
        resourcePackActivityText = Property(str, lambda self: "", constant=True)
        resourcePackageRows = Property("QVariantList", lambda self: [], constant=True)
        resourcePackStorageLocation = Property(str, lambda self: "E:/HaizFlow/runtime", constant=True)
        resourcePackInstalledText = Property(str, lambda self: "0 GB", constant=True)
        resourcePackFreeSpaceText = Property(str, lambda self: "100 GB", constant=True)
        resourcePackBusy = Property(bool, lambda self: False, constant=True)
        resourcePackStorageMoving = Property(bool, lambda self: False, constant=True)
        resourcePackActivityProgress = Property(float, lambda self: -1.0, constant=True)

    app = QGuiApplication.instance() or QGuiApplication([])
    engine = QQmlEngine()
    state = State()
    engine.rootContext().setContextProperty("TestController", state)
    path = Path(__file__).resolve().parents[1] / "src/haizflow/desktop/qml/ResourcePacksPage.qml"
    source = path.read_text(encoding="utf-8").replace("AppController", "TestController")
    component = QQmlComponent(engine)
    component.setData(source.encode(), QUrl.fromLocalFile(str(path)))
    assert component.isReady(), "\n".join(error.toString() for error in component.errors())
    page = component.create()
    window = QQuickWindow()
    item = wrapInstance(getCppPointer(page)[0], QQuickItem)
    item.setParentItem(window.contentItem())
    item.setWidth(1000)
    item.setHeight(640)
    window.resize(1000, 640)
    window.show()
    try:
        app.processEvents()
        summary = page.findChild(QObject, "resourceHardwareSummary")
        assert "K1000M" in summary.property("description")
        assert "HY-MT2 CPU Q4" in summary.property("description")
        for child in summary.findChildren(QQuickItem):
            if child.property("text") and "K1000M" in str(child.property("text")):
                assert child.property("contentWidth") <= child.width() + 1
                assert child.property("contentHeight") <= child.height() + 1
                break
        else:
            raise AssertionError("Compatibility guidance is missing from the rendered text")
    finally:
        window.close()
        page.deleteLater()
        app.processEvents()
