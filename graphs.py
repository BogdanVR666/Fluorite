"""Структури даних редактора графа.

NodesModel   — QAbstractListModel поверх вершин nx.Graph для QML.
GraphBackend — фасад над nx.Graph: редагування, алгоритми, статистика.

Вершини і ребра графа — це об'єкти родин елементів (нащадки BaseNode
та BaseEdge, див. elements.py); nx.Graph зберігає їх в атрибуті "obj"
вершини (за цілим ключем nodeId) чи ребра (за парою ключів).
"""

from itertools import combinations

import networkx as nx
from PySide6.QtCore import (
    Property,
    QAbstractListModel,
    QByteArray,
    QModelIndex,
    QObject,
    Qt,
    QUrl,
    Signal,
    Slot,
)

import storage
from edges import BaseEdge, DefaultEdge
from elements import ElementMeta
from nodes import BaseNode, DefaultNode


def _point_segment_dist2(px: float, py: float,
                         x1: float, y1: float, x2: float, y2: float) -> float:
    """Квадрат відстані від точки (px, py) до відрізка (x1,y1)-(x2,y2)."""
    vx, vy = x2 - x1, y2 - y1
    wx, wy = px - x1, py - y1
    seg2 = vx * vx + vy * vy
    t = 0.0 if seg2 == 0.0 else max(0.0, min(1.0, (wx * vx + wy * vy) / seg2))
    dx, dy = wx - t * vx, wy - t * vy
    return dx * dx + dy * dy


class NodesModel(QAbstractListModel):
    """Надає вершини nx.Graph як модель для QML Repeater."""

    NodeIdRole = Qt.UserRole + 1
    XRole = Qt.UserRole + 2
    YRole = Qt.UserRole + 3
    LabelRole = Qt.UserRole + 4
    InPathRole = Qt.UserRole + 5
    DegreeRole = Qt.UserRole + 6
    ShapeRole = Qt.UserRole + 7
    ColorRole = Qt.UserRole + 8
    ClassRole = Qt.UserRole + 9

    def __init__(self, graph: nx.Graph, parent=None):
        super().__init__(parent)
        self._g = graph
        self._ids: list[int] = []          # порядок рядків моделі
        self._path_nodes: set[int] = set() # вершини підсвіченого шляху

    # --- обов'язковий інтерфейс QAbstractListModel ---

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._ids)

    def roleNames(self):
        return {
            self.NodeIdRole: QByteArray(b"nodeId"),
            self.XRole: QByteArray(b"px"),
            self.YRole: QByteArray(b"py"),
            self.LabelRole: QByteArray(b"label"),
            self.InPathRole: QByteArray(b"inPath"),
            self.DegreeRole: QByteArray(b"degree"),
            self.ShapeRole: QByteArray(b"nodeShape"),
            self.ColorRole: QByteArray(b"nodeColor"),
            self.ClassRole: QByteArray(b"nodeClass"),
        }

    def data(self, index, role):
        if not index.isValid() or not (0 <= index.row() < len(self._ids)):
            return None
        nid = self._ids[index.row()]
        node: BaseNode = self._g.nodes[nid]["obj"]
        if role == self.NodeIdRole:
            return nid
        if role == self.XRole:
            return node.x
        if role == self.YRole:
            return node.y
        if role == self.LabelRole:
            return node.label
        if role == self.InPathRole:
            return nid in self._path_nodes
        if role == self.DegreeRole:
            return self._g.degree[nid]
        if role == self.ShapeRole:
            return node.shape
        if role == self.ColorRole:
            return node.color
        if role == self.ClassRole:
            return type(node).type_name
        return None

    # --- допоміжні методи для бекенда ---

    def row_of(self, nid: int) -> int:
        return self._ids.index(nid)

    def append_node(self, nid: int):
        row = len(self._ids)
        self.beginInsertRows(QModelIndex(), row, row)
        self._ids.append(nid)
        self.endInsertRows()

    def remove_node(self, nid: int):
        row = self.row_of(nid)
        self.beginRemoveRows(QModelIndex(), row, row)
        self._ids.pop(row)
        self._path_nodes.discard(nid)
        self.endRemoveRows()

    def notify_row(self, nid: int, roles: list[int]):
        row = self.row_of(nid)
        idx = self.index(row)
        self.dataChanged.emit(idx, idx, roles)

    def notify_all(self, roles: list[int]):
        if self._ids:
            self.dataChanged.emit(
                self.index(0), self.index(len(self._ids) - 1), roles)

    def set_path(self, nodes: set[int]):
        self._path_nodes = nodes
        self.notify_all([self.InPathRole])

    def reset_with(self, ids):
        """Повністю замінює рядки моделі (після завантаження з файла)."""
        self.beginResetModel()
        self._ids = list(ids)
        self._path_nodes.clear()
        self.endResetModel()

    def reset_all(self):
        self.beginResetModel()
        self._ids.clear()
        self._path_nodes.clear()
        self.endResetModel()


