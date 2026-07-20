from pydantic import Field

from elements import BaseElement, ElementClass, ElementStyle, styled


class NodeStyle(ElementStyle):
    shape: str | None = None
    opacity: float | None = None    # 0..1, непрозорість тіла вершини


class NodeClass(ElementClass):
    design: NodeStyle = Field(default_factory=lambda: NodeStyle(
        shape="circle", color="#3d7bd9", opacity=1.0))


class Node(BaseElement):
    klass: NodeClass
    style: NodeStyle = Field(default_factory=NodeStyle)
    x: float
    y: float

    shape = styled("shape")
    color = styled("color")
    opacity = styled("opacity")


DEFAULT_NODE_CLASS = "Звичайна"     # клас вершин, для яких клас не обрано
