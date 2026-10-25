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


_BEND_STEP = 14.0


Line = tuple[int, int, int]


def _edge_bends(lines: list[Line]) -> dict[Line, float]:
    pairs: dict[tuple[int, int], list[Line]] = {}
    for line in lines:
        _, a, b = line
        pairs.setdefault((a, b) if a < b else (b, a), []).append(line)
    bends: dict[Line, float] = {}
    for (low, _), group in pairs.items():
        k = len(group)
        if k < 2:
            continue
        for i, line in enumerate(group):
            off = (i - (k - 1) / 2.0) * _BEND_STEP
            bends[line] = off if line[1] == low else -off
    return bends


def _bend_control(x1: float, y1: float, x2: float, y2: float,
                  bend: float) -> tuple[float, float]:
    dx, dy = x2 - x1, y2 - y1
    d = math.hypot(dx, dy)
    if d < 1e-6:
        return x1, y1
    nx_, ny_ = -dy / d, dx / d
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


_NODE_R = 22.0
_BARB_BASE = 7.0
_BARB_K = 1.8
_BARB_COS = math.cos(math.radians(26))
_BARB_SIN = math.sin(math.radians(26))


def _barb_len(width: float) -> float:
    return _BARB_BASE + _BARB_K * width


def _fit_arrow(line: QLineF, left: QLineF, right: QLineF, blen: float,
               inset: float = _NODE_R):
    dx, dy = line.x2() - line.x1(), line.y2() - line.y1()
    d = math.hypot(dx, dy)
    if d <= inset:
        left.setLine(line.x2(), line.y2(), line.x2(), line.y2())
        right.setLine(line.x2(), line.y2(), line.x2(), line.y2())
        return
    ux, uy = dx / d, dy / d
    tx, ty = line.x2() - ux * inset, line.y2() - uy * inset
    lx, ly = -ux * _BARB_COS + uy * _BARB_SIN, -ux * _BARB_SIN - uy * _BARB_COS
    rx, ry = -ux * _BARB_COS - uy * _BARB_SIN, ux * _BARB_SIN - uy * _BARB_COS
    left.setLine(tx, ty, tx + lx * blen, ty + ly * blen)
    right.setLine(tx, ty, tx + rx * blen, ty + ry * blen)


_GRID_STEP = 80.0


def _snap(x: float, y: float) -> tuple[float, float]:
    half = _GRID_STEP / 2
    return (math.floor(x / half + 0.5) * half,
            math.floor(y / half + 0.5) * half)


_GROUP_HEADER = 32.0
_GROUP_MIN = 80.0
_GROUP_SIZE = (320.0, 240.0)
_GROUP_PAD = 16.0


def _tree_anchor(look) -> tuple[float, float]:
    dx, dy = look.node or (look.width / 2, _NODE_R)
    return look.x + dx, look.y + dy


def _endpoint(doc: Document, eid: int):
    if doc.has_node(eid):
        look = doc.look(eid)
        return look.x, look.y, None
    look = doc.group_look(eid)
    if look.collapsed:
        return look.x + look.width / 2, look.y + _NODE_R, None
    if look.mode == "tree":
        return (*_tree_anchor(look), None)
    return look.x + look.width / 2, look.y + look.height / 2, look


def _rect_exit(look, tx: float, ty: float) -> tuple[float, float]:
    cx, cy = look.x + look.width / 2, look.y + look.height / 2
    dx, dy = tx - cx, ty - cy
    if dx == 0 and dy == 0:
        return cx, look.y
    s = min(look.width / 2 / abs(dx) if dx else math.inf,
            look.height / 2 / abs(dy) if dy else math.inf)
    return cx + dx * s, cy + dy * s


def _ends(doc: Document, a: int, b: int):
    ax, ay, frame_a = _endpoint(doc, a)
    bx, by, frame_b = _endpoint(doc, b)
    x1, y1 = _rect_exit(frame_a, bx, by) if frame_a else (ax, ay)
    x2, y2 = _rect_exit(frame_b, ax, ay) if frame_b else (bx, by)
    return x1, y1, x2, y2, 0.0 if frame_b else _NODE_R


