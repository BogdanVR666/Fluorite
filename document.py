from dataclasses import asdict, replace
from itertools import count

import FluoriteGraph as fg
from FluoriteGraph import EdgeType, FluoriteGraph, Hyperedge, NodeType
from view import (CONTAINS_EDGE_TYPE, DEFAULT_EDGE_TYPE, DEFAULT_NODE_TYPE,
                  EDGE_DESIGN, GROUP_NODE_TYPE, NODE_DESIGN, EdgeLook,
                  EdgeStyle, GroupLook, NodeLook, NodeStyle, TypeLook, View,
                  effective, merged)

Node = NodeType.Node
Edge = EdgeType.Edge


def reserve_ids(last: int):
    fg._counter = count(max(next(fg._counter), last + 1))


class Document:
    def __init__(self):
        self.graph = FluoriteGraph()
        self.view = View()
        self.numbers = {"node": 1, "group": 1}
        self.create_class("node", DEFAULT_NODE_TYPE, {})
        self.create_class("edge", DEFAULT_EDGE_TYPE, {})
        self.create_class("node", GROUP_NODE_TYPE, {})
        self.create_class("edge", CONTAINS_EDGE_TYPE, {})
        self.view.defaults = {
            "node": self.view.node_types[DEFAULT_NODE_TYPE].uid,
            "edge": self.view.edge_types[DEFAULT_EDGE_TYPE].uid}
        self.reindex()

    def reindex(self):
        self.type_of: dict[int, str] = {}
        self.edge_type_of: dict[int, str] = {}
        self.incident: dict[int, set[int]] = {}
        self.parents: dict[int, set[int]] = {}
        for name, t in self.graph.nodes.items():
            for nid in t.nodes:
                self.type_of[nid] = name
        for name, t in self.graph.edges.items():
            for eid, e in t.edges.items():
                self.edge_type_of[eid] = name
                self.incident.setdefault(e.node_in, set()).add(eid)
                self.incident.setdefault(e.node_out, set()).add(eid)
        for gid, he in self.graph.hyperedges.items():
            for child in he.children:
                self.parents.setdefault(child, set()).add(gid)


    def types(self, family: str) -> dict[str, TypeLook]:
        return self.view.types(family)

    def resolve_type(self, family: str, name: str | None) -> str:
        return (name if name in self.types(family)
                else self.view.default_type(family))

    def class_ids(self, name: str) -> list[int]:
        t = self.graph.nodes.get(name)
        return list(t.nodes) if t is not None else []

    def class_count(self, family: str, name: str) -> int:
        t = (self.graph.nodes if family == "node" else self.graph.edges)[name]
        return len(t.nodes) if family == "node" else len(t.edges)

    def design_map(self, family: str, name: str) -> dict:
        out = asdict(self.types(family)[name].design)
        if family == "edge":
            out["directed"] = self.graph.edges[name].directed
        return out

    def create_class(self, family: str, name: str, design: dict) -> bool:
        name = name.strip()
        types = self.types(family)
        if not name or name in types:
            return False
        base = NODE_DESIGN if family == "node" else EDGE_DESIGN
        types[name] = TypeLook(merged(base, design))
        if family == "node":
            self.graph.nodes[name] = NodeType(name)
        else:
            self.graph.edges[name] = EdgeType(
                name, directed=bool(design.get("directed", False)))
        return True

    def update_class(self, family: str, name: str, design: dict) -> bool:
        types = self.types(family)
        look = types.get(name)
        if look is None:
            return False
        types[name] = replace(look, design=merged(look.design, design))
        if family == "edge" and "directed" in design:
            self.graph.edges[name].directed = bool(design["directed"])
        return True

    def rename_class(self, family: str, old: str, new: str) -> bool:
        new = new.strip()
        types = self.types(family)
        if old not in types or not new or new in types:
            return False
        _rekey(types, old, new, types[old])
        if family == "node":
            t = self.graph.nodes.pop(old)
            self.graph.nodes[new] = NodeType(new, t.nodes)
            for nid in t.nodes:
                self.type_of[nid] = new
        else:
            t = self.graph.edges.pop(old)
            self.graph.edges[new] = EdgeType(new, t.directed, t.edges)
            for eid in t.edges:
                self.edge_type_of[eid] = new
        return True

    def remove_class(self, family: str, name: str) -> set[int] | None:
        if (name not in self.types(family)
                or self.view.is_default(family, name)):
            return None
        if family == "node":
            touched = self.remove_nodes(set(self.graph.nodes[name].nodes))
            del self.graph.nodes[name]
        else:
            touched = set()
            for eid in list(self.graph.edges[name].edges):
                touched |= set(self.ends(eid))
                self._drop_edge(eid)
            del self.graph.edges[name]
        del self.types(family)[name]
        return touched

    def move_class(self, family: str, name: str, index: int) -> bool:
        types = self.types(family)
        if name not in types:
            return False
        names = [n for n in types if n != name]
        names.insert(max(0, min(index, len(names))), name)
        reordered = {n: types[n] for n in names}
        types.clear()
        types.update(reordered)
        return True

    def set_class_hidden(self, family: str, name: str, hidden: bool) -> bool:
        types = self.types(family)
        look = types.get(name)
        if look is None or look.hidden == hidden:
            return False
        types[name] = replace(look, hidden=hidden)
        return True


    def has_node(self, nid: int) -> bool:
        return nid in self.type_of

    def node(self, nid: int) -> Node:
        return self.graph.nodes[self.type_of[nid]].nodes[nid]

    def look(self, nid: int) -> NodeLook:
        return self.view.nodes[nid]

    def node_type(self, nid: int) -> str:
        return self.type_of[nid]

    def node_style(self, nid: int) -> NodeStyle:
        return effective(self.view.nodes[nid].style,
                         self.view.node_types[self.type_of[nid]].design)

    def add_node(self, x: float, y: float, type_name: str | None,
                 name: str | None = None) -> int:
        if name is None:
            name = str(self.numbers["node"])
            self.numbers["node"] += 1
        node = Node(name, "")
        self._insert_node(self.resolve_type("node", type_name), node,
                          NodeLook(x, y))
        return node.node_id

    def _insert_node(self, type_name: str, node: Node, look: NodeLook):
        self.graph.nodes[type_name].nodes[node.node_id] = node
        self.view.nodes[node.node_id] = look
        self.type_of[node.node_id] = type_name

    def _replace_node(self, nid: int, **fields):
        t = self.graph.nodes[self.type_of[nid]]
        t.nodes[nid] = replace(t.nodes[nid], **fields)

    def set_label(self, nid: int, text: str):
        self._replace_node(nid, name=text)

    def set_description(self, nid: int, text: str):
        self._replace_node(nid, description=text)

    def move_node(self, nid: int, x: float, y: float):
        self.view.nodes[nid] = replace(self.view.nodes[nid], x=x, y=y)

    def set_node_style(self, nid: int, **style):
        look = self.view.nodes[nid]
        self.view.nodes[nid] = replace(look, style=replace(look.style,
                                                           **style))

    def set_node_class(self, nid: int, type_name: str):
        old = self.type_of[nid]
        node = self.graph.nodes[old].nodes.pop(nid)
        self.graph.nodes[type_name].nodes[nid] = node
        self.type_of[nid] = type_name
        self.view.nodes[nid] = replace(self.view.nodes[nid],
                                       style=NodeStyle())

    def remove_node(self, nid: int) -> set[int]:
        neighbors = self.neighbors(nid)
        for eid in list(self.incident.get(nid, ())):
            self._drop_edge(eid)
        del self.graph.nodes[self.type_of.pop(nid)].nodes[nid]
        del self.view.nodes[nid]
        self.incident.pop(nid, None)
        self._forget_child(nid)
        return neighbors

    def remove_nodes(self, ids: set[int]) -> set[int]:
        neighbors = set()
        for nid in ids:
            if nid in self.type_of:
                neighbors |= self.remove_node(nid)
        return neighbors - ids

    def neighbors(self, nid: int) -> set[int]:
        out = set()
        for eid in self.incident.get(nid, ()):
            a, b = self.ends(eid)
            out.add(b if a == nid else a)
        return out

    def degree(self, nid: int) -> int:
        return len(self.incident.get(nid, ()))

    def component_count(self) -> int:
        parent = {nid: nid for nid in self.type_of}

        def root(n):
            while parent[n] != n:
                parent[n] = parent[parent[n]]
                n = parent[n]
            return n

        for t in self.graph.edges.values():
            for e in t.edges.values():
                parent.setdefault(e.node_in, e.node_in)
                parent.setdefault(e.node_out, e.node_out)
                parent[root(e.node_in)] = root(e.node_out)
        return sum(1 for nid in parent if root(nid) == nid)


    def has_edge(self, eid: int) -> bool:
        return eid in self.edge_type_of

    def edge(self, eid: int) -> Edge:
        return self.graph.edges[self.edge_type_of[eid]].edges[eid]

    def edge_type(self, eid: int) -> str:
        return self.edge_type_of[eid]

    def ends(self, eid: int) -> tuple[int, int]:
        e = self.edge(eid)
        return e.node_in, e.node_out

    def edge_directed(self, eid: int) -> bool:
        return self.graph.edges[self.edge_type_of[eid]].directed

    def edge_style(self, eid: int) -> EdgeStyle:
        return effective(self.view.edges[eid].style,
                         self.view.edge_types[self.edge_type_of[eid]].design)

    def edges(self):
        for t in self.graph.edges.values():
            for eid, e in t.edges.items():
                yield eid, e.node_in, e.node_out

    def shown_edges(self):
        for name, t in self.graph.edges.items():
            if self.view.edge_types[name].hidden:
                continue
            for eid, e in t.edges.items():
                yield eid, e.node_in, e.node_out

    def edge_count(self) -> int:
        return sum(len(t.edges) for t in self.graph.edges.values())

    def find_edge(self, type_name: str, a: int, b: int,
                  skip: int | None = None) -> int | None:
        for eid in self.incident.get(a, ()):
            if (eid != skip and self.edge_type_of[eid] == type_name
                    and b in self.ends(eid)):
                return eid
        return None

    def add_edge(self, a: int, b: int, type_name: str | None) -> int | None:
        name = self.resolve_type("edge", type_name)
        if (a == b or not self.has_element(a) or not self.has_element(b)
                or self.find_edge(name, a, b) is not None):
            return None
        edge = Edge(a, b, "")
        self._insert_edge(name, edge, EdgeLook())
        return edge.edge_id

    def bulk_add_edges(self, pairs, type_name: str | None) -> int:
        return sum(1 for a, b in pairs
                   if self.add_edge(a, b, type_name) is not None)

    def _insert_edge(self, type_name: str, edge: Edge, look: EdgeLook):
        eid = edge.edge_id
        self.graph.edges[type_name].edges[eid] = edge
        self.view.edges[eid] = look
        self.edge_type_of[eid] = type_name
        self.incident.setdefault(edge.node_in, set()).add(eid)
        self.incident.setdefault(edge.node_out, set()).add(eid)

    def _drop_edge(self, eid: int):
        e = self.graph.edges[self.edge_type_of.pop(eid)].edges.pop(eid)
        del self.view.edges[eid]
        for nid in (e.node_in, e.node_out):
            ids = self.incident.get(nid)
            if ids is not None:
                ids.discard(eid)

    def remove_edge(self, eid: int) -> bool:
        if eid not in self.edge_type_of:
            return False
        self._drop_edge(eid)
        return True

    def reverse_edge(self, eid: int) -> bool:
        if eid not in self.edge_type_of or not self.edge_directed(eid):
            return False
        t = self.graph.edges[self.edge_type_of[eid]]
        e = t.edges[eid]
        t.edges[eid] = replace(e, node_in=e.node_out, node_out=e.node_in)
        return True

    def set_edge_class(self, eid: int, new_name: str) -> bool:
        if eid not in self.edge_type_of or new_name not in self.graph.edges:
            return False
        a, b = self.ends(eid)
        if self.find_edge(new_name, a, b, skip=eid) is not None:
            return False
        edge = self.graph.edges[self.edge_type_of[eid]].edges.pop(eid)
        self.graph.edges[new_name].edges[eid] = edge
        self.edge_type_of[eid] = new_name
        self.view.edges[eid] = EdgeLook()
        return True

    def set_edge_style(self, eid: int, **style):
        look = self.view.edges[eid]
        self.view.edges[eid] = replace(look, style=replace(look.style,
                                                           **style))


    def has_group(self, gid: int) -> bool:
        return gid in self.view.groups

    def has_element(self, eid: int) -> bool:
        return eid in self.type_of or eid in self.view.groups

    def name_of(self, eid: int) -> str:
        if eid in self.view.groups:
            return self.graph.hyperedges[eid].name
        return self.node(eid).name

    def group_look(self, gid: int) -> GroupLook:
        return self.view.groups[gid]

    def group_members(self, gid: int) -> set[int]:
        return self.graph.hyperedges[gid].children

    def add_group(self, x: float, y: float, width: float,
                  height: float) -> int:
        label = f"Група {self.numbers['group']}"
        self.numbers["group"] += 1
        he = Hyperedge(label, "")
        self.graph.hyperadd(he)
        self.view.groups[he.hyperedge_id] = GroupLook(x, y, width, height)
        self.place()
        return he.hyperedge_id

    def remove_group(self, gid: int) -> set[int]:
        neighbors = self.neighbors(gid)
        for eid in list(self.incident.get(gid, ())):
            self._drop_edge(eid)
        self.incident.pop(gid, None)
        self._forget_child(gid)
        for child in self.graph.hyperedges.pop(gid).children:
            self.parents.get(child, set()).discard(gid)
        del self.view.groups[gid]
        self.place()
        return neighbors

    def rename_group(self, gid: int, name: str):
        self.graph.hyperedges[gid].name = name

    def move_group(self, gid: int, x: float, y: float):
        self.view.groups[gid] = replace(self.view.groups[gid], x=x, y=y)

    def resize_group(self, gid: int, width: float, height: float):
        self.view.groups[gid] = replace(self.view.groups[gid],
                                        width=width, height=height)

    def set_collapsed(self, gid: int, collapsed: bool) -> bool:
        look = self.view.groups.get(gid)
        if look is None or look.collapsed == collapsed:
            return False
        self.view.groups[gid] = replace(look, collapsed=collapsed)
        if not collapsed:
            self.place()
        return True

    def set_group_mode(self, gid: int, mode: str) -> bool:
        look = self.view.groups.get(gid)
        if look is None or look.mode == mode:
            return False
        self.view.groups[gid] = replace(look, mode=mode)
        if mode == "frame":
            self.place()
        return True

    def is_tree(self, gid: int) -> bool:
        look = self.view.groups[gid]
        return look.mode == "tree" and not look.collapsed

    def move_tree_node(self, gid: int, dx: float, dy: float):
        self.view.groups[gid] = replace(self.view.groups[gid], node=(dx, dy))

    def group_style(self) -> NodeStyle:
        look = self.view.node_types.get(GROUP_NODE_TYPE)
        return NODE_DESIGN if look is None else look.design

    def contains_style(self) -> tuple[EdgeStyle, bool]:
        look = self.view.edge_types.get(CONTAINS_EDGE_TYPE)
        if look is None:
            return EDGE_DESIGN, False
        return look.design, self.graph.edges[CONTAINS_EDGE_TYPE].directed

    def tree_links(self) -> list[tuple[int, int]]:
        look = self.view.edge_types.get(CONTAINS_EDGE_TYPE)
        if look is not None and look.hidden:
            return []
        return [(gid, child)
                for gid in self.view.groups
                if self.is_tree(gid) and self.shown(gid)
                for child in sorted(self.graph.hyperedges[gid].children)
                if self.shown(child)]

    def contents(self, gids) -> tuple[set[int], set[int]]:
        nodes, groups = set(), set()
        stack = list(gids)
        while stack:
            for child in self.graph.hyperedges[stack.pop()].children:
                if child not in self.view.groups:
                    nodes.add(child)
                elif child not in groups:
                    groups.add(child)
                    stack.append(child)
        return nodes, groups

    def _folders(self, eid: int) -> set[int | None]:
        parents = self.parents.get(eid)
        if not parents:
            return {None}
        out = set()
        for parent in parents:
            for folder in self._folders(parent):
                if folder is None and self.view.groups[parent].collapsed:
                    folder = parent
                out.add(folder)
        return out

    def visual_owners(self, eid: int) -> set[int]:
        if (eid in self.type_of
                and self.view.node_types[self.type_of[eid]].hidden):
            return set()
        kind = self.view.node_types.get(GROUP_NODE_TYPE)
        if (eid in self.view.groups and self.is_tree(eid)
                and kind is not None and kind.hidden):
            return set()
        return (self._folders(eid) - {None}) or {eid}

    def shown(self, eid: int) -> bool:
        return self.visual_owners(eid) == {eid}

    def _inside_open(self, u: int, v: int) -> bool:
        common = self.parents.get(u, set()) & self.parents.get(v, set())
        return any(not self.view.groups[gid].collapsed and self.shown(gid)
                   for gid in common)

    def visual_lines(self) -> list[tuple[int, int, int]]:
        owners = {eid: self.visual_owners(eid)
                  for eid in (*self.type_of, *self.view.groups)}
        lines = []
        for eid, u, v in self.shown_edges():
            ou, ov = owners[u], owners[v]
            if (ou != {u} or ov != {v}) and self._inside_open(u, v):
                continue
            seen = set()
            for a in sorted(ou):
                for b in sorted(ov):
                    pair = frozenset((a, b))
                    if a != b and pair not in seen:
                        seen.add(pair)
                        lines.append((eid, a, b))
        return lines

    def place(self, ids=None) -> set[int]:
        groups = self.view.groups
        frozen = {gid for gid, look in groups.items()
                  if look.collapsed or look.mode == "tree"
                  or not self.shown(gid)}
        live = [gid for gid in groups if gid not in frozen]
        if ids is None:
            ids = [*self.type_of, *groups]
        changed = set()
        for eid in ids:
            old = self.parents.get(eid, set())
            around = {gid for gid in old if gid in frozen}
            around |= {gid for gid in live if self._holds(gid, eid, frozen)}
            new = {gid for gid in around
                   if not any(self._holds(gid, other, frozen)
                              for other in around if other != gid)}
            if new == old:
                continue
            for gid in old - new:
                self.graph.hyperedges[gid].children.discard(eid)
            for gid in new - old:
                self.graph.hyperedges[gid].children.add(eid)
            self.parents[eid] = new
            changed |= old ^ new
        return changed

    def _holds(self, gid: int, eid: int, frozen: set[int]) -> bool:
        if gid in frozen:
            return eid in self.graph.hyperedges[gid].children
        g = self.view.groups[gid]
        if eid in self.view.nodes:
            n = self.view.nodes[eid]
            return (g.x <= n.x <= g.x + g.width
                    and g.y <= n.y <= g.y + g.height)
        inner = self.view.groups[eid]
        return (eid != gid
                and g.x <= inner.x and g.y <= inner.y
                and inner.x + inner.width <= g.x + g.width
                and inner.y + inner.height <= g.y + g.height
                and (inner.x, inner.y, inner.width, inner.height)
                != (g.x, g.y, g.width, g.height))

    def _forget_child(self, eid: int):
        for gid in self.parents.pop(eid, ()):
            self.graph.hyperedges[gid].children.discard(eid)


    def clear(self):
        for t in self.graph.nodes.values():
            t.nodes.clear()
        for t in self.graph.edges.values():
            t.edges.clear()
        self.graph.hyperedges.clear()
        self.view.nodes.clear()
        self.view.edges.clear()
        self.view.groups.clear()
        self.numbers = {"node": 1, "group": 1}
        self.reindex()

    def adopt(self, other: "Document"):
        self.graph = other.graph
        self.view = other.view
        self.numbers = other.numbers
        self.reindex()


def _rekey(d: dict, old, new, value):
    items = [(new if k == old else k, value if k == old else v)
             for k, v in d.items()]
    d.clear()
    d.update(items)
