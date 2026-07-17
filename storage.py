"""Серіалізація графа у JSON і назад.

Формат файла (version 2):
{
  "version": 2,
  "classes": {                        // класи кожної родини елементів
    "node": [{"name", "design": {"shape", "color", "opacity"}}, ...],
    "edge": [{"name", "design": {"color", "width", "line"}}, ...]
  },
  "nodes": [{"id", "x", "y", "label", "description", "class",
             "style": {"shape": null | "...", ...}}, ...],
  "edges": [{"a", "b", "label", "description", "class", "style": {...}}, ...]
}

"style" — перекриття стилю конкретного елемента; null означає
"використовується дизайн класу". Набір полів дизайну і перекриттів
не прописаний тут жорстко — він береться зі style_fields родини,
тож нові поля стилю підхоплюються автоматично.

Зберігаються всі зареєстровані класи, навіть порожні, — щоб визначені
користувачем класи не губилися між сеансами. Файли version 1
(лише класи вершин, ребра без атрибутів) читаються й підіймаються
до формату version 2.
"""

import json

import networkx as nx

from edges import BaseEdge, DefaultEdge
from elements import BaseElement, ElementMeta
from nodes import BaseNode, DefaultNode

FORMAT_VERSION = 2


def _element_to_json(obj: BaseElement) -> dict:
    """Спільна для всіх родин частина запису елемента."""
    return {"label": obj.label, "description": obj.description,
            "class": type(obj).type_name, "style": obj.style_overrides()}


def graph_to_json(g: nx.Graph) -> str:
    nodes = []
    for nid, data in g.nodes(data=True):
        obj: BaseNode = data["obj"]
        nodes.append({"id": nid, "x": obj.x, "y": obj.y,
                      **_element_to_json(obj)})
    return json.dumps({
        "version": FORMAT_VERSION,
        "classes": {family: [{"name": cls.type_name, "design": cls.design()}
                             for cls in root.registry.values()]
                    for family, root in ElementMeta.families.items()},
        "nodes": nodes,
        "edges": [{"a": a, "b": b, **_element_to_json(data["obj"])}
                  for a, b, data in g.edges(data=True)],
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


def _restore_classes(families_json: dict):
    """Реєструє класи з файла; наявним оновлює дизайн — файл є джерелом
    істини, тож граф виглядатиме так само, як при збереженні."""
    for family, entries in families_json.items():
        root = ElementMeta.families.get(family)
        if root is None:
            continue
        for entry in entries:
            design = {f: v for f, v in entry.get("design", {}).items()
                      if f in root.style_fields}
            cls = root.registry.get(entry["name"])
            if cls is None:
                root.define(entry["name"], **design)
            else:
                for field, value in design.items():
                    setattr(cls, "default_" + field, value)


def _style_of(entry: dict, cls: type) -> dict:
    """Перекриття стилю елемента з запису файла (лише відомі поля)."""
    return {f: v for f, v in (entry.get("style") or {}).items()
            if f in cls.style_fields}


def graph_from_json(text: str, g: nx.Graph) -> int:
    """Заповнює порожній g даними з JSON; повертає next_id.

    Кидає ValueError, якщо формат не розпізнано.
    """
    data = json.loads(text)
    if not isinstance(data, dict) or "nodes" not in data:
        raise ValueError("це не файл графа")
    if data.get("version", 1) > FORMAT_VERSION:
        raise ValueError("файл створено новішою версією програми")
    if data.get("version", 1) < 2:
        data = _upgrade_v1(data)

    _restore_classes(data.get("classes", {}))

    for n in data["nodes"]:
        cls = BaseNode.registry.get(n.get("class"), DefaultNode)
        g.add_node(int(n["id"]),
                   obj=cls(float(n["x"]), float(n["y"]), str(n["label"]),
                           str(n.get("description", "")),
                           **_style_of(n, cls)))

    for e in data.get("edges", []):
        a, b = e["a"], e["b"]
        if a in g and b in g and a != b:
            cls = BaseEdge.registry.get(e.get("class"), DefaultEdge)
            g.add_edge(a, b, obj=cls(str(e.get("label", "")),
                                     str(e.get("description", "")),
                                     **_style_of(e, cls)))

    return max(g.nodes, default=0) + 1
