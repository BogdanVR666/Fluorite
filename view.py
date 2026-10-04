"""Вигляд графа: усе, що бачить користувач, але що не є самим графом.

Граф (FluoriteGraph) знає лише смисл: типи, вершини, ребра, групи. Тут —
те, як це показано: позиції вершин, стилі, дизайн типів, їхній порядок і
схованість у панелі, стандартні типи, згортання груп.

Записи незмінні, як і в FluoriteGraph: змінити — означає замінити запис
новим (dataclasses.replace). Тому знімок для історії — це копія посилань,
а змінений запис — просто інший об'єкт.

Вигляд прив'язаний до графа через id (вершини, ребра, гіперребра) і назви
типів. Стиль елемента перекриває дизайн його типу полем, відмінним від None.
"""
from dataclasses import dataclass, field, fields, replace
from itertools import count


@dataclass(frozen=True, slots=True)
class NodeStyle:
    shape: str | None = None        # "circle" | "square"
    color: str | None = None
    opacity: float | None = None    # 0..1, непрозорість тіла вершини


@dataclass(frozen=True, slots=True)
class EdgeStyle:
    color: str | None = None
    width: float | None = None
    line: str | None = None         # "solid" | "dash" | "dot"


NODE_DESIGN = NodeStyle(shape="circle", color="#3d7bd9", opacity=1.0)
EDGE_DESIGN = EdgeStyle(color="#7f8fd9", width=2.5, line="solid")

DEFAULT_NODE_TYPE = "Звичайна"      # тип вершин, для яких тип не обрано
DEFAULT_EDGE_TYPE = "Звичайне"      # тип ребер, для яких тип не обрано

_type_uids = count(1)


@dataclass(frozen=True, slots=True)
class TypeLook:
    """Як показано тип вершин чи ребер."""
    design: NodeStyle | EdgeStyle   # усі поля задані
    hidden: bool = False            # елементи типу не показуються
    # незмінний за перейменування: по ньому історія впізнає тип
    uid: int = field(default_factory=lambda: next(_type_uids))


@dataclass(frozen=True, slots=True)
class NodeLook:
    x: float
    y: float
    style: NodeStyle = NodeStyle()


@dataclass(frozen=True, slots=True)
class EdgeLook:
    style: EdgeStyle = EdgeStyle()


@dataclass(frozen=True, slots=True)
class GroupLook:
    """Група на екрані: гіперребро зі складом + метавершина, що її показує."""
    node: int                       # id метавершини
    collapsed: bool = False


def effective(style, design):
    """Стиль елемента поверх дизайну типу."""
    return replace(design, **{f.name: v for f in fields(style)
                              if (v := getattr(style, f.name)) is not None})


def merged(design, values: dict):
    """design із полями з values (зайві ключі ігноруються)."""
    names = {f.name for f in fields(design)}
    return replace(design, **{k: v for k, v in values.items() if k in names})


@dataclass(slots=True)
class View:
    # порядок ключів — порядок типів у панелі
    node_types: dict[str, TypeLook] = field(default_factory=dict)
    edge_types: dict[str, TypeLook] = field(default_factory=dict)
    defaults: dict[str, int] = field(default_factory=dict)  # сім'я → uid
    nodes: dict[int, NodeLook] = field(default_factory=dict)
    edges: dict[int, EdgeLook] = field(default_factory=dict)
    groups: dict[int, GroupLook] = field(default_factory=dict)  # id гіперребра

    def types(self, family: str) -> dict[str, TypeLook]:
        return self.node_types if family == "node" else self.edge_types

    def default_type(self, family: str) -> str:
        uid = self.defaults[family]
        return next(name for name, look in self.types(family).items()
                    if look.uid == uid)

    def is_default(self, family: str, name: str) -> bool:
        look = self.types(family).get(name)
        return look is not None and look.uid == self.defaults[family]
