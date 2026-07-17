"""Класи ребер графа — родина "edge" (спільна механіка в elements.py).

BaseEdge    — корінь родини: поля стилю лінії (колір, товщина, штрих).
              Координати ребру дають вершини-кінці, тож власної
              геометрії воно не зберігає.
DefaultEdge — клас "за замовчуванням" для ребер без явного класу.

Нові класи ребер створюються під час виконання викликом
BaseEdge.define(ім'я, color=..., width=..., line=...).
"""

from elements import BaseElement, StyleAttr


class BaseEdge(BaseElement):
    """Ребро графа: стиль лінії, якою воно малюється."""

    abstract = True                 # корінь родини, не потрапляє до реєстру
    family = "edge"
    type_name = "Base"

    color = StyleAttr()
    width = StyleAttr()
    line = StyleAttr()              # "solid" | "dash" | "dot"

    default_color = "#7f8fd9"       # збігається з Theme.edge типової теми
    default_width = 2.5
    default_line = "solid"


class DefaultEdge(BaseEdge):
    """Ребра, для яких клас не обрано."""

    type_name = "Звичайне"
