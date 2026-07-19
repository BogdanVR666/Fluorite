"""Родина ребер: поля, що є ВИКЛЮЧНО у ребер (спільні — в elements.py).

EdgeStyle — стиль лінії: успадковує спільний color, додає товщину
            і штрих. Координати ребру дають вершини-кінці, тож власної
            геометрії воно не має.
EdgeClass — клас ребер: дизайн EdgeStyle плюс directed. Напрямленість —
            властивість КЛАСУ, а не стиль окремого ребра: "читає" або
            спрямоване, або ні. Для UI і файла воно входить у дизайн
            через extra_design.
Edge      — саме ребро: лише спільні поля елемента. Кінці й напрям
            зберігає шар-граф свого класу (див. layers.py): у
            напрямленому шарі (nx.DiGraph) орієнтація пари (u, v) —
            це і є напрям стрілки, тож ребру не треба пам'ятати
            власного "джерела".

Нові класи ребер створюються через Family(EdgeClass, EdgeStyle, ...)
у сховищі — див. elements.py, layers.py.
"""

from typing import ClassVar

from pydantic import Field

from elements import BaseElement, ElementClass, ElementStyle, styled


class EdgeStyle(ElementStyle):
    """Поля стилю, які має лише ребро."""

    width: float | None = None
    line: str | None = None         # "solid" | "dash" | "dot"


class EdgeClass(ElementClass):
    """Клас ребер: повністю заповнений дизайн + напрямленість."""

    design: EdgeStyle = Field(default_factory=lambda: EdgeStyle(
        color="#7f8fd9", width=2.5, line="solid"))
    directed: bool = False          # чи малювати стрілку в бік цілі

    extra_design: ClassVar[tuple[str, ...]] = ("directed",)


class Edge(BaseElement):
    """Ребро графа: стиль лінії, яким воно малюється."""

    klass: EdgeClass
    style: EdgeStyle = Field(default_factory=EdgeStyle)

    color = styled("color")
    width = styled("width")
    line = styled("line")

    @property
    def directed(self) -> bool:
        return self.klass.directed


DEFAULT_EDGE_CLASS = "Звичайне"     # клас ребер, для яких клас не обрано
