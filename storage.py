import json

from edges import Edge
from elements import BaseElement
from layers import LayeredGraph, NodeGroup
from nodes import Node

FORMAT_VERSION = 6


def _element_to_json(obj: BaseElement) -> dict:
    return {"label": obj.label, "description": obj.description,
            "class": obj.klass.name, "style": obj.style.model_dump()}


def graph_to_json(store: LayeredGraph) -> str:
    nodes = []
    for nid, obj in store.nodes.items():
        nodes.append({"id": nid, "x": obj.x, "y": obj.y,
                      **_element_to_json(obj)})
    return json.dumps({
        "version": FORMAT_VERSION,
        "classes": {family: [{"name": cls.name, "design": cls.design_map()}
                             for cls in fam.classes.values()]
                    for family, fam in store.families.items()},
        "nodes": nodes,
        "edges": [{"a": a, "b": b, **_element_to_json(obj)}
                  for _, a, b, obj in store.edges()],
        "groups": [{"id": gid, "node": g.node, "collapsed": g.collapsed,
                    "members": sorted(g.members)}
                   for gid, g in store.groups.items()],
    }, ensure_ascii=False, indent=2)


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


def _restore_classes(families_json: dict, store: LayeredGraph):
    for family, entries in families_json.items():
        fam = store.families.get(family)
        if fam is None:
            continue
        for entry in entries:
            design = entry.get("design", {})
            cls = fam.get(entry["name"])
            if cls is None:
                fam.define(entry["name"], **design)
            else:
                cls.apply_design(design)


def _style_of(entry: dict, style_type: type) -> dict:
    return {f: v for f, v in (entry.get("style") or {}).items()
            if f in style_type.model_fields}


def graph_from_json(text: str) -> LayeredGraph:
    data = json.loads(text)
    if not isinstance(data, dict) or "nodes" not in data:
        raise ValueError("це не файл графа")
    version = data.get("version", 1)
    if version > FORMAT_VERSION:
        raise ValueError("файл створено новішою версією програми")
    if version < 2:
        data = _upgrade_v1(data)

    store = LayeredGraph()
    _restore_classes(data.get("classes", {}), store)
    node_fam, edge_fam = store.families["node"], store.families["edge"]

    for n in data["nodes"]:
        cls = node_fam.get(n.get("class")) or node_fam.default
        store.insert_node(
            int(n["id"]),
            Node(klass=cls, x=float(n["x"]), y=float(n["y"]),
                 label=str(n["label"]),
                 description=str(n.get("description", "")),
                 style=node_fam.style_type(**_style_of(n, node_fam.style_type))))

    style_type = edge_fam.style_type
    for e in data.get("edges", []):
        a, b = e["a"], e["b"]
        if version == 3 and e.get("source") == b:
            a, b = b, a
        cls = edge_fam.get(e.get("class")) or edge_fam.default
        store.insert_edge(
            cls.name, a, b,
            Edge(klass=cls, label=str(e.get("label", "")),
                 description=str(e.get("description", "")),
                 style=style_type(**_style_of(e, style_type))))

    for g in data.get("groups", []):
        nid = g.get("node")
        if nid is None:
            nid = store.next_id
            store.insert_node(nid, Node(
                klass=node_fam.default,
                x=float(g.get("x", 0.0)), y=float(g.get("y", 0.0)),
                label=str(g.get("label", "")) or f"Група {g['id']}"))
        store.insert_group(int(g["id"]), NodeGroup(
            node=int(nid),
            collapsed=bool(g.get("collapsed", False)),
            members={int(m) for m in g.get("members", [])}))

    return store
