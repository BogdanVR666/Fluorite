import functools
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

import history
import storage
from document import Document


def _point_segment_dist2(px: float, py: float,
                         x1: float, y1: float, x2: float, y2: float) -> float:
    vx, vy = x2 - x1, y2 - y1
    wx, wy = px - x1, py - y1
    seg2 = vx * vx + vy * vy
    t = 0.0 if seg2 == 0.0 else max(0.0, min(1.0, (wx * vx + wy * vy) / seg2))
    dx, dy = wx - t * vx, wy - t * vy
    return dx * dx + dy * dy


_BEND_STEP = 14.0   # відстань між сусідніми паралельними ребрами, px


def _visual_owners(doc: Document) -> dict[int, int | None]:
    return {nid: doc.visual_owner(nid) for nid in doc.type_of}


def _edge_bends(doc: Document) -> dict[int, float]:
    """Вигин кожного з паралельних ребер (між тими самими вершинами на
    екрані), щоб вони не злипались в одну лінію."""
    owners = _visual_owners(doc)
    pairs: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for eid, u, v in doc.shown_edges():
        ou, ov = owners[u], owners[v]
        if ou is None or ov is None or ou == ov:
            continue
        key = (ou, ov) if ou < ov else (ov, ou)
        pairs.setdefault(key, []).append((eid, ou))
    bends: dict[int, float] = {}
    for (a, _), group in pairs.items():
        k = len(group)
        if k < 2:
            continue
        for i, (eid, ou) in enumerate(group):
            off = (i - (k - 1) / 2.0) * _BEND_STEP
            bends[eid] = off if ou == a else -off
    return bends


def _bend_control(x1: float, y1: float, x2: float, y2: float,
                  bend: float) -> tuple[float, float]:
    dx, dy = x2 - x1, y2 - y1
    d = math.hypot(dx, dy)
    if d < 1e-6:                       # вершини збіглись — дуги немає
        return x1, y1
    nx_, ny_ = -dy / d, dx / d         # нормаль ліворуч від напряму
    return ((x1 + x2) / 2.0 + nx_ * 2.0 * bend,
            (y1 + y2) / 2.0 + ny_ * 2.0 * bend)


def _point_bend_dist2(px: float, py: float, x1: float, y1: float,
                      x2: float, y2: float, bend: float) -> float:
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

    def __init__(self, doc: Document, parent=None):
        super().__init__(parent)
        self._doc = doc
        self._ids: list[int] = []          # порядок рядків моделі
        self._rows: dict[int, int] = {}    # nodeId → рядок, O(1) для row_of
        # Виділені вершини. Живуть тут, а не в QML, щоб делегат читав свій
        # стан роллю за O(1) — інакше кожен із них шукав би себе в масиві.
        self._selected: set[int] = set()

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
        doc = self._doc
        if role == self.NodeIdRole:
            return nid
        if role in (self.XRole, self.YRole):
            look = doc.look(nid)
            return look.x if role == self.XRole else look.y
        if role == self.LabelRole:
            return doc.node(nid).name
        if role == self.DegreeRole:
            return doc.degree(nid)
        if role in (self.ShapeRole, self.ColorRole, self.OpacityRole):
            style = doc.node_style(nid)
            return (style.shape if role == self.ShapeRole
                    else style.color if role == self.ColorRole
                    else style.opacity)
        if role == self.ClassRole:
            return doc.node_type(nid)
        if role == self.DescriptionRole:
            return doc.node(nid).description
        if role == self.SelectedRole:
            return nid in self._selected
        if role == self.HiddenRole:
            return doc.visual_owner(nid) != nid
        if role == self.IsGroupRole:
            return nid in doc.group_of_node
        if role == self.MembersRole:
            gid = doc.group_of_node.get(nid)
            return 0 if gid is None else len(doc.group_members(gid))
        return None

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
        if len(ids) == 1:
            self.remove_node(next(iter(ids)))
            return
        self.beginResetModel()
        self._ids = [nid for nid in self._ids if nid not in ids]
        self._rows = {nid: i for i, nid in enumerate(self._ids)}
        self._selected -= ids     # на місці: множину поділено з бекендом
        self.endResetModel()

    def reset_with(self, ids):
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


def _step(merge=None):
    """Слот змінює граф: після нього стан іде в історію одним кроком.

    merge(*args) дає ключ неперервної дії (перетягування, повзунок, набір
    тексту). Виклики з тим самим ключем зливаються в один крок; він
    записується перед іншою дією, перед Ctrl+Z або після паузи.
    """
    def wrap(fn):
        @functools.wraps(fn)
        def slot(self, *args):
            key = merge(*args) if merge else None
            if self._pending is not None and self._pending != key:
                self._commit()
            result = fn(self, *args)
            if key is None:
                self._commit()
            else:
                self._pending = key
                self._idle.start()
            return result
        return slot
    return wrap


