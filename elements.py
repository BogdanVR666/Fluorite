from typing import ClassVar

from pydantic import BaseModel, Field


class ElementStyle(BaseModel):
    color: str | None = None


class ElementClass(BaseModel):
    name: str
    design: ElementStyle = Field(default_factory=ElementStyle)

    extra_design: ClassVar[tuple[str, ...]] = ()

    def design_map(self) -> dict:
        return {**self.design.model_dump(),
                **{f: getattr(self, f) for f in self.extra_design}}

    def apply_design(self, values: dict) -> None:
        for field, value in values.items():
            if field in self.extra_design:
                setattr(self, field, value)
            elif field in type(self.design).model_fields:
                setattr(self.design, field, value)


class BaseElement(BaseModel):
    label: str = ""
    description: str = ""
    klass: ElementClass
    style: ElementStyle = Field(default_factory=ElementStyle)


def styled(field: str) -> property:
    def get(self):
        value = getattr(self.style, field)
        return getattr(self.klass.design, field) if value is None else value

    def set(self, value):
        setattr(self.style, field, value)

    return property(get, set)


class Family:
    def __init__(self, class_type: type[ElementClass],
                 style_type: type[ElementStyle], default_name: str):
        self.class_type = class_type
        self.style_type = style_type
        self.classes: dict[str, ElementClass] = {}
        self.default = self.define(default_name)

    @property
    def design_fields(self) -> tuple[str, ...]:
        return (tuple(self.style_type.model_fields)
                + self.class_type.extra_design)

    def get(self, name: str | None) -> ElementClass | None:
        return self.classes.get(name)

    def define(self, name: str, **design) -> ElementClass | None:
       name = name.strip()
        if not name or name in self.classes:
            return None
        cls = self.class_type(name=name)
        cls.apply_design(design)
        self.classes[name] = cls
        return cls
