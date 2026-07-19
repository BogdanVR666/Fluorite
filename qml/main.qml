import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts
import Graphs

/*
 * Головне вікно: режими роботи, робоче поле з ребрами (EdgeLayer,
 * малюється на боці Python) та вершинами (Repeater із Node), панель
 * класів (ClassPanel), контекстні меню вершини (NodeMenu) та ребра
 * (EdgeMenu). Уся логіка застосунку живе тут; решта — "дурні" компоненти.
 */
ApplicationWindow {
    id: root
    width: 1100
    height: 720
    visible: true
    title: "Fluorite"
    color: Theme.background

    property string statusMsg: ""

    // --- класи вершин і ребер ---
    // кеш backend.classList(родина); оновлюється за сигналами бекенда
    property var nodeClasses: []
    property var edgeClasses: []
    // класи, які отримають нові вершини та нові ребра
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
        // Лічильники елементів у класах живуть у classList. Слухаємо
        // summaryChanged, а не graphChanged: бекенд шле його з паузою,
        // тож імпорт файла чи кліка на сотні вершин не перебудовують
        // список класів (і не переверстують панель) на кожен елемент.
        function onSummaryChanged() { root.refreshClasses() }
    }

    // --- виділення рамкою ---
    // Сам набір виділених живе в бекенді (роль nodeSelected моделі);
    // тут лише геометрія гумової рамки, поки її тягнуть.
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

    // --- створення ребра перетягуванням ПКМ ---
    // Вершина-джерело під час right-drag; -1 — перетягування немає
    property int edgeSourceId: -1
    property real edgeSrcX: 0
    property real edgeSrcY: 0
    property real edgeDragX: 0
    property real edgeDragY: 0

    function resetSelection() {
        backend.clearSelection()
        root.statusMsg = ""
    }

    // --- розкладка контекстних меню ---
    // Точка, у якій викликали меню (координати робочого поля). Меню
    // прив'язують до неї x/y біндингами, тож позиція перераховується,
    // коли стане відомою справжня висота (вміст верстається після open)
    // і коли він змінюється на льоту — наприклад, росте поле опису.
    property point menuAnchor: Qt.point(0, 0)

    // Меню розкривається вниз-праворуч від курсора, а якщо там не влазить
    // у робоче поле — у протилежний бік. Інакше в нижніх вершин пункт
    // «Видалити» лишався б за краєм вікна.
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

    // Відкрити контекстне меню вершини id у точці (px, py) робочого поля
    function openNodeMenu(id, px, py) {
        // ПКМ по невиділеній вершині робить її єдиною виділеною — тоді
        // меню завжди діє рівно на поточне виділення, як у файлових
        // менеджерах, і не треба окремої гілки "одна вершина / група"
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

    // Відкрити контекстне меню ребра klass:(a, b) у точці (px, py)
    // робочого поля. Клас — частина адреси ребра: на одній парі вершин
    // можуть співіснувати ребра різних класів.
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

    // ЛКМ по порожньому полю: або завершення рамки, або звичайний клік
    function finishBandOrClick(mx, my, modifiers) {
        var wasBanding = root.banding
        root.banding = false
        var r = root.bandRect
        // мікрорух мишею під час кліку — це клік, а не рамка
        if (wasBanding && (r.width >= 4 || r.height >= 4)) {
            var hits = backend.selectInRect(r.x, r.y, r.width, r.height,
                                            root.bandAdditive)
            root.statusMsg = hits > 0
                ? "Виділено вершин: " + backend.selectionCount
                : "У рамку не потрапила жодна вершина"
            return
        }
        // Клік по полю при наявному виділенні лише знімає його: перший
        // клік скидає, і тільки наступний створює вершину. Shift тримає
        // виділення, тож із ним вершина створюється одразу.
        if (backend.selectionCount > 0
                && (modifiers & Qt.ShiftModifier) === 0) {
            backend.clearSelection()
            root.statusMsg = ""
            return
        }
        backend.addNode(mx, my, root.currentClass)
    }

    function handleNodeTap(id, modifiers) {
        // Shift набирає виділення по одній, звичайний клік — рівно одна
        backend.selectNode(id, (modifiers & Qt.ShiftModifier) !== 0)
        root.statusMsg = backend.selectionCount > 1
            ? "Виділено вершин: " + backend.selectionCount : ""
    }

    // Delete прибирає все виділення; Escape — знімає його
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

    // ============ Панель класів елементів (вершин і ребер) ============
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

            // ЛКМ обробляємо в onReleased, а не в onClicked: інакше клік
            // приходив би ще й після протягування рамки виділення.
            onPressed: function (mouse) {
                if (mouse.button === Qt.LeftButton) {
                    // Рамку починаємо завжди: якщо мишу не зрушили,
                    // onReleased розпізнає це як звичайний клік
                    root.bandAdditive =
                        (mouse.modifiers & Qt.ShiftModifier) !== 0
                    root.bandX0 = root.bandX1 = mouse.x
                    root.bandY0 = root.bandY1 = mouse.y
                    root.banding = true
                    return
                }
                var id = backend.nodeAt(mouse.x, mouse.y)
                if (id === -1) {
                    // ПКМ повз вершини — можливо, влучили в ребро
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
                canvas.requestPaint()
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
                canvas.requestPaint()
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
                    // Відпустили на тій самій вершині — контекстне меню
                    root.openNodeMenu(src, mouse.x, mouse.y)
                }
                canvas.requestPaint()
            }
        }

        // Шар ребер: Python малює їх напряму з графа (без edgeList)
        // і сам перемальовується за сигналами бекенда
        EdgeLayer {
            anchors.fill: parent
            source: backend
        }

        // Пунктирна "гумка" під час створення ребра ПКМ;
        // перемальовується лише під час right-drag
        Canvas {
            id: canvas
            anchors.fill: parent
            onPaint: {
                var ctx = getContext("2d")
                ctx.clearRect(0, 0, width, height)
                if (root.edgeSourceId === -1)
                    return
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

        // Шар вершин — модель приходить із Python
        Repeater {
            model: backend.nodesModel

            delegate: Node {
                id: nodeItem

                onTapped: function (modifiers) {
                    root.handleNodeTap(nodeId, modifiers)
                }
                onMoved: function (cx, cy) {
                    // тягнемо одну з виділених — їде вся група
                    if (nodeItem.nodeSelected && backend.selectionCount > 1)
                        backend.moveSelectionTo(nodeId, cx, cy)
                    else
                        backend.moveNode(nodeId, cx, cy)
                }
            }
        }

        // Гумова рамка виділення — поверх вершин (у них z 1..2)
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

        // Контекстне меню вершини (ПКМ по вершині): стиль + видалення
        NodeMenu {
            id: nodeMenu
            classes: root.nodeClasses

            x: root.menuX(width)
            y: root.menuY(height)

            // скільки вершин зачепить дія (текст правимо лише в одної)
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

        // Контекстне меню ребра (ПКМ по ребру): стиль лінії + видалення
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
                // переносить ребро в шар іншого класу; не вдасться, якщо
                // на цій парі вже є ребро цільового класу
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
                // напрямленість і підпис "A → B" беруться з дизайну класу
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