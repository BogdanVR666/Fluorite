import QtQuick
import QtQuick.Controls

Item {
    id: group

    required property int groupId
    required property real gx
    required property real gy
    required property real gw
    required property real gh
    required property string title
    required property bool collapsed
    required property string mode
    required property bool groupSelected
    required property bool groupHidden
    required property int memberCount
    required property real ax
    required property real ay
    required property string nodeShape
    required property color nodeColor
    required property real nodeOpacity
    required property int degree

    property Item grid

    readonly property bool framed: !collapsed && mode === "frame"
    readonly property bool tree: !collapsed && mode === "tree"
    readonly property bool round: tree && nodeShape === "circle"
    readonly property color strokeColor: groupSelected ? Theme.marked
                                                       : Theme.groupStroke

    function tap(modifiers) {
        backend.selectGroup(groupId, (modifiers & Qt.ShiftModifier) !== 0)
    }

    x: gx
    y: gy
    width: gw
    height: gh
    z: 0.5 + 0.4 / (1 + gw * gh)
    visible: !groupHidden

    Rectangle {
        visible: group.framed
        anchors.fill: parent
        color: "transparent"
        radius: Theme.radiusLg
        border.color: group.strokeColor
        border.width: Theme.strokeNode
    }

    Item {
        visible: group.framed
        anchors { left: parent.left; right: parent.right; top: parent.top }
        height: Theme.controlHeight

        DragArea {
            anchors.fill: parent
            cursorShape: Qt.SizeAllCursor
            space: group.parent
            origin: Qt.point(group.gx, group.gy)
            grid: group.grid

            onMoved: function (x, y, snap) {
                backend.moveGroup(group.groupId, x, y, snap)
            }
            onClicked: function (mouse) {
                if (!dragged)
                    group.tap(mouse.modifiers)
            }
            onDoubleClicked: backend.setGroupCollapsed(group.groupId, true)
        }

        Text {
            anchors { left: parent.left; right: toggle.left
                      leftMargin: Theme.spaceMd; rightMargin: Theme.spaceSm
                      verticalCenter: parent.verticalCenter }
            text: group.title
            color: Theme.foreground
            font.bold: true
            font.pixelSize: 14
            elide: Text.ElideRight
        }

        Text {
            id: toggle
            anchors { right: parent.right; rightMargin: Theme.spaceMd
                      verticalCenter: parent.verticalCenter }
            text: "▾"
            color: toggleArea.containsMouse ? Theme.foreground
                                            : Theme.mutedText
            font.pixelSize: 14

            MouseArea {
                id: toggleArea
                anchors.fill: parent
                anchors.margins: -Theme.spaceXs
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: backend.setGroupCollapsed(group.groupId, true)
            }
        }
    }

    DragArea {
        visible: group.framed
        anchors { right: parent.right; bottom: parent.bottom }
        width: Theme.badgeSize
        height: Theme.badgeSize
        cursorShape: Qt.SizeFDiagCursor
        space: group.parent
        origin: Qt.point(group.gx + group.gw, group.gy + group.gh)
        grid: group.grid

        onMoved: function (x, y, snap) {
            backend.resizeGroup(group.groupId, x, y, snap)
        }

        Text {
            anchors.centerIn: parent
            text: "◢"
            color: group.strokeColor
            font.pixelSize: 10
        }
    }

    Item {
        id: box
        visible: !group.framed
        x: group.ax - width / 2
        y: group.ay - height / 2
        width: Math.max(Theme.nodeHeight,
                        boxLabel.implicitWidth + (group.collapsed ? 28 : 20))
        height: Theme.nodeHeight

        Rectangle {
            visible: group.groupSelected
            anchors.centerIn: parent
            width: parent.width + 12
            height: parent.height + 12
            radius: group.round ? height / 2 : Theme.radiusMd + 6
            color: "transparent"
            border.color: Theme.marked
            border.width: Theme.strokeRing
        }

        Rectangle {
            visible: group.tree
            anchors.fill: parent
            radius: group.round ? height / 2 : Theme.radiusMd
            color: group.nodeColor
            border.color: boxArea.containsMouse ? Theme.foreground
                                                : Theme.nodeStroke
            border.width: Theme.strokeNode
            opacity: group.nodeOpacity
        }

        Item {
            visible: group.collapsed
            anchors.fill: parent

            Rectangle {
                x: 7
                y: 7
                width: box.width - 8
                height: box.height - 8
                radius: Theme.radiusMd
                color: Qt.darker(Theme.accent, 1.8)
                border.color: Qt.alpha(Theme.nodeStroke, 0.5)
                border.width: 1.5
            }
            Rectangle {
                x: 3.5
                y: 3.5
                width: box.width - 8
                height: box.height - 8
                radius: Theme.radiusMd
                color: Qt.darker(Theme.accent, 1.35)
                border.color: Qt.alpha(Theme.nodeStroke, 0.7)
                border.width: 1.5
            }
            Rectangle {
                width: box.width - 8
                height: box.height - 8
                radius: Theme.radiusMd
                color: Theme.accent
                border.color: Theme.nodeStroke
                border.width: Theme.strokeNode
            }
        }

        Text {
            id: boxLabel
            anchors.centerIn: parent
            anchors.horizontalCenterOffset: group.collapsed ? -4 : 0
            anchors.verticalCenterOffset: group.collapsed ? -4 : 0
            text: group.title
            color: Theme.foreground
            font.bold: true
            font.pixelSize: 15
            style: Text.Outline
            styleColor: Theme.labelOutline
        }

        Rectangle {
            visible: group.collapsed
            x: -7
            y: -7
            width: Theme.badgeSize
            height: Theme.badgeSize
            radius: Theme.badgeSize / 2
            color: Theme.badge
            border.color: Theme.edge
            border.width: Theme.strokeHairline
            Text {
                anchors.centerIn: parent
                text: group.memberCount
                color: Theme.badgeText
                font.pixelSize: 10
                font.bold: true
            }
        }

        Rectangle {
            visible: group.tree && group.degree > 0
            anchors { right: parent.right; top: parent.top
                      rightMargin: -5; topMargin: -5 }
            width: Theme.badgeSize
            height: Theme.badgeSize
            radius: Theme.badgeSize / 2
            color: Theme.badge
            border.color: Theme.edge
            border.width: Theme.strokeHairline
            Text {
                anchors.centerIn: parent
                text: group.degree
                color: Theme.badgeText
                font.pixelSize: 10
                font.bold: true
            }
        }

        DragArea {
            id: boxArea
            anchors.fill: parent
            cursorShape: Qt.SizeAllCursor
            space: group.parent
            origin: group.tree ? Qt.point(group.gx + group.ax, group.gy + group.ay)
                               : Qt.point(group.gx, group.gy)
            grid: group.grid

            onMoved: function (x, y, snap) {
                backend.moveGroup(group.groupId, x, y, snap)
            }
            onClicked: function (mouse) {
                if (!dragged)
                    group.tap(mouse.modifiers)
            }
            onDoubleClicked: backend.setGroupCollapsed(group.groupId,
                                                       !group.collapsed)
        }
    }
}
