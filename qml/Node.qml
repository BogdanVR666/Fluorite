import QtQuick
import QtQuick.Controls
import QtQuick.Shapes

/*
 * Вершина графа. Отримує дані з ролей моделі (required property),
 * стан — через звичайні властивості, а про дії повідомляє сигналами.
 * Жодної логіки застосунку тут немає — лише вигляд і жести.
 *
 * Заради швидкодії делегат тримає створеним лише те, що видно зараз:
 * коло, квадрат і ромб — це один Rectangle (коло — радіусом у півширини,
 * ромб — поворотом на 45°), і тільки трикутник потребує Shape. Кільце
 * виділення, "стопка" групи та бейджі живуть у Loader-ах і з'являються
 * лише за потреби. Так типова вершина — це кілька елементів сцени
 * замість десятка Shape із CurveRenderer у кожної.
 */
Item {
    id: node

    // --- дані з ролей NodesModel ---
    required property int nodeId
    required property real px
    required property real py
    required property string label
    required property int degree
    required property string nodeShape
    required property color nodeColor
    required property string nodeClass
    required property string nodeDescription
    required property real nodeOpacity
    required property bool nodeSelected   // входить у виділення
    required property bool nodeHidden     // зараз не видно (групи)
    required property bool isGroup        // метавершина групи
    required property int memberCount     // вершин у її групі

    // --- сигнали для власника ---
    // modifiers — Qt.ShiftModifier тощо; що вони означають, вирішує власник
    signal tapped(int modifiers)
    signal moved(real cx, real cy)     // нові координати центру

    width: 44
    height: 44
    x: px - width / 2
    y: py - height / 2
    z: hoverArea.containsMouse ? 2 : 1
    // сховане (члени згорнутих груп, метавершини розгорнутих) не видно
    visible: !nodeHidden

    // Метавершина групи має незмінну форму — "стопку" квадратів; форма
    // з дизайну класу/стилю на неї не діє
    readonly property string effShape: isGroup ? "square" : nodeShape

    // hover: плавне збільшення
    scale: hoverArea.containsMouse ? 1.18 : 1.0
    Behavior on scale { NumberAnimation { duration: 120 } }

    property color strokeColor:
        hoverArea.containsMouse ? Theme.foreground
                                : Qt.alpha(Theme.foreground, 0.78)

    // Кільце виділення повторює форму вершини: та сама геометрія, лише
    // в рамці, більшій на RING_PAD з кожного боку.
    // Рівномірний приріст рамки дає рівномірний зазор лише колу й квадрату:
    // у ромба й трикутника краї похилі, тож перпендикулярна відстань виходить
    // меншою за приріст (для ромба — у ~√2 разів). Компенсуємо падингом.
    readonly property real ringPad: effShape === "triangle" ? 11
                                  : effShape === "diamond" ? 9
                                                           : 6
    readonly property real ringW: width + ringPad * 2
    readonly property real ringH: height + ringPad * 2

    // --- кільце виділення: створюється лише коли вершина виділена ---
    Loader {
        active: node.nodeSelected
        anchors.centerIn: parent
        sourceComponent: node.effShape === "triangle" ? ringTriangle
                                                      : ringRect
    }
    Component {
        id: ringRect   // коло, квадрат і ромб — Rectangle без заливки
        Rectangle {
            readonly property bool diamond: node.effShape === "diamond"
            // ромб — квадрат, повернутий на 45°: сторона менша в √2 разів
            width: diamond ? node.ringW / Math.SQRT2 : node.ringW
            height: diamond ? node.ringH / Math.SQRT2 : node.ringH
            rotation: diamond ? 45 : 0
            radius: node.effShape === "circle" ? width / 2 : 9
            color: "transparent"
            border.color: Theme.marked
            border.width: 3
            antialiasing: true
        }
    }
    Component {
        id: ringTriangle
        Shape {
            width: node.ringW
            height: node.ringH
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                fillColor: "transparent"
                strokeColor: Theme.marked
                strokeWidth: 3
                joinStyle: ShapePath.RoundJoin
                startX: node.ringW / 2; startY: 2
                PathLine { x: node.ringW - 2; y: node.ringH - 3 }
                PathLine { x: 2;              y: node.ringH - 3 }
                PathLine { x: node.ringW / 2; y: 2 }
            }
        }
    }

    // --- форма ---
    // Коло, квадрат і ромб — один спільний Rectangle; трикутник і
    // "стопка" групи вантажаться Loader-ом лише за потреби.
    Rectangle {
        visible: !node.isGroup && node.nodeShape !== "triangle"
        readonly property bool diamond: node.nodeShape === "diamond"
        anchors.centerIn: parent
        width: diamond ? (node.width - 4) / Math.SQRT2 : node.width
        height: diamond ? (node.height - 4) / Math.SQRT2 : node.height
        rotation: diamond ? 45 : 0
        radius: node.nodeShape === "circle" ? width / 2
              : diamond ? 2 : 8
        color: node.nodeColor
        border.color: node.strokeColor
        border.width: 2
        opacity: node.nodeOpacity
        antialiasing: true
    }
    Loader {
        active: !node.isGroup && node.nodeShape === "triangle"
        anchors.fill: parent
        sourceComponent: triangleShape
    }
    Component {
        id: triangleShape
        Shape {
            preferredRendererType: Shape.CurveRenderer
            opacity: node.nodeOpacity
            ShapePath {
                fillColor: node.nodeColor
                strokeColor: node.strokeColor
                strokeWidth: 2
                joinStyle: ShapePath.RoundJoin
                startX: node.width / 2; startY: 2
                PathLine { x: node.width - 2; y: node.height - 3 }
                PathLine { x: 2;              y: node.height - 3 }
                PathLine { x: node.width / 2; y: 2 }
            }
        }
    }

    // Метавершина групи: "стопка" зсунутих квадратів замість форми.
    // Колір і прозорість — як у звичайної вершини (стиль діє).
    Loader {
        active: node.isGroup
        anchors.fill: parent
        sourceComponent: groupStack
    }
    Component {
        id: groupStack
        Item {
            opacity: node.nodeOpacity

            Rectangle {
                x: 7; y: 7; width: node.width - 8; height: node.height - 8
                radius: 9
                color: Qt.darker(node.nodeColor, 1.8)
                border.color: Qt.alpha(node.strokeColor, 0.5)
                border.width: 1.5
            }
            Rectangle {
                x: 3.5; y: 3.5
                width: node.width - 8; height: node.height - 8
                radius: 9
                color: Qt.darker(node.nodeColor, 1.35)
                border.color: Qt.alpha(node.strokeColor, 0.7)
                border.width: 1.5
            }
            Rectangle {
                x: 0; y: 0; width: node.width - 8; height: node.height - 8
                radius: 9
                color: node.nodeColor
                border.color: node.strokeColor
                border.width: 2
            }
        }
    }

    Text {
        anchors.horizontalCenter: parent.horizontalCenter
        // передній аркуш "стопки" групи зсунутий на 4px вліво-вгору
        anchors.horizontalCenterOffset: node.isGroup ? -4 : 0
        // у трикутника центр мас нижче
        y: node.effShape === "triangle"
           ? parent.height * 0.42
           : (parent.height - height) / 2 - (node.isGroup ? 4 : 0)
        text: node.label
        color: Theme.foreground
        font.bold: true
        font.pixelSize: 15
        style: Text.Outline
        styleColor: Qt.alpha(Theme.background, 0.38)
    }

    // Бейдж зі ступенем вершини
    Loader {
        active: node.degree > 0
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.rightMargin: -5
        anchors.topMargin: -5
        sourceComponent: degreeBadge
    }
    Component {
        id: degreeBadge
        Rectangle {
            width: 18; height: 18; radius: 9
            color: Theme.badge
            border.color: Theme.edge
            border.width: 1
            Text {
                anchors.centerIn: parent
                text: node.degree
                color: Theme.badgeText
                font.pixelSize: 10
                font.bold: true
            }
        }
    }

    // Бейдж із кількістю вершин у групі (лише в метавершини)
    Loader {
        active: node.isGroup
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.leftMargin: -7
        anchors.topMargin: -7
        sourceComponent: memberBadge
    }
    Component {
        id: memberBadge
        Rectangle {
            width: 18; height: 18; radius: 9
            color: Theme.badge
            border.color: Theme.edge
            border.width: 1
            Text {
                anchors.centerIn: parent
                text: node.memberCount
                color: Theme.badgeText
                font.pixelSize: 10
                font.bold: true
            }
        }
    }

    // hover: підказка з даними вершини. Текст складається лише під
    // курсором — інакше кожна зміна ступеня перебудовувала б рядки
    // в усіх вершинах графа.
    ToolTip.visible: hoverArea.containsMouse && !hoverArea.drag.active
    ToolTip.delay: 350
    ToolTip.text: !hoverArea.containsMouse ? ""
        : (isGroup ? "Група " + label + "  •  вершин: " + memberCount
                   : "Вершина " + label + "  •  клас: " + nodeClass)
          + "  •  ступінь: " + degree
          + (nodeDescription !== "" ? "\n" + nodeDescription : "")

    MouseArea {
        id: hoverArea
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.SizeAllCursor
        drag.target: node

        onClicked: function (mouse) { node.tapped(mouse.modifiers) }

        onPositionChanged: {
            if (drag.active)
                node.moved(node.x + node.width / 2,
                           node.y + node.height / 2)
        }
    }
}
