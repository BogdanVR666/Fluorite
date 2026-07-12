import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts

/*
 * Головне вікно: режими роботи, робоче поле з ребрами (Canvas)
 * та вершинами (Repeater із Node), панель стилю (StyleMenu).
 * Уся логіка застосунку живе тут; Node і StyleMenu — "дурні" компоненти.
 */
ApplicationWindow {
    id: root
    width: 1100
    height: 720
    visible: true
    title: "Graph IDE"
    color: Theme.background

    // Режими: 0 — вершина, 1 — ребро, 2 — переміщення, 3 — найкоротший шлях
    property int mode: 0
    // nodeId вершини, обраної першою (для ребра або шляху); -1 — не обрано
    property int selectedId: -1
    property string statusMsg: ""

    // --- класи вершин ---
    // кеш backend.classList(); оновлюється за сигналами бекенда
    property var nodeClasses: []
    // клас, який отримають нові вершини
    property string currentClass: "Звичайна"

    function refreshClasses() { root.nodeClasses = backend.classList() }
    Component.onCompleted: refreshClasses()

    Connections {
        target: backend
        function onClassesChanged() { root.refreshClasses() }
        // лічильники вершин у класах живуть у classList
        function onGraphChanged() { root.refreshClasses() }
    }

    // --- створення ребра перетягуванням ПКМ ---
    // Вершина-джерело під час right-drag; -1 — перетягування немає
    property int edgeSourceId: -1
    property real edgeSrcX: 0
    property real edgeSrcY: 0
    property real edgeDragX: 0
    property real edgeDragY: 0

    function resetSelection() {
        root.selectedId = -1
        root.statusMsg = ""
    }

    // Відкрити контекстне меню вершини id у точці (px, py) робочого поля
    function openNodeMenu(id, px, py) {
        var info = backend.nodeInfo(id)
        nodeMenu.targetId = id
        nodeMenu.targetLabel = info.label
        nodeMenu.currentShape = info.shape
        nodeMenu.currentColor = String(info.color)
        nodeMenu.currentClass = info.klass
        nodeMenu.x = px
        nodeMenu.y = py
        nodeMenu.open()
    }

    function handleNodeTap(id) {
        if (root.mode === 1) {
            if (root.selectedId === -1) {
                root.selectedId = id
            } else if (root.selectedId === id) {
                root.selectedId = -1
            } else {
                if (!backend.addEdge(root.selectedId, id))
                    root.statusMsg = "Таке ребро вже існує"
                root.selectedId = -1
            }
        } else if (root.mode === 3) {
            if (root.selectedId === -1) {
                root.selectedId = id
            } else if (root.selectedId === id) {
                root.selectedId = -1
            } else {
                root.statusMsg = backend.findShortestPath(root.selectedId, id)
                root.selectedId = -1
            }
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
                      : root.mode === 0
                        ? "ЛКМ по полю — нова вершина; ПКМ по вершині — меню (стиль/видалити); ПКМ-перетяг між вершинами — ребро"
                        : root.mode === 1
                          ? (root.selectedId === -1
                             ? "Оберіть першу вершину ребра (або ПКМ-перетяг між вершинами)"
                             : "Оберіть другу вершину ребра")
                          : root.mode === 2
                            ? "Перетягуйте вершини мишею"
                            : (root.selectedId === -1
                               ? "Оберіть початкову вершину шляху"
                               : "Оберіть кінцеву вершину шляху")
            }
        }
    }

    // ==================== Панель класів вершин ====================
    ClassPanel {
        id: classPanel
        anchors { left: parent.left; top: parent.top; bottom: parent.bottom }

        classes: root.nodeClasses
        currentClass: root.currentClass

        onClassPicked: function (name) { root.currentClass = name }
        onConnectClassRequested: function (name) {
            root.statusMsg = backend.connectClassNodes(name)
        }
        onCreateRequested: function (name, shape, color) {
            if (backend.createNodeClass(name, shape, color)) {
                root.currentClass = name
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

    // ==================== Робоче поле ====================
    Item {
        id: workspace
        anchors { left: classPanel.right; right: parent.right
                  top: parent.top; bottom: parent.bottom }

        // ЛКМ — клік по порожньому місцю; ПКМ — меню/створення ребра.
        // Права кнопка "провалюється" крізь вершини (їхній MouseArea
        // приймає лише ЛКМ), тож увесь right-drag обробляємо тут через
        // хіт-тест backend.nodeAt().
        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.LeftButton | Qt.RightButton

            onClicked: function (mouse) {
                if (mouse.button !== Qt.LeftButton)
                    return
                if (root.mode === 0) {
                    backend.addNode(mouse.x, mouse.y, root.currentClass)
                } else {
                    root.resetSelection()
                }
            }

            onPressed: function (mouse) {
                if (mouse.button !== Qt.RightButton)
                    return
                var id = backend.nodeAt(mouse.x, mouse.y)
                if (id === -1)
                    return
                var info = backend.nodeInfo(id)
                root.edgeSourceId = id
                root.edgeSrcX = info.x
                root.edgeSrcY = info.y
                root.edgeDragX = mouse.x
                root.edgeDragY = mouse.y
                canvas.requestPaint()
            }

            onPositionChanged: function (mouse) {
                if (root.edgeSourceId === -1)
                    return
                root.edgeDragX = mouse.x
                root.edgeDragY = mouse.y
                canvas.requestPaint()
            }

            onReleased: function (mouse) {
                if (mouse.button !== Qt.RightButton || root.edgeSourceId === -1)
                    return
                var src = root.edgeSourceId
                root.edgeSourceId = -1
                var tgt = backend.nodeAt(mouse.x, mouse.y)
                if (tgt !== -1 && tgt !== src) {
                    if (!backend.addEdge(src, tgt))
                        root.statusMsg = "Таке ребро вже існує"
                } else if (tgt === src) {
                    // Відпустили на тій самій вершині — контекстне меню
                    root.openNodeMenu(src, mouse.x, mouse.y)
                }
                canvas.requestPaint()
            }
        }

        // Шар ребер — координати запитуємо у бекенда
        Canvas {
            id: canvas
            anchors.fill: parent
            onPaint: {
                var ctx = getContext("2d")
                ctx.clearRect(0, 0, width, height)
                var edges = backend.edgeList()
                for (var i = 0; i < edges.length; i++) {
                    var e = edges[i]
                    ctx.strokeStyle = String(e.inPath ? Theme.edgeHighlight
                                                      : Theme.edge)
                    ctx.lineWidth = e.inPath ? 4.5 : 2.5
                    ctx.beginPath()
                    ctx.moveTo(e.x1, e.y1)
                    ctx.lineTo(e.x2, e.y2)
                    ctx.stroke()
                }

                // Пунктирна "гумка" під час створення ребра ПКМ
                if (root.edgeSourceId !== -1) {
                    ctx.strokeStyle = String(Theme.selection)
                    ctx.lineWidth = 3
                    ctx.setLineDash([6, 5])
                    ctx.beginPath()
                    ctx.moveTo(root.edgeSrcX, root.edgeSrcY)
                    ctx.lineTo(root.edgeDragX, root.edgeDragY)
                    ctx.stroke()
                    ctx.setLineDash([])
                }
            }
        }

        Connections {
            target: backend
            function onGraphChanged() { canvas.requestPaint() }
        }

        // при зміні теми ребра теж треба перемалювати
        Connections {
            target: Theme
            function onColorsChanged() { canvas.requestPaint() }
        }

        // Шар вершин — модель приходить із Python
        Repeater {
            model: backend.nodesModel

            delegate: Node {
                draggable: root.mode === 2
                selected: root.selectedId === nodeId

                onTapped: root.handleNodeTap(nodeId)
                onMoved: function (cx, cy) {
                    backend.moveNode(nodeId, cx, cy)
                }
            }
        }

        // Контекстне меню вершини (ПКМ по вершині): стиль + видалення
        NodeMenu {
            id: nodeMenu
            classes: root.nodeClasses

            onClassPicked: function (name) {
                if (targetId === -1)
                    return
                backend.setNodeClass(targetId, name)
                currentClass = name
                var info = backend.nodeInfo(targetId)
                currentShape = info.shape
                currentColor = String(info.color)
            }
            onConnectToClassRequested: function (name) {
                if (targetId !== -1)
                    root.statusMsg = backend.connectNodeToClass(targetId, name)
            }
            onShapePicked: function (shape) {
                if (targetId === -1)
                    return
                backend.setNodeShape(targetId, shape)
                currentShape = shape
            }
            onColorPicked: function (color) {
                if (targetId === -1)
                    return
                backend.setNodeColor(targetId, color)
                currentColor = color
            }
            onRemoveRequested: {
                if (targetId !== -1) {
                    backend.removeNode(targetId)
                    if (root.selectedId === targetId)
                        root.resetSelection()
                }
                close()
            }
        }
    }
}