class GraphBackend(QObject):
    graphChanged = Signal()     # структура: шар ребер перемальовується
    edgesChanged = Signal()     # стиль/підсвітка ребер — перемалювання
    nodeMoved = Signal(int, float, float)   # рух вершини: (nid, x, y)
    classesChanged = Signal()   # змінились типи вершин чи ребер
    selectionChanged = Signal() # змінився набір виділених вершин
    summaryChanged = Signal()   # статистика й лічильники класів (з паузою)
    statusChanged = Signal()    # повідомлення в статус-рядку

    _SUMMARY_MS = 100           # не частіше 10 оновлень зведення на секунду
    _IDLE_MS = 600              # пауза, що завершує неперервну дію

    def __init__(self, parent=None):
        super().__init__(parent)
        self._doc = Document()
        self._model = NodesModel(self._doc, self)
        self._selected: set[int] = self._model._selected
        self._summary = QTimer(self)
        self._summary.setSingleShot(True)
        self._summary.setInterval(self._SUMMARY_MS)
        self._summary.timeout.connect(self.summaryChanged)
        self._status = ""
        self._history = history.History()
        self._history.reset(self._snapshot())
        self._pending = None        # ключ неперервної дії, ще не в історії
        self._idle = QTimer(self)
        self._idle.setSingleShot(True)
        self._idle.setInterval(self._IDLE_MS)
        self._idle.timeout.connect(self._commit)

    def _snapshot(self) -> dict:
        return history.snapshot(self._doc)

    def _commit(self):
        """Записати в історію все, що змінилось від попереднього кроку."""
        self._pending = None
        self._idle.stop()
        self._history.record(self._snapshot())

    def _travel(self, change: dict, side: int):
        """Перевести граф у стан side кроку change і оновити інтерфейс."""
        added, removed = history.apply(self._doc, change, side)
        if removed:
            self._model.remove_nodes(removed)
        for nid in sorted(added):
            self._model.append_node(nid)
        roles = list(self._model.roleNames())
        for nid, pair in change.get("nodes", {}).items():
            if None not in pair:          # вершина лишилась, але змінилась
                self._model.notify_row(nid, roles)
        for pair in change.get("edges", {}).values():
            for rec in pair:              # у кінців змінився ступінь
                if rec is None:
                    continue
                for nid in (rec[0].node_in, rec[0].node_out):
                    if self._model.has_node(nid):
                        self._model.notify_row(nid, [NodesModel.DegreeRole])
        if "types" in change:
            self._model.notify_all(self._CLASS_ROLES
                                   + [NodesModel.HiddenRole])
        if "groups" in change:
            self._model.notify_all(self._GROUP_ROLES)
        # виділення не в історії: лише прибрати з нього зниклі вершини
        self._selected.intersection_update(self._doc.type_of.keys())
        self._selection_changed()
        self.graphChanged.emit()
        self.classesChanged.emit()
        self._summary_now()
        self._history.rebase(self._snapshot())

    @Slot()
    def undo(self):
        if self._pending is not None:
            self._commit()
        change = self._history.undo()
        if change is None:
            self._set_status("Нема що скасовувати")
            return
        self._travel(change, history.BEFORE)
        self._set_status(f"Скасовано. Можна скасувати ще: "
                         f"{self._history.undo_count}")

    @Slot()
    def redo(self):
        if self._pending is not None:
            self._commit()
        change = self._history.redo()
        if change is None:
            self._set_status("Нема що повторювати")
            return
        self._travel(change, history.AFTER)
        self._set_status(f"Повторено. Можна повторити ще: "
                         f"{self._history.redo_count}")

    def _structure_changed(self):
        self.graphChanged.emit()
        if not self._summary.isActive():
            self._summary.start()

    def _summary_now(self):
        self._summary.stop()
        self.summaryChanged.emit()

    @Property(QObject, constant=True)
    def nodesModel(self):
        return self._model

    @Property(str, notify=summaryChanged)
    def stats(self):
        n = len(self._doc.type_of)
        m = self._doc.edge_count()
        c = self._doc.component_count()
        return f"Вершин: {n}  •  Ребер: {m}  •  Компонент зв'язності: {c}"

    _HINT = ("ЛКМ по полю — нова вершина, ЛКМ-перетяг — рамка виділення "
             "(Shift — додати до наявного); Shift+ЛКМ по вершині — виділити "
             "ще одну, Ctrl+Shift+ЛКМ — з'єднати виділені з нею, Delete — "
             "видалити виділені; ПКМ по вершині чи ребру — меню, ПКМ-перетяг "
             "між вершинами — ребро")

    @Property(str, notify=statusChanged)
    def status(self):
        """Повідомлення останньої дії, а без нього — підказка з жестами."""
        return self._status or self._HINT

    def _set_status(self, msg: str):
        if msg != self._status:
            self._status = msg
            self.statusChanged.emit()

    @Property(int, notify=selectionChanged)
    def selectionCount(self):
        return len(self._selected)

    def _selection_changed(self):
        """Штовхнути модель і QML після зміни self._selected."""
        self._model.set_selected(self._selected)
        self.selectionChanged.emit()

    # ---- виділення ----------------------------------------------------

    @Slot(int, bool)
    def selectNode(self, nid: int, additive: bool):
        if not self._doc.has_node(nid):
            return
        if additive:
            self._selected ^= {nid}
        else:
            self._selected.clear()
            self._selected.add(nid)
        self._selection_changed()
        n = len(self._selected)
        self._set_status(f"Виділено вершин: {n}" if n > 1 else "")

    @Slot(float, float, float, float, bool)
    def selectInRect(self, x: float, y: float, w: float, h: float,
                     additive: bool):
        x2, y2 = x + w, y + h
        hits = {nid for nid, look in self._doc.view.nodes.items()
                if x <= look.x <= x2 and y <= look.y <= y2
                and self._doc.visual_owner(nid) == nid}
        if not additive:
            self._selected.clear()
        self._selected |= hits
        self._selection_changed()
        self._set_status(f"Виділено вершин: {len(self._selected)}" if hits
                         else "У рамку не потрапила жодна вершина")

    @Slot()
    def clearSelection(self):
        if not self._selected:
            return   # статус не чіпаємо: тут, напр., «Видалено вершин: N»
        self._selected.clear()
        self._selection_changed()
        self._set_status("")

    @Slot(int, result=bool)
    def isSelected(self, nid: int) -> bool:
        return nid in self._selected

    # ---- типи (класи) -------------------------------------------------

    @Slot(str, result="QVariantList")
    def classList(self, family: str):
        if family not in ("node", "edge"):
            return []
        doc = self._doc
        return [{
            "name": name,
            "count": doc.class_count(family, name),
            "default": doc.view.is_default(family, name),
            "hidden": look.hidden,
            **doc.design_map(family, name),
        } for name, look in doc.types(family).items()]

    @Slot(str, str, "QVariantMap", result=bool)
    @_step()
    def createClass(self, family: str, name: str, design: dict) -> bool:
        if not self._doc.create_class(family, name, design):
            self._set_status(f"Клас «{name}» вже існує")
            return False
        self.classesChanged.emit()
        return True

    @Slot(str, str, "QVariantMap")
    @_step(lambda family, name, design: ('class', family, name))
    def updateClass(self, family: str, name: str, design: dict):
        if not self._doc.update_class(family, name, design):
            return
        if family == "node":
            self._model.notify_all([NodesModel.ShapeRole,
                                    NodesModel.ColorRole,
                                    NodesModel.OpacityRole])
        else:
            self.edgesChanged.emit()   # кеш EdgeLayer стане недійсним
        self.classesChanged.emit()

    @Slot(str, str, str, result=bool)
    @_step()
    def renameClass(self, family: str, old: str, new: str) -> bool:
        if not self._doc.rename_class(family, old, new):
            self._set_status("Назва порожня" if not new.strip()
                             else f"Клас «{new.strip()}» вже існує")
            return False
        if family == "node":
            self._model.notify_all([NodesModel.ClassRole])
        self._structure_changed()
        self.classesChanged.emit()
        self._set_status("")
        return True

    @Slot(str, str)
    @_step()
    def removeClass(self, family: str, name: str):
        doc = self._doc
        if doc.view.is_default(family, name):
            self._set_status(f"Стандартний клас «{name}» видалити не можна")
            return
        if name not in doc.types(family):
            return
        doomed = set(doc.class_ids(name)) if family == "node" else set()
        count = doc.class_count(family, name)
        touched = doc.remove_class(family, name)
        if touched is None:
            return
        self._nodes_removed(doomed, touched)
        self.classesChanged.emit()
        self._set_status(
            f"Видалено клас «{name}»: "
            + (f"вершин — {count}" if family == "node"
               else f"ребер — {count}"))

    @Slot(str, str, bool)
    def setClassHidden(self, family: str, name: str, hidden: bool):
        if not self._doc.set_class_hidden(family, name, hidden):
            return
        if family == "node":
            self._model.notify_all([NodesModel.HiddenRole])
            self._drop_hidden_from_selection()
        self.graphChanged.emit()          # ребра до схованих теж зникають
        self.classesChanged.emit()

    @Slot(str, str, int)
    def moveClass(self, family: str, name: str, index: int):
        if self._doc.move_class(family, name, index):
            self.classesChanged.emit()

    _CLASS_ROLES = [NodesModel.ShapeRole, NodesModel.ColorRole,
                    NodesModel.OpacityRole, NodesModel.ClassRole]

    # ---- вершини ------------------------------------------------------

    @Slot(float, float, str)
    @_step()
    def addNode(self, x: float, y: float, class_name: str):
        nid = self._doc.add_node(x, y, class_name)
        self._model.append_node(nid)
        self._structure_changed()

    @Slot(int, str)
    @_step()
    def setNodeLabel(self, nid: int, text: str):
        self._doc.set_label(nid, text)
        self._model.notify_row(nid, [NodesModel.LabelRole])

    @Slot(int, str)
    @_step(lambda nid, text: ('description', nid))
    def setNodeDescription(self, nid: int, text: str):
        self._doc.set_description(nid, text)
        self._model.notify_row(nid, [NodesModel.DescriptionRole])

    @Slot(int, float, float)
    @_step(lambda nid, x, y: ('move', nid))
    def moveNode(self, nid: int, x: float, y: float):
        self._doc.move_node(nid, x, y)
        self._model.notify_row(nid, [NodesModel.XRole, NodesModel.YRole])
        # структура не змінилась — статистику й класи не перераховуємо,
        # а шар ребер оновлює лише лінії цієї вершини
        self.nodeMoved.emit(nid, x, y)

    @Slot(int, float, float)
    @_step(lambda anchor, x, y: ('move', anchor))
    def moveSelectionTo(self, anchor: int, x: float, y: float):
        doc = self._doc
        if not doc.has_node(anchor):
            return
        look = doc.look(anchor)
        dx, dy = x - look.x, y - look.y
        for nid in self._selected | {anchor}:
            look = doc.look(nid)
            nx_, ny_ = ((x, y) if nid == anchor
                        else (look.x + dx, look.y + dy))
            doc.move_node(nid, nx_, ny_)
            self._model.notify_row(nid, [NodesModel.XRole, NodesModel.YRole])
            self.nodeMoved.emit(nid, nx_, ny_)

    def _remove_one(self, nid: int):
        if not self._doc.has_node(nid):
            return
        neighbors = self._doc.remove_node(nid)
        self._model.remove_node(nid)      # і викидає nid із self._selected
        for nb in neighbors:              # у сусідів змінився ступінь
            if self._model.has_node(nb):
                self._model.notify_row(nb, [NodesModel.DegreeRole])

    def _drain_orphans(self):
        while True:
            orphans = self._doc.take_orphans()
            if not orphans:
                return
            for nid in orphans:
                self._remove_one(nid)

    _GROUP_ROLES = [NodesModel.HiddenRole, NodesModel.IsGroupRole,
                    NodesModel.MembersRole]

    @Slot(int)
    @_step()
    def removeNode(self, nid: int):
        if not self._doc.has_node(nid):
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
        hit2 = 26.0 * 26.0                # радіус влучання (вершина ~44px)
        best, best_d = -1, hit2
        for nid, look in self._doc.view.nodes.items():
            if self._doc.visual_owner(nid) != nid:
                continue                  # зараз не видно (групи)
            dx, dy = look.x - x, look.y - y
            d = dx * dx + dy * dy
            if d <= best_d:
                best, best_d = nid, d
        return best

    @Slot(int, result="QVariantMap")
    def nodeInfo(self, nid: int):
        doc = self._doc
        if not doc.has_node(nid):
            return {}
        node, look, style = doc.node(nid), doc.look(nid), doc.node_style(nid)
        gid = doc.member_of.get(nid, -1)     # чий вона член
        own = doc.group_of_node.get(nid, -1)  # чия метавершина
        return {"label": node.name, "description": node.description,
                "shape": style.shape, "color": style.color,
                "opacity": style.opacity, "x": look.x, "y": look.y,
                "klass": doc.node_type(nid), "groupId": gid,
                "groupLabel": (doc.node(doc.group_node(gid)).name
                               if gid != -1 else ""),
                "isGroup": own != -1, "ownGroupId": own,
                "memberCount": (len(doc.group_members(own))
                                if own != -1 else 0)}

    @Slot()
    @_step()
    def removeSelection(self):
        if not self._selected:
            return
        n = len(self._selected)
        doomed = set(self._selected)
        self._nodes_removed(doomed, self._doc.remove_nodes(doomed))
        self._set_status(f"Видалено вершин: {n}")

    def _nodes_removed(self, doomed: set[int], touched: set[int]):
        """Донести до моделі видалення вершин doomed із документа."""
        was_selected = bool(self._selected & doomed)
        if doomed:
            self._model.remove_nodes(doomed)  # і викидає їх із self._selected
        self._drain_orphans()                 # метавершини розчинених груп
        for nid in touched:                   # у них змінився ступінь
            if self._model.has_node(nid):
                self._model.notify_row(nid, [NodesModel.DegreeRole])
        if was_selected:
            self._selection_changed()
        self._model.notify_all(self._GROUP_ROLES)
        self._structure_changed()

    @Slot(str)
    @_step()
    def setSelectionClass(self, class_name: str):
        if class_name not in self._doc.view.node_types or not self._selected:
            return
        for nid in self._selected:
            self._doc.set_node_class(nid, class_name)
        self._model.notify_all(self._CLASS_ROLES)
        self._structure_changed()

    @Slot(str)
    @_step()
    def setSelectionShape(self, shape: str):
        for nid in self._selected:
            self._doc.set_node_style(nid, shape=shape)
        self._model.notify_all([NodesModel.ShapeRole])

    @Slot(str)
    @_step()
    def setSelectionColor(self, color: str):
        for nid in self._selected:
            self._doc.set_node_style(nid, color=color)
        self._model.notify_all([NodesModel.ColorRole])

    @Slot(float)
    @_step(lambda opacity: ('opacity',))
    def setSelectionOpacity(self, opacity: float):
        for nid in self._selected:
            self._doc.set_node_style(nid, opacity=opacity)
        self._model.notify_all([NodesModel.OpacityRole])

    # ---- ребра --------------------------------------------------------

    def _bulk_add_edges(self, pairs, edge_class: str) -> int:
        added = self._doc.bulk_add_edges(pairs, edge_class)
        if added:
            self._model.notify_all([NodesModel.DegreeRole])
            self._structure_changed()
        return added

    @Slot(str, str)
    @_step()
    def connectClassNodes(self, class_name: str, edge_class: str):
        ids = self._doc.class_ids(class_name)
        if len(ids) < 2:
            self._set_status(f"У класі «{class_name}» менше двох вершин")
            return
        added = self._bulk_add_edges(combinations(ids, 2), edge_class)
        self._set_status(f"Клас «{class_name}»: додано ребер — {added}")

    @Slot(int, int, str)
    @_step()
    def addEdge(self, a: int, b: int, edge_class: str):
        if self._doc.add_edge(a, b, edge_class) is None:
            self._set_status("Таке ребро вже існує")
            return
        for nid in (a, b):
            self._model.notify_row(nid, [NodesModel.DegreeRole])
        self._structure_changed()

    @Slot(int)
    @_step()
    def removeEdge(self, eid: int):
        if not self._doc.has_edge(eid):
            return
        ends = self._doc.ends(eid)
        self._doc.remove_edge(eid)
        for nid in ends:
            self._model.notify_row(nid, [NodesModel.DegreeRole])
        self._structure_changed()

    @Slot(int, str)
    @_step()
    def setEdgeColor(self, eid: int, color: str):
        if self._doc.has_edge(eid):
            self._doc.set_edge_style(eid, color=color)
            self.edgesChanged.emit()

    @Slot(int, float)
    @_step()
    def setEdgeWidth(self, eid: int, width: float):
        if self._doc.has_edge(eid):
            self._doc.set_edge_style(eid, width=width)
            self.edgesChanged.emit()

    @Slot(int, str)
    @_step()
    def setEdgeLine(self, eid: int, line: str):
        if self._doc.has_edge(eid):
            self._doc.set_edge_style(eid, line=line)
            self.edgesChanged.emit()

    @Slot(int)
    @_step()
    def reverseEdge(self, eid: int):
        if self._doc.reverse_edge(eid):
            self.edgesChanged.emit()

    @Slot(int, str, result=bool)
    @_step()
    def setEdgeClass(self, eid: int, new_name: str) -> bool:
        # False, зокрема, коли пара вже зайнята ребром цільового класу
        if not self._doc.set_edge_class(eid, new_name):
            self._set_status(f"Ребро класу «{new_name}» між цими вершинами "
                             "вже існує")
            return False
        self._structure_changed()      # перемальовує ребра й лічильники
        return True

    @Slot(float, float, result=int)
    def edgeAt(self, x: float, y: float) -> int:
        """id ребра під точкою або -1."""
        hit2 = 7.0 * 7.0                  # допуск влучання у лінію, px^2
        doc = self._doc
        owners = _visual_owners(doc)
        bends = _edge_bends(doc)
        best, best_d = -1, hit2
        for eid, a, b in doc.shown_edges():
            oa, ob = owners[a], owners[b]
            if oa is None or ob is None or oa == ob:
                continue                  # ребра зараз не видно
            la, lb = doc.look(oa), doc.look(ob)
            bend = bends.get(eid, 0.0)
            if bend:
                d = _point_bend_dist2(x, y, la.x, la.y, lb.x, lb.y, bend)
            else:
                d = _point_segment_dist2(x, y, la.x, la.y, lb.x, lb.y)
            if d <= best_d:
                best, best_d = eid, d
        return best

    @Slot(int, result="QVariantMap")
    def edgeInfo(self, eid: int):
        doc = self._doc
        if not doc.has_edge(eid):
            return {}
        src, dst = doc.ends(eid)
        directed = doc.edge_directed(eid)
        style = doc.edge_style(eid)
        sep = " → " if directed else "–"
        return {"label": f"{doc.node(src).name}{sep}{doc.node(dst).name}",
                "color": style.color, "width": style.width,
                "line": style.line, "directed": directed,
                "klass": doc.edge_type(eid)}

    @Slot(str)
    @_step()
    def connectSelection(self, edge_class: str):
        if len(self._selected) < 2:
            self._set_status("Виділено менше двох вершин")
            return
        added = self._bulk_add_edges(combinations(self._selected, 2),
                                     edge_class)
        self._set_status(f"Виділено вершин: {len(self._selected)}, "
                         f"додано ребер — {added}")

    @Slot(str, str)
    @_step()
    def connectSelectionToClass(self, class_name: str,
                                edge_class: str):
        if not self._selected:
            self._set_status("")
            return
        ids = self._doc.class_ids(class_name)
        if not ids or set(ids) <= self._selected:
            self._set_status(f"У класі «{class_name}» немає інших вершин")
            return
        added = self._bulk_add_edges(
            ((nid, other) for nid in self._selected for other in ids),
            edge_class)
        self._set_status(
            f"Виділені → клас «{class_name}»: додано ребер — {added}")

    @Slot(int, str)
    @_step()
    def connectSelectionTo(self, nid: int, edge_class: str):
        """Ребра від усіх виділених до nid, потім nid стає виділеною.
        Виділена nid натомість знімається з виділення, без ребер."""
        if not self._doc.has_node(nid):
            self._set_status("")
            return
        if nid in self._selected:
            self._selected.discard(nid)
            self._selection_changed()
            self._set_status("")
            return
        added = self._bulk_add_edges(
            ((src, nid) for src in self._selected), edge_class)
        self._selected.add(nid)
        self._selection_changed()
        self._set_status(f"Додано ребер: {added}" if added else "")

    # ---- групи --------------------------------------------------------

    def _groups_changed(self):
        self._model.notify_all(self._GROUP_ROLES)
        self.graphChanged.emit()

    def _drop_hidden_from_selection(self):
        hidden = {nid for nid in self._selected
                  if self._doc.visual_owner(nid) != nid}
        if hidden:
            self._selected -= hidden
            self._selection_changed()

    @Slot()
    @_step()
    def groupSelection(self):
        doc = self._doc
        gid = doc.add_group(set(self._selected))
        if gid is None:
            self._set_status("Для групи треба щонайменше дві вершини")
            return
        meta = doc.group_node(gid)
        if not self._model.has_node(meta):
            self._model.append_node(meta)   # свіжа метавершина
        doc.set_collapsed(gid, True)
        self._model.notify_row(meta, [NodesModel.XRole, NodesModel.YRole])
        self._drop_hidden_from_selection()
        self._drain_orphans()          # метавершини поглинутих груп
        self._groups_changed()
        self._set_status(f"Групу «{doc.node(meta).name}» згорнуто "
                         f"(вершин: {len(doc.group_members(gid))})")

    @Slot(int, bool)
    @_step()
    def setGroupCollapsed(self, gid: int, collapsed: bool):
        if not self._doc.set_collapsed(gid, collapsed):
            return
        if collapsed:
            # метавершина стала в центроїд членів
            self._model.notify_row(self._doc.group_node(gid),
                                   [NodesModel.XRole, NodesModel.YRole])
        self._drop_hidden_from_selection()
        self._groups_changed()

    @Slot(int)
    @_step()
    def ungroup(self, gid: int):
        node = self._doc.remove_group(gid)
        if node is None:
            return
        was_selected = node in self._selected
        self._remove_one(node)
        self._drain_orphans()          # батьківська група могла розчинитись
        if was_selected:
            self.selectionChanged.emit()
        self._model.notify_all(self._GROUP_ROLES)
        self._structure_changed()

    # ---- документ цілком ----------------------------------------------

    @Slot()
    @_step()
    def clear(self):
        self._doc.clear()
        self._model.reset_all()      # чистить і виділення
        self.selectionChanged.emit()
        self.graphChanged.emit()
        self._summary_now()
        self._set_status("")

    @Slot(QUrl)
    def saveToFile(self, url: QUrl):
        path = url.toLocalFile()
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(storage.graph_to_json(self._doc))
        except OSError as e:
            self._set_status(f"Не вдалося зберегти: {e}")
            return
        self._set_status(f"Збережено: {path}")

    @Slot(QUrl)
    def loadFromFile(self, url: QUrl):
        path = url.toLocalFile()
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except OSError as e:
            self._set_status(f"Не вдалося відкрити: {e}")
            return

        try:
            # документ мутується лише після успішного розбору всього файла
            new_doc = storage.graph_from_json(text)
        except (ValueError, KeyError, TypeError) as e:
            self._set_status(f"Не вдалося прочитати граф: {e}")
            return

        self._doc.adopt(new_doc)
        self._model.reset_with(self._doc.type_of)   # чистить і виділення
        self._pending = None
        self._idle.stop()
        self._history.reset(self._snapshot())       # новий файл — нова історія
        self.selectionChanged.emit()
        self.classesChanged.emit()
        self.graphChanged.emit()
        self._summary_now()
        self._set_status(
            f"Відкрито: {path}  (вершин: {len(self._doc.type_of)}, "
            f"ребер: {self._doc.edge_count()})")


