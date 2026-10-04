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
    required property bool nodeSelected
    required property bool nodeHidden
    required property bool isGroup
    required property int memberCount

    property string edgeClass

    function tap(modifiers) {
        var chord = Qt.ControlModifier | Qt.ShiftModifier
        if ((modifiers & chord) === chord)
            backend.connectSelectionTo(nodeId, edgeClass)
        else
            backend.selectNode(nodeId, (modifiers & Qt.ShiftModifier) !== 0)
    }

    function moveTo(cx, cy) {
        if (nodeSelected && backend.selectionCount > 1)
            backend.moveSelectionTo(nodeId, cx, cy)
        else
            backend.moveNode(nodeId, cx, cy)
    }

    property bool editing: false

    function commitLabel(text) {
        if (!editing)
            return
        editing = false
        var t = text.trim()
        if (t !== "" && t !== label)
            backend.setNodeLabel(nodeId, t)
    }

    width: Math.max(Theme.nodeHeight, (editing && editLoader.item ? editLoader.item.width
                                                     : textElement.width) + 20)
    height: Theme.nodeHeight
    x: px - width / 2
    y: py - height / 2
    z: editing || hoverArea.containsMouse ? 2 : 1
    visible: !nodeHidden

    readonly property string effShape: isGroup ? "square" : nodeShape

    property color strokeColor:
        hoverArea.containsMouse ? Theme.foreground
                                : Theme.nodeStroke

    readonly property bool round: effShape === "circle"

    Rectangle {
        visible: node.nodeSelected
        anchors.centerIn: parent
        width: node.width + 12
        height: node.height + 12
        radius: node.round ? width / 2 : Theme.radiusMd + 6
        color: "transparent"
        border.color: Theme.marked
        border.width: Theme.strokeRing
        antialiasing: true
    }

    Rectangle {
        visible: !node.isGroup
        anchors.fill: parent
        radius: node.round ? width / 2 : Theme.radiusMd
        color: node.nodeColor
        border.color: node.strokeColor
        border.width: Theme.strokeNode
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
                radius: Theme.radiusMd
                color: Qt.darker(node.nodeColor, 1.8)
                border.color: Qt.alpha(node.strokeColor, 0.5)
                border.width: 1.5
            }
            Rectangle {
                x: 3.5
                y: 3.5
                width: node.width - 8
                height: node.height - 8
                radius: Theme.radiusMd
                color: Qt.darker(node.nodeColor, 1.35)
                border.color: Qt.alpha(node.strokeColor, 0.7)
                border.width: 1.5
            }
            Rectangle {
                x: 0
                y: 0 
                width: node.width - 8
                height: node.height - 8
                radius: Theme.radiusMd
                color: node.nodeColor
                border.color: node.strokeColor
                border.width: Theme.strokeNode
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
        styleColor: Theme.labelOutline
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
            selectionColor: Theme.markedTextSelection
            selectedTextColor: Theme.foreground

            Component.onCompleted: {
                selectAll()
                forceActiveFocus()
            }
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
                height: Theme.strokeNode
                radius: Theme.strokeNode / 2
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
            width: Theme.badgeSize; height: Theme.badgeSize
            radius: Theme.badgeSize / 2
            color: Theme.badge
            border.color: Theme.edge
            border.width: Theme.strokeHairline
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
            width: Theme.badgeSize; height: Theme.badgeSize
            radius: Theme.badgeSize / 2
            color: Theme.badge
            border.color: Theme.edge
            border.width: Theme.strokeHairline
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
        enabled: !node.editing
        hoverEnabled: true
        cursorShape: Qt.SizeAllCursor
        drag.target: node

        onPressed: node.forceActiveFocus()
        onClicked: function (mouse) { node.tap(mouse.modifiers) }
        onDoubleClicked: node.editing = true

        onPositionChanged: {
            if (drag.active)
                node.moveTo(node.x + node.width / 2,
                            node.y + node.height / 2)
        }
    }
}
