"""Стрес-тест GraphBackend: 1000 вершин зі степенем 1, 10 та 100.

Граф будується виключно через публічні слоти бекенда (addNode/addEdge),
тобто тим самим шляхом, яким його викликає QML. Для кожного раунду
вимірюється час побудови й основних операцій та перевіряється коректність:
кількість вершин/ребер і те, що кожна вершина має рівно потрібний степінь.

Запуск:  uv run python stress_test.py
"""

import math
import sys
import time

import networkx as nx
from PySide6.QtCore import QCoreApplication

from graphs import GraphBackend

N_NODES = 1000
DEGREES = (1, 10, 100)
SEED = 42


def build_round(backend: GraphBackend, degree: int) -> None:
    print(f"\n=== Раунд: {N_NODES} вершин, у кожної по {degree} ребер ===")

    # --- вершини: розкладаємо по сітці, щоб nodeAt мав що шукати ---
    cols = math.ceil(math.sqrt(N_NODES))
    t0 = time.perf_counter()
    for i in range(N_NODES):
        backend.addNode(60.0 + (i % cols) * 50.0,
                        60.0 + (i // cols) * 50.0,
                        "Звичайна")
    t_nodes = time.perf_counter() - t0
    print(f"addNode x{N_NODES}: {t_nodes:.3f} c")

    # --- ребра: випадковий d-регулярний граф гарантує степінь d усім ---
    regular = nx.random_regular_graph(degree, N_NODES, seed=SEED)
    t0 = time.perf_counter()
    for a, b in regular.edges():
        assert backend.addEdge(a + 1, b + 1), f"addEdge({a + 1}, {b + 1}) не вдався"
    n_edges = regular.number_of_edges()
    t_edges = time.perf_counter() - t0
    print(f"addEdge x{n_edges}: {t_edges:.3f} c "
          f"({n_edges / t_edges:.0f} ребер/с)")

    # --- перевірка коректності ---
    g = backend._g
    assert g.number_of_nodes() == N_NODES, "невірна кількість вершин"
    assert g.number_of_edges() == n_edges, "невірна кількість ребер"
    bad = [nid for nid in g.nodes if g.degree[nid] != degree]
    assert not bad, f"вершини зі степенем != {degree}: {bad[:5]}…"

    # --- операції, які QML смикає на кожному кадрі/кліку ---
    t0 = time.perf_counter()
    edges = backend.edgeList()
    print(f"edgeList ({len(edges)} ребер): {time.perf_counter() - t0:.3f} c")

    t0 = time.perf_counter()
    hit = backend.nodeAt(60.0, 60.0)
    miss = backend.nodeAt(-500.0, -500.0)
    print(f"nodeAt (влучання={hit}, промах={miss}): "
          f"{time.perf_counter() - t0:.3f} c")
    assert hit == 1 and miss == -1, "nodeAt повернув неочікуване"

    t0 = time.perf_counter()
    msg = backend.findShortestPath(1, N_NODES)
    print(f"findShortestPath(1, {N_NODES}): {time.perf_counter() - t0:.3f} c — {msg}")

    t0 = time.perf_counter()
    stats = backend.stats
    print(f"stats: {time.perf_counter() - t0:.3f} c — {stats}")

    t0 = time.perf_counter()
    backend.clear()
    print(f"clear: {time.perf_counter() - t0:.3f} c")
    assert g.number_of_nodes() == 0, "clear не спорожнив граф"


def class_round(backend: GraphBackend) -> None:
    """Групові операції через класи вершин: кліка + вершина→клас."""
    print(f"\n=== Раунд: класи вершин ({N_NODES} вершин) ===")
    assert backend.createNodeClass("Хаб", "diamond", "#f39c12")
    assert not backend.createNodeClass("Хаб", "circle", "#000000"), \
        "дубль імені класу мав бути відхилений"

    for i in range(N_NODES):
        backend.addNode(float(i), float(i), "Звичайна")
    backend.addNode(0.0, 0.0, "Хаб")           # id = N_NODES + 1
    hub = N_NODES + 1

    t0 = time.perf_counter()
    msg = backend.connectClassNodes("Звичайна")
    t_clique = time.perf_counter() - t0
    want = N_NODES * (N_NODES - 1) // 2
    print(f"connectClassNodes: {t_clique:.3f} c — {msg}")
    assert backend._g.number_of_edges() == want, "кліка неповна"

    t0 = time.perf_counter()
    msg = backend.connectNodeToClass(hub, "Звичайна")
    print(f"connectNodeToClass: {time.perf_counter() - t0:.3f} c — {msg}")
    assert backend._g.degree[hub] == N_NODES, "хаб з'єднано не з усіма"

    backend.clear()


def main() -> int:
    app = QCoreApplication(sys.argv)  # noqa: F841 — потрібен для QObject-інфраструктури
    backend = GraphBackend()

    total = time.perf_counter()
    for degree in DEGREES:
        build_round(backend, degree)
    class_round(backend)
    print(f"\nУсі раунди пройдено за {time.perf_counter() - total:.3f} c ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
