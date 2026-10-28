"""A loaded QML source player must release Windows handles before deletion."""

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.skipif(sys.platform != "win32", reason="Windows native media file handles")
def test_delete_project_with_loaded_source_player(tmp_path):
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), str(tmp_path)],
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    assert result.returncode == 0, result.stdout + result.stderr


def exercise(directory):
    import time
    from types import SimpleNamespace
    from unittest.mock import Mock, patch

    from PySide6.QtCore import QObject, Property, QUrl, Signal
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtMultimedia import QMediaPlayer
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    from haizflow.desktop.project_commands_controller import ProjectCommandsController
    from haizflow.services import project_store, video_store
    from haizflow.utils.ffmpeg import _binary

    class Backend(QObject):
        selectedVideoChanged = Signal()
        sourceReplacementRequested = Signal(str)
        mediaImportChanged = Signal()

        @Property(str, constant=True)
        def selectedVideoId(self):
            return "video"

        @Property(bool, constant=True)
        def mediaImportBusy(self):
            return False

    def wait_until(predicate, timeout=8):
        deadline = time.monotonic() + timeout
        while not predicate() and time.monotonic() < deadline:
            QTest.qWait(20)
        assert predicate(), "Native media/deletion did not finish"

    directory = Path(directory).resolve()
    project_store.PROJECT_INDEX_PATH = str(directory / "data/projects.json")
    project = project_store.ensure_project("Loaded source", str(directory / "projects"), "single")
    root = Path(project["project_root"])
    assert root.resolve().is_relative_to(directory)
    source = root / "source.mp4"
    subprocess.run([
        _binary("ffmpeg"), "-v", "error", "-y", "-f", "lavfi", "-i",
        "color=c=blue:s=64x64:r=10:d=10", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source),
    ], capture_output=True, check=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
    app = QGuiApplication([])
    backend = Backend()
    engine = QQmlEngine()
    engine.rootContext().setContextProperty("AppController", backend)
    engine.rootContext().setContextProperty("testSource", QUrl.fromLocalFile(str(source)))
    qml = Path(__file__).resolve().parents[1] / "src/haizflow/desktop/qml"
    component = QQmlComponent(engine)
    component.setData(b'''import QtQuick
import QtQuick.Controls.Basic
import "."
ApplicationWindow {
    visible: true; width: 400; height: 300
    SourceVideoPlayer { objectName: "source-player"; anchors.fill: parent; source: testSource }
}''', QUrl.fromLocalFile(str(qml / "DeleteProjectTest.qml")))
    assert component.isReady(), [error.toString() for error in component.errors()]
    window = component.create()
    assert window is not None
    preview = window.findChild(QQuickItem, "source-player")
    player = preview.findChild(QMediaPlayer)
    owner = SimpleNamespace(
        _background_events_timer=object(), _selected_project_key=project["key"], _selected_video_id="video",
        _deleted_video_ids=set(), sourceReplacementRequested=backend.sourceReplacementRequested,
        releaseEditorPreview=Mock(), _audio_preview=SimpleNamespace(invalidate=Mock()),
        _processing_queue=SimpleNamespace(detach_pending=Mock(return_value=(None, [])), active_video_id=""),
        _channel_importer=SimpleNamespace(cancel_project=Mock(return_value=True)), _channel_import_targets={},
        appAlertRequested=SimpleNamespace(emit=Mock()),
    )
    commands = ProjectCommandsController(owner)
    try:
        player.audioOutput().setMuted(True)
        player.play()
        wait_until(lambda: player.playbackState() == QMediaPlayer.PlayingState and player.position() > 100)
        # Reproduce the user's rename failure with the real decoder open.
        with pytest.raises(PermissionError):
            project_store.delete_project_by_key(project["key"])
        assert source.is_file() and project_store.get_project(project["key"])
        with patch.object(video_store, "get_video_dir", return_value=str(root)):
            assert commands._delete_confirmed_project(project, [SimpleNamespace(video_id="video")])
            worker = commands._deletions[project["key"]]
            wait_until(lambda: not worker.is_alive(), timeout=18)
        events = []
        while not commands._deletion_events.empty():
            events.append(commands._deletion_events.get_nowait())
        assert [event[0] for event in events] == ["detached", "done"], events
        assert preview.property("sourceDetached") and player.source().isEmpty()
        assert not root.exists() and not project_store.get_project(project["key"])
        assert not list(project_store._deletion_journal_dir().glob("*.json"))
    finally:
        player.stop()
        player.setSource(QUrl())
        window.close()
        app.processEvents()


if __name__ == "__main__":
    exercise(sys.argv[1])
