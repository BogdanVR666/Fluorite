"""Прослойка між структурою даних (layers.py) та QML.

NodesModel   — QAbstractListModel поверх пулу вершин сховища.
GraphBackend — тонкий адаптер: транслює дії UI в методи LayeredGraph,
               а їх результати — у сигнали та ролі моделі. Власного
               стану даних не має; йому належить лише UI-стан
               (виділення) і механіка сповіщень (таймери, коалесценція).
EdgeLayer    — QQuickPaintedItem, що малює всі ребра напряму зі сховища.

Сам стан (класи Family, пул вершин, шар-граф на кожен клас ребер) живе
в LayeredGraph — див. layers.py; схема елементів — elements.py,
nodes.py, edges.py; файлами займається storage.py.

Ребро адресується трійкою (клас, a, b): ребра різних класів на одній
парі вершин — різні об'єкти, тож слоти ребер приймають клас першим
аргументом. QML тримає його в EdgeMenu.currentClass.

Сигнали бекенда розділені за вартістю реакції:
  graphChanged   — зміна структури; шар ребер перемальовується негайно;
  edgesChanged   — лише геометрія чи стиль ребер (тільки перемалювання);
  summaryChanged — зведені дані (статистика, лічильники класів). Шле його
                   таймер із коалесценцією: шквал змін (імпорт файла,
                   кліка на сотні вершин) дає одне оновлення панелі,
                   а не одне на кожну вершину.
Завдяки цьому перетягування вершини не перераховує компоненти
зв'язності й класи на кожен рух миші.
"""

import math
from itertools import combinations
from time import monotonic

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
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen
from PySide6.QtQuick import QQuickPaintedItem

import storage
from layers import LayeredGraph
from nodes import Node


def _point_segment_dist2(px: float, py: float,
                         x1: float, y1: float, x2: float, y2: float) -> float:
    """Квадрат відстані від точки (px, py) до відрізка (x1,y1)-(x2,y2)."""
    vx, vy = x2 - x1, y2 - y1
    wx, wy = px - x1, py - y1
    seg2 = vx * vx + vy * vy
    t = 0.0 if seg2 == 0.0 else max(0.0, min(1.0, (wx * vx + wy * vy) / seg2))
    dx, dy = wx - t * vx, wy - t * vy
    return dx * dx + dy * dy


_BEND_STEP = 14.0   # відстань між сусідніми паралельними ребрами, px


def _visual_owners(store) -> dict[int, int | None]:
    """Видимий представник кожної вершини пулу.

    Просто закешований store.visual_owner для гарячих проходів по всіх
    ребрах: метавершина згорнутої групи представляє своїх членів, None —
    вершину зараз не видно зовсім (метавершина розгорнутої групи).
    """
    return {nid: store.visual_owner(nid) for nid in store.nodes}


def _edge_bends(store) -> dict[tuple[str, int, int], float]:
    """Прогин (апекс дуги, px) для ребер, що ділять пару кінців.

    Кінці — видимі представники (_visual_owners): ребра різних вершин,
    сховані в одну згорнуту групу, теж стають "паралельними" і
    розводяться дугами. Невидимі ребра (всередині згорнутої групи або
    до метавершини розгорнутої) пропускаються.

    Ключ — (клас, u, v) у тій самій орієнтації, що віддає store.edges(),
    тож споживач шукає прогин без перестановок. Ребра без "сусідів" у
    словник не потрапляють і малюються прямими — швидкий шлях батчингу
    не втрачається. Прогини розкладаються симетрично навколо нуля, а
    знак нормалізується до канонічного напряму пари (менший представник
    → більший): ребра з протилежною орієнтацією вигинаються у свій бік,
    а не накладаються знову.
    """
    owners = _visual_owners(store)
    pairs: dict[tuple[int, int], list[tuple[str, int, int, int]]] = {}
    for name, u, v, _ in store.edges():
        ou, ov = owners[u], owners[v]
        if ou is None or ov is None or ou == ov:
            continue
        key = (ou, ov) if ou < ov else (ov, ou)
        pairs.setdefault(key, []).append((name, u, v, ou))
    bends: dict[tuple[str, int, int], float] = {}
    for (a, _), group in pairs.items():
        k = len(group)
        if k < 2:
            continue
        for i, (name, u, v, ou) in enumerate(group):
            off = (i - (k - 1) / 2.0) * _BEND_STEP
            bends[(name, u, v)] = off if ou == a else -off
    return bends


def _bend_control(x1: float, y1: float, x2: float, y2: float,
                  bend: float) -> tuple[float, float]:
    """Контрольна точка квадратичної кривої з прогином bend посередині.

    Крива проходить через середину відрізка контроль-хорда, тому щоб
    апекс дуги дорівнював bend, контрольна точка відсувається на 2·bend.
    """
    dx, dy = x2 - x1, y2 - y1
    d = math.hypot(dx, dy)
    if d < 1e-6:                       # вершини збіглись — дуги немає
        return x1, y1
    nx_, ny_ = -dy / d, dx / d         # нормаль ліворуч від напряму
    return ((x1 + x2) / 2.0 + nx_ * 2.0 * bend,
            (y1 + y2) / 2.0 + ny_ * 2.0 * bend)


