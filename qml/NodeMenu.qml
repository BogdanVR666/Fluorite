import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

/*
 * Контекстне меню вершини: спливає при ПКМ на вершині, біля курсора.
 * Дозволяє змінити форму/колір саме цієї вершини або видалити її.
 * Суто презентаційний компонент — яку саме вершину редагувати
 * і що робити з натисканнями, вирішує власник (main.qml).
 */
Popup {
    id: menu

    property int targetId: -1          // яку вершину редагуємо/видаляємо
    property string targetLabel: ""
    property string currentDescription: ""
    property string currentShape: "circle"
    property string currentColor: Theme.nodePalette[0]
    property real currentOpacity: 1.0
    property string currentClass: ""   // клас цієї вершини
    property var classes: []           // [{name, shape, color, opacity, count}]

    // Скільки вершин зачепить дія. Стиль, клас і видалення застосовуються
    // до всього виділення, а от текст і опис — лише до targetId, бо для
    // групи вони не мають сенсу; тому при >1 ці поля ховаємо.
    property int selectionCount: 1
    readonly property bool group: selectionCount > 1

    // група вершин, якій належить targetId (-1 — нікому): розгорнуту
    // групу згортають назад через меню будь-якого її члена
    property int groupId: -1
    property string groupLabel: ""

    // сама вершина — метавершина групи (видима, отже група згорнута):
    // форма в неї незмінна, зате можна розгорнути чи розпустити групу
    property bool isGroup: false
    property int ownGroupId: -1
    property int memberCount: 0

    readonly property var classNames: classes.map(function (c) { return c.name })

    signal labelEdited(string text)
    signal descriptionEdited(string text)
    signal shapePicked(string shape)
    signal colorPicked(string color)
    signal opacityPicked(real opacity)
    signal classPicked(string name)
    signal connectToClassRequested(string name)
    signal connectSelectedRequested()
    signal groupSelectedRequested()
    signal collapseGroupRequested()
    signal expandGroupRequested()
    signal ungroupRequested()
    signal removeRequested()

    // TextArea не розрізняє редагування користувача і програмний запис,
    // тож на час заповнення полів при відкритті глушимо сигнали
    property bool syncing: false

    // ComboBox рве прив'язку currentIndex після вибору користувача,
    // тож виставляємо індекс щоразу при відкритті
    onOpened: {
        syncing = true
        labelField.text = targetLabel
        descArea.text = currentDescription
        opacitySlider.value = currentOpacity
        classCombo.currentIndex = classNames.indexOf(currentClass)
        connectCombo.currentIndex = -1
        syncing = false
    }

    // зміна класу вершини скидає прозорість на дизайн класу
    onCurrentOpacityChanged: opacitySlider.value = currentOpacity

    padding: 0
    modal: false
    focus: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    readonly property var shapeDefs: [
        { key: "circle",   glyph: "\u25CF" },  // ●
        { key: "square",   glyph: "\u25A0" },  // ■
        { key: "diamond",  glyph: "\u25C6" },  // ◆
        { key: "triangle", glyph: "\u25B2" }   // ▲
    ]
    readonly property var colorPalette: Theme.nodePalette

    background: Rectangle {
        color: Theme.popup
        radius: 10
        border.color: Theme.popupBorder
        border.width: 1
    }

    contentItem: Item {
        implicitWidth: 190
        implicitHeight: col.implicitHeight + 24

        ColumnLayout {
            id: col
            anchors.fill: parent
            anchors.margins: 12
            spacing: 10

            Label {
                text: menu.group ? "Виділено вершин: " + menu.selectionCount
                    : menu.isGroup ? "Група " + menu.targetLabel
                                     + " (" + menu.memberCount + ")"
                                   : "Вершина " + menu.targetLabel
                color: Theme.foreground
                font.bold: true
                font.pixelSize: 14
            }

            // дії метавершини: розгорнути групу назад чи розпустити її
            Button {
                visible: menu.isGroup && !menu.group
                text: "📂 Розгорнути групу"
                Layout.fillWidth: true
                onClicked: menu.expandGroupRequested()
            }

            Button {
                visible: menu.isGroup && !menu.group
                text: "✂ Розгрупувати"
                Layout.fillWidth: true
                onClicked: menu.ungroupRequested()
            }

            Label {
                visible: !menu.group
                text: "Текст"; color: Theme.mutedText; font.pixelSize: 12
            }

            TextField {
                id: labelField
                visible: !menu.group
                Layout.fillWidth: true
                placeholderText: "Підпис вершини"
                onTextEdited: menu.labelEdited(text)
            }

            Label {
                visible: !menu.group
                text: "Опис"; color: Theme.mutedText; font.pixelSize: 12
            }

            ScrollView {
                visible: !menu.group
                Layout.fillWidth: true
                Layout.preferredHeight: 56
                clip: true

                TextArea {
                    id: descArea
                    placeholderText: "Опис вершини…"
                    wrapMode: TextArea.Wrap
                    font.pixelSize: 12
                    onTextChanged: {
                        if (!menu.syncing)
                            menu.descriptionEdited(text)
                    }
                }
            }

            Label {
                // форма метавершини незмінна — "стопка" квадратів
                visible: !menu.isGroup
                text: "Форма"; color: Theme.mutedText; font.pixelSize: 12
            }

            GridLayout {
                visible: !menu.isGroup
                columns: 4
                columnSpacing: 6
                Repeater {
                    model: menu.shapeDefs
                    delegate: Rectangle {
                        required property var modelData
                        width: 38; height: 38; radius: 8
                        color: menu.currentShape === modelData.key
                               ? Theme.accent
                               : shapeHover.containsMouse ? Theme.hover
                                                          : Theme.control
                        border.width: menu.currentShape === modelData.key ? 0 : 1
                        border.color: Theme.border
                        Behavior on color { ColorAnimation { duration: 100 } }

                        Text {
                            anchors.centerIn: parent
                            text: parent.modelData.glyph
                            color: Theme.foreground
                            font.pixelSize: 18
                        }
                        MouseArea {
                            id: shapeHover
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: menu.shapePicked(parent.modelData.key)
                        }
                    }
                }
            }

            Label { text: "Колір"; color: Theme.mutedText; font.pixelSize: 12 }

            GridLayout {
                columns: 4
                columnSpacing: 6
                rowSpacing: 6
                Repeater {
                    model: menu.colorPalette
                    delegate: Rectangle {
                        required property string modelData
                        width: 38; height: 38; radius: 19
                        color: modelData
                        scale: colorHover.containsMouse ? 1.15 : 1.0
                        Behavior on scale { NumberAnimation { duration: 100 } }
                        border.width: menu.currentColor === modelData ? 3 : 0
                        border.color: Theme.foreground

                        MouseArea {
                            id: colorHover
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: menu.colorPicked(parent.modelData)
                        }
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Label {
                    text: "Прозорість"
                    color: Theme.mutedText
                    font.pixelSize: 12
                    Layout.fillWidth: true
                }
                Label {
                    text: Math.round(opacitySlider.value * 100) + "%"
                    color: Theme.mutedText
                    font.pixelSize: 12
                }
            }

            Slider {
                id: opacitySlider
                Layout.fillWidth: true
                from: 0.1
                to: 1.0
                onMoved: menu.opacityPicked(value)
            }

            Label { text: "Клас"; color: Theme.mutedText; font.pixelSize: 12 }

            ComboBox {
                id: classCombo
                Layout.fillWidth: true
                model: menu.classNames
                onActivated: function (index) {
                    menu.classPicked(textAt(index))
                }
            }

            // Діє як кнопка-меню: вибір пункту одразу з'єднує вершину
            // з усіма вершинами обраного класу
            ComboBox {
                id: connectCombo
                Layout.fillWidth: true
                displayText: "🔗 З'єднати з класом…"
                model: menu.classNames
                onActivated: function (index) {
                    menu.connectToClassRequested(textAt(index))
                    menu.close()
                }
            }

            Button {
                visible: menu.group
                text: "🔗 З'єднати виділені між собою"
                Layout.fillWidth: true
                onClicked: menu.connectSelectedRequested()
            }

            Button {
                visible: menu.group
                text: "🗂 Згорнути виділені у групу"
                Layout.fillWidth: true
                onClicked: menu.groupSelectedRequested()
            }

            Button {
                visible: menu.groupId !== -1
                text: "🗂 Згорнути групу «" + menu.groupLabel + "»"
                Layout.fillWidth: true
                onClicked: menu.collapseGroupRequested()
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.popupBorder }

            Button {
                text: menu.group ? "🗑 Видалити виділені (" + menu.selectionCount + ")"
                                 : "🗑 Видалити вершину"
                Layout.fillWidth: true
                palette.buttonText: Theme.error
                onClicked: menu.removeRequested()
            }
        }
    }
}
