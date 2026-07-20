import networkx as nx
from pydantic import BaseModel, Field

from edges import DEFAULT_EDGE_CLASS, Edge, EdgeClass, EdgeStyle
from elements import Family
from nodes import DEFAULT_NODE_CLASS, Node, NodeClass, NodeStyle


class NodeGroup(BaseModel):
    node: int
    members: set[int] = Field(default_factory=set)
    collapsed: bool = False


def make_families() -> dict[str, Family]:
    return {"node": Family(NodeClass, NodeStyle, DEFAULT_NODE_CLASS),
            "edge": Family(EdgeClass, EdgeStyle, DEFAULT_EDGE_CLASS)}


class LayeredGraph:
    def __init__(self):
        self.families = make_families()
        self.nodes: dict[int, Node] = {}
        self.layers: dict[str, nx.Graph] = {}     # клас ребер → його шар
        self.next_id = 1
        self.node_ids: dict[str, set[int]] = {}   # клас вершин → id вершин
        self.groups: dict[int, NodeGroup] = {}    # gid → група вершин
        self.member_of: dict[int, int] = {}       # nid члена → gid групи
        self.group_of_node: dict[int, int] = {}   # nid метавершини → gid
        self.next_group_id = 1
        self.orphans: list[int] = []   # метавершини розпущених груп


    def node_class(self, name: str | None) -> NodeClass:
        fam = self.families["node"]
        return fam.get(name) or fam.default

    def edge_class(self, name: str | None) -> EdgeClass:
        fam = self.families["edge"]
        return fam.get(name) or fam.default

    def class_ids(self, class_name: str) -> list[int]:
        return list(self.node_ids.get(class_name, ()))

    def create_class(self, family: str, name: str, design: dict) -> bool:
        fam = self.families.get(family)
        return fam is not None and fam.define(name, **design) is not None

    def update_class(self, family: str, name: str, design: dict) -> bool:
        fam = self.families.get(family)
        cls = fam.get(name) if fam is not None else None
        if cls is None:
            return False
        cls.apply_design(design)
        if family == "edge":
            self._sync_layer_type(name, cls.directed)
        return True

    def _sync_layer_type(self, name: str, directed: bool):
        old = self.layers.get(name)
        if old is None or old.is_directed() == directed:
            return
        new = nx.DiGraph() if directed else nx.Graph()
        for u, v, data in old.edges(data=True):
            if not (new.has_edge(u, v) or new.has_edge(v, u)):
                new.add_edge(u, v, **data)
        self.layers[name] = new

    def node(self, nid: int) -> Node:
        return self.nodes[nid]

    def add_node(self, x: float, y: float, class_name: str) -> int:
        nid = self.next_id
        obj = Node(klass=self.node_class(class_name), x=x, y=y,
                   label=str(nid))
        self.insert_node(nid, obj)
        return nid

    def insert_node(self, nid: int, obj: Node):
        self.nodes[nid] = obj
        self._track_node(nid, obj)
        if nid >= self.next_id:
            self.next_id = nid + 1

    def remove_node(self, nid: int) -> set[int]:
        gid = self.group_of_node.get(nid)
        if gid is not None:
            self.remove_group(gid)
        neighbors = self.neighbors(nid)
        for g in self.layers.values():
            if nid in g:
                nbrs = self._layer_neighbors(g, nid)
                g.remove_node(nid)               # разом з інцидентними
                self._drop_isolated(g, nbrs)     # сусіди могли осиротіти
        self._untrack_node(nid, self.nodes.pop(nid))
        self._forget_member(nid)
        return neighbors

    def remove_nodes(self, ids: set[int]) -> set[int]:
        neighbors = set()
        for nid in ids:
            if nid in self.nodes:
                neighbors |= self.remove_node(nid)
        return neighbors - ids

    def set_node_class(self, nid: int, cls: NodeClass):
        node = self.nodes[nid]
        self._untrack_node(nid, node)
        node.klass = cls
        node.style = NodeStyle()   # без перекриттів — дизайн класу
        self._track_node(nid, node)

    def _track_node(self, nid: int, obj: Node):
        self.node_ids.setdefault(obj.klass.name, set()).add(nid)

    def _untrack_node(self, nid: int, obj: Node):
        ids = self.node_ids.get(obj.klass.name)
        if ids is not None:
            ids.discard(nid)

    @staticmethod
    def _layer_neighbors(g: nx.Graph, nid: int) -> set[int]:
        if g.is_directed():
            return set(g.successors(nid)) | set(g.predecessors(nid))
        return set(g.neighbors(nid))

    @staticmethod
    def _drop_isolated(g: nx.Graph, ids):
        """Прибирає з шару вершини, що лишились там без ребер."""
        for nid in ids:
            if nid in g and g.degree(nid) == 0:
                g.remove_node(nid)

    def neighbors(self, nid: int) -> set[int]:
        out: set[int] = set()
        for g in self.layers.values():
            if nid in g:
                out |= self._layer_neighbors(g, nid)
        return out

    def degree(self, nid: int) -> int:
        return sum(g.degree(nid) for g in self.layers.values() if nid in g)

    def edge_count(self) -> int:
        return sum(g.number_of_edges() for g in self.layers.values())

    def component_count(self) -> int:
        if not self.nodes:
            return 0
        union = nx.Graph()
        union.add_nodes_from(self.nodes)
        for g in self.layers.values():
            union.add_edges_from(g.edges())
        return nx.number_connected_components(union)

    def layer(self, class_name: str) -> nx.Graph:
        """Шар класу ребер; створюється ліниво за налаштуванням класу."""
        g = self.layers.get(class_name)
        if g is None:
            cls = self.edge_class(class_name)
            g = nx.DiGraph() if cls.directed else nx.Graph()
            self.layers[cls.name] = g
        return g

    def orientation(self, class_name: str, a: int, b: int):
        """(u, v), як ребро лежить у шарі (u — джерело), або None."""
        g = self.layers.get(class_name)
        if g is None:
            return None
        if g.has_edge(a, b):
            return (a, b)
        if g.is_directed() and g.has_edge(b, a):
            return (b, a)
        return None

    def find_edge(self, class_name: str, a: int, b: int) -> Edge | None:
        uv = self.orientation(class_name, a, b)
        if uv is None:
            return None
        return self.layers[class_name].edges[uv]["obj"]

    def add_edge(self, a: int, b: int, class_name: str) -> bool:
        cls = self.edge_class(class_name)
        return self.insert_edge(cls.name, a, b, Edge(klass=cls))

    def insert_edge(self, class_name: str, a: int, b: int,
                    obj: Edge) -> bool:
        if a == b or a not in self.nodes or b not in self.nodes:
            return False
        g = self.layer(class_name)
        if g.has_edge(a, b) or (g.is_directed() and g.has_edge(b, a)):
            return False               # одне ребро класу на пару вершин
        g.add_edge(a, b, obj=obj)      # орієнтація = (a, b)
        return True

    def bulk_add_edges(self, pairs, edge_cls: EdgeClass) -> int:
        added = 0
        for a, b in pairs:             # пари йдуть "джерело, ціль"
            if self.insert_edge(edge_cls.name, a, b, Edge(klass=edge_cls)):
                added += 1
        return added

    def remove_edge(self, class_name: str, a: int, b: int) -> bool:
        uv = self.orientation(class_name, a, b)
        if uv is None:
            return False
        g = self.layers[class_name]
        g.remove_edge(*uv)
        self._drop_isolated(g, uv)
        return True

    def reverse_edge(self, class_name: str, a: int, b: int) -> bool:
        uv = self.orientation(class_name, a, b)
        g = self.layers.get(class_name)
        if uv is None or not g.is_directed():
            return False
        obj = g.edges[uv]["obj"]
        g.remove_edge(*uv)
        g.add_edge(uv[1], uv[0], obj=obj)
        return True

    def set_edge_class(self, class_name: str, a: int, b: int,
                       new_name: str) -> bool:
        new_cls = self.families["edge"].get(new_name)
        uv = self.orientation(class_name, a, b)
        if new_cls is None or uv is None:
            return False
        src = self.layers[class_name]
        dst = self.layer(new_cls.name)
        if dst is not src and (dst.has_edge(*uv) or dst.has_edge(uv[1],
                                                                 uv[0])):
            return False
        obj = src.edges[uv]["obj"]
        src.remove_edge(*uv)
        self._drop_isolated(src, uv)
        obj.klass = new_cls
        obj.style = EdgeStyle()        # без перекриттів — дизайн класу
        dst.add_edge(*uv, obj=obj)     # орієнтація зберігається
        return True

    def edges(self):
        for name, g in self.layers.items():
            for u, v, data in g.edges(data=True):
                yield name, u, v, data["obj"]

    def add_group(self, members: set[int]) -> int | None:
        picked = {nid for nid in members
                  if nid in self.nodes and self.visual_owner(nid) == nid}
        if len(picked) < 2:
            return None
        gid = self.member_of.get(next(iter(picked)))
        if gid is not None and self.groups[gid].members == picked:
            return gid
        for nid in picked:
            self._forget_member(nid)
        gid = self.next_group_id
        self.next_group_id += 1
        nid = self.next_id
        self.insert_node(nid, Node(
            klass=self.families["node"].default,
            x=sum(self.nodes[n].x for n in picked) / len(picked),
            y=sum(self.nodes[n].y for n in picked) / len(picked),
            label=f"Група {gid}"))
        self.groups[gid] = NodeGroup(node=nid, members=picked)
        self.group_of_node[nid] = gid
        for m in picked:
            self.member_of[m] = gid
        return gid

    def insert_group(self, gid: int, obj: NodeGroup) -> bool:
        obj.members = {nid for nid in obj.members
                       if nid in self.nodes and nid not in self.member_of
                       and nid != obj.node}
        if (obj.node not in self.nodes or obj.node in self.group_of_node
                or len(obj.members) < 2):
            return False
        self.groups[gid] = obj
        self.group_of_node[obj.node] = gid
        for nid in obj.members:
            self.member_of[nid] = gid
        if gid >= self.next_group_id:
            self.next_group_id = gid + 1
        return True

    def remove_group(self, gid: int) -> int | None:
        grp = self.groups.pop(gid, None)
        if grp is None:
            return None
        for nid in grp.members:
            self.member_of.pop(nid, None)
        self.group_of_node.pop(grp.node, None)
        return grp.node

    def set_collapsed(self, gid: int, collapsed: bool) -> bool:
        grp = self.groups.get(gid)
        if grp is None or grp.collapsed == collapsed:
            return False
        if collapsed:
            node = self.nodes[grp.node]
            node.x = (sum(self.nodes[n].x for n in grp.members)
                      / len(grp.members))
            node.y = (sum(self.nodes[n].y for n in grp.members)
                      / len(grp.members))
        grp.collapsed = collapsed
        return True

    def visual_owner(self, nid: int) -> int | None:
        top = None
        cur = nid
        while (gid := self.member_of.get(cur)) is not None:
            grp = self.groups[gid]
            cur = grp.node
            if grp.collapsed:
                top = cur
        if top is not None:
            return top
        own = self.group_of_node.get(nid)
        if own is not None and not self.groups[own].collapsed:
            return None
        return nid

    def take_orphans(self) -> list[int]:
        out, self.orphans = self.orphans, []
        return out

    def _forget_member(self, nid: int):
        gid = self.member_of.pop(nid, None)
        if gid is None:
            return
        grp = self.groups[gid]
        grp.members.discard(nid)
        if len(grp.members) < 2:
            self.orphans.append(self.remove_group(gid))

    def clear(self):
        self.nodes.clear()
        self.layers.clear()
        self.node_ids.clear()
        self.next_id = 1
        self.groups.clear()
        self.member_of.clear()
        self.group_of_node.clear()
        self.next_group_id = 1
        self.orphans.clear()

    def adopt(self, other: "LayeredGraph"):
        self.families = other.families
        self.nodes.clear()
        self.nodes.update(other.nodes)
        self.layers.clear()
        self.layers.update(other.layers)
        self.node_ids = other.node_ids
        self.next_id = other.next_id
        self.groups.clear()
        self.groups.update(other.groups)
        self.member_of = other.member_of
        self.group_of_node = other.group_of_node
        self.next_group_id = other.next_group_id
        self.orphans = other.orphans
