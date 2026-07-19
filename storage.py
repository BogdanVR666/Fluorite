"""Серіалізація сховища (LayeredGraph) у JSON і назад.

Це "інша структура", що займається файлами: саме сховище (layers.py)
про них не знає нічого.

Формат файла (version 6):
{
  "version": 6,
  "classes": {                        // класи кожної родини елементів
    "node": [{"name", "design": {"shape", "color", "opacity"}}, ...],
    "edge": [{"name", "design": {"color", "width", "line", "directed"}}, ...]
  },
  "nodes": [{"id", "x", "y", "label", "description", "class",
             "style": {"shape": null | "...", ...}}, ...],
  "edges": [{"a", "b", "label", "description", "class", "style": {...}}, ...],
  "groups": [{"id", "node", "collapsed", "members": [id, ...]}, ...]
}

"style" — перекриття стилю конкретного елемента; null означає
"використовується дизайн класу". Набір полів дизайну і перекриттів
не прописаний тут жорстко — він береться зі схем родини, тож нові
поля підхоплюються автоматично. "directed" — поле класу ребер
(extra_design), у файлі воно лежить у "design" класу.

Напрям ребра напрямленого класу кодує сам порядок кінців: a — джерело,
b — ціль. Окремого поля "source" version 4 не має; ребра різних класів
на одній парі вершин — звичайна річ.

"groups" — групи вершин: "node" — id метавершини групи (вона лежить
серед "nodes" як звичайна вершина: підпис, стиль і ребра — її),
members — id вершин-членів (можуть бути метавершинами інших груп),
collapsed — чи група згорнута. У version 5 метавершини ще не було —
група мала власні label/x/y; при читанні їй довиділяється вершина.
Файли без "groups" (version 4 і старіші) читаються як граф без груп.

Зберігаються всі класи сховища, навіть порожні, — щоб визначені
користувачем класи не губилися між сеансами. Старіші файли читаються:
version 1 підіймається до version 2; у version 2 напрям беруть з
порядку кінців; version 3 мав поле "source" — за ним ребро
орієнтується при завантаженні.
"""

import json

from edges import Edge
from elements import BaseElement
from layers import LayeredGraph, NodeGroup
from nodes import Node

FORMAT_VERSION = 6


def _element_to_json(obj: BaseElement) -> dict:
    """Спільна для всіх родин частина запису елемента."""
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
    """Підіймає файл version 1 до формату version 2."""
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
    """Реєструє класи з файла; наявним (дефолтним) оновлює дизайн — файл
    є джерелом істини, тож граф виглядатиме так само, як при збереженні."""
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
    """Перекриття стилю елемента з запису файла (лише відомі поля)."""
    return {f: v for f, v in (entry.get("style") or {}).items()
            if f in style_type.model_fields}


def graph_from_json(text: str) -> LayeredGraph:
    """Будує нове сховище з JSON.

    Кидає ValueError, якщо формат не розпізнано. Сховище свіже —
    жодного глобального стану, класи інших документів не перетікають.
    """
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
        # у version 3 напрям задавало поле "source"; відтоді — порядок кінців
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
            # version 5: група ще не мала метавершини — довиділяємо
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
