"""Родина вершин: поля, що є ВИКЛЮЧНО у вершин (спільні — в elements.py).

NodeStyle — стиль вершини: успадковує спільний color, додає форму
            і прозорість.
NodeClass — клас вершин: дизайн NodeStyle з дефолтами родини.
Node      — сама вершина: позиція на полі + спільні поля елемента.

Нові класи вершин створюються через Family(NodeClass, NodeStyle, ...)
у бекенді — див. elements.py.
"""

from pydantic import Field

from elements import BaseElement, ElementClass, ElementStyle, styled


class NodeStyle(ElementStyle):
    """Поля стилю, які має лише вершина."""

    shape: str | None = None
    opacity: float | None = None    # 0..1, непрозорість тіла вершини


class NodeClass(ElementClass):
    """Клас вершин: повністю заповнений дизайн."""

    design: NodeStyle = Field(default_factory=lambda: NodeStyle(
        shape="circle", color="#3d7bd9", opacity=1.0))


class Node(BaseElement):
    """Вершина графа: позиція на полі + підпис, опис, клас і стиль."""

    klass: NodeClass
    style: NodeStyle = Field(default_factory=NodeStyle)
    x: float
    y: float

    shape = styled("shape")
    color = styled("color")
    opacity = styled("opacity")


DEFAULT_NODE_CLASS = "Звичайна"     # клас вершин, для яких клас не обрано
