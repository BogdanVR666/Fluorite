"""Спільна основа елементів графа (вершин, ребер, ...) — pydantic-схема.

Три рівні опису полів (спільні тут, власні — у nodes.py та edges.py):

  ElementStyle — поля стилю, спільні для всіх родин. Родини успадковують
                 його (NodeStyle, EdgeStyle) і додають власні поля.
                 Той самий тип грає дві ролі: як дизайн класу він
                 заповнений повністю, як style елемента — це перекриття,
                 де None означає "берётся з дизайну класу".
  ElementClass — клас елементів як ДАНІ (а не Python-тип): ім'я + дизайн.
                 Родини успадковують і уточнюють тип дизайну; поля
                 класу поза стилем (напр. directed у ребер) оголошуються
                 в extra_design.
  BaseElement  — спільні поля самих елементів: підпис, опис, посилання
                 на клас і перекриття стилю.

Family — реєстр класів однієї родини. Він живе в бекенді (per-документ),
а не глобально: завантаження файла більше не забруднює класами весь
процес, класи можна видаляти, а два документи можуть мати різні набори.

styled(поле) — властивість ефективного стилю: значення елемента, а якщо
воно None — дизайн класу. Заміна колишнього дескриптора StyleAttr.
"""

from typing import ClassVar

from pydantic import BaseModel, Field


class ElementStyle(BaseModel):
    """Поля стилю, спільні для вершин і ребер. None = дизайн класу."""

    color: str | None = None


class ElementClass(BaseModel):
    """Клас елементів: ім'я + дизайн за замовчуванням для його елементів.

    Це звичайний об'єкт даних. Усі елементи класу тримають посилання
    на нього, тож зміна дизайну одразу видима елементам без власних
    перекриттів (styled читає його динамічно).
    """

    name: str
    design: ElementStyle = Field(default_factory=ElementStyle)

    # поля класу поза стилем, які UI і файл бачать як частину дизайну
    # (наприклад directed у класів ребер)
    extra_design: ClassVar[tuple[str, ...]] = ()

    def design_map(self) -> dict:
        """Дизайн для UI/файла: поля стилю + extra_design-поля класу."""
        return {**self.design.model_dump(),
                **{f: getattr(self, f) for f in self.extra_design}}

    def apply_design(self, values: dict) -> None:
        """Накладає значення дизайну; невідомі ключі мовчки пропускає."""
        for field, value in values.items():
            if field in self.extra_design:
                setattr(self, field, value)
            elif field in type(self.design).model_fields:
                setattr(self.design, field, value)


class BaseElement(BaseModel):
    """Елемент графа: підпис, опис, клас і перекриття стилю."""

    label: str = ""
    description: str = ""
    klass: ElementClass
    style: ElementStyle = Field(default_factory=ElementStyle)


def styled(field: str) -> property:
    """Властивість ефективного стилю елемента.

    Читання: власне перекриття, а якщо воно None — дизайн класу
    (динамічно, тож зміна дизайну класу видима одразу).
    Запис: у перекриття елемента.
    """
    def get(self):
        value = getattr(self.style, field)
        return getattr(self.klass.design, field) if value is None else value

    def set(self, value):
        setattr(self.style, field, value)

    return property(get, set)


class Family:
    """Реєстр класів однієї родини елементів (вершин або ребер).

    Належить документові (бекенду), а не процесові. Клас "за
    замовчуванням" створюється одразу і не видаляється — на нього
    спираються елементи без явного класу.
    """

    def __init__(self, class_type: type[ElementClass],
                 style_type: type[ElementStyle], default_name: str):
        self.class_type = class_type
        self.style_type = style_type
        self.classes: dict[str, ElementClass] = {}
        self.default = self.define(default_name)

    @property
    def design_fields(self) -> tuple[str, ...]:
        """Усі поля дизайну родини: стиль + extra_design класу."""
        return (tuple(self.style_type.model_fields)
                + self.class_type.extra_design)

    def get(self, name: str | None) -> ElementClass | None:
        return self.classes.get(name)

    def define(self, name: str, **design) -> ElementClass | None:
        """Створює й реєструє клас родини; None — ім'я порожнє чи зайняте.

        Незадані поля дизайну отримують значення за замовчуванням
        родини (дефолти design у class_type).
        """
        name = name.strip()
        if not name or name in self.classes:
            return None
        cls = self.class_type(name=name)
        cls.apply_design(design)
        self.classes[name] = cls
        return cls