def _is_frame(doc: Document, eid: int) -> bool:
    if not doc.has_group(eid):
        return False
    look = doc.group_look(eid)
    return not look.collapsed and look.mode == "frame"


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
    HiddenRole = Qt.UserRole + 13

    def __init__(self, doc: Document, parent=None):
        super().__init__(parent)
        self._doc = doc
        self._ids: list[int] = []
        self._rows: dict[int, int] = {}
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
            return not doc.shown(nid)
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
        for i in range(row, len(self._ids)):
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
        self._selected -= ids
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


class GroupsModel(QAbstractListModel):
    GroupIdRole = Qt.UserRole + 1
    XRole = Qt.UserRole + 2
    YRole = Qt.UserRole + 3
    WidthRole = Qt.UserRole + 4
    HeightRole = Qt.UserRole + 5
    TitleRole = Qt.UserRole + 6
    CollapsedRole = Qt.UserRole + 7
    ModeRole = Qt.UserRole + 8
    SelectedRole = Qt.UserRole + 9
    HiddenRole = Qt.UserRole + 10
    MembersRole = Qt.UserRole + 11
    AnchorXRole = Qt.UserRole + 12
    AnchorYRole = Qt.UserRole + 13
    ShapeRole = Qt.UserRole + 14
    ColorRole = Qt.UserRole + 15
    OpacityRole = Qt.UserRole + 16
    DegreeRole = Qt.UserRole + 17

    def __init__(self, doc: Document, parent=None):
        super().__init__(parent)
        self._doc = doc
        self._ids: list[int] = []
        self._rows: dict[int, int] = {}
        self._selected: set[int] = set()

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._ids)

    def roleNames(self):
        return {
            self.GroupIdRole: QByteArray(b"groupId"),
            self.XRole: QByteArray(b"gx"),
            self.YRole: QByteArray(b"gy"),
            self.WidthRole: QByteArray(b"gw"),
            self.HeightRole: QByteArray(b"gh"),
            self.TitleRole: QByteArray(b"title"),
            self.CollapsedRole: QByteArray(b"collapsed"),
            self.ModeRole: QByteArray(b"mode"),
            self.SelectedRole: QByteArray(b"groupSelected"),
            self.HiddenRole: QByteArray(b"groupHidden"),
            self.MembersRole: QByteArray(b"memberCount"),
            self.AnchorXRole: QByteArray(b"ax"),
            self.AnchorYRole: QByteArray(b"ay"),
            self.ShapeRole: QByteArray(b"nodeShape"),
            self.ColorRole: QByteArray(b"nodeColor"),
            self.OpacityRole: QByteArray(b"nodeOpacity"),
            self.DegreeRole: QByteArray(b"degree"),
        }

    def data(self, index, role):
        if not index.isValid() or not (0 <= index.row() < len(self._ids)):
            return None
        gid = self._ids[index.row()]
        doc = self._doc
        look = doc.group_look(gid)
        if role == self.GroupIdRole:
            return gid
        if role == self.XRole:
            return look.x
        if role == self.YRole:
            return look.y
        if role == self.WidthRole:
            return look.width
        if role == self.HeightRole:
            return look.height
        if role == self.TitleRole:
            return doc.name_of(gid)
        if role == self.CollapsedRole:
            return look.collapsed
        if role == self.ModeRole:
            return look.mode
        if role == self.SelectedRole:
            return gid in self._selected
        if role == self.HiddenRole:
            return not doc.shown(gid)
        if role == self.MembersRole:
            return len(doc.group_members(gid))
        if role in (self.AnchorXRole, self.AnchorYRole):
            ax, ay, _ = _endpoint(doc, gid)
            return ax - look.x if role == self.AnchorXRole else ay - look.y
        if role in (self.ShapeRole, self.ColorRole, self.OpacityRole):
            style = doc.group_style()
            return (style.shape if role == self.ShapeRole
                    else style.color if role == self.ColorRole
                    else style.opacity)
        if role == self.DegreeRole:
            return doc.degree(gid) + sum(gid in link
                                         for link in doc.tree_links())
        return None

    def notify_row(self, gid: int, roles: list[int]):
        idx = self.index(self._rows[gid])
        self.dataChanged.emit(idx, idx, roles)

    def notify_all(self, roles: list[int]):
        if self._ids:
            self.dataChanged.emit(
                self.index(0), self.index(len(self._ids) - 1), roles)

    def set_selected(self, groups: set[int]):
        self._selected = groups
        self.notify_all([self.SelectedRole])

    def reset_with(self, ids):
        self.beginResetModel()
        self._ids = list(ids)
        self._rows = {gid: i for i, gid in enumerate(self._ids)}
        self._selected.intersection_update(self._ids)
        self.endResetModel()


