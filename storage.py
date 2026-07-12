"""Серіалізація графа у JSON і назад.

Формат файла (version 1):
{
  "version": 1,
  "classes": [{"name", "shape", "color"}, ...],   // усі класи вершин
  "nodes":   [{"id", "x", "y", "label", "class",
               "shape": null | "...",              // перекриття стилю
               "color": null | "..."}, ...],       // (null — дизайн класу)
  "edges":   [[a, b], ...]
}

Зберігаються всі зареєстровані класи, навіть порожні, — щоб визначені
користувачем класи не губилися між сеансами.
"""

import json

import networkx as nx

from nodes import BaseNode, DefaultNode, NodeMeta, make_node_class

FORMAT_VERSION = 1


def graph_to_json(g: nx.Graph) -> str:
    nodes = []
    for nid in g.nodes:
        obj: BaseNode = g.nodes[nid]["obj"]
        nodes.append({
            "id": nid, "x": obj.x, "y": obj.y, "label": obj.label,
            "class": type(obj).type_name,
            "shape": obj._shape, "color": obj._color,
        })
    return json.dumps({
        "version": FORMAT_VERSION,
        "classes": [{"name": cls.type_name,
                     "shape": cls.default_shape,
                     "color": cls.default_color}
                    for cls in NodeMeta.registry.values()],
        "nodes": nodes,
        "edges": [[a, b] for a, b in g.edges()],
    }, ensure_ascii=False, indent=2)


def graph_from_json(text: str, g: nx.Graph) -> int:
    """Заповнює порожній g даними з JSON; повертає next_id.

    Класи з файла реєструються, якщо їх ще немає; наявним оновлюється
    дизайн — файл є джерелом істини, тож граф виглядатиме як при
    збереженні. Кидає ValueError, якщо формат не розпізнано.
    """
    data = json.loads(text)
    if not isinstance(data, dict) or "nodes" not in data:
        raise ValueError("це не файл графа")
    if data.get("version", 1) > FORMAT_VERSION:
        raise ValueError("файл створено новішою версією програми")

    for c in data.get("classes", []):
        cls = NodeMeta.registry.get(c["name"])
        if cls is None:
            make_node_class(c["name"], c["shape"], c["color"])
        else:
            cls.default_shape = c["shape"]
            cls.default_color = c["color"]

    for n in data["nodes"]:
        cls = NodeMeta.registry.get(n.get("class"), DefaultNode)
        g.add_node(int(n["id"]),
                   obj=cls(float(n["x"]), float(n["y"]), str(n["label"]),
                           shape=n.get("shape"), color=n.get("color")))

    for a, b in data.get("edges", []):
        if a in g and b in g and a != b:
            g.add_edge(a, b)

    return max(g.nodes, default=0) + 1
