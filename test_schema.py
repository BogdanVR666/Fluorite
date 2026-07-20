import json

import pytest

import storage
from edges import DEFAULT_EDGE_CLASS, Edge, EdgeStyle
from layers import LayeredGraph, make_families
from nodes import DEFAULT_NODE_CLASS, Node


def test_styled_fallback_override_and_reset():
    fam = make_families()["node"]
    cls = fam.define("Хаб", shape="diamond", color="#f39c12")
    node = Node(klass=cls, x=0, y=0)

    assert node.shape == "diamond" and node.color == "#f39c12"
    node.shape = "square"
    assert node.shape == "square" and cls.design.shape == "diamond"
    node.shape = None
    assert node.shape == "diamond"


def test_class_design_update_is_live():
    fam = make_families()["node"]
    cls = fam.define("Хаб", color="#f39c12")
    plain = Node(klass=cls, x=0, y=0)
    overridden = Node(klass=cls, x=0, y=0)
    overridden.color = "#000000"

    cls.apply_design({"color": "#ffffff"})
    assert plain.color == "#ffffff"
    assert overridden.color == "#000000"


def test_klass_is_shared_reference_not_copy():
    fam = make_families()["node"]
    cls = fam.define("Хаб")
    assert Node(klass=cls, x=0, y=0).klass is cls


def test_define_rejects_empty_and_duplicate_names():
    fam = make_families()["node"]
    assert fam.define("") is None
    assert fam.define("   ") is None
    assert fam.define("  Хаб  ") is not None      # ім'я обрізається
    assert fam.get("Хаб") is not None
    assert fam.define("Хаб") is None              # дубль
    assert fam.define(DEFAULT_NODE_CLASS) is None  # дефолт уже існує


def test_define_merges_partial_design_and_ignores_unknown():
    fam = make_families()["node"]
    cls = fam.define("Хаб", shape="diamond", невідоме_поле=42)
    # незадані поля — з дефолтів родини, невідомі — мовчки пропущені
    assert cls.design.shape == "diamond"
    assert cls.design.color == fam.default.design.color
    assert cls.design.opacity == 1.0
    assert not hasattr(cls.design, "невідоме_поле")


def test_directed_lives_on_class_not_style():
    fam = make_families()["edge"]
    cls = fam.define("читає", directed=True, line="dash")

    assert cls.directed is True
    assert "directed" not in EdgeStyle.model_fields   # це не поле стилю
    assert cls.design_map()["directed"] is True       # але у дизайні для UI

    edge = Edge(klass=cls)
    assert edge.directed is True
    cls.directed = False                              # напрям їде за класом
    assert edge.directed is False


def test_families_are_isolated_registries():
    a, b = make_families()["node"], make_families()["node"]
    a.define("Хаб")
    assert b.get("Хаб") is None
    assert a.default is not b.default    # навіть дефолти — різні об'єкти


def test_store_layers_follow_edge_classes():
    store = LayeredGraph()
    store.families["edge"].define("читає", directed=True)
    a = store.add_node(0, 0, DEFAULT_NODE_CLASS)
    b = store.add_node(1, 1, DEFAULT_NODE_CLASS)

    assert store.add_edge(a, b, "читає")
    assert store.layer("читає").is_directed()
    assert not store.add_edge(a, b, "читає")
    assert not store.add_edge(b, a, "читає")
    assert store.add_edge(a, b, DEFAULT_EDGE_CLASS)
    assert store.degree(a) == 2 and store.edge_count() == 2
    assert store.component_count() == 1
    assert store.update_class("edge", "читає", {"directed": False})
    assert not store.layer("читає").is_directed()
    assert store.find_edge("читає", b, a) is not None


