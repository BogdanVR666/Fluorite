import QtQuick
import QtQuick.Controls

Item {
    id: node

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

    signal tapped(int modifiers)
    signal moved(real cx, real cy)     // нові координати центру

    property bool editing: false   // підпис редагується на місці

    function commitLabel(text) {
        if (!editing)
            return
        editing = false
        var t = text.trim()
        if (t !== "" && t !== label)
            backend.setNodeLabel(nodeId, t)
    }

    width: Math.max(44, (editing && editLoader.item ? editLoader.item.width
                                                     : textElement.width) + 20)
    height: 44
    x: px - width / 2
    y: py - height / 2
    z: editing || hoverArea.containsMouse ? 2 : 1
    visible: !nodeHidden

    readonly property string effShape: isGroup ? "square" : nodeShape

    property color strokeColor:
        hoverArea.containsMouse ? Theme.foreground
                                : Qt.alpha(Theme.foreground, 0.78)

    // будь-яка форма, крім кола, малюється квадратом
    readonly property bool round: effShape === "circle"

    Rectangle {   // рамка виділення
        visible: node.nodeSelected
        anchors.centerIn: parent
        width: node.width + 12
        height: node.height + 12
        radius: node.round ? width / 2 : 9
        color: "transparent"
        border.color: Theme.marked
        border.width: 3
        antialiasing: true
    }

    Rectangle {
        visible: !node.isGroup
        anchors.fill: parent
        radius: node.round ? width / 2 : 8
        color: node.nodeColor
        border.color: node.strokeColor
        border.width: 2
        opacity: node.nodeOpacity
        antialiasing: true
    }

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
                x: 7 
                y: 7
                width: node.width - 8
                height: node.height - 8
                radius: 9
                color: Qt.darker(node.nodeColor, 1.8)
                border.color: Qt.alpha(node.strokeColor, 0.5)
                border.width: 1.5
            }
            Rectangle {
                x: 3.5
                y: 3.5
                width: node.width - 8
                height: node.height - 8
                radius: 9
                color: Qt.darker(node.nodeColor, 1.35)
                border.color: Qt.alpha(node.strokeColor, 0.7)
                border.width: 1.5
            }
            Rectangle {
                x: 0
                y: 0 
                width: node.width - 8
                height: node.height - 8
                radius: 9
                color: node.nodeColor
                border.color: node.strokeColor
                border.width: 2
            }
        }
    }

    Text {
        id: textElement
        visible: !node.editing
        anchors.centerIn: parent
        text: node.label
        color: Theme.foreground
        font.bold: true
        font.pixelSize: 15
        style: Text.Outline
        styleColor: Qt.alpha(Theme.background, 0.38)
    }

    Loader {
        id: editLoader
        active: node.editing
        anchors.centerIn: parent
        sourceComponent: labelEditor
    }
    Component {
        id: labelEditor
        TextInput {
            width: Math.max(contentWidth + 2, 16)
            text: node.label
            color: Theme.foreground
            font: textElement.font
            horizontalAlignment: TextInput.AlignHCenter
            selectByMouse: true
            selectionColor: Qt.alpha(Theme.marked, 0.45)
            selectedTextColor: Theme.foreground

            Component.onCompleted: {
                selectAll()
                forceActiveFocus()
            }
            // інакше Escape забере Shortcut вікна (скидання виділення)
            Keys.onShortcutOverride: function (event) {
                event.accepted = event.key === Qt.Key_Escape
            }
            Keys.onEscapePressed: node.editing = false
            onAccepted: node.commitLabel(text)
            onActiveFocusChanged: {
                if (!activeFocus)
                    node.commitLabel(text)
            }

            Rectangle {
                anchors { left: parent.left; right: parent.right
                          top: parent.bottom; topMargin: 1 }
                height: 2
                radius: 1
                color: Theme.marked
            }
        }
    }

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
    ToolTip.visible: hoverArea.containsMouse && !hoverArea.drag.active
                     && !editing
    ToolTip.delay: 500
    ToolTip.text: isGroup ? 
        "Група " + label + "  •  вершин: " + memberCount : "Вершина " + label + "  •  клас: " + nodeClass + "  •  ступінь: " + degree +  "\n" + nodeDescription

    MouseArea {
        id: hoverArea
        anchors.fill: parent
        enabled: !node.editing   // клацання йдуть у поле вводу
        hoverEnabled: true
        cursorShape: Qt.SizeAllCursor
        drag.target: node

        // MouseArea сама фокус не бере, а поле вводу має його втратити
        onPressed: node.forceActiveFocus()
        onClicked: function (mouse) { node.tapped(mouse.modifiers) }
        onDoubleClicked: node.editing = true

        onPositionChanged: {
            if (drag.active)
                node.moved(node.x + node.width / 2,
                           node.y + node.height / 2)
        }
    }
}
