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
    required property string nodeDescription
    required property real nodeOpacity

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

    // Кільце стану: шлях / вибір / редагування стилю
    Shape {
        anchors.centerIn: parent
        width: parent.width + 12
        height: parent.height + 12
        preferredRendererType: Shape.CurveRenderer
        visible: node.inPath || node.selected
        ShapePath {
            fillColor: "transparent"
            strokeColor: node.inPath ? Theme.edgeHighlight
                                     : Theme.selection
            strokeWidth: 3
            PathAngleArc {
                centerX: node.width / 2 + 6
                centerY: node.height / 2 + 6
                radiusX: node.width / 2 + 4.5
                radiusY: node.height / 2 + 4.5
                startAngle: 0
                sweepAngle: 360
            }
        }
    }

    // --- форми ---
    NodeShape {   // коло
        visible: node.nodeShape === "circle"
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
        visible: node.nodeShape === "square"
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
        visible: node.nodeShape === "diamond"
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
        visible: node.nodeShape === "triangle"
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

    // hover: підказка з даними вершини
    ToolTip.visible: hoverArea.containsMouse && !hoverArea.drag.active
    ToolTip.delay: 350
    ToolTip.text: "Вершина " + label + "  •  клас: " + nodeClass
                  + "  •  ступінь: " + degree
                  + (nodeDescription !== "" ? "\n" + nodeDescription : "")

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