def _step(merge=None):
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
    graphChanged = Signal()
    edgesChanged = Signal()
    nodeMoved = Signal(int, float, float)
    classesChanged = Signal()
    selectionChanged = Signal()
    summaryChanged = Signal()
    statusChanged = Signal()

    _SUMMARY_MS = 100
    _IDLE_MS = 600

    def __init__(self, parent=None):
        super().__init__(parent)
        self._doc = Document()
        self._model = NodesModel(self._doc, self)
        self._selected: set[int] = self._model._selected
        self._groups = GroupsModel(self._doc, self)
        self._selected_groups: set[int] = self._groups._selected
        self._summary = QTimer(self)
        self._summary.setSingleShot(True)
        self._summary.setInterval(self._SUMMARY_MS)
        self._summary.timeout.connect(self.summaryChanged)
        self._status = ""
        self._history = history.History()
        self._history.reset(self._snapshot())
        self._pending = None
        self._idle = QTimer(self)
        self._idle.setSingleShot(True)
        self._idle.setInterval(self._IDLE_MS)
        self._idle.timeout.connect(self._commit)

    def _snapshot(self) -> dict:
        return history.snapshot(self._doc)

    def _commit(self):
        self._pending = None
        self._idle.stop()
        self._history.record(self._snapshot())

    def _travel(self, change: dict, side: int):
        added, removed = history.apply(self._doc, change, side)
        if removed:
            self._model.remove_nodes(removed)
        for nid in sorted(added):
            self._model.append_node(nid)
        roles = list(self._model.roleNames())
        for nid, pair in change.get("nodes", {}).items():
            if None not in pair:
                self._model.notify_row(nid, roles)
        for pair in change.get("edges", {}).values():
            for rec in pair:
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
            self._groups.reset_with(self._doc.view.groups)
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

    @Property(QObject, constant=True)
    def groupsModel(self):
        return self._groups

    @Property(float, constant=True)
    def gridStep(self):
        return _GRID_STEP

    @Property(str, notify=summaryChanged)
    def stats(self):
        n = len(self._doc.type_of)
        m = self._doc.edge_count()
        c = self._doc.component_count()
        return f"Вершин: {n}  •  Ребер: {m}  •  Компонент зв'язності: {c}"

    _HINT = ("ЛКМ по полю — нова вершина, ЛКМ-перетяг — рамка виділення "
             "(Shift — додати до наявного); Shift+ЛКМ по вершині — виділити "
             "ще одну, Ctrl+Shift+ЛКМ — з'єднати виділені з нею, Delete — "
             "видалити виділені; Shift+перетяг вершини — по сітці; ПКМ по "
             "вершині чи ребру — меню, ПКМ-перетяг між вершинами — ребро")

    @Property(str, notify=statusChanged)
    def status(self):
        return self._status or self._HINT

    def _set_status(self, msg: str):
        if msg != self._status:
            self._status = msg
            self.statusChanged.emit()

    @Property(int, notify=selectionChanged)
    def selectionCount(self):
        return len(self._selected)

    @Property(int, notify=selectionChanged)
    def groupSelectionCount(self):
        return len(self._selected_groups)

    def _selection_changed(self):
        self._model.set_selected(self._selected)
        self._groups.set_selected(self._selected_groups)
        self.selectionChanged.emit()


    @Slot(int, bool)
    def selectNode(self, nid: int, additive: bool):
        if not self._doc.has_node(nid):
            return
        if additive:
            self._selected ^= {nid}
        else:
            self._selected.clear()
            self._selected_groups.clear()
            self._selected.add(nid)
        self._selection_changed()
        n = len(self._selected)
        self._set_status(f"Виділено вершин: {n}" if n > 1 else "")

    @Slot(float, float, float, float, bool)
    def selectInRect(self, x: float, y: float, w: float, h: float,
                     additive: bool):
        x2, y2 = x + w, y + h
        doc = self._doc
        hits = {nid for nid, look in doc.view.nodes.items()
                if x <= look.x <= x2 and y <= look.y <= y2
                and doc.shown(nid)}
        group_hits = set()
        for gid in doc.view.groups:
            if not doc.shown(gid):
                continue
            ax, ay, frame = _endpoint(doc, gid)
            if frame is None:
                caught = x <= ax <= x2 and y <= ay <= y2
            else:
                caught = (x <= frame.x and frame.x + frame.width <= x2
                          and y <= frame.y and frame.y + frame.height <= y2)
            if caught:
                group_hits.add(gid)
        if not additive:
            self._selected.clear()
            self._selected_groups.clear()
        self._selected |= hits
        self._selected_groups |= group_hits
        self._selection_changed()
        if hits or group_hits:
            self._set_status(f"Виділено вершин: {len(self._selected)}, "
                             f"груп: {len(self._selected_groups)}")
        else:
            self._set_status("У рамку не потрапила жодна вершина")

    @Slot()
    def clearSelection(self):
        if not self._selected and not self._selected_groups:
            return
        self._selected.clear()
        self._selected_groups.clear()
        self._selection_changed()
        self._set_status("")

    @Slot(int, result=bool)
    def isSelected(self, nid: int) -> bool:
        return nid in self._selected


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
            self._groups.notify_all([GroupsModel.ShapeRole,
                                     GroupsModel.ColorRole,
                                     GroupsModel.OpacityRole])
        else:
            self.edgesChanged.emit()
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
        self._groups_changed()
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
        self._groups_changed()
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
        self._groups_changed()
        self.classesChanged.emit()

    @Slot(str, str, int)
    def moveClass(self, family: str, name: str, index: int):
        if self._doc.move_class(family, name, index):
            self.classesChanged.emit()

    _CLASS_ROLES = [NodesModel.ShapeRole, NodesModel.ColorRole,
                    NodesModel.OpacityRole, NodesModel.ClassRole]


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

    @Slot(int, float, float, bool)
    @_step(lambda nid, x, y, snap: ('move', nid))
    def moveNode(self, nid: int, x: float, y: float, snap: bool):
        if not self._doc.has_node(nid):
            return
        look = self._doc.look(nid)
        self._moved(*self._shift(nid, x - look.x, y - look.y, snap))

    def _drag_set(self, anchor: int) -> tuple[set[int], set[int]]:
        picked = self._selected | self._selected_groups
        if anchor in picked and len(picked) > 1:
            return set(self._selected), set(self._selected_groups)
        if self._doc.has_group(anchor):
            return set(), {anchor}
        return {anchor}, set()

    def _shift(self, anchor: int, dx: float, dy: float,
               snap: bool) -> tuple[set[int], set[int]]:
        doc = self._doc
        nodes, groups = self._drag_set(anchor)
        trees = {gid for gid in groups if doc.is_tree(gid)}
        carried_nodes, carried_groups = doc.contents(groups - trees)
        moved_nodes, moved_groups = set(), set()
        for gid in trees - carried_groups:
            look = doc.group_look(gid)
            ax, ay = _tree_anchor(look)
            x, y = ax + dx, ay + dy
            if snap:
                x, y = _snap(x, y)
            if (x, y) != (ax, ay):
                doc.move_tree_node(gid, x - look.x, y - look.y)
                moved_groups.add(gid)
        for gid in groups - trees - carried_groups:
            look = doc.group_look(gid)
            x, y = look.x + dx, look.y + dy
            if snap:
                x, y = _snap(x, y)
            gdx, gdy = x - look.x, y - look.y
            if not (gdx or gdy):
                continue
            inner_nodes, inner_groups = doc.contents({gid})
            for g in ({gid} | inner_groups) - moved_groups:
                look = doc.group_look(g)
                doc.move_group(g, look.x + gdx, look.y + gdy)
                moved_groups.add(g)
            for nid in inner_nodes - moved_nodes:
                look = doc.look(nid)
                doc.move_node(nid, look.x + gdx, look.y + gdy)
                moved_nodes.add(nid)
        for nid in nodes - carried_nodes - moved_nodes:
            look = doc.look(nid)
            x, y = look.x + dx, look.y + dy
            if snap:
                x, y = _snap(x, y)
            if (x, y) == (look.x, look.y):
                continue
            doc.move_node(nid, x, y)
            moved_nodes.add(nid)
        return moved_nodes, moved_groups

    def _moved(self, nodes: set[int], groups: set[int]):
        doc = self._doc
        for nid in nodes:
            self._model.notify_row(nid, [NodesModel.XRole, NodesModel.YRole])
            if not groups:
                look = doc.look(nid)
                self.nodeMoved.emit(nid, look.x, look.y)
        for gid in groups:
            self._groups.notify_row(gid, self._GROUP_GEOMETRY)
        if not nodes and not groups:
            return
        changed = doc.place(None if groups else nodes)
        if changed:
            self._groups.notify_all(self._GROUP_COUNTS)
        if groups or changed:
            self.graphChanged.emit()

    def _remove_one(self, nid: int):
        if not self._doc.has_node(nid):
            return
        neighbors = self._doc.remove_node(nid)
        self._model.remove_node(nid)
        for nb in neighbors:
            if self._model.has_node(nb):
                self._model.notify_row(nb, [NodesModel.DegreeRole])

    _GROUP_ROLES = [NodesModel.HiddenRole]
    _GROUP_GEOMETRY = [GroupsModel.XRole, GroupsModel.YRole,
                       GroupsModel.WidthRole, GroupsModel.HeightRole,
                       GroupsModel.AnchorXRole, GroupsModel.AnchorYRole]
    _GROUP_COUNTS = [GroupsModel.MembersRole, GroupsModel.DegreeRole]

    @Slot(int)
    @_step()
    def removeNode(self, nid: int):
        if not self._doc.has_node(nid):
            return
        was_selected = nid in self._selected
        self._remove_one(nid)
        if was_selected:
            self.selectionChanged.emit()
        self._groups.notify_all(self._GROUP_COUNTS)
        self._structure_changed()

    @Slot(float, float, result=int)
    def nodeAt(self, x: float, y: float) -> int:
        hit2 = 26.0 * 26.0
        best, best_d = -1, hit2
        for nid, look in self._doc.view.nodes.items():
            if not self._doc.shown(nid):
                continue
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
        return {"label": node.name, "description": node.description,
                "shape": style.shape, "color": style.color,
                "opacity": style.opacity, "x": look.x, "y": look.y,
                "klass": doc.node_type(nid)}

    @Slot()
    @_step()
    def removeSelection(self):
        if not self._selected and not self._selected_groups:
            return
        doc = self._doc
        n, k = len(self._selected), len(self._selected_groups)
        doomed = set(self._selected)
        touched = doc.remove_nodes(doomed)
        for gid in set(self._selected_groups):
            touched |= doc.remove_group(gid)
        self._groups.reset_with(doc.view.groups)
        self._nodes_removed(doomed, touched)
        self._set_status(f"Видалено вершин: {n}"
                         + (f", рамок: {k}" if k else ""))

    def _nodes_removed(self, doomed: set[int], touched: set[int]):
        was_selected = bool(self._selected & doomed)
        if doomed:
            self._model.remove_nodes(doomed)
        for nid in touched:
            if self._model.has_node(nid):
                self._model.notify_row(nid, [NodesModel.DegreeRole])
        if was_selected:
            self._selection_changed()
        self._model.notify_all(self._GROUP_ROLES)
        self._groups.notify_all(self._GROUP_COUNTS
                                + [GroupsModel.HiddenRole])
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
            if self._model.has_node(nid):
                self._model.notify_row(nid, [NodesModel.DegreeRole])
        self._groups.notify_all([GroupsModel.DegreeRole])
        self._structure_changed()

    @Slot(int)
    @_step()
    def removeEdge(self, eid: int):
        if not self._doc.has_edge(eid):
            return
        ends = self._doc.ends(eid)
        self._doc.remove_edge(eid)
        for nid in ends:
            if self._model.has_node(nid):
                self._model.notify_row(nid, [NodesModel.DegreeRole])
        self._groups.notify_all([GroupsModel.DegreeRole])
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
        if not self._doc.set_edge_class(eid, new_name):
            self._set_status(f"Ребро класу «{new_name}» між цими вершинами "
                             "вже існує")
            return False
        self._structure_changed()
        return True

    @Slot(float, float, result=int)
    def edgeAt(self, x: float, y: float) -> int:
        hit2 = 7.0 * 7.0
        doc = self._doc
        lines = doc.visual_lines()
        bends = _edge_bends(lines)
        best, best_d = -1, hit2
        for line in lines:
            eid, oa, ob = line
            x1, y1, x2, y2, _ = _ends(doc, oa, ob)
            bend = bends.get(line, 0.0)
            if bend:
                d = _point_bend_dist2(x, y, x1, y1, x2, y2, bend)
            else:
                d = _point_segment_dist2(x, y, x1, y1, x2, y2)
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
        return {"label": f"{doc.name_of(src)}{sep}{doc.name_of(dst)}",
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


    def _groups_changed(self):
        self._model.notify_all(self._GROUP_ROLES)
        self._groups.notify_all(list(self._groups.roleNames()))
        self.graphChanged.emit()

    def _drop_hidden_from_selection(self):
        doc = self._doc
        hidden = {nid for nid in self._selected if not doc.shown(nid)}
        hidden_groups = {gid for gid in self._selected_groups
                         if not doc.shown(gid)}
        if hidden or hidden_groups:
            self._selected -= hidden
            self._selected_groups -= hidden_groups
            self._selection_changed()

    @Slot(float, float)
    @_step()
    def addGroup(self, x: float, y: float):
        gid = self._doc.add_group(x, y, *_GROUP_SIZE)
        self._groups.reset_with(self._doc.view.groups)
        self.graphChanged.emit()
        self._set_status(f"Створено групу «{self._doc.name_of(gid)}»")

    @Slot()
    @_step()
    def groupSelection(self):
        doc = self._doc
        boxes = [(look.x - 2 * _NODE_R, look.y - _NODE_R,
                  look.x + 2 * _NODE_R, look.y + _NODE_R)
                 for look in (doc.look(nid) for nid in self._selected)]
        boxes += [(look.x, look.y, look.x + look.width, look.y + look.height)
                  for look in (doc.group_look(gid)
                               for gid in self._selected_groups)]
        if not boxes:
            self._set_status("Нічого не виділено")
            return
        left = min(b[0] for b in boxes) - _GROUP_PAD
        top = min(b[1] for b in boxes) - _GROUP_PAD - _GROUP_HEADER
        right = max(b[2] for b in boxes) + _GROUP_PAD
        bottom = max(b[3] for b in boxes) + _GROUP_PAD
        gid = doc.add_group(left, top, right - left, bottom - top)
        self._groups.reset_with(doc.view.groups)
        self.graphChanged.emit()
        self._set_status(f"Створено групу «{doc.name_of(gid)}» "
                         f"(елементів: {len(doc.group_members(gid))})")

    @Slot(int, bool)
    def selectGroup(self, gid: int, additive: bool):
        if not self._doc.has_group(gid):
            return
        if additive:
            self._selected_groups ^= {gid}
        else:
            self._selected.clear()
            self._selected_groups.clear()
            self._selected_groups.add(gid)
        self._selection_changed()
        self._set_status("")

    @Slot(int, float, float, bool)
    @_step(lambda gid, x, y, snap: ('move', gid))
    def moveGroup(self, gid: int, x: float, y: float, snap: bool):
        if not self._doc.has_group(gid):
            return
        look = self._doc.group_look(gid)
        hx, hy = (_tree_anchor(look) if self._doc.is_tree(gid)
                  else (look.x, look.y))
        self._moved(*self._shift(gid, x - hx, y - hy, snap))

    @Slot(int, float, float, bool)
    @_step(lambda gid, right, bottom, snap: ('resize', gid))
    def resizeGroup(self, gid: int, right: float, bottom: float, snap: bool):
        doc = self._doc
        if not doc.has_group(gid):
            return
        if snap:
            right, bottom = _snap(right, bottom)
        look = doc.group_look(gid)
        width = max(_GROUP_MIN, right - look.x)
        height = max(_GROUP_MIN, bottom - look.y)
        if (width, height) == (look.width, look.height):
            return
        doc.resize_group(gid, width, height)
        self._groups.notify_row(gid, self._GROUP_GEOMETRY)
        if doc.place():
            self._groups.notify_all(self._GROUP_COUNTS)
        self.graphChanged.emit()

    @Slot(int, bool)
    @_step()
    def setGroupCollapsed(self, gid: int, collapsed: bool):
        if not self._doc.set_collapsed(gid, collapsed):
            return
        self._drop_hidden_from_selection()
        self._groups_changed()

    @Slot(int, str)
    @_step()
    def setGroupMode(self, gid: int, mode: str):
        if mode in ("frame", "tree") and self._doc.set_group_mode(gid, mode):
            self._groups_changed()

    @Slot(int, str)
    @_step(lambda gid, text: ('group-name', gid))
    def renameGroup(self, gid: int, text: str):
        if self._doc.has_group(gid):
            self._doc.rename_group(gid, text)
            self._groups.notify_row(gid, [GroupsModel.TitleRole])

    @Slot(int)
    @_step()
    def removeGroup(self, gid: int):
        doc = self._doc
        if not doc.has_group(gid):
            return
        name = doc.name_of(gid)
        touched = doc.remove_group(gid)
        self._groups.reset_with(doc.view.groups)
        self._nodes_removed(set(), touched)
        self._set_status(f"Рамку «{name}» видалено, вміст лишився")

    @Slot(float, float, bool, result=int)
    def groupAt(self, x: float, y: float, whole: bool) -> int:
        doc = self._doc
        best, best_area = -1, math.inf
        for gid, look in doc.view.groups.items():
            if not doc.shown(gid):
                continue
            ax, ay, frame = _endpoint(doc, gid)
            if frame is None:
                if (ax - x) ** 2 + (ay - y) ** 2 <= 26.0 * 26.0:
                    return gid
                continue
            inside = (look.x <= x <= look.x + look.width
                      and look.y <= y <= look.y + look.height)
            edge = min(x - look.x, look.x + look.width - x,
                       y - look.y, look.y + look.height - y)
            area = look.width * look.height
            grip = whole or y <= look.y + _GROUP_HEADER or edge <= 6.0
            if inside and grip and area < best_area:
                best, best_area = gid, area
        return best

    @Slot(int, result="QVariantMap")
    def groupInfo(self, gid: int):
        doc = self._doc
        if not doc.has_group(gid):
            return {}
        look = doc.group_look(gid)
        ax, ay, frame = _endpoint(doc, gid)
        if frame is not None:
            ay = look.y + _GROUP_HEADER / 2
        return {"label": doc.name_of(gid), "collapsed": look.collapsed,
                "mode": look.mode, "selected": gid in self._selected_groups,
                "memberCount": len(doc.group_members(gid)),
                "x": ax, "y": ay}


    @Slot()
    @_step()
    def clear(self):
        self._doc.clear()
        self._model.reset_all()
        self._groups.reset_with(self._doc.view.groups)
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
            new_doc = storage.graph_from_json(text)
        except (ValueError, KeyError, TypeError) as e:
            self._set_status(f"Не вдалося прочитати граф: {e}")
            return

        self._doc.adopt(new_doc)
        self._model.reset_with(self._doc.type_of)
        self._groups.reset_with(self._doc.view.groups)
        self._pending = None
        self._idle.stop()
        self._history.reset(self._snapshot())
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

    _FAST_EDGES = 300
    _BURST_GAP = 0.1
    _REFINE_MS = 150

    def __init__(self, parent=None):
        super().__init__(parent)
        self._backend: GraphBackend | None = None
        self._groups: dict[tuple, list[QLineF]] | None = None
        self._arrows: dict[tuple, list[QLineF]] = {}
        self._curves: dict[tuple, list[tuple[QLineF, float, float]]] = {}
        self._incident: dict[int, list[tuple[QLineF, bool, tuple | None]]] = {}
        self._rebuild_on: set[int] = set()
        self._moving: set[int] = set()
        self._static: QImage | None = None
        self._dyn_groups: dict[tuple, list[QLineF]] = {}
        self._dyn_arrows: dict[tuple, list[QLineF]] = {}
        self._dyn_curves: dict[tuple, list[tuple[QLineF, float, float]]] = {}
        self._pens: dict[tuple, QPen] = {}
        self._fast = False
        self._low_res = False
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
        if nid in self._rebuild_on:
            self._mark_dirty()
            return
        if nid not in self._moving:
            self._moving.add(nid)
            self._static = None
        if self._groups is not None:
            point = QPointF(x, y)
            for line, at_p1, barbs in self._incident.get(nid, ()):
                if at_p1:
                    line.setP1(point)
                else:
                    line.setP2(point)
                if barbs is not None:
                    _fit_arrow(line, *barbs)
        self._enter_fast()
        self._last_request = monotonic()
        self.update()

    def _refine_pass(self):
        self._fast = False
        self._moving.clear()
        self._static = None
        if self._low_res:
            self._low_res = False
            self.setTextureSize(QSize())
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
                pass
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
        lines = doc.visual_lines()
        bends = _edge_bends(lines)
        groups: dict[tuple, list[QLineF]] = {}
        arrows: dict[tuple, list[QLineF]] = {}
        curves: dict[tuple, list[tuple[QLineF, float, float]]] = {}
        incident: dict[int, list[tuple[QLineF, bool, tuple | None]]] = {}
        rebuild_on: set[int] = set()

        def straight(line: QLineF, key: tuple, inset: float):
            groups.setdefault(key, []).append(line)
            _, width, _, directed = key
            if not directed:
                return None
            left, right = QLineF(), QLineF()
            barbs = (left, right, _barb_len(width), inset)
            _fit_arrow(line, *barbs)
            arrows.setdefault(key, []).extend((left, right))
            return barbs

        for visual in lines:
            eid, oa, ob = visual
            x1, y1, x2, y2, inset = _ends(doc, oa, ob)
            style = doc.edge_style(eid)
            key = (style.color, style.width, style.line,
                   doc.edge_directed(eid))
            line = QLineF(x1, y1, x2, y2)
            bend = bends.get(visual, 0.0)
            barbs = None
            if bend:
                curves.setdefault(key, []).append((line, bend, inset))
            else:
                barbs = straight(line, key, inset)
            if _is_frame(doc, oa) or _is_frame(doc, ob):
                rebuild_on.update((oa, ob))
                continue
            incident.setdefault(oa, []).append((line, True, barbs))
            incident.setdefault(ob, []).append((line, False, barbs))

        style, directed = doc.contains_style()
        key = (style.color, style.width, style.line, directed)
        for gid, child in doc.tree_links():
            x1, y1, x2, y2, inset = _ends(doc, gid, child)
            line = QLineF(x1, y1, x2, y2)
            barbs = straight(line, key, inset)
            if _is_frame(doc, child):
                rebuild_on.add(child)
                continue
            incident.setdefault(child, []).append((line, False, barbs))
        self._groups = groups
        self._arrows = arrows
        self._curves = curves
        self._incident = incident
        self._rebuild_on = rebuild_on
        self._static = None
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
            for chord, bend, inset in items:
                x1, y1 = chord.x1(), chord.y1()
                x2, y2 = chord.x2(), chord.y2()
                cx, cy = _bend_control(x1, y1, x2, y2, bend)
                path.moveTo(x1, y1)
                path.quadTo(cx, cy, x2, y2)
                if directed:
                    left, right = QLineF(), QLineF()
                    _fit_arrow(QLineF(cx, cy, x2, y2), left, right,
                               _barb_len(width), inset)
                    barbs.extend((left, right))
            p.setPen(self._body_pen(color, width, line))
            p.drawPath(path)
            if barbs:
                p.setPen(self._head_pen(color, width))
                p.drawLines(barbs)

    def _build_static(self, dw: int, dh: int, s: float):
        dyn_ids: set[int] = set()
        for nid in self._moving:
            for line, _, barbs in self._incident.get(nid, ()):
                dyn_ids.add(id(line))
                if barbs is not None:
                    dyn_ids.add(id(barbs[0]))
                    dyn_ids.add(id(barbs[1]))

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
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if abs(s - 1.0) > 0.001:
            p.scale(s, s)
        self._draw_edges(p, stat_groups, stat_arrows, stat_curves)
        p.end()
        self._static = img

    def paint(self, painter: QPainter):
        if self._backend is None:
            return
        if self._groups is None:
            self._rebuild()
        n_edges = self._backend._doc.edge_count()
        if not self._groups and not self._curves:
            return

        dev = painter.device()
        dw, dh = dev.width(), dev.height()
        if dw <= 0 or dh <= 0:
            return

        item_w = self.width()
        s = dw / item_w if item_w > 0 else 1.0

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
