"""Структури даних редактора графа.

NodesModel   — QAbstractListModel поверх вершин nx.Graph для QML.
GraphBackend — фасад над nx.Graph: редагування, алгоритми, статистика.
EdgeLayer    — QQuickPaintedItem, що малює всі ребра напряму з графа.

Вершини і ребра графа — це об'єкти родин елементів (нащадки BaseNode
та BaseEdge, див. elements.py); nx.Graph зберігає їх в атрибуті "obj"
вершини (за цілим ключем nodeId) чи ребра (за парою ключів).

Сигнали бекенда розділені за вартістю реакції: graphChanged — зміна
структури (перераховуються статистика і лічильники класів),
edgesChanged — лише геометрія чи стиль ребер (тільки перемалювання
шару ребер). Завдяки цьому перетягування вершини не перераховує
компоненти зв'язності й класи на кожен рух миші.
"""

from itertools import combinations
from time import monotonic

import networkx as nx
from PySide6.QtCore import (
    Property,
    QAbstractListModel,
    QByteArray,
    QLineF,
    QModelIndex,
    QObject,
    QPointF,
    QSize,
    Qt,
    QTimer,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtQuick import QQuickPaintedItem

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
    DescriptionRole = Qt.UserRole + 10
    OpacityRole = Qt.UserRole + 11

    def __init__(self, graph: nx.Graph, parent=None):
        super().__init__(parent)
        self._g = graph
        self._ids: list[int] = []          # порядок рядків моделі
        self._rows: dict[int, int] = {}    # nodeId → рядок, O(1) для row_of
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
            self.DescriptionRole: QByteArray(b"nodeDescription"),
            self.OpacityRole: QByteArray(b"nodeOpacity"),
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
        if role == self.DescriptionRole:
            return node.description
        if role == self.OpacityRole:
            return node.opacity
        return None

    # --- допоміжні методи для бекенда ---

    def row_of(self, nid: int) -> int:
        return self._rows[nid]

    def append_node(self, nid: int):
        row = len(self._ids)
        self.beginInsertRows(QModelIndex(), row, row)
        self._ids.append(nid)
        self._rows[nid] = row
        self.endInsertRows()

    def remove_node(self, nid: int):
        row = self.row_of(nid)
        self.beginRemoveRows(QModelIndex(), row, row)
        self._ids.pop(row)
        del self._rows[nid]
        for i in range(row, len(self._ids)):   # рядки нижче зсунулись
            self._rows[self._ids[i]] = i
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
        self._rows = {nid: i for i, nid in enumerate(self._ids)}
        self._path_nodes.clear()
        self.endResetModel()

    def reset_all(self):
        self.beginResetModel()
        self._ids.clear()
        self._rows.clear()
        self._path_nodes.clear()
        self.endResetModel()


class GraphBackend(QObject):
    """Тримає nx.Graph і надає QML операції над ним."""

    graphChanged = Signal()     # структура: статистика, лічильники класів
    edgesChanged = Signal()     # стиль/підсвітка ребер — перемалювання
    nodeMoved = Signal(int, float, float)   # рух вершини: (nid, x, y)
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

    @Slot(str, str, "QVariantMap", result=bool)
    def updateClass(self, family: str, name: str, design: dict) -> bool:
        """Змінює дизайн наявного класу; елементи без власних перекриттів
        підхоплюють його одразу (StyleAttr читає default_* динамічно)."""
        root = ElementMeta.families.get(family)
        if root is None:
            return False
        cls = root.registry.get(name)
        if cls is None:
            return False
        for field, value in design.items():
            if field in root.style_fields:
                setattr(cls, "default_" + field, value)
        if family == "node":
            self._model.notify_all([NodesModel.ShapeRole,
                                    NodesModel.ColorRole,
                                    NodesModel.OpacityRole])
        else:
            self.edgesChanged.emit()   # кеш EdgeLayer стане недійсним
        self.classesChanged.emit()
        return True

    @Slot(int, str)
    def setNodeClass(self, nid: int, class_name: str):
        cls = BaseNode.registry.get(class_name)
        if cls is None or nid not in self._g:
            return
        old = self._node(nid)
        # новий об'єкт без перекриттів стилю — вершина приймає дизайн класу
        self._g.nodes[nid]["obj"] = cls(old.x, old.y, old.label,
                                        old.description)
        self._model.notify_row(nid, [NodesModel.ShapeRole,
                                     NodesModel.ColorRole,
                                     NodesModel.OpacityRole,
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

    @Slot(int, float)
    def setNodeOpacity(self, nid: int, opacity: float):
        self._node(nid).opacity = opacity
        self._model.notify_row(nid, [NodesModel.OpacityRole])

    @Slot(int, str)
    def setNodeLabel(self, nid: int, text: str):
        self._node(nid).label = text
        self._model.notify_row(nid, [NodesModel.LabelRole])

    @Slot(int, str)
    def setNodeDescription(self, nid: int, text: str):
        self._node(nid).description = text
        self._model.notify_row(nid, [NodesModel.DescriptionRole])

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
            self.edgesChanged.emit()

    @Slot(int, int, float)
    def setEdgeWidth(self, a: int, b: int, width: float):
        if self._g.has_edge(a, b):
            self._edge(a, b).width = width
            self.edgesChanged.emit()

    @Slot(int, int, str)
    def setEdgeLine(self, a: int, b: int, line: str):
        if self._g.has_edge(a, b):
            self._edge(a, b).line = line
            self.edgesChanged.emit()

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
        return {"label": node.label, "description": node.description,
                "shape": node.shape, "color": node.color,
                "opacity": node.opacity, "x": node.x, "y": node.y,
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
        # структура не змінилась — статистику й класи не перераховуємо,
        # а шар ребер оновлює лише лінії цієї вершини
        self.nodeMoved.emit(nid, x, y)

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

    # --- алгоритми NetworkX ---

    @Slot(int, int, result=str)
    def findShortestPath(self, a: int, b: int) -> str:
        try:
            path = nx.shortest_path(self._g, a, b)
        except nx.NetworkXNoPath:
            self.clearHighlight()
            return "Шляху між цими вершинами не існує"
        self._path_edges = {frozenset(p) for p in zip(path, path[1:])}
        self._model.set_path(set(path))
        self.edgesChanged.emit()
        labels = [self._node(n).label for n in path]
        return (f"Найкоротший шлях: {' → '.join(labels)}  "
                f"(довжина {len(path) - 1})")

    @Slot()
    def clearHighlight(self):
        self._path_edges.clear()
        self._model.set_path(set())
        self.edgesChanged.emit()


class EdgeLayer(QQuickPaintedItem):
    """Шар ребер: малює їх напряму з nx.Graph одним проходом QPainter.

    Заміна пари Canvas + edgeList(): дані не конвертуються у QVariant
    на кожен кадр, а ребра групуються за пером (колір, товщина, штрих,
    підсвітка шляху), тож QPainter отримує кілька викликів drawLines
    замість тисяч окремих stroke. Перемальовується за сигналами бекенда
    graphChanged (структура) та edgesChanged (геометрія/стиль).

    Малювання йде у власний буфер ARGB32_Premultiplied, який потім
    копіюється у painter вузла одним drawImage у режимі Source. Це
    принципово: під RHI текстура QQuickPaintedItem має формат
    RGBA8888, для якого у растрового рушія немає оптимізованих функцій
    змішування — лінії малюються у ~6–7 разів повільніше (виміряно:
    32 мс проти 4.8 мс на 1225 ребрах). Конвертація ж усієї поверхні
    разом із копіюванням — один швидкий прохід (~1–2 мс).

    Адаптивна якість: під час шквалу оновлень (перетягування вершини)
    у великому графі кадри малюються без згладжування (AA — це ще ~6×
    вартості растеризації), а після паузи _REFINE_MS таймер домальовує
    чистовий кадр з AA. Важливо: QQuickPaintedItem сам вмикає AA-хінт
    ще до виклику paint(), тож стан хінта виставляється явно в обидва
    боки. На HiDPI у швидкому режимі текстура зменшується до логічного
    розміру: площа менша у dpr², а трансформація лишається identity.

    Геометрія кешується між кадрами: повна перебудова QLineF-ів лише при
    зміні структури чи стилю (graphChanged/edgesChanged); рух вершини
    (nodeMoved) мутує тільки її інцидентні лінії прямо в кеші.
    """

    sourceChanged = Signal()
    highlightColorChanged = Signal()

    # штрихи Canvas-версії у пікселях; QPen чекає їх в одиницях товщини
    _DASHES = {"dash": (8.0, 6.0), "dot": (2.0, 5.0)}

    _FAST_EDGES = 300    # від скількох ребер вмикається швидкий режим
    _BURST_GAP = 0.1     # с між оновленнями, щоб вважати їх шквалом
    _REFINE_MS = 150     # пауза тиші перед чистовим кадром

    def __init__(self, parent=None):
        super().__init__(parent)
        self._backend: GraphBackend | None = None
        self._highlight = QColor("#2ecc71")
        # кеш геометрії: перо → [QLineF]; вершина → [(QLineF, чи кінець P1)]
        self._groups: dict[tuple, list[QLineF]] | None = None
        self._incident: dict[int, list[tuple[QLineF, bool]]] = {}
        self._fast = False           # поточні кадри — швидкі (шквал)
        self._low_res = False        # текстура зараз зменшена
        self._buffer: QImage | None = None   # ARGB32-буфер малювання
        self._last_request = 0.0
        self._refine = QTimer(self)
        self._refine.setSingleShot(True)
        self._refine.setInterval(self._REFINE_MS)
        self._refine.timeout.connect(self._refine_pass)

    def _enter_fast(self):
        """Вмикає швидкий режим (якщо граф великий) і планує чистовий кадр."""
        if (self._backend is None
                or self._backend._g.number_of_edges() < self._FAST_EDGES):
            return
        if not self._fast:
            self._fast = True
            w, h = self.width(), self.height()
            dpr = (self.window().effectiveDevicePixelRatio()
                   if self.window() else 1.0)
            # на HiDPI малюємо в текстуру логічного розміру: площа менша
            # у dpr², а трансформація лишається identity (швидкий шлях
            # растеризатора ліній). На dpr=1 зиску немає — не чіпаємо.
            if w > 0 and h > 0 and dpr > 1.01:
                self.setTextureSize(QSize(max(1, int(w)), max(1, int(h))))
                self._low_res = True
        self._refine.start()

    def _request(self):
        """Запит перемалювання; детектор шквалу оновлень."""
        now = monotonic()
        if now - self._last_request < self._BURST_GAP:
            self._enter_fast()
        self._last_request = now
        self.update()

    def _mark_dirty(self):
        """Структура чи стиль змінились — кеш геометрії недійсний."""
        self._groups = None
        self._request()

    def _node_moved(self, nid: int, x: float, y: float):
        if self._groups is not None:
            point = QPointF(x, y)
            for line, at_p1 in self._incident.get(nid, ()):
                if at_p1:
                    line.setP1(point)
                else:
                    line.setP2(point)
        # перетягування інтерактивне з першого ж кадру, без детектора
        self._enter_fast()
        self._last_request = monotonic()
        self.update()

    def _refine_pass(self):
        self._fast = False
        if self._low_res:
            self._low_res = False
            self.setTextureSize(QSize())    # авто: розмір елемента × DPR
        self.update()

    def _source(self):
        return self._backend

    def _set_source(self, backend):
        if backend is self._backend:
            return
        if self._backend is not None:
            try:
                self._backend.graphChanged.disconnect(self._mark_dirty)
                self._backend.edgesChanged.disconnect(self._mark_dirty)
                self._backend.nodeMoved.disconnect(self._node_moved)
            except RuntimeError:
                pass    # бекенд уже знищується разом із застосунком
        self._backend = backend
        if backend is not None:
            backend.graphChanged.connect(self._mark_dirty)
            backend.edgesChanged.connect(self._mark_dirty)
            backend.nodeMoved.connect(self._node_moved)
        self._groups = None
        self.sourceChanged.emit()
        self.update()

    source = Property(QObject, _source, _set_source, notify=sourceChanged)

    def _highlight_color(self):
        return self._highlight

    def _set_highlight_color(self, color):
        color = QColor(color)
        if color == self._highlight:
            return
        self._highlight = color
        self.highlightColorChanged.emit()
        self.update()

    highlightColor = Property(QColor, _highlight_color,
                              _set_highlight_color,
                              notify=highlightColorChanged)

    def _rebuild(self):
        """Повна перебудова кешу геометрії з графа."""
        g = self._backend._g
        path = self._backend._path_edges
        nodes = g.nodes
        groups: dict[tuple, list[QLineF]] = {}
        incident: dict[int, list[tuple[QLineF, bool]]] = {}
        for a, b, data in g.edges(data=True):
            edge: BaseEdge = data["obj"]
            na, nb = nodes[a]["obj"], nodes[b]["obj"]
            in_path = bool(path) and frozenset((a, b)) in path
            key = (edge.color, edge.width, edge.line, in_path)
            line = QLineF(na.x, na.y, nb.x, nb.y)
            groups.setdefault(key, []).append(line)
            incident.setdefault(a, []).append((line, True))
            incident.setdefault(b, []).append((line, False))
        self._groups = groups
        self._incident = incident

    def paint(self, painter: QPainter):
        if self._backend is None:
            return
        g = self._backend._g
        if g.number_of_edges() == 0:
            return
        if self._groups is None:
            self._rebuild()

        dev = painter.device()
        dw, dh = dev.width(), dev.height()
        if dw <= 0 or dh <= 0:
            return

        # малюємо у власний ARGB32-буфер: цільова текстура вузла має
        # формат RGBA8888, у якому растеризація ліній у ~6 разів
        # повільніша (див. докстрінг класу)
        buf = self._buffer
        if buf is None or buf.width() != dw or buf.height() != dh:
            buf = QImage(dw, dh, QImage.Format.Format_ARGB32_Premultiplied)
            self._buffer = buf
        buf.fill(0)

        p = QPainter(buf)
        # хінт виставляється явно в обидва боки: швидкі кадри — без AA
        fast = self._fast and g.number_of_edges() >= self._FAST_EDGES
        p.setRenderHint(QPainter.RenderHint.Antialiasing, not fast)

        # буфер має роздільність текстури; переводимо логічні координати
        # кешу в пікселі буфера (identity, коли розміри збігаються)
        item_w = self.width()
        if item_w > 0:
            s = dw / item_w
            if abs(s - 1.0) > 0.001:
                p.scale(s, s)

        for (color, width, line, in_path), lines in self._groups.items():
            if in_path:
                width += 2
            pen = QPen(self._highlight if in_path else QColor(color))
            pen.setWidthF(width)
            pen.setCapStyle(Qt.PenCapStyle.FlatCap)
            dash = self._DASHES.get(line)
            if dash:
                pen.setDashPattern([dash[0] / width, dash[1] / width])
            p.setPen(pen)
            p.drawLines(lines)
        p.end()

        # один повноекранний перенос: Source копіює пікселі без
        # змішування, конвертація формату — швидкий SIMD-прохід
        painter.save()
        painter.resetTransform()
        painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_Source)
        painter.drawImage(0, 0, buf)
        painter.restore()
