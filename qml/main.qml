import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Shapes
import Graphs

ApplicationWindow {
    id: root
    width: 1100
    height: 720
    visible: true
    title: "Fluorite"
    color: Theme.background

    property var nodeClasses: []
    property var edgeClasses: []

    function refreshClasses() {
        root.nodeClasses = backend.classList("node")
        root.edgeClasses = backend.classList("edge")
    }
    Component.onCompleted: refreshClasses()

    Connections {
        target: backend
        function onClassesChanged() { root.refreshClasses() }
        function onSummaryChanged() { root.refreshClasses() }
    }

    property bool banding: false
    property bool bandAdditive: false
    property real bandX0: 0
    property real bandY0: 0
    property real bandX1: 0
    property real bandY1: 0
    readonly property rect bandRect: Qt.rect(Math.min(bandX0, bandX1),
                                             Math.min(bandY0, bandY1),
                                             Math.abs(bandX1 - bandX0),
                                             Math.abs(bandY1 - bandY0))

    property int edgeSourceId: -1
    property real edgeSrcX: 0
    property real edgeSrcY: 0
    property real edgeDragX: 0
    property real edgeDragY: 0

    property point menuAnchor: Qt.point(0, 0)

    function menuX(w) {
        return root.menuAnchor.x + w <= workspace.width ? root.menuAnchor.x
             : root.menuAnchor.x - w >= 0 ? root.menuAnchor.x - w
             : Math.max(0, workspace.width - w)
    }
    function menuY(h) {
        return root.menuAnchor.y + h <= workspace.height ? root.menuAnchor.y
             : root.menuAnchor.y - h >= 0 ? root.menuAnchor.y - h
             : Math.max(0, workspace.height - h)
    }

    function openNodeMenu(id, px, py) {
        if (!backend.isSelected(id))
            backend.selectNode(id, false)
        nodeMenu.targetId = id
        if (!nodeMenu.refresh())
            return
        root.menuAnchor = Qt.point(px, py)
        nodeMenu.open()
    }

    function openEdgeMenu(id, px, py) {
        edgeMenu.edgeId = id
        if (!edgeMenu.refresh())
            return
        root.menuAnchor = Qt.point(px, py)
        edgeMenu.open()
    }

    function finishBandOrClick(mx, my, modifiers) {
        var wasBanding = root.banding
        root.banding = false
        var r = root.bandRect
        if (wasBanding && (r.width >= 4 || r.height >= 4)) {
            backend.selectInRect(r.x, r.y, r.width, r.height,
                                 root.bandAdditive)
            return
        }
        if (backend.selectionCount > 0
                && (modifiers & Qt.ShiftModifier) === 0) {
            backend.clearSelection()
            return
        }
        backend.addNode(mx, my, classPanel.currentNodeClass)
    }

    Shortcut {
        sequences: [StandardKey.Delete, "Backspace"]
        enabled: backend.selectionCount > 0
        onActivated: backend.removeSelection()
    }
    Shortcut {
        sequence: "Escape"
        onActivated: backend.clearSelection()
    }
    Shortcut {
        sequence: "Ctrl+Z"
        enabled: classPanel.keyboard
        onActivated: backend.undo()
    }
    Shortcut {
        sequence: "Ctrl+Shift+Z"
        enabled: classPanel.keyboard
        onActivated: backend.redo()
    }

    footer: ToolBar {
        background: Rectangle { color: Theme.statusBar }
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: Theme.spaceMd
            anchors.rightMargin: Theme.spaceMd
            spacing: Theme.spaceMd

            Label {
                color: Theme.mutedText
                text: backend.stats
            }

            Item { Layout.fillWidth: true }

            Label {
                color: Theme.statusText
                elide: Text.ElideRight
                Layout.maximumWidth: 600
                text: backend.status
            }
        }
    }

    ClassPanel {
        id: classPanel
        anchors { left: parent.left; top: parent.top; bottom: parent.bottom }

        nodeClasses: root.nodeClasses
        edgeClasses: root.edgeClasses
        keyboard: !nodeMenu.opened && !edgeMenu.opened
                  && !(root.activeFocusItem instanceof TextInput)
                  && !(root.activeFocusItem instanceof TextEdit)
        arrows: backend.selectionCount === 0
    }

    Item {
        id: workspace
        anchors { left: classPanel.right; right: parent.right
                  top: parent.top; bottom: parent.bottom }

        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.LeftButton | Qt.RightButton

            onPressed: function (mouse) {
                workspace.forceActiveFocus()
                if (mouse.button === Qt.LeftButton) {
                    root.bandAdditive =
                        (mouse.modifiers & Qt.ShiftModifier) !== 0
                    root.bandX0 = root.bandX1 = mouse.x
                    root.bandY0 = root.bandY1 = mouse.y
                    root.banding = true
                    return
                }
                var id = backend.nodeAt(mouse.x, mouse.y)
                if (id === -1) {
                    var edge = backend.edgeAt(mouse.x, mouse.y)
                    if (edge !== -1)
                        root.openEdgeMenu(edge, mouse.x, mouse.y)
                    return
                }
                var info = backend.nodeInfo(id)
                root.edgeSourceId = id
                root.edgeSrcX = info.x
                root.edgeSrcY = info.y
                root.edgeDragX = mouse.x
                root.edgeDragY = mouse.y
            }

            onPositionChanged: function (mouse) {
                if (root.banding) {
                    root.bandX1 = mouse.x
                    root.bandY1 = mouse.y
                    return
                }
                if (root.edgeSourceId === -1)
                    return
                root.edgeDragX = mouse.x
                root.edgeDragY = mouse.y
            }

            onReleased: function (mouse) {
                if (mouse.button === Qt.LeftButton) {
                    root.finishBandOrClick(mouse.x, mouse.y, mouse.modifiers)
                    return
                }
                if (root.edgeSourceId === -1)
                    return
                var src = root.edgeSourceId
                root.edgeSourceId = -1
                var tgt = backend.nodeAt(mouse.x, mouse.y)
                if (tgt !== -1 && tgt !== src) {
                    backend.addEdge(src, tgt, classPanel.currentEdgeClass)
                } else if (tgt === src) {
                    root.openNodeMenu(src, mouse.x, mouse.y)
                }
            }
        }

        EdgeLayer {
            anchors.fill: parent
            source: backend
        }

        Shape {
            visible: root.edgeSourceId !== -1
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                fillColor: "transparent"
                strokeColor: Theme.selection
                strokeWidth: Theme.edgeDraftWidth
                strokeStyle: ShapePath.DashLine
                dashPattern: Theme.edgeDraftDash.map(function (v) {
                    return v / Theme.edgeDraftWidth
                })
                startX: root.edgeSrcX
                startY: root.edgeSrcY
                PathLine { x: root.edgeDragX; y: root.edgeDragY }
            }
        }

        Repeater {
            model: backend.nodesModel

            delegate: Node {
                edgeClass: classPanel.currentEdgeClass
            }
        }

        Rectangle {
            z: 3
            visible: root.banding
            x: root.bandRect.x
            y: root.bandRect.y
            width: root.bandRect.width
            height: root.bandRect.height
            color: Theme.markedFill
            border.color: Theme.marked
            border.width: Theme.strokeHairline
        }

        NodeMenu {
            id: nodeMenu
            classes: root.nodeClasses

            x: root.menuX(width)
            y: root.menuY(height)

            selectionCount: backend.selectionCount
            edgeClass: classPanel.currentEdgeClass
        }

        EdgeMenu {
            id: edgeMenu
            classes: root.edgeClasses

            x: root.menuX(width)
            y: root.menuY(height)
        }
    }
}
