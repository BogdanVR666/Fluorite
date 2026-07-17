"""Точка входу застосунку: створює QGuiApplication, бекенд і QML-рушій."""

import sys
from pathlib import Path

from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from graphs import GraphBackend


def main() -> int:
    app = QGuiApplication(sys.argv)

    backend = GraphBackend()

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("backend", backend)
    
    engine.load(str(Path(__file__).resolve().parent / "qml" / "main.qml"))

    if not engine.rootObjects():
        return 1

    rc = app.exec()
    engine.deleteLater()
    return rc


if __name__ == "__main__":
    sys.exit(main())