def _point_bend_dist2(px: float, py: float, x1: float, y1: float,
                      x2: float, y2: float, bend: float) -> float:
    """Квадрат відстані від точки до дуги з прогином bend.

    Дуга наближається ламаною з 12 ланок — для хіт-тесту по кліку
    точності вистачає, а рахується це лише для паралельних ребер.
    """
    cx, cy = _bend_control(x1, y1, x2, y2, bend)
    steps = 12
    best = math.inf
    lx, ly = x1, y1
    for i in range(1, steps + 1):
        t = i / steps
        mt = 1.0 - t
        qx = mt * mt * x1 + 2.0 * mt * t * cx + t * t * x2
        qy = mt * mt * y1 + 2.0 * mt * t * cy + t * t * y2
        best = min(best, _point_segment_dist2(px, py, lx, ly, qx, qy))
        lx, ly = qx, qy
    return best


_NODE_R = 22.0                          # радіус вершини (Node.qml: 44px)
_BARB_BASE = 7.0                        # довжина вусика = base + k·товщина:
_BARB_K = 1.8                           # у товстої лінії вістря має рости
_BARB_COS = math.cos(math.radians(26))  # 26° — половина кута розкриття
_BARB_SIN = math.sin(math.radians(26))


def _barb_len(width: float) -> float:
    return _BARB_BASE + _BARB_K * width


def _fit_arrow(line: QLineF, left: QLineF, right: QLineF, blen: float):
    """Кладе вусики стрілки на кінець P2 лінії (лінія йде від джерела).

    Вістря відсуваємо на радіус вершини, інакше стрілка ховається під
    самою вершиною. Вусики — окремі QLineF, які мутуються на місці: той
    самий об'єкт лежить і в списку для drawLines, і в кеші інцидентних
    ліній вершини, тож рух вершини не перебудовує жодного списку.
    """
    dx, dy = line.x2() - line.x1(), line.y2() - line.y1()
    d = math.hypot(dx, dy)
    if d <= _NODE_R:            # вершини налізли одна на одну
        # вироджуємо вусики в точку під ціллю, щоб не лишити артефакт
        left.setLine(line.x2(), line.y2(), line.x2(), line.y2())
        right.setLine(line.x2(), line.y2(), line.x2(), line.y2())
        return
    ux, uy = dx / d, dy / d
    tx, ty = line.x2() - ux * _NODE_R, line.y2() - uy * _NODE_R
    # вектор назад (-u), повернутий на ±кут розкриття
    lx, ly = -ux * _BARB_COS + uy * _BARB_SIN, -ux * _BARB_SIN - uy * _BARB_COS
    rx, ry = -ux * _BARB_COS - uy * _BARB_SIN, ux * _BARB_SIN - uy * _BARB_COS
    left.setLine(tx, ty, tx + lx * blen, ty + ly * blen)
    right.setLine(tx, ty, tx + rx * blen, ty + ry * blen)


