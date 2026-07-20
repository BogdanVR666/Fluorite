from typing import ClassVar

from pydantic import Field

from elements import BaseElement, ElementClass, ElementStyle, styled


class EdgeStyle(ElementStyle):
    width: float | None = None
    line: str | None = None         # "solid" | "dash" | "dot"


class EdgeClass(ElementClass):
    design: EdgeStyle = Field(default_factory=lambda: EdgeStyle(
        color="#7f8fd9", width=2.5, line="solid"))
    directed: bool = False          # чи малювати стрілку в бік цілі

    extra_design: ClassVar[tuple[str, ...]] = ("directed",)


class Edge(BaseElement):
    klass: EdgeClass
    style: EdgeStyle = Field(default_factory=EdgeStyle)

    color = styled("color")
    width = styled("width")
    line = styled("line")

    @property
    def directed(self) -> bool:
        return self.klass.directed


DEFAULT_EDGE_CLASS = "Звичайне"     # клас ребер, для яких клас не обрано
