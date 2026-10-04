"""Збереження документа у JSON і відкриття, зокрема файлів старих версій.

Формат 7 ділить файл на дві частини, як і сам документ:
"graph" — FluoriteGraph (типи, вершини, ребра, гіперребра),
"view" — вигляд (позиції, стилі, дизайн і порядок типів, групи на екрані).
"""
import json
from dataclasses import asdict, fields

from FluoriteGraph import EdgeType, Hyperedge, NodeType
from document import Document, reserve_ids
from view import EdgeLook, EdgeStyle, GroupLook, NodeLook, NodeStyle

FORMAT_VERSION = 7

Node = NodeType.Node
Edge = EdgeType.Edge


def _style_json(style) -> dict:
    return {k: v for k, v in asdict(style).items() if v is not None}


def _style(style_type, data: dict | None):
    names = {f.name for f in fields(style_type)}
    return style_type(**{k: v for k, v in (data or {}).items() if k in names})


def graph_to_json(doc: Document) -> str:
    graph, view = doc.graph, doc.view
    return json.dumps({
        "version": FORMAT_VERSION,
        "graph": {
            "node_types": {
                name: [{"id": nid, "name": n.name,
                        "description": n.description}
                       for nid, n in t.nodes.items()]
                for name, t in graph.nodes.items()},
            "edge_types": {
                name: {"directed": t.directed,
                       "edges": [{"id": eid, "node_in": e.node_in,
                                  "node_out": e.node_out,
                                  "description": e.description}
                                 for eid, e in t.edges.items()]}
                for name, t in graph.edges.items()},
            "hyperedges": [{"id": gid, "name": he.name,
                            "description": he.description,
                            "children": sorted(he.children)}
                           for gid, he in graph.hyperedges.items()],
        },
        "view": {
            family: [{"name": name, "design": asdict(look.design),
                      "hidden": look.hidden}
                     for name, look in view.types(family).items()]
            for family in ("node", "edge")
        } | {
            "defaults": {family: view.default_type(family)
                         for family in ("node", "edge")},
            "nodes": {str(nid): {"x": look.x, "y": look.y,
                                 "style": _style_json(look.style)}
                      for nid, look in view.nodes.items()},
            "edges": {str(eid): {"style": _style_json(look.style)}
                      for eid, look in view.edges.items()},
            "groups": {str(gid): {"node": look.node,
                                  "collapsed": look.collapsed}
                       for gid, look in view.groups.items()},
        },
        "numbers": doc.numbers,
    }, ensure_ascii=False, indent=2)


def graph_from_json(text: str) -> Document:
    data = json.loads(text)
    if not isinstance(data, dict) or ("nodes" not in data
                                      and "graph" not in data):
        raise ValueError("це не файл графа")
    version = data.get("version", 1)
    if version > FORMAT_VERSION:
        raise ValueError("файл створено новішою версією програми")
    doc = _from_v7(data) if version >= 7 else _from_legacy(data, version)
    doc.reindex()
    return doc


def _restore_types(doc: Document, entries: dict, defaults: dict):
    """entries: сім'я → [{"name", "design", "hidden"}] у порядку панелі."""
    for family, items in entries.items():
        if family not in ("node", "edge"):
            continue
        if family in defaults:   # стандартний тип міг бути перейменований
            doc.rename_class(family, doc.view.default_type(family),
                             str(defaults[family]))
        for index, entry in enumerate(items):
            name = str(entry["name"]).strip()
            design = entry.get("design") or {}
            if not doc.create_class(family, name, design):
                doc.update_class(family, name, design)
            doc.set_class_hidden(family, name,
                                 bool(entry.get("hidden", False)))
            doc.move_class(family, name, index)