class NodesModel(QAbstractListModel):
    """Надає пул вершин сховища як модель для QML Repeater."""

    NodeIdRole = Qt.UserRole + 1
    XRole = Qt.UserRole + 2
    YRole = Qt.UserRole + 3
    LabelRole = Qt.UserRole + 4
    DegreeRole = Qt.UserRole + 6
    ShapeRole = Qt.UserRole + 7
    ColorRole = Qt.UserRole + 8
    ClassRole = Qt.UserRole + 9
    DescriptionRole = Qt.UserRole + 10
    OpacityRole = Qt.UserRole + 11
    SelectedRole = Qt.UserRole + 12
    HiddenRole = Qt.UserRole + 13    # вершину зараз не видно (групи)
    IsGroupRole = Qt.UserRole + 14   # вершина — метавершина групи
    MembersRole = Qt.UserRole + 15   # скільки вершин у її групі

    def __init__(self, store: LayeredGraph, parent=None):
        super().__init__(parent)
        self._store = store
        self._ids: list[int] = []          # порядок рядків моделі
        self._rows: dict[int, int] = {}    # nodeId → рядок, O(1) для row_of
        # Виділені вершини. Живуть тут, а не в QML, щоб делегат читав свій
        # стан роллю за O(1) — інакше кожен із них шукав би себе в масиві.
        self._selected: set[int] = set()

    # --- обов'язковий інтерфейс QAbstractListModel ---

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._ids)

    def roleNames(self):
        return {
            self.NodeIdRole: QByteArray(b"nodeId"),
            self.XRole: QByteArray(b"px"),
            self.YRole: QByteArray(b"py"),
            self.LabelRole: QByteArray(b"label"),
            self.DegreeRole: QByteArray(b"degree"),
            self.ShapeRole: QByteArray(b"nodeShape"),
            self.ColorRole: QByteArray(b"nodeColor"),
            self.ClassRole: QByteArray(b"nodeClass"),
            self.DescriptionRole: QByteArray(b"nodeDescription"),
            self.OpacityRole: QByteArray(b"nodeOpacity"),
            self.SelectedRole: QByteArray(b"nodeSelected"),
            self.HiddenRole: QByteArray(b"nodeHidden"),
            self.IsGroupRole: QByteArray(b"isGroup"),
            self.MembersRole: QByteArray(b"memberCount"),
        }

    def data(self, index, role):
        if not index.isValid() or not (0 <= index.row() < len(self._ids)):
            return None
        nid = self._ids[index.row()]
        node: Node = self._store.nodes[nid]
        if role == self.NodeIdRole:
            return nid
        if role == self.XRole:
            return node.x
        if role == self.YRole:
            return node.y
        if role == self.LabelRole:
            return node.label
        if role == self.DegreeRole:
            return self._store.degree(nid)
        if role == self.ShapeRole:
            return node.shape
        if role == self.ColorRole:
            return node.color
        if role == self.ClassRole:
            return node.klass.name
        if role == self.DescriptionRole:
            return node.description
        if role == self.OpacityRole:
            return node.opacity
        if role == self.SelectedRole:
            return nid in self._selected
        if role == self.HiddenRole:
            return self._store.visual_owner(nid) != nid
        if role == self.IsGroupRole:
            return nid in self._store.group_of_node
        if role == self.MembersRole:
            gid = self._store.group_of_node.get(nid)
            return 0 if gid is None else len(self._store.groups[gid].members)
        return None

    # --- допоміжні методи для бекенда ---

    def row_of(self, nid: int) -> int:
        return self._rows[nid]

    def has_node(self, nid: int) -> bool:
        return nid in self._rows

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
        self._selected.discard(nid)
        self.endRemoveRows()

    def notify_row(self, nid: int, roles: list[int]):
        row = self.row_of(nid)
        idx = self.index(row)
        self.dataChanged.emit(idx, idx, roles)

    def notify_all(self, roles: list[int]):
        if self._ids:
            self.dataChanged.emit(
                self.index(0), self.index(len(self._ids) - 1), roles)

    def set_selected(self, nodes: set[int]):
        self._selected = nodes
        self.notify_all([self.SelectedRole])

    def remove_nodes(self, ids: set[int]):
        """Прибирає групу вершин одним скиданням моделі.

        Порядкове remove_node переіндексовує хвіст _rows на кожній
        вершині, тож видалення k вершин із n коштувало б O(n·k).
        Скидання моделі робить те саме за O(n) — але воно перестворює
        всі делегати, тож для однієї вершини лишаємо звичайний шлях.
        """
        if len(ids) == 1:
            self.remove_node(next(iter(ids)))
            return
        self.beginResetModel()
        self._ids = [nid for nid in self._ids if nid not in ids]
        self._rows = {nid: i for i, nid in enumerate(self._ids)}
        self._selected -= ids     # на місці: множину поділено з бекендом
        self.endResetModel()

    def reset_with(self, ids):
        """Повністю замінює рядки моделі (після завантаження з файла)."""
        self.beginResetModel()
        self._ids = list(ids)
        self._rows = {nid: i for i, nid in enumerate(self._ids)}
        self._selected.clear()
        self.endResetModel()

    def reset_all(self):
        self.beginResetModel()
        self._ids.clear()
        self._rows.clear()
        self._selected.clear()
        self.endResetModel()


