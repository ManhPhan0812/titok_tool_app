"""Exercise the four output choices in the real shared QML settings form."""

import os
import subprocess
import sys
from pathlib import Path


def test_automatic_output_controls():
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve())], env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    assert result.returncode == 0, result.stdout + result.stderr


if __name__ == "__main__":
    from PySide6.QtCore import Q_ARG, QMetaObject, QObject, Property, Qt, QUrl
    from PySide6.QtGui import QFont, QFontDatabase, QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    class Backend(QObject):
        processingDevice = Property(str, lambda _: "cpu", constant=True)
        isSwitchingProcessingDevice = Property(bool, lambda _: False, constant=True)
        selectedVideoSourceKey = Property(str, lambda _: "source", constant=True)
        projectKey = Property(str, lambda _: "project", constant=True)
        selectedVideoId = Property(str, lambda _: "video", constant=True)

    app = QGuiApplication([])
    for name in ("segoeui.ttf", "SegUIVar.ttf", "SegoeIcons.ttf"):
        font = Path("C:/Windows/Fonts") / name
        if font.is_file():
            QFontDatabase.addApplicationFont(str(font))
    app.setFont(QFont("Segoe UI Variable", 10))
    backend = Backend()
    engine = QQmlEngine()
    warnings = []
    engine.warnings.connect(lambda errors: warnings.extend(error.toString() for error in errors))
    engine.rootContext().setContextProperty("AppController", backend)
    directory = Path(__file__).resolve().parents[1]
    qml = directory / "src/haizflow/desktop/qml"
    component = QQmlComponent(engine)
    component.setData(b'''import QtQuick
import QtQuick.Controls.Basic
import "."
ApplicationWindow {
    width: 1080; height: 940; visible: true; color: Theme.window
    ProcessingSettingsForm {
        objectName: "form"; anchors.fill: parent; anchors.margins: 24
        showAutomaticOutputMode: true; availableHeight: height
        speechRecognitionOptions: [{label: "Whisper Small CPU", value: "small-cpu"}]
        ttsProviderOptions: [{label: "VieNeu CPU", provider: "vieneu"}]
        targetLanguageOptions: [{label: "Vietnamese", code: "vi"}]
        onAutomaticOutputModeEdited: function(value) { automaticOutputMode = value; }
    }
}''', QUrl.fromLocalFile(str(qml / "AutomaticOutputTest.qml")))
    assert component.isReady(), [error.toString() for error in component.errors()]
    window = component.create()
    assert window is not None
    QTest.qWait(200)
    form = window.findChild(QQuickItem, "form")
    combo = form.findChild(QObject, "automaticOutputModeCombo")
    assert combo.property("count") == 4 and combo.property("visible")
    for index, mode, subtitles, dubbing in [
        (3, "original", False, False), (1, "subtitles_only", True, False),
        (2, "voice_only", False, True), (0, "subtitles_and_voice", True, True),
    ]:
        combo.setProperty("currentIndex", index)
        assert QMetaObject.invokeMethod(combo, "activated", Qt.DirectConnection, Q_ARG(int, index))
        QTest.qWait(50)
        assert form.property("automaticOutputMode") == mode
        assert form.property("subtitlesEnabled") == subtitles
        assert form.property("dubbingEnabled") == dubbing
    output = directory / "build/automatic-output-modes-ui.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    assert window.grabWindow().save(str(output))
    assert not warnings, "\n".join(warnings)
    window.close()
    app.processEvents()