def _from_v7(data: dict) -> Document:
    graph, view = data["graph"], data.get("view", {})
    doc = Document()
    directed = {name: {"directed": bool(t.get("directed", False))}
                for name, t in graph.get("edge_types", {}).items()}
    entries = {family: view.get(family, []) for family in ("node", "edge")}
    for entry in entries["edge"]:
        entry["design"] = {**(entry.get("design") or {}),
                           **directed.get(entry["name"], {})}
    # типи, яких немає у вигляді (файл зібрано не редактором), — у кінець
    for family, key in (("node", "node_types"), ("edge", "edge_types")):
        listed = {e["name"] for e in entries[family]}
        entries[family] += [{"name": name, "design": directed.get(name, {})}
                            for name in graph.get(key, {})
                            if name not in listed]
    _restore_types(doc, entries, view.get("defaults", {}))

    looks = view.get("nodes", {})
    seen: set[int] = set()

    def take(eid: int) -> int:
        if eid in seen:
            raise ValueError(f"id {eid} зустрічається двічі")
        seen.add(eid)
        return eid

    for name, items in graph.get("node_types", {}).items():
        for n in items:
            nid = take(int(n["id"]))
            look = looks.get(str(nid), {})
            doc._insert_node(
                doc.resolve_type("node", name),
                Node(str(n.get("name", "")), str(n.get("description") or ""),
                     nid),
                NodeLook(float(look.get("x", 0.0)), float(look.get("y", 0.0)),
                         _style(NodeStyle, look.get("style"))))

    looks = view.get("edges", {})
    for name, t in graph.get("edge_types", {}).items():
        for e in t.get("edges", []):
            eid = take(int(e["id"]))
            a, b = int(e["node_in"]), int(e["node_out"])
            if a == b or not doc.has_node(a) or not doc.has_node(b):
                continue
            doc._insert_edge(
                doc.resolve_type("edge", name),
                Edge(a, b, str(e.get("description") or ""), eid),
                EdgeLook(_style(EdgeStyle,
                                looks.get(str(eid), {}).get("style"))))

    looks = view.get("groups", {})
    for h in graph.get("hyperedges", []):
        gid = take(int(h["id"]))
        look = looks.get(str(gid))
        if look is None or not doc.has_node(int(look["node"])):
            continue             # групу нема чим показати
        doc.graph.hyperadd(Hyperedge(
            str(h.get("name", "")), h.get("description"),
            {int(c) for c in h.get("children", []) if doc.has_node(int(c))},
            gid))
        doc.view.groups[gid] = GroupLook(int(look["node"]),
                                         bool(look.get("collapsed", False)))

    if seen:
        reserve_ids(max(seen))
    numbers = data.get("numbers") or {}
    doc.numbers = {"node": int(numbers.get("node", len(doc.view.nodes) + 1)),
                   "group": int(numbers.get("group", 1))}
    return doc


# ---- файли версій 1–6 (до FluoriteGraph) --------------------------------

def _upgrade_v1(data: dict) -> dict:
    data["classes"] = {"node": [
        {"name": c["name"],
         "design": {"shape": c["shape"], "color": c["color"]}}
        for c in data.get("classes", [])
    ]}
    for n in data["nodes"]:
        n["style"] = {"shape": n.pop("shape", None),
                      "color": n.pop("color", None)}
    data["edges"] = [{"a": a, "b": b} for a, b in data.get("edges", [])]
    return data


def _from_legacy(data: dict, version: int) -> Document:
    """Старий формат: id вершин зберігаються, ребра й групи отримують нові
    (раніше в них або не було id, або вони перетинались з id вершин)."""
    if version < 2:
        data = _upgrade_v1(data)
    doc = Document()
    _restore_types(doc, data.get("classes", {}), data.get("defaults", {}))

    last = 0
    for n in data["nodes"]:
        nid = int(n["id"])
        last = max(last, nid)
        doc._insert_node(
            doc.resolve_type("node", n.get("class")),
            Node(str(n["label"]), str(n.get("description", "")), nid),
            NodeLook(float(n["x"]), float(n["y"]),
                     _style(NodeStyle, n.get("style"))))
    reserve_ids(last)
    doc.reindex()

    for e in data.get("edges", []):
        a, b = e["a"], e["b"]
        if version == 3 and e.get("source") == b:
            a, b = b, a
        eid = doc.add_edge(a, b, e.get("class"))
        if eid is None:
            continue
        doc.view.edges[eid] = EdgeLook(_style(EdgeStyle, e.get("style")))
        if e.get("description"):
            doc.graph.edges[doc.edge_type(eid)].edges[eid] = Edge(
                a, b, str(e["description"]), eid)

    group_number = 1
    for g in data.get("groups", []):
        group_number = max(group_number, int(g["id"]) + 1)
        nid = g.get("node")
        label = str(g.get("label", "")) or f"Група {g['id']}"
        if nid is None:          # ще старіше: група без метавершини
            nid = doc.add_node(float(g.get("x", 0.0)), float(g.get("y", 0.0)),
                               None, name=label)
        nid = int(nid)
        members = {int(m) for m in g.get("members", [])
                   if doc.has_node(int(m)) and int(m) not in doc.member_of
                   and int(m) != nid}
        if (not doc.has_node(nid) or nid in doc.group_of_node
                or len(members) < 2):
            continue
        he = Hyperedge(label, children=members)
        doc.graph.hyperadd(he)
        doc.view.groups[he.hyperedge_id] = GroupLook(
            nid, bool(g.get("collapsed", False)))
        doc.group_of_node[nid] = he.hyperedge_id
        for m in members:
            doc.member_of[m] = he.hyperedge_id

    doc.numbers = {"node": last + 1, "group": group_number}
    return doc
