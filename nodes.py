"""Класи вершин графа.

NodeMeta    — метаклас-реєстр: кожен неабстрактний клас вершини
              автоматично потрапляє до NodeMeta.registry за своїм type_name.
BaseNode    — спільний предок: координати, лейбл і стиль. Форма/колір
              беруться з класу, але кожен екземпляр може їх перекрити.
DefaultNode — клас "за замовчуванням" для вершин без явного класу.

make_node_class() створює новий клас вершин під час виконання — саме
через нього UI визначає власні класи з потрібним дизайном. Оскільки
екземпляри читають default_shape/default_color динамічно з класу,
майбутня зміна дизайну класу одразу вплине на всі його вершини,
які не мають власного перекриття стилю.
"""


class NodeMeta(type):
    """Реєструє всі класи вершин, щоб UI міг їх перелічити й створювати."""

    registry: dict[str, "NodeMeta"] = {}

    def __new__(mcls, name, bases, namespace):
        cls = super().__new__(mcls, name, bases, namespace)
        # abstract шукаємо лише у власному namespace, щоб нащадки
        # не успадковували "абстрактність" від BaseNode
        if not namespace.get("abstract", False):
            mcls.registry[cls.type_name] = cls
        return cls


class BaseNode(metaclass=NodeMeta):
    """Вершина графа. Дизайн за замовчуванням визначає клас."""

    abstract = True                 # не потрапляє до реєстру
    type_name = "Base"              # ім'я класу, яке бачить користувач
    default_shape = "circle"
    default_color = "#3d7bd9"

    def __init__(self, x: float, y: float, label: str,
                 shape: str | None = None, color: str | None = None):
        self.x = x
        self.y = y
        self.label = label
        self._shape = shape         # None — використовувати дизайн класу
        self._color = color

    @property
    def shape(self) -> str:
        return self._shape or type(self).default_shape

    @shape.setter
    def shape(self, value: str):
        self._shape = value

    @property
    def color(self) -> str:
        return self._color or type(self).default_color

    @color.setter
    def color(self, value: str):
        self._color = value


class DefaultNode(BaseNode):
    """Вершини, для яких клас не обрано."""

    type_name = "Звичайна"


def make_node_class(name: str, shape: str, color: str) -> type | None:
    """Створює й реєструє новий клас вершин; None — ім'я вже зайняте.

    Виклик метакласа еквівалентний оголошенню
        class <name>(BaseNode, metaclass=NodeMeta):
            type_name = name
            default_shape = shape
            default_color = color
    """
    name = name.strip()
    if not name or name in NodeMeta.registry:
        return None
    return NodeMeta(name, (BaseNode,), {
        "type_name": name,
        "default_shape": shape,
        "default_color": color,
    })