def test_store_removals_clean_layers_and_index():
    store = LayeredGraph()
    hub = store.families["node"].define("Хаб")
    a = store.add_node(0, 0, "Хаб")
    b = store.add_node(1, 1, "нема такого")    # → дефолтний клас
    c = store.add_node(2, 2, DEFAULT_NODE_CLASS)
    store.add_edge(a, b, DEFAULT_EDGE_CLASS)
    store.add_edge(b, c, DEFAULT_EDGE_CLASS)

    assert store.node_ids["Хаб"] == {a}
    assert store.nodes[b].klass is store.families["node"].default
    store.set_node_class(b, hub)               # переїзд між класами
    assert store.node_ids["Хаб"] == {a, b}

    assert store.remove_node(b) == {a, c}      # сусіди по всіх шарах
    layer = store.layers[DEFAULT_EDGE_CLASS]
    assert layer.number_of_edges() == 0
    assert a not in layer and c not in layer   # осиротілі зникли з шару
    assert a in store.nodes and c in store.nodes   # але не з пулу
    assert store.node_ids["Хаб"] == {a}


def test_set_edge_class_moves_edge_between_layers():
    store = LayeredGraph()
    store.families["edge"].define("читає", directed=True)
    a = store.add_node(0, 0, DEFAULT_NODE_CLASS)
    b = store.add_node(1, 1, DEFAULT_NODE_CLASS)
    store.add_edge(b, a, "читає")              # напрям b → a
    edge = store.find_edge("читає", a, b)
    edge.width = 9.0                           # перекриття — скинеться

    assert store.set_edge_class("читає", a, b, DEFAULT_EDGE_CLASS)
    assert store.find_edge("читає", a, b) is None
    moved = store.find_edge(DEFAULT_EDGE_CLASS, a, b)
    assert moved is edge and edge.style.width is None
    store.add_edge(a, b, "читає")
    assert not store.set_edge_class("читає", a, b, DEFAULT_EDGE_CLASS)


def test_groups_metanode_membership_and_collapse():
    store = LayeredGraph()
    a = store.add_node(0, 0, DEFAULT_NODE_CLASS)
    b = store.add_node(10, 0, DEFAULT_NODE_CLASS)
    c = store.add_node(0, 10, DEFAULT_NODE_CLASS)
    assert store.add_group({a}) is None
    gid = store.add_group({a, b})
    g = store.groups[gid].node
    assert g in store.nodes and store.nodes[g].label == f"Група {gid}"
    assert store.member_of == {a: gid, b: gid}
    assert store.group_of_node == {g: gid}
    assert store.visual_owner(a) == a
    assert store.visual_owner(g) is None
    assert store.add_group({a, b}) == gid
    assert store.set_collapsed(gid, True)
    assert store.visual_owner(a) == g and store.visual_owner(c) == c
    assert store.visual_owner(g) == g
    node = store.nodes[g]
    assert (node.x, node.y) == (5.0, 0.0)
    assert not store.set_collapsed(gid, True)     # уже згорнута
    assert store.add_group({a, c}) is None
    assert store.remove_group(gid) == g
    assert store.member_of == {} and store.group_of_node == {}
    assert g in store.nodes and store.visual_owner(g) == g


def test_groups_nest_and_own_transitively():
    store = LayeredGraph()
    a = store.add_node(0, 0, DEFAULT_NODE_CLASS)
    b = store.add_node(2, 0, DEFAULT_NODE_CLASS)
    c = store.add_node(4, 0, DEFAULT_NODE_CLASS)
    g1 = store.add_group({a, b})
    n1 = store.groups[g1].node
    store.set_collapsed(g1, True)
    g2 = store.add_group({n1, c})
    n2 = store.groups[g2].node
    assert store.member_of[n1] == g2
    store.set_collapsed(g2, True)
    assert store.visual_owner(a) == n2
    assert store.visual_owner(n1) == n2
    assert store.visual_owner(n2) == n2
    store.set_collapsed(g2, False)
    assert store.visual_owner(a) == n1
    assert store.visual_owner(n1) == n1
    assert store.visual_owner(n2) is None         # метавершина розгорнутої


def test_regroup_steals_and_orphans_metanode():
    store = LayeredGraph()
    a = store.add_node(0, 0, DEFAULT_NODE_CLASS)
    b = store.add_node(1, 1, DEFAULT_NODE_CLASS)
    c = store.add_node(2, 2, DEFAULT_NODE_CLASS)
    g1 = store.add_group({a, b})
    n1 = store.groups[g1].node

    g2 = store.add_group({a, b, c})               # та сама + ще одна
    assert g2 != g1 and g1 not in store.groups
    assert store.groups[g2].members == {a, b, c}
    assert store.take_orphans() == [n1] and store.take_orphans() == []