class GraphBackend(QObject):
    """Прослойка між сховищем LayeredGraph і QML."""

    graphChanged = Signal()     # структура: шар ребер перемальовується
    edgesChanged = Signal()     # стиль/підсвітка ребер — перемалювання
    nodeMoved = Signal(int, float, float)   # рух вершини: (nid, x, y)
    classesChanged = Signal()   # з'явився новий клас вершин
    selectionChanged = Signal() # змінився набір виділених вершин
    summaryChanged = Signal()   # статистика й лічильники класів (з паузою)

    _SUMMARY_MS = 100           # не частіше 10 оновлень зведення на секунду

    def __init__(self, parent=None):
        super().__init__(parent)
        # весь стан даних — у сховищі; бекенд ним не володіє, а керує
        self._store = LayeredGraph()
        self._model = NodesModel(self._store, self)
        # Та сама множина, що й у моделі, — не копія: коли модель прибирає
        # видалену вершину з виділення, бекенд бачить це без синхронізації.
        self._selected: set[int] = self._model._selected
        self._summary = QTimer(self)
        self._summary.setSingleShot(True)
        self._summary.setInterval(self._SUMMARY_MS)
        self._summary.timeout.connect(self.summaryChanged)

    def _node(self, nid: int) -> Node:
        return self._store.nodes[nid]

    # --- сповіщення про зміну структури ---

    def _structure_changed(self):
        """Ребра перемальовуємо негайно, зведення — з коалесценцією.

        Таймер не перезапускається, поки тікає: під час довгого шквалу
        змін панель усе одно оновлюється рівно кожні _SUMMARY_MS.
        """
        self.graphChanged.emit()
        if not self._summary.isActive():
            self._summary.start()

    def _summary_now(self):
        """Зведення негайно — для разових змін усього графа."""
        self._summary.stop()
        self.summaryChanged.emit()

    # --- властивості для QML ---

    @Property(QObject, constant=True)
    def nodesModel(self):
        return self._model

    @Property(str, notify=summaryChanged)
    def stats(self):
        n = len(self._store.nodes)
        m = self._store.edge_count()
        c = self._store.component_count()
        return f"Вершин: {n}  •  Ребер: {m}  •  Компонент зв'язності: {c}"

    @Property(int, notify=selectionChanged)
    def selectionCount(self):
        return len(self._selected)

    # --- виділення вершин ---
    #
    # Набір виділених лежить у моделі (роль nodeSelected), тож делегат
    # знає свій стан без пошуку по масиву. Групові операції нижче беруть
    # цілі просто з self._selected — QML не передає списки id.

    def _selection_changed(self):
        """Штовхнути модель і QML після зміни self._selected."""
        self._model.set_selected(self._selected)
        self.selectionChanged.emit()

    @Slot(int, bool)
    def selectNode(self, nid: int, additive: bool):
        """Виділити вершину. additive (Shift) — перемкнути її в наборі,
        інакше — зробити єдиною виділеною."""
        if nid not in self._store.nodes:
            return
        if additive:
            self._selected ^= {nid}
        else:
            self._selected.clear()
            self._selected.add(nid)
        self._selection_changed()

    @Slot(float, float, float, float, bool, result=int)
    def selectInRect(self, x: float, y: float, w: float, h: float,
                     additive: bool) -> int:
        """Виділити вершини, центри яких потрапили в прямокутник."""
        x2, y2 = x + w, y + h
        hits = {nid for nid, node in self._store.nodes.items()
                if x <= node.x <= x2 and y <= node.y <= y2
                and self._store.visual_owner(nid) == nid}
        if not additive:
            self._selected.clear()
        self._selected |= hits
        self._selection_changed()
        return len(hits)

    @Slot()
    def clearSelection(self):
        if not self._selected:
            return
        self._selected.clear()
        self._selection_changed()

    @Slot(int, result=bool)
    def isSelected(self, nid: int) -> bool:
        return nid in self._selected

    # --- класи елементів (родини "node" і "edge") ---

    @Slot(str, result="QVariantList")
    def classList(self, family: str):
        """Класи родини: дизайн і кількість елементів кожного."""
        fam = self._store.families.get(family)
        if fam is None:
            return []
        counts = ({n: len(ids) for n, ids in self._store.node_ids.items()}
                  if family == "node"
                  else {n: g.number_of_edges()
                        for n, g in self._store.layers.items()})
        return [{
            "name": cls.name,
            "count": counts.get(cls.name, 0),
            **cls.design_map(),
        } for cls in fam.classes.values()]

    @Slot(str, str, "QVariantMap", result=bool)
    def createClass(self, family: str, name: str, design: dict) -> bool:
        if not self._store.create_class(family, name, design):
            return False
        self.classesChanged.emit()
        return True

    @Slot(str, str, "QVariantMap", result=bool)
    def updateClass(self, family: str, name: str, design: dict) -> bool:
        """Змінює дизайн наявного класу; елементи без власних перекриттів
        підхоплюють його одразу (styled читає дизайн класу динамічно)."""
        if not self._store.update_class(family, name, design):
            return False
        if family == "node":
            self._model.notify_all([NodesModel.ShapeRole,
                                    NodesModel.ColorRole,
                                    NodesModel.OpacityRole])
        else:
            self.edgesChanged.emit()   # кеш EdgeLayer стане недійсним
        self.classesChanged.emit()
        return True

    _CLASS_ROLES = [NodesModel.ShapeRole, NodesModel.ColorRole,
                    NodesModel.OpacityRole, NodesModel.ClassRole]

    @Slot(str, int, int, str, result=bool)
    def setEdgeClass(self, klass: str, a: int, b: int,
                     new_name: str) -> bool:
        # False, зокрема, коли пара вже зайнята ребром цільового класу
        if not self._store.set_edge_class(klass, a, b, new_name):
            return False
        self._structure_changed()      # перемальовує ребра й лічильники
        return True

    def _bulk_add_edges(self, pairs, edge_cls) -> int:
        """Додає ребра пачкою з одним сповіщенням; повертає к-ть нових."""
        added = self._store.bulk_add_edges(pairs, edge_cls)
        if added:
            self._model.notify_all([NodesModel.DegreeRole])
            self._structure_changed()
        return added

    @Slot(str, str, result=str)
    def connectClassNodes(self, class_name: str, edge_class: str) -> str:
        """З'єднує всі вершини класу між собою (кліка)."""
        ids = self._store.class_ids(class_name)
        if len(ids) < 2:
            return f"У класі «{class_name}» менше двох вершин"
        added = self._bulk_add_edges(combinations(ids, 2),
                                     self._store.edge_class(edge_class))
        return f"Клас «{class_name}»: додано ребер — {added}"

    # --- редагування графа ---

    @Slot(float, float, str)
    def addNode(self, x: float, y: float, class_name: str):
        nid = self._store.add_node(x, y, class_name)
        self._model.append_node(nid)
        self._structure_changed()

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
        # ПКМ-перетяг веде від a до b — це й напрям
        if not self._store.add_edge(a, b, edge_class):
            return False
        for nid in (a, b):
            self._model.notify_row(nid, [NodesModel.DegreeRole])
        self._structure_changed()
        return True

    @Slot(str, int, int)
    def removeEdge(self, klass: str, a: int, b: int):
        if not self._store.remove_edge(klass, a, b):
            return
        for nid in (a, b):
            self._model.notify_row(nid, [NodesModel.DegreeRole])
        self._structure_changed()

    @Slot(str, int, int, str)
    def setEdgeColor(self, klass: str, a: int, b: int, color: str):
        edge = self._store.find_edge(klass, a, b)
        if edge is not None:
            edge.color = color
            self.edgesChanged.emit()

    @Slot(str, int, int, float)
    def setEdgeWidth(self, klass: str, a: int, b: int, width: float):
        edge = self._store.find_edge(klass, a, b)
        if edge is not None:
            edge.width = width
            self.edgesChanged.emit()

    @Slot(str, int, int, str)
    def setEdgeLine(self, klass: str, a: int, b: int, line: str):
        edge = self._store.find_edge(klass, a, b)
        if edge is not None:
            edge.line = line
            self.edgesChanged.emit()

    def _remove_one(self, nid: int):
        """Вершина геть зі сховища й моделі; без сповіщень структури."""
        if nid not in self._store.nodes:
            return
        neighbors = self._store.remove_node(nid)
        self._model.remove_node(nid)      # і викидає nid із self._selected
        for nb in neighbors:              # у сусідів змінився ступінь
            if self._model.has_node(nb):
                self._model.notify_row(nb, [NodesModel.DegreeRole])

    def _drain_orphans(self):
        """Прибирає метавершини груп, що розчинились дорогою.

        Видалення сироти саме може розчинити її батьківську групу і
        поставити в чергу нову сироту — тому цикл до порожньої черги.
        """
        while True:
            orphans = self._store.take_orphans()
            if not orphans:
                return
            for nid in orphans:
                self._remove_one(nid)

    _GROUP_ROLES = [NodesModel.HiddenRole, NodesModel.IsGroupRole,
                    NodesModel.MembersRole]

    @Slot(int)
    def removeNode(self, nid: int):
        if nid not in self._store.nodes:
            return
        was_selected = nid in self._selected
        self._remove_one(nid)
        self._drain_orphans()
        if was_selected:
            self.selectionChanged.emit()
        # членство і видимість могли змінитись (розпуск груп)
        self._model.notify_all(self._GROUP_ROLES)
        self._structure_changed()

    @Slot(float, float, result=int)
    def nodeAt(self, x: float, y: float) -> int:
        """nodeId вершини під точкою (x, y) або -1. Для хіт-тесту з QML."""
        hit2 = 26.0 * 26.0                # радіус влучання (вершина ~44px)
        best, best_d = -1, hit2
        for nid, node in self._store.nodes.items():
            if self._store.visual_owner(nid) != nid:
                continue                  # зараз не видно (групи)
            dx, dy = node.x - x, node.y - y
            d = dx * dx + dy * dy
            if d <= best_d:
                best, best_d = nid, d
        return best

    @Slot(int, result="QVariantMap")
    def nodeInfo(self, nid: int):
        if nid not in self._store.nodes:
            return {}
        node = self._node(nid)
        gid = self._store.member_of.get(nid, -1)     # чий вона член
        own = self._store.group_of_node.get(nid, -1)  # чия метавершина
        return {"label": node.label, "description": node.description,
                "shape": node.shape, "color": node.color,
                "opacity": node.opacity, "x": node.x, "y": node.y,
                "klass": node.klass.name, "groupId": gid,
                "groupLabel": (self._node(self._store.groups[gid].node).label
                               if gid != -1 else ""),
                "isGroup": own != -1, "ownGroupId": own,
                "memberCount": (len(self._store.groups[own].members)
                                if own != -1 else 0)}

    @Slot(float, float, result="QVariantMap")
    def edgeAt(self, x: float, y: float):
        """Ребро під точкою: {"klass", "a", "b"} або {}. Для хіт-тесту.

        Геометрія та сама, що в EdgeLayer: кінці підміняються видимими
        представниками, невидимі ребра пропускаються, паралельні —
        йдуть дугою.
        """
        hit2 = 7.0 * 7.0                  # допуск влучання у лінію, px^2
        owners = _visual_owners(self._store)
        bends = _edge_bends(self._store)
        best, best_d = None, hit2
        for name, a, b, _ in self._store.edges():
            oa, ob = owners[a], owners[b]
            if oa is None or ob is None or oa == ob:
                continue                  # ребра зараз не видно
            na, nb = self._node(oa), self._node(ob)
            bend = bends.get((name, a, b), 0.0)
            if bend:
                d = _point_bend_dist2(x, y, na.x, na.y, nb.x, nb.y, bend)
            else:
                d = _point_segment_dist2(x, y, na.x, na.y, nb.x, nb.y)
            if d <= best_d:
                best, best_d = (name, a, b), d
        if best is None:
            return {}
        return {"klass": best[0], "a": best[1], "b": best[2]}

    @Slot(str, int, int, result="QVariantMap")
    def edgeInfo(self, klass: str, a: int, b: int):
        uv = self._store.orientation(klass, a, b)
        if uv is None:
            return {}
        edge = self._store.find_edge(klass, a, b)
        src, dst = uv                     # орієнтація в шарі і є напрям
        sep = " → " if edge.directed else "–"
        return {"label": f"{self._node(src).label}{sep}{self._node(dst).label}",
                "color": edge.color, "width": edge.width, "line": edge.line,
                "directed": edge.directed,
                "klass": edge.klass.name}

    @Slot(str, int, int)
    def reverseEdge(self, klass: str, a: int, b: int):
        """Розвертає ребро: те, що було джерелом, стає ціллю."""
        if self._store.reverse_edge(klass, a, b):
            self.edgesChanged.emit()

    @Slot(int, float, float)
    def moveNode(self, nid: int, x: float, y: float):
        node = self._node(nid)
        node.x = x
        node.y = y
        self._model.notify_row(nid, [NodesModel.XRole, NodesModel.YRole])
        # структура не змінилась — статистику й класи не перераховуємо,
        # а шар ребер оновлює лише лінії цієї вершини
        self.nodeMoved.emit(nid, x, y)

    # --- групові операції над виділенням ---
    #
    # Дзеркалять одиночні слоти вище, але шлють одне сповіщення на всю
    # групу замість одного на вершину: інакше зміна класу в сотні
    # виділених вершин перерахувала б статистику сотню разів.

    @Slot(int, float, float)
    def moveSelectionTo(self, anchor: int, x: float, y: float):
        """Тягнемо вершину anchor у (x, y), решта виділених — на той
        самий зсув. Зсув рахує бекенд, бо лише він знає стару позицію."""
        if anchor not in self._store.nodes:
            return
        node = self._node(anchor)
        dx, dy = x - node.x, y - node.y
        for nid in self._selected | {anchor}:
            n = self._node(nid)
            n.x = x if nid == anchor else n.x + dx
            n.y = y if nid == anchor else n.y + dy
            self._model.notify_row(nid, [NodesModel.XRole, NodesModel.YRole])
            self.nodeMoved.emit(nid, n.x, n.y)

    @Slot()
    def removeSelection(self):
        if not self._selected:
            return
        doomed = set(self._selected)
        # сховище повертає сусідів поза групою — у них змінився ступінь
        neighbors = self._store.remove_nodes(doomed)
        # одним скиданням, а не по вершині: інакше O(n·k) на переіндексації
        self._model.remove_nodes(doomed)  # і викидає їх із self._selected
        self._drain_orphans()             # метавершини розчинених груп
        for nb in neighbors:
            if self._model.has_node(nb):
                self._model.notify_row(nb, [NodesModel.DegreeRole])
        self._selection_changed()
        self._model.notify_all(self._GROUP_ROLES)
        self._structure_changed()

    @Slot(str)
    def setSelectionClass(self, class_name: str):
        cls = self._store.families["node"].get(class_name)
        if cls is None or not self._selected:
            return
        for nid in self._selected:
            self._store.set_node_class(nid, cls)
        self._model.notify_all(self._CLASS_ROLES)
        self._structure_changed()

    @Slot(str)
    def setSelectionShape(self, shape: str):
        for nid in self._selected:
            self._node(nid).shape = shape
        self._model.notify_all([NodesModel.ShapeRole])

    @Slot(str)
    def setSelectionColor(self, color: str):
        for nid in self._selected:
            self._node(nid).color = color
        self._model.notify_all([NodesModel.ColorRole])

    @Slot(float)
    def setSelectionOpacity(self, opacity: float):
        for nid in self._selected:
            self._node(nid).opacity = opacity
        self._model.notify_all([NodesModel.OpacityRole])

    @Slot(str, result=str)
    def connectSelection(self, edge_class: str) -> str:
        """З'єднує всі виділені вершини між собою (кліка)."""
        if len(self._selected) < 2:
            return "Виділено менше двох вершин"
        added = self._bulk_add_edges(combinations(self._selected, 2),
                                     self._store.edge_class(edge_class))
        return f"Виділено вершин: {len(self._selected)}, додано ребер — {added}"

    @Slot(str, str, result=str)
    def connectSelectionToClass(self, class_name: str,
                                edge_class: str) -> str:
        """З'єднує кожну виділену вершину з усіма вершинами класу."""
        if not self._selected:
            return ""
        ids = self._store.class_ids(class_name)
        if not ids or set(ids) <= self._selected:
            return f"У класі «{class_name}» немає інших вершин"
        added = self._bulk_add_edges(
            ((nid, other) for nid in self._selected for other in ids),
            self._store.edge_class(edge_class))
        return (f"Виділені → клас «{class_name}»: додано ребер — {added}")

    # --- групи вершин ---
    #
    # Метавершина групи — звичайна вершина пулу: рухається, зв'язується
    # ребрами і виділяється спільними слотами вершин. Згортання — стан
    # відображення: граф не мутується, але вигляд шару ребер змінюється,
    # тож потрібен graphChanged; статистика не перераховується.

    def _groups_changed(self):
        self._model.notify_all(self._GROUP_ROLES)
        self.graphChanged.emit()

    def _drop_hidden_from_selection(self):
        """Сховане не може лишатись у виділенні: Delete зніс би його
        непомітно для користувача."""
        hidden = {nid for nid in self._selected
                  if self._store.visual_owner(nid) != nid}
        if hidden:
            self._selected -= hidden
            self._selection_changed()

    @Slot(result=str)
    def groupSelection(self) -> str:
        """Згортає виділені вершини у групу з новою метавершиною.

        Вершини розгорнутих груп при цьому переходять у нову групу;
        якщо виділення точно збігається з наявною групою — згортається
        вона сама (див. LayeredGraph.add_group).
        """
        gid = self._store.add_group(set(self._selected))
        if gid is None:
            return "Для групи треба щонайменше дві вершини"
        grp = self._store.groups[gid]
        if not self._model.has_node(grp.node):
            self._model.append_node(grp.node)   # свіжа метавершина
        self._store.set_collapsed(gid, True)
        self._model.notify_row(grp.node, [NodesModel.XRole,
                                          NodesModel.YRole])
        self._drop_hidden_from_selection()
        self._drain_orphans()          # метавершини поглинутих груп
        self._groups_changed()
        label = self._node(grp.node).label
        return f"Групу «{label}» згорнуто (вершин: {len(grp.members)})"

    @Slot(int, bool)
    def setGroupCollapsed(self, gid: int, collapsed: bool):
        if not self._store.set_collapsed(gid, collapsed):
            return
        if collapsed:
            # метавершина стала в центроїд членів
            self._model.notify_row(self._store.groups[gid].node,
                                   [NodesModel.XRole, NodesModel.YRole])
        self._drop_hidden_from_selection()
        self._groups_changed()

    @Slot(int)
    def ungroup(self, gid: int):
        """Розпускає групу і прибирає її метавершину разом з її ребрами;
        вершини-члени лишаються в графі як були."""
        node = self._store.remove_group(gid)
        if node is None:
            return
        was_selected = node in self._selected
        self._remove_one(node)
        self._drain_orphans()          # батьківська група могла розчинитись
        if was_selected:
            self.selectionChanged.emit()
        self._model.notify_all(self._GROUP_ROLES)
        self._structure_changed()

    @Slot()
    def clear(self):
        self._store.clear()
        self._model.reset_all()      # чистить і виділення
        self.selectionChanged.emit()
        self.graphChanged.emit()
        self._summary_now()

    # --- збереження/завантаження ---

    @Slot(QUrl, result=str)
    def saveToFile(self, url: QUrl) -> str:
        path = url.toLocalFile()
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(storage.graph_to_json(self._store))
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

        try:
            # сховище мутується лише після успішного розбору всього файла
            new_store = storage.graph_from_json(text)
        except (ValueError, KeyError, TypeError) as e:
            return f"Не вдалося прочитати граф: {e}"

        self._store.adopt(new_store)
        self._model.reset_with(self._store.nodes)   # чистить і виділення
        self.selectionChanged.emit()
        self.classesChanged.emit()
        self.graphChanged.emit()
        self._summary_now()
        return (f"Відкрито: {path}  (вершин: {len(self._store.nodes)}, "
                f"ребер: {self._store.edge_count()})")


