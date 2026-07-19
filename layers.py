"""Сховище графа: класи елементів + пул вершин + шар на клас ребер.

LayeredGraph — багатошаровий (multiplex) граф, стан у пам'яті:
  * families — реєстри класів вершин і ребер (Family з elements.py);
  * nodes    — пул вершин, dict id → Node; вершини існують незалежно
               від шарів;
  * layers   — окремий граф на КОЖЕН клас ребер: nx.DiGraph, якщо клас
               напрямлений, інакше nx.Graph. Налаштування класу ребер
               визначає тип його шару; зміна directed конвертує шар.
               У напрямленому шарі орієнтація пари (u, v) — це напрям
               стрілки, окремого поля "джерело" ребро не має.

Інваріанти:
  * вершина присутня в шарі тоді й лише тоді, коли має там ребра —
    мутації самі прибирають ізольовані вершини з шарів;
  * на пару вершин у межах одного класу — щонайбільше одне ребро
    (у напрямленому шарі — в будь-який бік); ребра РІЗНИХ класів на
    одній парі вершин співіснують вільно;
  * node_ids (клас вершин → множина id) підтримується інкрементно;
    аналог для ребер не потрібен — кількість ребер класу і є
    number_of_edges() його шару.

Ідентичність ребра — (клас, a, b); порядок (a, b) у напрямленому шарі
не важливий для пошуку (find_edge/orientation дивляться в обидва боки),
але важливий для стрілки.

Групи вершин (NodeGroup) — теж стан сховища. Метавершина групи —
ПОВНОЦІННА вершина пулу (Node): має підпис, колір, власні ребра і може
сама бути членом іншої групи (вкладеність). Згорнута група показує
лише метавершину, розгорнута — лише членів (метавершина і її ребра
не видні). Згортання — стан ВІДОБРАЖЕННЯ: граф не мутується, лише
малюється інакше: visual_owner каже, хто кого представляє на полі.
Вершина належить щонайбільше одній групі; група з < 2 членами
розчиняється, а її метавершина стає в чергу orphans на прибирання.

Файли — не справа цієї структури: серіалізацією займається storage.py.
Qt тут теж немає — сховище живе й тестується без GUI.
"""

import networkx as nx
from pydantic import BaseModel, Field

from edges import DEFAULT_EDGE_CLASS, Edge, EdgeClass, EdgeStyle
from elements import Family
from nodes import DEFAULT_NODE_CLASS, Node, NodeClass, NodeStyle


class NodeGroup(BaseModel):
    """Група вершин: власна метавершина (node) + члени.

    Позицію, підпис і стиль групи тримає її метавершина — звичайна
    вершина пулу; тут лише зв'язок і стан згорнутості.
    """

    node: int                      # id метавершини групи в пулі
    members: set[int] = Field(default_factory=set)
    collapsed: bool = False


def make_families() -> dict[str, Family]:
    """Свіжі реєстри класів обох родин з дефолтними класами."""
    return {"node": Family(NodeClass, NodeStyle, DEFAULT_NODE_CLASS),
            "edge": Family(EdgeClass, EdgeStyle, DEFAULT_EDGE_CLASS)}


