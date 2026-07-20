import math
import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import networkx as nx
from PySide6.QtGui import QGuiApplication, QImage, QPainter

from graphs import EdgeLayer, GraphBackend

N_NODES = 1000
DEGREES = (1, 10, 100)
SEED = 42

FRAME_BUDGET_MS = 33.0


def paint_frame(layer: EdgeLayer) -> float:
    img = QImage(1100, 720, QImage.Format_ARGB32_Premultiplied)
    img.fill(0)
    painter = QPainter(img)
    t0 = time.perf_counter()
    layer.paint(painter)
    dt = time.perf_counter() - t0
    painter.end()
    return dt


def build_round(backend: GraphBackend, layer: EdgeLayer,
                degree: int) -> None:
    print(f"\n=== Раунд: {N_NODES} вершин, у кожної по {degree} ребер ===")
    cols = math.ceil(math.sqrt(N_NODES))
    t0 = time.perf_counter()
    for i in range(N_NODES):
        backend.addNode(60.0 + (i % cols) * 50.0,
                        60.0 + (i // cols) * 50.0,
                        "Звичайна")
    t_nodes = time.perf_counter() - t0
    print(f"addNode x{N_NODES}: {t_nodes:.3f} c")

    regular = nx.random_regular_graph(degree, N_NODES, seed=SEED)
    t0 = time.perf_counter()
    for a, b in regular.edges():
        assert backend.addEdge(a + 1, b + 1, "Звичайне"), \
            f"addEdge({a + 1}, {b + 1}) не вдався"
    n_edges = regular.number_of_edges()
    t_edges = time.perf_counter() - t0
    print(f"addEdge x{n_edges}: {t_edges:.3f} c "
          f"({n_edges / t_edges:.0f} ребер/с)")

    store = backend._store
    assert len(store.nodes) == N_NODES, "невірна кількість вершин"
    assert store.edge_count() == n_edges, "невірна кількість ребер"
    bad = [nid for nid in store.nodes if store.degree(nid) != degree]
    assert not bad, f"вершини зі степенем != {degree}: {bad[:5]}…"

    dt = paint_frame(layer)
    print(f"кадр EdgeLayer ({n_edges} ребер): {dt * 1000:.1f} мс")

    t0 = time.perf_counter()
    hit = backend.nodeAt(60.0, 60.0)
    miss = backend.nodeAt(-500.0, -500.0)
    print(f"nodeAt (влучання={hit}, промах={miss}): "
          f"{time.perf_counter() - t0:.3f} c")
    assert hit == 1 and miss == -1, "nodeAt повернув неочікуване"

    t0 = time.perf_counter()
    hits = backend.selectInRect(0.0, 0.0, 400.0, 400.0, False)
    print(f"selectInRect (виділено={hits}): {time.perf_counter() - t0:.3f} c")
    backend.clearSelection()

    t0 = time.perf_counter()
    stats = backend.stats
    print(f"stats: {time.perf_counter() - t0:.3f} c — {stats}")

    t0 = time.perf_counter()
    backend.clear()
    print(f"clear: {time.perf_counter() - t0:.3f} c")
    assert len(store.nodes) == 0, "clear не спорожнив граф"


def drag_round(backend: GraphBackend, layer: EdgeLayer, n: int,
               budget_ms: float | None) -> None:
    n_edges = n * (n - 1) // 2
    print(f"\n=== Раунд: перетягування у K{n} ({n_edges} ребер) ===")
    cols = math.ceil(math.sqrt(n))
    for i in range(n):
        backend.addNode(60.0 + (i % cols) * 90.0,
                        60.0 + (i // cols) * 90.0,
                        "Звичайна")
    t0 = time.perf_counter()
    backend.connectClassNodes("Звичайна", "Звичайне")
    print(f"connectClassNodes: {time.perf_counter() - t0:.3f} c")
    assert backend._store.edge_count() == n_edges, "кліка неповна"

    frames = 120
    img = QImage(1100, 720, QImage.Format_ARGB32_Premultiplied)
    t0 = time.perf_counter()
    for i in range(frames):
        backend.moveNode(1, 60.0 + i, 60.0 + i)
        painter = QPainter(img)
        layer.paint(painter)
        painter.end()
    ms = (time.perf_counter() - t0) / frames * 1000
    print(f"кадр перетягування: {ms:.1f} мс ({1000 / ms:.0f} FPS)")
    if budget_ms is not None:
        assert ms < budget_ms, \
            f"кадр {ms:.1f} мс перевищує бюджет {budget_ms} мс"
    backend.clear()


def class_round(backend: GraphBackend) -> None:
    print(f"\n=== Раунд: класи вершин і ребер ({N_NODES} вершин) ===")
    assert backend.createClass("node", "Хаб",
                               {"shape": "diamond", "color": "#f39c12"})
    assert not backend.createClass("node", "Хаб",
                                   {"shape": "circle", "color": "#000000"}), \
        "дубль імені класу мав бути відхилений"
    assert backend.createClass("edge", "Міцне",
                               {"color": "#e74c3c", "width": 5, "line": "dash"})

    for i in range(N_NODES):
        backend.addNode(float(i), float(i), "Звичайна")
    backend.addNode(0.0, 0.0, "Хаб")           # id = N_NODES + 1
    hub = N_NODES + 1

    t0 = time.perf_counter()
    msg = backend.connectClassNodes("Звичайна", "Міцне")
    t_clique = time.perf_counter() - t0
    want = N_NODES * (N_NODES - 1) // 2
    print(f"connectClassNodes: {t_clique:.3f} c — {msg}")
    assert backend._store.edge_count() == want, "кліка неповна"
    strong = next(c for c in backend.classList("edge") if c["name"] == "Міцне")
    assert strong["count"] == want, "ребра кліки мали отримати клас «Міцне»"
    backend.selectNode(hub, False)
    t0 = time.perf_counter()
    msg = backend.connectSelectionToClass("Звичайна", "Звичайне")
    print(f"connectSelectionToClass: {time.perf_counter() - t0:.3f} c — {msg}")
    assert backend._store.degree(hub) == N_NODES, "хаб з'єднано не з усіма"
    backend.clearSelection()

    backend.clear()


def main() -> int:
    app = QGuiApplication(sys.argv)  # noqa: F841 — потрібен для QPainter/QImage
    backend = GraphBackend()
    layer = EdgeLayer()
    layer.source = backend

    total = time.perf_counter()
    for degree in DEGREES:
        build_round(backend, layer, degree)
    drag_round(backend, layer, 60, FRAME_BUDGET_MS)
    drag_round(backend, layer, 120, None)
    class_round(backend)
    print(f"\nУсі раунди пройдено за {time.perf_counter() - total:.3f} c ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
