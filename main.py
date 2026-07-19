"""Точка входу застосунку: створює QGuiApplication, бекенд і QML-рушій."""

import sys
from pathlib import Path

from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterType

from graphs import EdgeLayer, GraphBackend


def main() -> int:
    app = QGuiApplication(sys.argv)

    qmlRegisterType(EdgeLayer, "Graphs", 1, 0, "EdgeLayer")
    backend = GraphBackend()

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("backend", backend)
    
    engine.load(str(Path(__file__).resolve().parent / "qml" / "main.qml"))

    if not engine.rootObjects():
        return 1

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())