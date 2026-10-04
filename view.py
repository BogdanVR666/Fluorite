from dataclasses import dataclass, field, fields, replace
from itertools import count


@dataclass(frozen=True, slots=True)
class NodeStyle:
    shape: str | None = None
    color: str | None = None
    opacity: float | None = None


@dataclass(frozen=True, slots=True)
class EdgeStyle:
    color: str | None = None
    width: float | None = None
    line: str | None = None


NODE_DESIGN = NodeStyle(shape="circle", color="#3d7bd9", opacity=1.0)
EDGE_DESIGN = EdgeStyle(color="#7f8fd9", width=2.5, line="solid")

DEFAULT_NODE_TYPE = "Звичайна"
DEFAULT_EDGE_TYPE = "Звичайне"

_type_uids = count(1)


@dataclass(frozen=True, slots=True)
class TypeLook:
    design: NodeStyle | EdgeStyle
    hidden: bool = False
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
    node: int
    collapsed: bool = False


def effective(style, design):
    return replace(design, **{f.name: v for f in fields(style)
                              if (v := getattr(style, f.name)) is not None})


def merged(design, values: dict):
    names = {f.name for f in fields(design)}
    return replace(design, **{k: v for k, v in values.items() if k in names})


@dataclass(slots=True)
class View:
    node_types: dict[str, TypeLook] = field(default_factory=dict)
    edge_types: dict[str, TypeLook] = field(default_factory=dict)
    defaults: dict[str, int] = field(default_factory=dict)
    nodes: dict[int, NodeLook] = field(default_factory=dict)
    edges: dict[int, EdgeLook] = field(default_factory=dict)
    groups: dict[int, GroupLook] = field(default_factory=dict)

    def types(self, family: str) -> dict[str, TypeLook]:
        return self.node_types if family == "node" else self.edge_types

    def default_type(self, family: str) -> str:
        uid = self.defaults[family]
        return next(name for name, look in self.types(family).items()
                    if look.uid == uid)

    def is_default(self, family: str, name: str) -> bool:
        look = self.types(family).get(name)
        return look is not None and look.uid == self.defaults[family]
