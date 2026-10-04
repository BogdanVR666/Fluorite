from collections import deque

from FluoriteGraph import EdgeType, Hyperedge, NodeType
from document import Document
from view import TypeLook

UNDO_DEPTH = 10

_KEYED = ("types", "nodes", "edges", "groups")

BEFORE, AFTER = 0, 1


def snapshot(doc: Document) -> dict:
    view = doc.view
    uid = {family: {name: look.uid for name, look in view.types(family).items()}
           for family in ("node", "edge")}
    return {
        "types": {**{("node", look.uid): (name, look.design, None)
                     for name, look in view.node_types.items()},
                  **{("edge", look.uid): (name, look.design,
                                          doc.graph.edges[name].directed)
                     for name, look in view.edge_types.items()}},
        "nodes": {nid: (node, uid["node"][name], view.nodes[nid])
                  for name, t in doc.graph.nodes.items()
                  for nid, node in t.nodes.items()},
        "edges": {eid: (edge, uid["edge"][name], view.edges[eid])
                  for name, t in doc.graph.edges.items()
                  for eid, edge in t.edges.items()},
        "groups": {gid: (frozenset(he.children), he.name, he.description,
                         view.groups[gid])
                   for gid, he in doc.graph.hyperedges.items()},
        "numbers": tuple(sorted(doc.numbers.items())),
    }


def diff(old: dict, new: dict) -> dict | None:
    change = {}
    for part in _KEYED:
        a, b = old[part], new[part]
        changed = {k: (a.get(k), b.get(k)) for k in a.keys() | b.keys()
                   if a.get(k) != b.get(k)}
        if changed:
            change[part] = changed
    if old["numbers"] != new["numbers"]:
        change["numbers"] = (old["numbers"], new["numbers"])
    return change or None


def apply(doc: Document, change: dict, side: int) -> tuple[set, set]:
    now = 1 - side
    graph, view = doc.graph, doc.view
    types = change.get("types", {})

    for (family, uid), pair in types.items():
        rec = pair[side]
        if rec is None:
            continue
        name, design, directed = rec
        looks = view.types(family)
        if pair[now] is None:
            looks[name] = TypeLook(design, uid=uid)
            if family == "node":
                graph.nodes[name] = NodeType(name)
            else:
                graph.edges[name] = EdgeType(name, directed)
            continue
        current = pair[now][0]
        if current != name:
            doc.rename_class(family, current, name)
        looks[name] = TypeLook(design, looks[name].hidden, uid)
        if family == "edge":
            graph.edges[name].directed = directed

    names = {family: {look.uid: name
                      for name, look in view.types(family).items()}
             for family in ("node", "edge")}

    edges = change.get("edges", {})
    for eid, pair in edges.items():
        if pair[side] is None and doc.has_edge(eid):
            doc._drop_edge(eid)

    added, removed = set(), set()
    for nid, pair in change.get("nodes", {}).items():
        rec = pair[side]
        if rec is None:
            if doc.has_node(nid):
                del graph.nodes[doc.type_of.pop(nid)].nodes[nid]
                del view.nodes[nid]
            removed.add(nid)
            continue
        node, type_uid, look = rec
        name = names["node"][type_uid]
        if doc.has_node(nid) and doc.type_of[nid] != name:
            del graph.nodes[doc.type_of[nid]].nodes[nid]
        if not doc.has_node(nid):
            added.add(nid)
        graph.nodes[name].nodes[nid] = node
        view.nodes[nid] = look
        doc.type_of[nid] = name

    for eid, pair in edges.items():
        rec = pair[side]
        if rec is None:
            continue
        edge, type_uid, look = rec
        name = names["edge"][type_uid]
        if doc.has_edge(eid) and doc.edge_type_of[eid] != name:
            del graph.edges[doc.edge_type_of[eid]].edges[eid]
        graph.edges[name].edges[eid] = edge
        view.edges[eid] = look
        doc.edge_type_of[eid] = name

    for gid, pair in change.get("groups", {}).items():
        rec = pair[side]
        if rec is None:
            graph.hyperedges.pop(gid, None)
            view.groups.pop(gid, None)
            continue
        children, name, description, look = rec
        he = graph.hyperedges.get(gid)
        if he is None:
            graph.hyperadd(Hyperedge(name, description, set(children), gid))
        else:
            he.name, he.description = name, description
            he.children = set(children)
        view.groups[gid] = look

    for (family, uid), pair in types.items():
        if pair[side] is None and pair[now] is not None:
            name = pair[now][0]
            del view.types(family)[name]
            del (graph.nodes if family == "node" else graph.edges)[name]

    if "numbers" in change:
        doc.numbers = dict(change["numbers"][side])
    doc.orphans = []
    doc.reindex()
    return added, removed


class History:
    def __init__(self):
        self._undo: deque[dict] = deque(maxlen=UNDO_DEPTH)
        self._redo: list[dict] = []
        self._base: dict | None = None

    def reset(self, state: dict):
        self._undo.clear()
        self._redo.clear()
        self._base = state

    def record(self, state: dict) -> bool:
        change = diff(self._base, state)
        self._base = state
        if change is None:
            return False
        self._undo.append(change)
        self._redo.clear()
        return True

    def rebase(self, state: dict):
        self._base = state

    def undo(self) -> dict | None:
        if not self._undo:
            return None
        change = self._undo.pop()
        self._redo.append(change)
        return change

    def redo(self) -> dict | None:
        if not self._redo:
            return None
        change = self._redo.pop()
        self._undo.append(change)
        return change

    @property
    def undo_count(self) -> int:
        return len(self._undo)

    @property
    def redo_count(self) -> int:
        return len(self._redo)