class LayeredGraph:
    """Класи, вершини і шари-графи одного відкритого графа."""

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

    # --- класи ---

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
        """Конвертує шар класу, якщо його напрямленість змінилась.

        Орієнтація наявних ребер при цьому довільна, але стабільна:
        береться поточний порядок кінців у шарі.
        """
        old = self.layers.get(name)
        if old is None or old.is_directed() == directed:
            return
        new = nx.DiGraph() if directed else nx.Graph()
        for u, v, data in old.edges(data=True):
            if not (new.has_edge(u, v) or new.has_edge(v, u)):
                new.add_edge(u, v, **data)
        self.layers[name] = new

    # --- вершини ---

    def node(self, nid: int) -> Node:
        return self.nodes[nid]

    def add_node(self, x: float, y: float, class_name: str) -> int:
        nid = self.next_id
        obj = Node(klass=self.node_class(class_name), x=x, y=y,
                   label=str(nid))
        self.insert_node(nid, obj)
        return nid

    def insert_node(self, nid: int, obj: Node):
        """Кладе готову вершину під заданим id (шлях завантажувача)."""
        self.nodes[nid] = obj
        self._track_node(nid, obj)
        if nid >= self.next_id:
            self.next_id = nid + 1

    def remove_node(self, nid: int) -> set[int]:
        """Прибирає вершину звідусіль; повертає її сусідів по всіх шарах.

        Метавершина групи тягне за собою розпуск своєї групи (члени
        вільні й лишаються в графі).
        """
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
        """Прибирає групу вершин; повертає їхніх сусідів поза групою.

        По одній, а не пачкою по шарах: видалення може розпускати групи
        й стискати інші, тож порядкові побічні ефекти простіші за
        батчинг (видаляється зазвичай виділення — десятки вершин).
        """
        neighbors = set()
        for nid in ids:
            if nid in self.nodes:
                neighbors |= self.remove_node(nid)
        return neighbors - ids

    def set_node_class(self, nid: int, cls: NodeClass):
        """Перевести вершину в клас cls, скинувши перекриття стилю."""
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

    # --- топологія поверх усіх шарів ---

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
        """Компоненти зв'язності об'єднання шарів (напрям — байдуже)."""
        if not self.nodes:
            return 0
        union = nx.Graph()
        union.add_nodes_from(self.nodes)
        for g in self.layers.values():
            union.add_edges_from(g.edges())
        return nx.number_connected_components(union)

    # --- ребра ---

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
        """Додає ребро a→b у шар класу; False, якщо додати не можна."""
        cls = self.edge_class(class_name)
        return self.insert_edge(cls.name, a, b, Edge(klass=cls))

    def insert_edge(self, class_name: str, a: int, b: int,
                    obj: Edge) -> bool:
        """Кладе готове ребро у шар (шлях завантажувача і add_edge)."""
        if a == b or a not in self.nodes or b not in self.nodes:
            return False
        g = self.layer(class_name)
        if g.has_edge(a, b) or (g.is_directed() and g.has_edge(b, a)):
            return False               # одне ребро класу на пару вершин
        g.add_edge(a, b, obj=obj)      # орієнтація = (a, b)
        return True

    def bulk_add_edges(self, pairs, edge_cls: EdgeClass) -> int:
        """Додає ребра пачкою; повертає кількість нових."""
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
        """Розвертає ребро напрямленого шару: джерело стає ціллю."""
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
        """Переносить ребро в шар іншого класу, скинувши перекриття.

        False, якщо ребра/класу немає або цільова пара вже зайнята.
        """
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
        """Ітерує (клас, u, v, Edge) по всіх шарах; u — джерело."""
        for name, g in self.layers.items():
            for u, v, data in g.edges(data=True):
                yield name, u, v, data["obj"]

    # --- групи вершин ---

    def add_group(self, members: set[int]) -> int | None:
        """Групує видимі вершини пулу; повертає gid або None (менше двох).

        Створює і метавершину групи — звичайну вершину дефолтного класу
        в центроїді членів (підпис "Група N"). Групою стає те, що
        користувач бачить у виділенні: вершини РОЗГОРНУТИХ груп
        переходять у нову групу (стара, лишившись із < 2 членами,
        розчиняється, її метавершина йде в orphans), інакше повторне
        групування мовчки відмовляло б через невидиме "членство".
        Якщо набір точно збігається з наявною групою, дубль не
        створюється — повертається вона сама.
        """
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
        """Кладе готову групу під заданим id (шлях завантажувача).

        Биті записи (нема метавершини, члени зайняті/відсутні, членів
        менше двох) мовчки відкидаються — файл міг бути зібраний
        вручну; метавершина тоді лишається звичайною вершиною.
        """
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
        """Розпускає групу; повертає nid її метавершини.

        Члени і метавершина ЛИШАЮТЬСЯ в пулі звичайними вершинами —
        прибирати метавершину чи ні, вирішує рівень вище.
        """
        grp = self.groups.pop(gid, None)
        if grp is None:
            return None
        for nid in grp.members:
            self.member_of.pop(nid, None)
        self.group_of_node.pop(grp.node, None)
        return grp.node

    def set_collapsed(self, gid: int, collapsed: bool) -> bool:
        """Згортає/розгортає групу; згорнута метавершина стає в
        центроїд членів."""
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
        """Вершина, що представляє nid на полі, або None (не видно).

        Підйом ланцюжком членства: представник — метавершина
        НАЙВИЩОГО згорнутого предка (згорнуте всередині згорнутого
        показує лише зовнішню групу). Без згорнутих предків вершина
        видима сама, крім метавершини РОЗГОРНУТОЇ групи — та не видна
        зовсім, разом зі своїми ребрами.
        """
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
        """Забирає чергу метавершин розпущених груп (на видалення)."""
        out, self.orphans = self.orphans, []
        return out

    def _forget_member(self, nid: int):
        """Прибирає вершину з її групи; група з < 2 членів розчиняється.

        Група з однієї вершини не має сенсу (нема чого згортати) і
        лише невидимо блокувала б цю вершину для нових груп.
        Метавершина розчиненої групи стає в чергу orphans — видалення
        вершини звідси зациклило б взаємні виклики з remove_node.
        """
        gid = self.member_of.pop(nid, None)
        if gid is None:
            return
        grp = self.groups[gid]
        grp.members.discard(nid)
        if len(grp.members) < 2:
            self.orphans.append(self.remove_group(gid))

    # --- сховище цілком ---

    def clear(self):
        """Спорожнює вершини і шари; класи лишаються — вони не елементи."""
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
        """Переймає вміст іншого сховища (після завантаження файла).

        Власні контейнери nodes/layers не замінюються, а наповнюються
        заново: на них посилаються модель вершин і шар малювання.
        """
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