def test_groups_dissolve_with_node_removal():
    store = LayeredGraph()
    a = store.add_node(0, 0, DEFAULT_NODE_CLASS)
    b = store.add_node(1, 1, DEFAULT_NODE_CLASS)
    c = store.add_node(2, 2, DEFAULT_NODE_CLASS)
    gid = store.add_group({a, b, c})
    g = store.groups[gid].node

    store.remove_node(a)
    assert store.groups[gid].members == {b, c}    # група стиснулась
    store.remove_nodes({b})
    assert gid not in store.groups
    assert store.member_of == {}
    assert store.take_orphans() == [g]
    d = store.add_node(3, 3, DEFAULT_NODE_CLASS)
    gid2 = store.add_group({c, d})
    g2 = store.groups[gid2].node
    store.remove_node(g2)
    assert gid2 not in store.groups and g2 not in store.nodes
    assert c in store.nodes and store.member_of == {}


def test_adopt_keeps_container_identity():
    store = LayeredGraph()
    nodes, layers = store.nodes, store.layers
    store.add_node(0, 0, DEFAULT_NODE_CLASS)

    other = LayeredGraph()
    other.families["node"].define("Хаб")
    other.add_node(5, 5, "Хаб")

    store.adopt(other)
    assert store.nodes is nodes and store.layers is layers
    assert set(nodes) == {1}
    assert store.node_ids["Хаб"] == {1}
    assert store.next_id == 2


def test_roundtrip_preserves_overrides_orientation_and_classes():
    store = LayeredGraph()
    hub = store.families["node"].define("Хаб", shape="diamond",
                                        color="#f39c12")
    store.families["edge"].define("читає", directed=True, line="dash")

    a = store.add_node(1.5, -2.0, "Хаб")
    b = store.add_node(0, 0, DEFAULT_NODE_CLASS)
    nb = store.nodes[b]
    nb.description = "опис"
    nb.color = "#000000"                       # перекриття стилю вершини
    assert store.add_edge(b, a, "читає")       # напрям b → a
    store.find_edge("читає", a, b).width = 5.0  # перекриття стилю ребра
    assert store.add_edge(a, b, DEFAULT_EDGE_CLASS)   # паралельне, інший клас

    text = storage.graph_to_json(store)
    s2 = storage.graph_from_json(text)

    assert s2.next_id == 3
    n2 = s2.nodes[b]
    assert n2.style.color == "#000000" and n2.style.shape is None
    assert n2.description == "опис"
    assert s2.orientation("читає", a, b) == (b, a)    # напрям зберігся
    le = s2.find_edge("читає", a, b)
    assert le.width == 5.0 and le.directed is True
    assert s2.find_edge(DEFAULT_EDGE_CLASS, a, b) is not None  # обидва класи
    hub2 = s2.families["node"].get("Хаб")
    assert hub2 is not hub and hub2.design == hub.design
    raw = json.loads(text)
    cls_entry = next(c for c in raw["classes"]["edge"] if c["name"] == "читає")
    assert cls_entry["design"]["directed"] is True
    assert all("directed" not in e["style"] for e in raw["edges"])