class EdgeLayer(QQuickPaintedItem):
    """Шар ребер: малює їх напряму зі сховища одним проходом QPainter.

    Заміна пари Canvas + edgeList(): дані не конвертуються у QVariant
    на кожен кадр, а ребра групуються за пером (колір, товщина, штрих,
    напрямленість), тож QPainter отримує кілька викликів drawLines
    замість тисяч окремих stroke. Спрямовані ребра додають групі другий
    drawLines — на вусики стрілок, зібрані в такий самий плаский список.
    Паралельні ребра (одна пара вершин у різних шарах) вигинаються
    квадратичними дугами (_edge_bends), щоб не накладатись одне на одне;
    їх зазвичай одиниці, тож шлях і стрілка дуги будуються прямо в
    paint() з поточних кінців хорди, поза батчингом прямих ліній.
    Групи вершин: кінці ребер підміняються видимими представниками
    (_visual_owners) — метавершина згорнутої групи збирає на себе ребра
    своїх членів; невидимі ребра (всередині згорнутої групи, до
    метавершини розгорнутої) не потрапляють у кеш зовсім. Метавершина —
    звичайна вершина, тож її рух іде звичайним шляхом nodeMoved.
    Перемальовується за сигналами бекенда graphChanged (структура) та
    edgesChanged (геометрія/стиль).

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
    (nodeMoved) мутує тільки її інцидентні лінії прямо в кеші — разом із
    вусиками стрілок, бо ті залежать від обох кінців ребра.
    """

    sourceChanged = Signal()

    # штрихи Canvas-версії у пікселях; QPen чекає їх в одиницях товщини
    _DASHES = {"dash": (8.0, 6.0), "dot": (2.0, 5.0)}

    _FAST_EDGES = 300    # від скількох ребер вмикається швидкий режим
    _BURST_GAP = 0.1     # с між оновленнями, щоб вважати їх шквалом
    _REFINE_MS = 150     # пауза тиші перед чистовим кадром

    def __init__(self, parent=None):
        super().__init__(parent)
        self._backend: GraphBackend | None = None
        # кеш геометрії: перо → [QLineF] тіл ребер і [QLineF] вусиків стрілок;
        # вершина → [(QLineF, чи кінець P1, вусики або None)]
        self._groups: dict[tuple, list[QLineF]] | None = None
        self._arrows: dict[tuple, list[QLineF]] = {}
        # перо → [(хорда, прогин)] дуг паралельних ребер; хорда — той
        # самий QLineF, що лежить у _incident, тож рух вершини мутує її
        self._curves: dict[tuple, list[tuple[QLineF, float]]] = {}
        # вершина → [(лінія, чи кінець P1, (вусик, вусик, довжина) | None)]
        self._incident: dict[int, list[tuple[QLineF, bool, tuple | None]]] = {}
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
                or self._backend._store.edge_count() < self._FAST_EDGES):
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
            for line, at_p1, barbs in self._incident.get(nid, ()):
                if at_p1:
                    line.setP1(point)
                else:
                    line.setP2(point)
                if barbs is not None:   # стрілка залежить від обох кінців
                    _fit_arrow(line, *barbs)
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

    def _rebuild(self):
        """Повна перебудова кешу геометрії зі сховища."""
        store = self._backend._store
        nodes = store.nodes
        owners = _visual_owners(store)
        bends = _edge_bends(store)
        groups: dict[tuple, list[QLineF]] = {}
        arrows: dict[tuple, list[QLineF]] = {}
        curves: dict[tuple, list[tuple[QLineF, float]]] = {}
        # ключ інцидентності — видимий представник кінця: рух метавершини
        # згорнутої групи мутує ребра всіх її членів
        incident: dict[int, list[tuple[QLineF, bool, tuple | None]]] = {}
        # напрямлений шар віддає пари (джерело, ціль), тож вістря стрілки
        # завжди сідає на P2 лінії без жодних перестановок
        for name, a, b, edge in store.edges():
            oa, ob = owners[a], owners[b]
            if oa is None or ob is None or oa == ob:
                continue    # ребра зараз не видно
            na, nb = nodes[oa], nodes[ob]
            directed = edge.directed
            key = (edge.color, edge.width, edge.line, directed)
            line = QLineF(na.x, na.y, nb.x, nb.y)
            bend = bends.get((name, a, b), 0.0)
            barbs = None
            if bend:
                # дуга: шлях і стрілка будуються в paint() з поточної
                # хорди, тож у кеші вусиків їй робити нічого
                curves.setdefault(key, []).append((line, bend))
            else:
                groups.setdefault(key, []).append(line)
                if directed:
                    # довжина вусика їде з кешем: _node_moved перераховує
                    # стрілку, не маючи під рукою стилю ребра
                    left, right = QLineF(), QLineF()
                    barbs = (left, right, _barb_len(edge.width))
                    _fit_arrow(line, *barbs)
                    arrows.setdefault(key, []).extend((left, right))
            incident.setdefault(oa, []).append((line, True, barbs))
            incident.setdefault(ob, []).append((line, False, barbs))
        self._groups = groups
        self._arrows = arrows
        self._curves = curves
        self._incident = incident

    def _body_pen(self, color: str, width: float, line: str) -> QPen:
        pen = QPen(QColor(color))
        pen.setWidthF(width)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        dash = self._DASHES.get(line)
        if dash:
            pen.setDashPattern([dash[0] / width, dash[1] / width])
        return pen

    def _head_pen(self, color: str, width: float) -> QPen:
        pen = QPen(QColor(color))
        pen.setWidthF(width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        return pen

    def paint(self, painter: QPainter):
        if self._backend is None:
            return
        n_edges = self._backend._store.edge_count()
        if n_edges == 0:
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
        fast = self._fast and n_edges >= self._FAST_EDGES
        p.setRenderHint(QPainter.RenderHint.Antialiasing, not fast)

        # буфер має роздільність текстури; переводимо логічні координати
        # кешу в пікселі буфера (identity, коли розміри збігаються)
        item_w = self.width()
        if item_w > 0:
            s = dw / item_w
            if abs(s - 1.0) > 0.001:
                p.scale(s, s)

        for key, lines in self._groups.items():
            color, width, line, _ = key
            p.setPen(self._body_pen(color, width, line))
            p.drawLines(lines)

            barbs = self._arrows.get(key)
            if barbs:
                # вусики завжди суцільні: штрихове перо розсипало б саму
                # стрілку. Ще один drawLines на групу — батчинг цілий
                p.setPen(self._head_pen(color, width))
                p.drawLines(barbs)

        # дуги паралельних ребер: шлях і стрілка — з поточної хорди
        for key, items in self._curves.items():
            color, width, line, directed = key
            path = QPainterPath()
            barbs = []
            for chord, bend in items:
                x1, y1 = chord.x1(), chord.y1()
                x2, y2 = chord.x2(), chord.y2()
                cx, cy = _bend_control(x1, y1, x2, y2, bend)
                path.moveTo(x1, y1)
                path.quadTo(cx, cy, x2, y2)
                if directed:
                    # дотична дуги в кінці йде від контрольної точки до
                    # P2 — стрілка сідає уздовж неї, а не уздовж хорди
                    left, right = QLineF(), QLineF()
                    _fit_arrow(QLineF(cx, cy, x2, y2), left, right,
                               _barb_len(width))
                    barbs.extend((left, right))
            p.setPen(self._body_pen(color, width, line))
            p.drawPath(path)
            if barbs:
                p.setPen(self._head_pen(color, width))
                p.drawLines(barbs)
        p.end()

        # один повноекранний перенос: Source копіює пікселі без
        # змішування, конвертація формату — швидкий SIMD-прохід
        painter.save()
        painter.resetTransform()
        painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_Source)
        painter.drawImage(0, 0, buf)
        painter.restore()
