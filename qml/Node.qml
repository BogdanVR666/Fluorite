import QtQuick
import QtQuick.Controls
import QtQuick.Shapes

/*
 * Вершина графа. Отримує дані з ролей моделі (required property),
 * стан — через звичайні властивості, а про дії повідомляє сигналами.
 * Жодної логіки застосунку тут немає — лише вигляд і жести.
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

    // Уся графіка вершини малюється QtQuick.Shapes.
    // NodeShape — Shape на весь Item з рендерером кривих (гладкі дуги);
    // NodeFill  — ShapePath із заливкою кольором вершини та обведенням.
    component NodeShape: Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
    }
    component NodeFill: ShapePath {
        fillColor: node.nodeColor
        strokeColor: node.strokeColor
        strokeWidth: 2
        joinStyle: ShapePath.RoundJoin
    }

    // Кільце виділення повторює форму вершини: та сама геометрія, лише
    // в рамці, більшій на RING_PAD з кожного боку. Варіанти оголошені
    // окремо, як і заливки нижче, — ShapePath не має visible, тож
    // перемикати можна тільки самі Shape.
    // Рівномірний приріст рамки дає рівномірний зазор лише колу й квадрату:
    // у ромба й трикутника краї похилі, тож перпендикулярна відстань виходить
    // меншою за приріст (для ромба — у ~√2 разів). Компенсуємо падингом.
    readonly property real ringPad: effShape === "triangle" ? 11
                                  : effShape === "diamond" ? 9
                                                           : 6
    readonly property real ringW: width + ringPad * 2
    readonly property real ringH: height + ringPad * 2

    component Ring: Shape {
        anchors.centerIn: parent
        width: node.ringW
        height: node.ringH
        preferredRendererType: Shape.CurveRenderer
    }
    component RingPath: ShapePath {
        fillColor: "transparent"
        strokeColor: Theme.marked
        strokeWidth: 3
        joinStyle: ShapePath.RoundJoin
    }

    // --- кільця виділення ---
    Ring {   // коло
        visible: node.nodeSelected && node.effShape === "circle"
        RingPath {
            PathAngleArc {
                centerX: node.ringW / 2
                centerY: node.ringH / 2
                radiusX: node.ringW / 2 - 1.5
                radiusY: node.ringH / 2 - 1.5
                startAngle: 0
                sweepAngle: 360
            }
        }
    }
    Ring {   // квадрат
        visible: node.nodeSelected && node.effShape === "square"
        RingPath {
            PathRectangle {
                x: 1.5; y: 1.5
                width: node.ringW - 3
                height: node.ringH - 3
                radius: 9
            }
        }
    }
    Ring {   // ромб
        visible: node.nodeSelected && node.effShape === "diamond"
        RingPath {
            startX: node.ringW / 2; startY: 2
            PathLine { x: node.ringW - 2; y: node.ringH / 2 }
            PathLine { x: node.ringW / 2; y: node.ringH - 2 }
            PathLine { x: 2;              y: node.ringH / 2 }
            PathLine { x: node.ringW / 2; y: 2 }
        }
    }
    Ring {   // трикутник
        visible: node.nodeSelected && node.effShape === "triangle"
        RingPath {
            startX: node.ringW / 2; startY: 2
            PathLine { x: node.ringW - 2; y: node.ringH - 3 }
            PathLine { x: 2;              y: node.ringH - 3 }
            PathLine { x: node.ringW / 2; y: 2 }
        }
    }

    // --- форми ---
    // Метавершина групи: "стопка" зсунутих квадратів замість форми.
    // Колір і прозорість — як у звичайної вершини (стиль діє).
    Item {
        visible: node.isGroup
        anchors.fill: parent
        opacity: node.nodeOpacity

        Rectangle {
            x: 7; y: 7; width: node.width - 8; height: node.height - 8
            radius: 9
            color: Qt.darker(node.nodeColor, 1.8)
            border.color: Qt.alpha(node.strokeColor, 0.5)
            border.width: 1.5
        }
        Rectangle {
            x: 3.5; y: 3.5; width: node.width - 8; height: node.height - 8
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

    NodeShape {   // коло
        visible: !node.isGroup && node.nodeShape === "circle"
        opacity: node.nodeOpacity
        NodeFill {
            PathAngleArc {
                centerX: node.width / 2
                centerY: node.height / 2
                radiusX: node.width / 2 - 1
                radiusY: node.height / 2 - 1
                startAngle: 0
                sweepAngle: 360
            }
        }
    }
    NodeShape {   // квадрат
        visible: !node.isGroup && node.nodeShape === "square"
        opacity: node.nodeOpacity
        NodeFill {
            PathRectangle {
                x: 1; y: 1
                width: node.width - 2
                height: node.height - 2
                radius: 7
            }
        }
    }
    NodeShape {   // ромб
        visible: !node.isGroup && node.nodeShape === "diamond"
        opacity: node.nodeOpacity
        NodeFill {
            startX: node.width / 2; startY: 2
            PathLine { x: node.width - 2; y: node.height / 2 }
            PathLine { x: node.width / 2; y: node.height - 2 }
            PathLine { x: 2;              y: node.height / 2 }
            PathLine { x: node.width / 2; y: 2 }
        }
    }
    NodeShape {   // трикутник
        visible: !node.isGroup && node.nodeShape === "triangle"
        opacity: node.nodeOpacity
        NodeFill {
            startX: node.width / 2; startY: 2
            PathLine { x: node.width - 2; y: node.height - 3 }
            PathLine { x: 2;              y: node.height - 3 }
            PathLine { x: node.width / 2; y: 2 }
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
    Shape {
        visible: node.degree > 0
        width: 18; height: 18
        preferredRendererType: Shape.CurveRenderer
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.rightMargin: -5
        anchors.topMargin: -5
        ShapePath {
            fillColor: Theme.badge
            strokeColor: Theme.edge
            strokeWidth: 1
            PathAngleArc {
                centerX: 9; centerY: 9
                radiusX: 8.5; radiusY: 8.5
                startAngle: 0
                sweepAngle: 360
            }
        }
        Text {
            anchors.centerIn: parent
            text: node.degree
            color: Theme.badgeText
            font.pixelSize: 10
            font.bold: true
        }
    }

    // Бейдж із кількістю вершин у групі (лише в метавершини)
    Rectangle {
        visible: node.isGroup
        width: 18; height: 18; radius: 9
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.leftMargin: -7
        anchors.topMargin: -7
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

    // hover: підказка з даними вершини
    ToolTip.visible: hoverArea.containsMouse && !hoverArea.drag.active
    ToolTip.delay: 350
    ToolTip.text: (isGroup ? "Група " + label + "  •  вершин: " + memberCount
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