def test_groups_roundtrip_and_older_files():
    store = LayeredGraph()
    a = store.add_node(0, 0, DEFAULT_NODE_CLASS)
    b = store.add_node(10, 0, DEFAULT_NODE_CLASS)
    c = store.add_node(0, 10, DEFAULT_NODE_CLASS)
    gid = store.add_group({a, b})
    g = store.groups[gid].node
    store.nodes[g].label = "Ядро"                 # перейменована група
    store.set_collapsed(gid, True)
    store.nodes[g].x = 7.0                        # метавершину посунули
    assert store.add_edge(c, g, DEFAULT_EDGE_CLASS)   # ребро ДО групи

    s2 = storage.graph_from_json(storage.graph_to_json(store))
    g2 = s2.groups[gid]
    assert g2.node == g and g2.members == {a, b} and g2.collapsed
    assert s2.nodes[g].label == "Ядро" and s2.nodes[g].x == 7.0
    assert s2.find_edge(DEFAULT_EDGE_CLASS, c, g) is not None
    assert s2.member_of == {a: gid, b: gid}
    assert s2.group_of_node == {g: gid}
    assert s2.next_group_id == gid + 1
    raw = json.loads(storage.graph_to_json(store))
    raw["version"] = 5
    raw["nodes"] = [n for n in raw["nodes"] if n["id"] != g]
    raw["edges"] = [e for e in raw["edges"] if g not in (e["a"], e["b"])]
    raw["groups"] = [{"id": gid, "label": "Ядро", "collapsed": True,
                      "x": 7.0, "y": 0.0, "members": [a, b]}]
    s3 = storage.graph_from_json(json.dumps(raw))
    made = s3.groups[gid].node
    assert s3.nodes[made].label == "Ядро"
    assert (s3.nodes[made].x, s3.nodes[made].y) == (7.0, 0.0)
    assert s3.groups[gid].collapsed and s3.member_of == {a: gid, b: gid}
    raw = json.loads(storage.graph_to_json(store))
    del raw["groups"]
    raw["version"] = 4
    s4 = storage.graph_from_json(json.dumps(raw))
    assert s4.groups == {} and s4.member_of == {}
    raw = json.loads(storage.graph_to_json(store))
    entry = next(e for e in raw["groups"] if e["id"] == gid)
    entry["members"] = [a, b, 999]
    s5 = storage.graph_from_json(json.dumps(raw))
    assert s5.groups[gid].members == {a, b}
    entry["members"] = [a, 999]
    s6 = storage.graph_from_json(json.dumps(raw))
    assert s6.groups == {} and g in s6.nodes


def test_load_v3_skips_broken_edges_and_orients_by_source():
    data = {
        "version": 3,
        "classes": {"edge": [
            {"name": "читає",
             "design": {"directed": True}}
        ]},
        "nodes": [
            {"id": 1, "x": 0, "y": 0, "label": "A", "class": "нема"},
            {"id": 2, "x": 1, "y": 1, "label": "B"},
        ],
        "edges": [
            {"a": 1, "b": 3},                  # кінця 3 не існує
            {"a": 2, "b": 2},                  # петля
            {"a": 1, "b": 2, "source": 2, "class": "читає"},
        ],
    }
    store = storage.graph_from_json(json.dumps(data))
    assert store.nodes[1].klass is store.families["node"].default
    assert [(u, v) for _, u, v, _ in store.edges()] == [(2, 1)]


def test_load_rejects_garbage_and_newer_versions():
    with pytest.raises(ValueError):
        storage.graph_from_json("{бите")                    # не JSON
    with pytest.raises(ValueError):
        storage.graph_from_json(json.dumps([1, 2]))         # не файл графа
    with pytest.raises(ValueError):
        storage.graph_from_json(
            json.dumps({"version": 99, "nodes": []}))       # новіша версія


def test_v1_file_upgrades():
    v1 = {
        "classes": [{"name": "Хаб", "shape": "diamond", "color": "#f39c12"}],
        "nodes": [
            {"id": 1, "x": 0, "y": 0, "label": "A",
             "shape": None, "color": "#123456", "class": "Хаб"},
            {"id": 2, "x": 1, "y": 1, "label": "B"},
        ],
        "edges": [[1, 2]],
    }
    store = storage.graph_from_json(json.dumps(v1))

    assert store.next_id == 3
    hub = store.families["node"].get("Хаб")
    assert hub.design.shape == "diamond" and hub.design.opacity == 1.0
    node = store.nodes[1]
    assert node.style.color == "#123456"     # переїхало в перекриття
    assert node.shape == "diamond"           # фолбек на клас
    edge = store.find_edge(DEFAULT_EDGE_CLASS, 1, 2)
    assert edge is not None and edge.klass is store.families["edge"].default
