"""Спільна основа для всіх елементів графа (вершин, ребер, ...).

ElementMeta — єдиний метаклас усієї ієрархії елементів:
  * веде реєстр родин (ElementMeta.families: "node" → BaseNode, ...);
  * веде реєстр класів кожної родини (registry в її корені);
  * обчислює перелік полів стилю класу (style_fields) за StyleAttr.

Родина — гілка ієрархії з власним реєстром і власним набором полів
стилю. Корінь родини (BaseNode, BaseEdge) — абстрактний клас з
атрибутом family; всі його неабстрактні нащадки автоматично
реєструються і стають видимими для UI за своїм type_name.

StyleAttr    — дескриптор поля стилю: значення екземпляра, а якщо його
               немає (None) — дизайн класу default_<ім'я поля>.
BaseElement  — спільний предок: лейбл, ініціалізація полів стилю,
               серіалізація дизайну (design) і перекриттів
               (style_overrides), створення класів у рантаймі (define).
"""


class StyleAttr:
    """Поле стилю: значення екземпляра або, якщо воно None, дизайн класу.

    default_<ім'я> читається динамічно з класу, тож зміна дизайну класу
    одразу впливає на всі його елементи без власного перекриття.
    """

    def __set_name__(self, owner, name):
        self.slot = "_" + name
        self.default = "default_" + name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        value = getattr(obj, self.slot)
        return getattr(type(obj), self.default) if value is None else value

    def __set__(self, obj, value):
        setattr(obj, self.slot, value)


class ElementMeta(type):
    """Метаклас елементів графа: реєструє родини і класи в них."""

    families: dict[str, "ElementMeta"] = {}   # family → корінь родини

    def __new__(mcls, name, bases, namespace):
        cls = super().__new__(mcls, name, bases, namespace)
        # усі поля стилю класу — StyleAttr-и по всьому MRO
        fields: list[str] = []
        for klass in reversed(cls.__mro__):
            for attr, value in vars(klass).items():
                if isinstance(value, StyleAttr) and attr not in fields:
                    fields.append(attr)
        cls.style_fields = tuple(fields)

        # abstract шукаємо лише у власному namespace, щоб нащадки
        # не успадковували "абстрактність" від предків
        if namespace.get("abstract", False):
            cls.registry = {}                 # новий корінь родини
            if "family" in namespace:
                mcls.families[namespace["family"]] = cls
        else:
            cls.registry[cls.type_name] = cls
        return cls


class BaseElement(metaclass=ElementMeta):
    """Елемент графа. Дизайн за замовчуванням визначає клас."""

    abstract = True                 # не потрапляє до реєстру
    type_name = "Base"              # ім'я класу, яке бачить користувач

    def __init__(self, label: str = "", **style):
        unknown = set(style) - set(self.style_fields)
        if unknown:
            raise TypeError(f"невідомі поля стилю: {sorted(unknown)}")
        self.label = label
        for field in self.style_fields:
            setattr(self, "_" + field, style.get(field))

    # --- серіалізація стилю ---

    def style_overrides(self) -> dict:
        """Перекриття стилю екземпляра; None — діє дизайн класу."""
        return {f: getattr(self, "_" + f) for f in self.style_fields}

    @classmethod
    def design(cls) -> dict:
        """Дизайн класу: поле стилю → значення за замовчуванням."""
        return {f: getattr(cls, "default_" + f) for f in cls.style_fields}

    # --- створення класів під час виконання ---

    @classmethod
    def define(cls, name: str, **design) -> "ElementMeta | None":
        """Створює й реєструє новий клас родини; None — ім'я вже зайняте.

        Виклик метакласа еквівалентний оголошенню
            class <name>(cls):
                type_name = name
                default_<поле> = <значення>   # для кожного поля design
        """
        unknown = set(design) - set(cls.style_fields)
        if unknown:
            raise TypeError(f"невідомі поля стилю: {sorted(unknown)}")
        name = name.strip()
        if not name or name in cls.registry:
            return None
        return type(cls)(name, (cls,), {
            "type_name": name,
            **{"default_" + f: v for f, v in design.items()},
        })
