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
    required property bool inPath
    required property int degree
    required property string nodeShape
    required property color nodeColor
    required property string nodeClass

    // --- стан, який задає власник ---
    property bool draggable: false     // режим переміщення
    property bool selected: false      // перша вершина ребра/шляху

    // --- сигнали для власника ---
    signal tapped()
    signal moved(real cx, real cy)     // нові координати центру

    width: 44
    height: 44
    x: px - width / 2
    y: py - height / 2
    z: hoverArea.containsMouse ? 2 : 1

    // hover: плавне збільшення
    scale: hoverArea.containsMouse ? 1.18 : 1.0
    Behavior on scale { NumberAnimation { duration: 120 } }

    property color strokeColor:
        hoverArea.containsMouse ? Theme.foreground
                                : Qt.alpha(Theme.foreground, 0.78)

    // Кільце стану: шлях / вибір / редагування стилю
    Rectangle {
        anchors.centerIn: parent
        width: parent.width + 12
        height: parent.height + 12
        radius: width / 2
        color: "transparent"
        border.width: 3
        border.color: node.inPath ? Theme.edgeHighlight
                                  : Theme.selection
        visible: node.inPath || node.selected
    }

    // --- форми ---
    Rectangle {   // коло та квадрат
        visible: node.nodeShape === "circle" || node.nodeShape === "square"
        anchors.fill: parent
        radius: node.nodeShape === "circle" ? width / 2 : 7
        color: node.nodeColor
        border.color: node.strokeColor
        border.width: 2
    }
    Rectangle {   // ромб — повернутий квадрат
        visible: node.nodeShape === "diamond"
        anchors.centerIn: parent
        width: parent.width * 0.76
        height: width
        rotation: 45
        radius: 5
        color: node.nodeColor
        border.color: node.strokeColor
        border.width: 2
    }
    Shape {       // трикутник
        visible: node.nodeShape === "triangle"
        anchors.fill: parent
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

    Text {
        anchors.horizontalCenter: parent.horizontalCenter
        // у трикутника центр мас нижче
        y: node.nodeShape === "triangle"
           ? parent.height * 0.42
           : (parent.height - height) / 2
        text: node.label
        color: Theme.foreground
        font.bold: true
        font.pixelSize: 15
        style: Text.Outline
        styleColor: Qt.alpha(Theme.background, 0.38)
    }

    // Бейдж зі ступенем вершини
    Rectangle {
        visible: node.degree > 0
        width: 18; height: 18; radius: 9
        color: Theme.badge
        border.color: Theme.edge
        border.width: 1
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.rightMargin: -5
        anchors.topMargin: -5
        Text {
            anchors.centerIn: parent
            text: node.degree
            color: Theme.badgeText
            font.pixelSize: 10
            font.bold: true
        }
    }

    // hover: підказка з даними вершини
    ToolTip.visible: hoverArea.containsMouse && !hoverArea.drag.active
    ToolTip.delay: 350
    ToolTip.text: "Вершина " + label + "  •  клас: " + nodeClass
                  + "  •  ступінь: " + degree

    MouseArea {
        id: hoverArea
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: node.draggable ? Qt.SizeAllCursor
                                    : Qt.PointingHandCursor
        drag.target: node

        onClicked: node.tapped()

        onPositionChanged: {
            if (drag.active)
                node.moved(node.x + node.width / 2,
                           node.y + node.height / 2)
        }
    }
}