class EdgeLayer(QQuickPaintedItem):
    sourceChanged = Signal()

    _DASHES = {"dash": (8.0, 6.0), "dot": (2.0, 5.0)}

    _FAST_EDGES = 300    # від скількох ребер вмикається швидкий режим
    _BURST_GAP = 0.1     # с між оновленнями, щоб вважати їх шквалом
    _REFINE_MS = 150     # пауза тиші перед чистовим кадром

    def __init__(self, parent=None):
        super().__init__(parent)
        self._backend: GraphBackend | None = None
        self._groups: dict[tuple, list[QLineF]] | None = None
        self._arrows: dict[tuple, list[QLineF]] = {}
        self._curves: dict[tuple, list[tuple[QLineF, float]]] = {}
        self._incident: dict[int, list[tuple[QLineF, bool, tuple | None]]] = {}
        # Під час перетягування рухаються лише ребра, інцидентні тягнутим
        # вершинам. Решту растеризуємо один раз у _static і далі щокадру
        # лише підкладаємо готову картинку, домальовуючи рухомі з _dyn_*.
        self._moving: set[int] = set()       # вершини, які зараз тягнуть
        self._static: QImage | None = None   # кеш нерухомих ребер
        self._dyn_groups: dict[tuple, list[QLineF]] = {}
        self._dyn_arrows: dict[tuple, list[QLineF]] = {}
        self._dyn_curves: dict[tuple, list[tuple[QLineF, float]]] = {}
        self._pens: dict[tuple, QPen] = {}   # перо за стилем: QPen недешевий
        self._fast = False           # поточні кадри — швидкі (шквал)
        self._low_res = False        # текстура зараз зменшена
        # Малюємо у власний ARGB32-буфер: цільова текстура елемента має
        # формат RGBA8888, у якому растеризація ліній QPainter у рази
        # повільніша; готовий буфер лише блітиться в текстуру.
        self._buffer: QImage | None = None
        self._last_request = 0.0
        self._refine = QTimer(self)
        self._refine.setSingleShot(True)
        self._refine.setInterval(self._REFINE_MS)
        self._refine.timeout.connect(self._refine_pass)

    def _enter_fast(self):
        if (self._backend is None
                or self._backend._doc.edge_count() < self._FAST_EDGES):
            return
        if not self._fast:
            self._fast = True
            w, h = self.width(), self.height()
            dpr = (self.window().effectiveDevicePixelRatio()
                   if self.window() else 1.0)
            if w > 0 and h > 0 and dpr > 1.01:
                self.setTextureSize(QSize(max(1, int(w)), max(1, int(h))))
                self._low_res = True
        self._refine.start()

    def _request(self):
        now = monotonic()
        if now - self._last_request < self._BURST_GAP:
            self._enter_fast()
        self._last_request = now
        self.update()

    def _mark_dirty(self):
        self._groups = None
        self._static = None
        self._moving.clear()
        self._request()

    def _node_moved(self, nid: int, x: float, y: float):
        if nid not in self._moving:
            self._moving.add(nid)
            self._static = None    # набір рухомих змінився — кеш застарів
        if self._groups is not None:
            point = QPointF(x, y)
            for line, at_p1, barbs in self._incident.get(nid, ()):
                if at_p1:
                    line.setP1(point)
                else:
                    line.setP2(point)
                if barbs is not None:   # стрілка залежить від обох кінців
                    _fit_arrow(line, *barbs)
        self._enter_fast()
        self._last_request = monotonic()
        self.update()

    def _refine_pass(self):
        self._fast = False
        self._moving.clear()        # перетягування скінчилось
        self._static = None
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
        doc = self._backend._doc
        owners = _visual_owners(doc)
        bends = _edge_bends(doc)
        groups: dict[tuple, list[QLineF]] = {}
        arrows: dict[tuple, list[QLineF]] = {}
        curves: dict[tuple, list[tuple[QLineF, float]]] = {}
        incident: dict[int, list[tuple[QLineF, bool, tuple | None]]] = {}
        for eid, a, b in doc.shown_edges():
            oa, ob = owners[a], owners[b]
            if oa is None or ob is None or oa == ob:
                continue    # ребра зараз не видно
            na, nb = doc.look(oa), doc.look(ob)
            directed = doc.edge_directed(eid)
            style = doc.edge_style(eid)
            key = (style.color, style.width, style.line, directed)
            line = QLineF(na.x, na.y, nb.x, nb.y)
            bend = bends.get(eid, 0.0)
            barbs = None
            if bend:
                curves.setdefault(key, []).append((line, bend))
            else:
                groups.setdefault(key, []).append(line)
                if directed:
                    left, right = QLineF(), QLineF()
                    barbs = (left, right, _barb_len(style.width))
                    _fit_arrow(line, *barbs)
                    arrows.setdefault(key, []).extend((left, right))
            incident.setdefault(oa, []).append((line, True, barbs))
            incident.setdefault(ob, []).append((line, False, barbs))
        self._groups = groups
        self._arrows = arrows
        self._curves = curves
        self._incident = incident
        self._static = None      # старі QLineF більше не в кешах
        self._pens.clear()

    def _body_pen(self, color: str, width: float, line: str) -> QPen:
        key = (color, width, line)
        pen = self._pens.get(key)
        if pen is None:
            pen = QPen(QColor(color))
            pen.setWidthF(width)
            pen.setCapStyle(Qt.PenCapStyle.FlatCap)
            dash = self._DASHES.get(line)
            if dash:
                pen.setDashPattern([dash[0] / width, dash[1] / width])
            self._pens[key] = pen
        return pen

    def _head_pen(self, color: str, width: float) -> QPen:
        key = (color, width)
        pen = self._pens.get(key)
        if pen is None:
            pen = QPen(QColor(color))
            pen.setWidthF(width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            self._pens[key] = pen
        return pen

    def _draw_edges(self, p: QPainter, groups, arrows, curves):
        for key, lines in groups.items():
            color, width, line, _ = key
            p.setPen(self._body_pen(color, width, line))
            p.drawLines(lines)

            barbs = arrows.get(key)
            if barbs:
                p.setPen(self._head_pen(color, width))
                p.drawLines(barbs)

        for key, items in curves.items():
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
                    left, right = QLineF(), QLineF()
                    _fit_arrow(QLineF(cx, cy, x2, y2), left, right,
                               _barb_len(width))
                    barbs.extend((left, right))
            p.setPen(self._body_pen(color, width, line))
            p.drawPath(path)
            if barbs:
                p.setPen(self._head_pen(color, width))
                p.drawLines(barbs)

    def _build_static(self, dw: int, dh: int, s: float):
        """Розкладає ребра на рухомі (_dyn_*) та нерухомі й растеризує
        нерухомі в картинку _static розміру буфера."""
        dyn_ids: set[int] = set()
        for nid in self._moving:
            for line, _, barbs in self._incident.get(nid, ()):
                dyn_ids.add(id(line))
                if barbs is not None:
                    dyn_ids.add(id(barbs[0]))
                    dyn_ids.add(id(barbs[1]))

        # Списки містять ті самі QLineF, що їх _node_moved рухає на місці,
        # тож розбиття лишається чинним протягом усього перетягування.
        def split(d: dict, ident):
            stat, dyn = {}, {}
            for key, items in d.items():
                moved = [it for it in items if ident(it) in dyn_ids]
                if not moved:
                    stat[key] = items
                    continue
                dyn[key] = moved
                rest = [it for it in items if ident(it) not in dyn_ids]
                if rest:
                    stat[key] = rest
            return stat, dyn

        stat_groups, self._dyn_groups = split(self._groups, id)
        stat_arrows, self._dyn_arrows = split(self._arrows, id)
        stat_curves, self._dyn_curves = split(self._curves,
                                              lambda it: id(it[0]))

        img = QImage(dw, dh, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(0)
        p = QPainter(img)
        # кеш малюється один раз на перетягування — завжди з АА
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if abs(s - 1.0) > 0.001:
            p.scale(s, s)
        self._draw_edges(p, stat_groups, stat_arrows, stat_curves)
        p.end()
        self._static = img

    def paint(self, painter: QPainter):
        if self._backend is None:
            return
        n_edges = self._backend._doc.edge_count()
        if n_edges == 0:
            return
        if self._groups is None:
            self._rebuild()

        dev = painter.device()
        dw, dh = dev.width(), dev.height()
        if dw <= 0 or dh <= 0:
            return

        item_w = self.width()
        s = dw / item_w if item_w > 0 else 1.0

        # кеш нерухомих ребер має сенс лише коли їх багато
        cached = bool(self._moving) and n_edges >= self._FAST_EDGES
        if cached and (self._static is None
                       or self._static.width() != dw
                       or self._static.height() != dh):
            self._build_static(dw, dh, s)

        buf = self._buffer
        if buf is None or buf.width() != dw or buf.height() != dh:
            buf = QImage(dw, dh, QImage.Format.Format_ARGB32_Premultiplied)
            self._buffer = buf
        if not cached:
            buf.fill(0)

        p = QPainter(buf)
        fast = self._fast and n_edges >= self._FAST_EDGES
        p.setRenderHint(QPainter.RenderHint.Antialiasing, not fast)

        if cached:
            # Source: картинка замінює вміст буфера, окремий fill не треба
            p.setCompositionMode(
                QPainter.CompositionMode.CompositionMode_Source)
            p.drawImage(0, 0, self._static)
            p.setCompositionMode(
                QPainter.CompositionMode.CompositionMode_SourceOver)

        if abs(s - 1.0) > 0.001:
            p.scale(s, s)

        if cached:
            self._draw_edges(p, self._dyn_groups, self._dyn_arrows,
                             self._dyn_curves)
        else:
            self._draw_edges(p, self._groups, self._arrows, self._curves)
        p.end()

        painter.save()
        painter.resetTransform()
        painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_Source)
        painter.drawImage(0, 0, buf)
        painter.restore()
