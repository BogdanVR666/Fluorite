import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
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

    property string statusMsg: ""

    property var nodeClasses: []
    property var edgeClasses: []
    property string currentClass: "Звичайна"
    property string currentEdgeClass: "Звичайне"

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
    property bool bandAdditive: false      // Shift — додавати до наявного
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

    function resetSelection() {
        backend.clearSelection()
        root.statusMsg = ""
    }

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
        var info = backend.nodeInfo(id)
        nodeMenu.targetId = id
        nodeMenu.targetLabel = info.label
        nodeMenu.currentDescription = info.description
        nodeMenu.currentShape = info.shape
        nodeMenu.currentColor = String(info.color)
        nodeMenu.currentOpacity = info.opacity
        nodeMenu.currentClass = info.klass
        nodeMenu.groupId = info.groupId
        nodeMenu.groupLabel = info.groupLabel
        nodeMenu.isGroup = info.isGroup === true
        nodeMenu.ownGroupId = info.ownGroupId
        nodeMenu.memberCount = info.memberCount
        root.menuAnchor = Qt.point(px, py)
        nodeMenu.open()
    }

    function openEdgeMenu(klass, a, b, px, py) {
        var info = backend.edgeInfo(klass, a, b)
        if (!info.klass)
            return
        edgeMenu.targetA = a
        edgeMenu.targetB = b
        edgeMenu.targetLabel = info.label
        edgeMenu.currentLine = info.line
        edgeMenu.currentWidth = info.width
        edgeMenu.currentColor = String(info.color)
        edgeMenu.currentClass = info.klass
        edgeMenu.currentDirected = info.directed === true
        root.menuAnchor = Qt.point(px, py)
        edgeMenu.open()
    }

    function finishBandOrClick(mx, my, modifiers) {
        var wasBanding = root.banding
        root.banding = false
        var r = root.bandRect
        if (wasBanding && (r.width >= 4 || r.height >= 4)) {
            var hits = backend.selectInRect(r.x, r.y, r.width, r.height,
                                            root.bandAdditive)
            root.statusMsg = hits > 0
                ? "Виділено вершин: " + backend.selectionCount
                : "У рамку не потрапила жодна вершина"
            return
        }
        if (backend.selectionCount > 0
                && (modifiers & Qt.ShiftModifier) === 0) {
            backend.clearSelection()
            root.statusMsg = ""
            return
        }
        backend.addNode(mx, my, root.currentClass)
    }

    function handleNodeTap(id, modifiers) {
        backend.selectNode(id, (modifiers & Qt.ShiftModifier) !== 0)
        root.statusMsg = backend.selectionCount > 1
            ? "Виділено вершин: " + backend.selectionCount : ""
    }

    Shortcut {
        sequences: [StandardKey.Delete, "Backspace"]
        onActivated: {
            if (backend.selectionCount === 0)
                return
            var n = backend.selectionCount
            backend.removeSelection()
            root.resetSelection()          // скидає й statusMsg
            root.statusMsg = "Видалено вершин: " + n
        }
    }
    Shortcut {
        sequence: "Escape"
        onActivated: {
            backend.clearSelection()
            root.resetSelection()
        }
    }

    footer: ToolBar {
        background: Rectangle { color: Theme.statusBar }
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 12
            anchors.rightMargin: 12
            spacing: 12

            Label {
                color: Theme.mutedText
                text: backend.stats   // рахує NetworkX на боці Python
            }

            Item { Layout.fillWidth: true }

            Label {
                color: Theme.statusText
                elide: Text.ElideRight
                Layout.maximumWidth: 600
                text: root.statusMsg !== ""
                      ? root.statusMsg
                      : "ЛКМ по полю — нова вершина, ЛКМ-перетяг — рамка виділення (Shift — додати до наявного); Shift+ЛКМ по вершині — виділити ще одну, Delete — видалити виділені; ПКМ по вершині чи ребру — меню, ПКМ-перетяг між вершинами — ребро"
            }
        }
    }

    ClassPanel {
        id: classPanel
        anchors { left: parent.left; top: parent.top; bottom: parent.bottom }

        nodeClasses: root.nodeClasses
        edgeClasses: root.edgeClasses
        currentNodeClass: root.currentClass
        currentEdgeClass: root.currentEdgeClass

        onClassPicked: function (family, name) {
            if (family === "node")
                root.currentClass = name
            else
                root.currentEdgeClass = name
        }
        onConnectClassRequested: function (name) {
            root.statusMsg = backend.connectClassNodes(name,
                                                       root.currentEdgeClass)
        }
        onUpdateRequested: function (family, name, design) {
            backend.updateClass(family, name, design)
        }
        onCreateRequested: function (family, name, design) {
            if (backend.createClass(family, name, design)) {
                if (family === "node")
                    root.currentClass = name
                else
                    root.currentEdgeClass = name
                classPanel.resetForm()
            } else {
                root.statusMsg = "Клас «" + name + "» вже існує"
            }
        }
        onSaveRequested: saveDialog.open()
        onOpenRequested: openDialog.open()
        onClearRequested: {
            backend.clear()
            root.resetSelection()
        }
    }

    FileDialog {
        id: saveDialog
        title: "Зберегти граф"
        fileMode: FileDialog.SaveFile
        nameFilters: ["Граф JSON (*.json)", "Усі файли (*)"]
        defaultSuffix: "json"
        onAccepted: root.statusMsg = backend.saveToFile(selectedFile)
    }

    FileDialog {
        id: openDialog
        title: "Відкрити граф"
        fileMode: FileDialog.OpenFile
        nameFilters: ["Граф JSON (*.json)", "Усі файли (*)"]
        onAccepted: {
            root.resetSelection()
            root.statusMsg = backend.loadFromFile(selectedFile)
        }
    }

    Item {
        id: workspace
        anchors { left: classPanel.right; right: parent.right
                  top: parent.top; bottom: parent.bottom }

        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.LeftButton | Qt.RightButton

            onPressed: function (mouse) {
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
                    if (edge.a !== undefined)
                        root.openEdgeMenu(edge.klass, edge.a, edge.b,
                                          mouse.x, mouse.y)
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
                    if (!backend.addEdge(src, tgt, root.currentEdgeClass))
                        root.statusMsg = "Таке ребро вже існує"
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
                strokeWidth: 3
                strokeStyle: ShapePath.DashLine
                dashPattern: [2, 5 / 3]   // 6 і 5 px у одиницях товщини
                startX: root.edgeSrcX
                startY: root.edgeSrcY
                PathLine { x: root.edgeDragX; y: root.edgeDragY }
            }
        }

        Repeater {
            model: backend.nodesModel

            delegate: Node {
                id: nodeItem

                onTapped: function (modifiers) {
                    root.handleNodeTap(nodeId, modifiers)
                }
                onMoved: function (cx, cy) {
                    if (nodeItem.nodeSelected && backend.selectionCount > 1)
                        backend.moveSelectionTo(nodeId, cx, cy)
                    else
                        backend.moveNode(nodeId, cx, cy)
                }
            }
        }

        Rectangle {
            z: 3
            visible: root.banding
            x: root.bandRect.x
            y: root.bandRect.y
            width: root.bandRect.width
            height: root.bandRect.height
            color: Qt.alpha(Theme.marked, 0.12)
            border.color: Theme.marked
            border.width: 1
        }

        NodeMenu {
            id: nodeMenu
            classes: root.nodeClasses

            x: root.menuX(width)
            y: root.menuY(height)

            selectionCount: backend.selectionCount

            onClassPicked: function (name) {
                if (targetId === -1)
                    return
                backend.setSelectionClass(name)
                currentClass = name
                var info = backend.nodeInfo(targetId)
                currentShape = info.shape
                currentColor = String(info.color)
                currentOpacity = info.opacity
            }
            onLabelEdited: function (text) {
                if (targetId === -1)
                    return
                backend.setNodeLabel(targetId, text)
                targetLabel = text
            }
            onDescriptionEdited: function (text) {
                if (targetId === -1)
                    return
                backend.setNodeDescription(targetId, text)
                currentDescription = text
            }
            onOpacityPicked: function (opacity) {
                if (targetId === -1)
                    return
                backend.setSelectionOpacity(opacity)
                currentOpacity = opacity
            }
            onConnectToClassRequested: function (name) {
                if (targetId !== -1)
                    root.statusMsg = backend.connectSelectionToClass(
                        name, root.currentEdgeClass)
            }
            onConnectSelectedRequested: {
                root.statusMsg = backend.connectSelection(root.currentEdgeClass)
                close()
            }
            onGroupSelectedRequested: {
                root.statusMsg = backend.groupSelection()
                close()
            }
            onCollapseGroupRequested: {
                backend.setGroupCollapsed(groupId, true)
                close()
            }
            onExpandGroupRequested: {
                if (ownGroupId !== -1)
                    backend.setGroupCollapsed(ownGroupId, false)
                close()
            }
            onUngroupRequested: {
                if (ownGroupId !== -1)
                    backend.ungroup(ownGroupId)
                close()
            }
            onShapePicked: function (shape) {
                if (targetId === -1)
                    return
                backend.setSelectionShape(shape)
                currentShape = shape
            }
            onColorPicked: function (color) {
                if (targetId === -1)
                    return
                backend.setSelectionColor(color)
                currentColor = color
            }
            onRemoveRequested: {
                var n = backend.selectionCount
                backend.removeSelection()
                root.resetSelection()      // скидає й statusMsg
                root.statusMsg = "Видалено вершин: " + n
                close()
            }
        }

        EdgeMenu {
            id: edgeMenu
            classes: root.edgeClasses

            x: root.menuX(width)
            y: root.menuY(height)

            onLinePicked: function (line) {
                if (targetA === -1)
                    return
                backend.setEdgeLine(currentClass, targetA, targetB, line)
                currentLine = line
            }
            onWidthPicked: function (width) {
                if (targetA === -1)
                    return
                backend.setEdgeWidth(currentClass, targetA, targetB, width)
                currentWidth = width
            }
            onColorPicked: function (color) {
                if (targetA === -1)
                    return
                backend.setEdgeColor(currentClass, targetA, targetB, color)
                currentColor = color
            }
            onClassPicked: function (name) {
                if (targetA === -1)
                    return
                if (!backend.setEdgeClass(currentClass, targetA, targetB,
                                          name)) {
                    root.statusMsg = "Ребро класу «" + name
                        + "» між цими вершинами вже існує"
                    return
                }
                currentClass = name
                var info = backend.edgeInfo(name, targetA, targetB)
                currentLine = info.line
                currentWidth = info.width
                currentColor = String(info.color)
                currentDirected = info.directed === true
                targetLabel = info.label
            }
            onReverseRequested: {
                if (targetA === -1)
                    return
                backend.reverseEdge(currentClass, targetA, targetB)
                targetLabel = backend.edgeInfo(currentClass,
                                               targetA, targetB).label
            }
            onRemoveRequested: {
                if (targetA !== -1)
                    backend.removeEdge(currentClass, targetA, targetB)
                close()
            }
        }
    }
}
