"""Класи вершин графа — родина "node" (спільна механіка в elements.py).

BaseNode    — корінь родини: координати, лейбл і поля стилю
              (форма, колір). Дизайн береться з класу, але кожен
              екземпляр може його перекрити.
DefaultNode — клас "за замовчуванням" для вершин без явного класу.

Нові класи вершин створюються під час виконання викликом
BaseNode.define(ім'я, shape=..., color=...) — саме так UI визначає
власні класи з потрібним дизайном.
"""

from elements import BaseElement, StyleAttr


class BaseNode(BaseElement):
    """Вершина графа: позиція на полі + форма і колір."""

    abstract = True                 # корінь родини, не потрапляє до реєстру
    family = "node"
    type_name = "Base"

    shape = StyleAttr()
    color = StyleAttr()
    default_shape = "circle"
    default_color = "#3d7bd9"

    def __init__(self, x: float, y: float, label: str = "", **style):
        super().__init__(label, **style)
        self.x = x
        self.y = y


class DefaultNode(BaseNode):
    """Вершини, для яких клас не обрано."""

    type_name = "Звичайна"