class GraphBackend(QObject):
    """Тримає nx.Graph і надає QML операції над ним."""

    graphChanged = Signal()
    classesChanged = Signal()   # з'явився новий клас вершин

    def __init__(self, parent=None):
        super().__init__(parent)
        self._g = nx.Graph()
        self._next_id = 1
        self._path_edges: set[frozenset] = set()
        self._model = NodesModel(self._g, self)

    def _node(self, nid: int) -> BaseNode:
        return self._g.nodes[nid]["obj"]

    def _edge(self, a: int, b: int) -> BaseEdge:
        return self._g.edges[a, b]["obj"]

    def _objects(self, family: str):
        """Об'єкти всіх елементів родини, що зараз є у графі."""
        if family == "node":
            return (data["obj"] for _, data in self._g.nodes(data=True))
        return (data["obj"] for _, _, data in self._g.edges(data=True))

    # --- властивості для QML ---

    @Property(QObject, constant=True)
    def nodesModel(self):
        return self._model

    @Property(str, notify=graphChanged)
    def stats(self):
        n = self._g.number_of_nodes()
        m = self._g.number_of_edges()
        c = nx.number_connected_components(self._g) if n else 0
        return f"Вершин: {n}  •  Ребер: {m}  •  Компонент зв'язності: {c}"

    # --- класи елементів (родини "node" і "edge") ---

    @Slot(str, result="QVariantList")
    def classList(self, family: str):
        """Класи родини: дизайн і кількість елементів кожного."""
        root = ElementMeta.families.get(family)
        if root is None:
            return []
        counts: dict[str, int] = {}
        for obj in self._objects(family):
            name = type(obj).type_name
            counts[name] = counts.get(name, 0) + 1
        return [{
            "name": cls.type_name,
            "count": counts.get(cls.type_name, 0),
            **cls.design(),
        } for cls in root.registry.values()]

    @Slot(str, str, "QVariantMap", result=bool)
    def createClass(self, family: str, name: str, design: dict) -> bool:
        root = ElementMeta.families.get(family)
        if root is None:
            return False
        design = {f: v for f, v in design.items() if f in root.style_fields}
        if root.define(name, **design) is None:
            return False
        self.classesChanged.emit()
        return True

    @Slot(int, str)
    def setNodeClass(self, nid: int, class_name: str):
        cls = BaseNode.registry.get(class_name)
        if cls is None or nid not in self._g:
            return
        old = self._node(nid)
        # новий об'єкт без перекриттів стилю — вершина приймає дизайн класу
        self._g.nodes[nid]["obj"] = cls(old.x, old.y, old.label)
        self._model.notify_row(nid, [NodesModel.ShapeRole,
                                     NodesModel.ColorRole,
                                     NodesModel.ClassRole])
        self.graphChanged.emit()   # у classList змінились лічильники

    @Slot(int, int, str)
    def setEdgeClass(self, a: int, b: int, class_name: str):
        cls = BaseEdge.registry.get(class_name)
        if cls is None or not self._g.has_edge(a, b):
            return
        old = self._edge(a, b)
        # новий об'єкт без перекриттів стилю — ребро приймає дизайн класу
        self._g.edges[a, b]["obj"] = cls(old.label)
        self.graphChanged.emit()   # перемальовує ребра й оновлює лічильники

    def _class_ids(self, class_name: str) -> list[int]:
        return [nid for nid in self._g.nodes
                if type(self._node(nid)).type_name == class_name]

    def _bulk_add_edges(self, pairs, edge_cls: type) -> int:
        """Додає ребра пачкою з одним сповіщенням; повертає к-ть нових."""
        added = 0
        for a, b in pairs:
            if a != b and not self._g.has_edge(a, b):
                self._g.add_edge(a, b, obj=edge_cls())
                added += 1
        if added:
            self._path_edges.clear()
            self._model.set_path(set())
            self._model.notify_all([NodesModel.DegreeRole])
            self.graphChanged.emit()
        return added

    @Slot(str, str, result=str)
    def connectClassNodes(self, class_name: str, edge_class: str) -> str:
        """З'єднує всі вершини класу між собою (кліка)."""
        ids = self._class_ids(class_name)
        if len(ids) < 2:
            return f"У класі «{class_name}» менше двох вершин"
        cls = BaseEdge.registry.get(edge_class, DefaultEdge)
        added = self._bulk_add_edges(combinations(ids, 2), cls)
        return f"Клас «{class_name}»: додано ребер — {added}"

    @Slot(int, str, str, result=str)
    def connectNodeToClass(self, nid: int, class_name: str,
                           edge_class: str) -> str:
        """З'єднує вершину nid з усіма вершинами класу class_name."""
        if nid not in self._g:
            return ""
        ids = self._class_ids(class_name)
        if not ids or ids == [nid]:
            return f"У класі «{class_name}» немає інших вершин"
        cls = BaseEdge.registry.get(edge_class, DefaultEdge)
        added = self._bulk_add_edges(((nid, other) for other in ids), cls)
        return (f"Вершина {self._node(nid).label} → клас «{class_name}»: "
                f"додано ребер — {added}")

    # --- редагування графа ---

    @Slot(float, float, str)
    def addNode(self, x: float, y: float, class_name: str):
        cls = BaseNode.registry.get(class_name, DefaultNode)
        nid = self._next_id
        self._next_id += 1
        self._g.add_node(nid, obj=cls(x, y, label=str(nid)))
        self._model.append_node(nid)
        self.graphChanged.emit()

    @Slot(int, str)
    def setNodeShape(self, nid: int, shape: str):
        self._node(nid).shape = shape
        self._model.notify_row(nid, [NodesModel.ShapeRole])

    @Slot(int, str)
    def setNodeColor(self, nid: int, color: str):
        self._node(nid).color = color
        self._model.notify_row(nid, [NodesModel.ColorRole])

    @Slot(int, int, str, result=bool)
    def addEdge(self, a: int, b: int, edge_class: str) -> bool:
        if a == b or a not in self._g or b not in self._g \
                or self._g.has_edge(a, b):
            return False
        cls = BaseEdge.registry.get(edge_class, DefaultEdge)
        self._g.add_edge(a, b, obj=cls())
        for nid in (a, b):
            self._model.notify_row(nid, [NodesModel.DegreeRole])
        self.clearHighlight()
        self.graphChanged.emit()
        return True

    @Slot(int, int)
    def removeEdge(self, a: int, b: int):
        if not self._g.has_edge(a, b):
            return
        self._g.remove_edge(a, b)
        for nid in (a, b):
            self._model.notify_row(nid, [NodesModel.DegreeRole])
        self.clearHighlight()
        self.graphChanged.emit()

    @Slot(int, int, str)
    def setEdgeColor(self, a: int, b: int, color: str):
        if self._g.has_edge(a, b):
            self._edge(a, b).color = color
            self.graphChanged.emit()

    @Slot(int, int, float)
    def setEdgeWidth(self, a: int, b: int, width: float):
        if self._g.has_edge(a, b):
            self._edge(a, b).width = width
            self.graphChanged.emit()

    @Slot(int, int, str)
    def setEdgeLine(self, a: int, b: int, line: str):
        if self._g.has_edge(a, b):
            self._edge(a, b).line = line
            self.graphChanged.emit()

    @Slot(int)
    def removeNode(self, nid: int):
        if nid not in self._g:
            return
        neighbors = list(self._g.neighbors(nid))
        self._g.remove_node(nid)          # networkx прибирає й інцидентні ребра
        self._model.remove_node(nid)
        for nb in neighbors:              # у сусідів змінився ступінь
            self._model.notify_row(nb, [NodesModel.DegreeRole])
        self.clearHighlight()
        self.graphChanged.emit()

    @Slot(float, float, result=int)
    def nodeAt(self, x: float, y: float) -> int:
        """nodeId вершини під точкою (x, y) або -1. Для хіт-тесту з QML."""
        hit2 = 26.0 * 26.0                # радіус влучання (вершина ~44px)
        best, best_d = -1, hit2
        for nid in self._g.nodes:
            node = self._node(nid)
            dx, dy = node.x - x, node.y - y
            d = dx * dx + dy * dy
            if d <= best_d:
                best, best_d = nid, d
        return best

    @Slot(int, result="QVariantMap")
    def nodeInfo(self, nid: int):
        if nid not in self._g:
            return {}
        node = self._node(nid)
        return {"label": node.label, "shape": node.shape,
                "color": node.color, "x": node.x, "y": node.y,
                "klass": type(node).type_name}

    @Slot(float, float, result="QVariantMap")
    def edgeAt(self, x: float, y: float):
        """Ребро під точкою (x, y): {"a", "b"} або {}. Для хіт-тесту."""
        hit2 = 7.0 * 7.0                  # допуск влучання у лінію, px^2
        best, best_d = None, hit2
        for a, b in self._g.edges():
            na, nb = self._node(a), self._node(b)
            d = _point_segment_dist2(x, y, na.x, na.y, nb.x, nb.y)
            if d <= best_d:
                best, best_d = (a, b), d
        return {"a": best[0], "b": best[1]} if best else {}

    @Slot(int, int, result="QVariantMap")
    def edgeInfo(self, a: int, b: int):
        if not self._g.has_edge(a, b):
            return {}
        edge = self._edge(a, b)
        return {"label": f"{self._node(a).label}–{self._node(b).label}",
                "color": edge.color, "width": edge.width, "line": edge.line,
                "klass": type(edge).type_name}

    @Slot(int, float, float)
    def moveNode(self, nid: int, x: float, y: float):
        node = self._node(nid)
        node.x = x
        node.y = y
        self._model.notify_row(nid, [NodesModel.XRole, NodesModel.YRole])
        self.graphChanged.emit()

    @Slot()
    def clear(self):
        self._g.clear()
        self._next_id = 1
        self._path_edges.clear()
        self._model.reset_all()
        self.graphChanged.emit()

    # --- збереження/завантаження ---

    @Slot(QUrl, result=str)
    def saveToFile(self, url: QUrl) -> str:
        path = url.toLocalFile()
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(storage.graph_to_json(self._g))
        except OSError as e:
            return f"Не вдалося зберегти: {e}"
        return f"Збережено: {path}"

    @Slot(QUrl, result=str)
    def loadFromFile(self, url: QUrl) -> str:
        path = url.toLocalFile()
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except OSError as e:
            return f"Не вдалося відкрити: {e}"

        new_g = nx.Graph()
        try:
            next_id = storage.graph_from_json(text, new_g)
        except (ValueError, KeyError, TypeError) as e:
            return f"Не вдалося прочитати граф: {e}"

        # застосовуємо завантажене лише після успішного розбору
        self._g.clear()
        self._g.update(new_g)
        self._next_id = next_id
        self._path_edges.clear()
        self._model.reset_with(self._g.nodes)
        self.classesChanged.emit()
        self.graphChanged.emit()
        return (f"Відкрито: {path}  (вершин: {self._g.number_of_nodes()}, "
                f"ребер: {self._g.number_of_edges()})")

    # --- дані для малювання ребер ---

    @Slot(result="QVariantList")
    def edgeList(self):
        out = []
        for a, b, data in self._g.edges(data=True):
            na, nb = self._node(a), self._node(b)
            edge: BaseEdge = data["obj"]
            out.append({
                "x1": na.x, "y1": na.y,
                "x2": nb.x, "y2": nb.y,
                "color": edge.color, "width": edge.width, "line": edge.line,
                "inPath": frozenset((a, b)) in self._path_edges,
            })
        return out

    # --- алгоритми NetworkX ---

    @Slot(int, int, result=str)
    def findShortestPath(self, a: int, b: int) -> str:
        try:
            path = nx.shortest_path(self._g, a, b)
        except nx.NetworkXNoPath:
            self.clearHighlight()
            self.graphChanged.emit()
            return "Шляху між цими вершинами не існує"
        self._path_edges = {frozenset(p) for p in zip(path, path[1:])}
        self._model.set_path(set(path))
        self.graphChanged.emit()
        labels = [self._node(n).label for n in path]
        return (f"Найкоротший шлях: {' → '.join(labels)}  "
                f"(довжина {len(path) - 1})")

    @Slot()
    def clearHighlight(self):
        self._path_edges.clear()
        self._model.set_path(set())
        self.graphChanged.emit()
