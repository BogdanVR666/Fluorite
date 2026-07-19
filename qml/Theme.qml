pragma Singleton
import QtQuick

/*
 * Тема застосунку, сумісна з колірними темами VS Code.
 * `colors` зберігає стандартні ключі з секції "colors" JSON-теми VS Code,
 * тож будь-яка тема підключається без змін у решті коду:
 *   Theme.load(JSON.parse(вмістФайлаТеми))   // або лише його "colors"
 * Решта QML користується ролями нижче (Theme.background, Theme.accent...).
 */
QtObject {
    id: theme

    // Ключі VS Code; дефолт відтворює поточний вигляд застосунку
    property var colors: ({
        "editor.background":           "#222222",
        "editor.foreground":           "#ffffff",
        "titleBar.activeBackground":   "#2a2a3d",
        "statusBar.background":        "#222222",
        "statusBar.foreground":        "#a0a0c0",
        "sideBar.background":          "#222222",
        "menu.background":             "#26263a",
        "menu.border":                 "#44445e",
        "widget.border":               "#44445e",
        "button.background":           "#3d7bd9",
        "list.hoverBackground":        "#3a3a52",
        "input.background":            "#2f2f45",
        "descriptionForeground":       "#8888aa",
        "disabledForeground":          "#66668a",
        "focusBorder":                 "#f39c12",
        "badge.background":            "#2a2a3d",
        "badge.foreground":            "#ffffff",
        "errorForeground":             "#e74c3c",
        "editorLineNumber.foreground": "#7f8fd9",
        "terminal.ansiBlue":           "#3d7bd9",
        "terminal.ansiRed":            "#e74c3c",
        "terminal.ansiGreen":          "#27ae60",
        "terminal.ansiBrightGreen":    "#2ecc71",
        "terminal.ansiYellow":         "#f39c12",
        "terminal.ansiMagenta":        "#9b59b6",
        "terminal.ansiCyan":           "#1abc9c",
        "terminal.ansiBrightMagenta":  "#e84393",
        "terminal.ansiWhite":          "#95a5a6"
    })

    // Приймає розпарсений JSON теми VS Code цілком або лише його "colors"
    function load(vsTheme) {
        colors = vsTheme && vsTheme.colors ? vsTheme.colors : vsTheme
    }

    // Колір за ключем VS Code; теми пишуть альфу в кінці (#RRGGBBAA),
    // а QML чекає її на початку (#AARRGGBB) — конвертуємо на льоту
    function c(key, fallback) {
        var v = colors[key]
        if (v === undefined)
            return fallback
        if (v.length === 9)
            v = "#" + v.slice(7) + v.slice(1, 7)
        else if (v.length === 5)
            v = "#" + v[4] + v.slice(1, 4)
        return v
    }

    // ---- ролі застосунку, замаплені на ключі VS Code ----
    readonly property color background:    c("editor.background", "#1e1e1e")
    readonly property color foreground:    c("editor.foreground", "#d4d4d4")
    readonly property color toolbar:       c("titleBar.activeBackground", "#2a2a3d")
    readonly property color statusBar:     c("statusBar.background", toolbar)
    readonly property color statusText:    c("statusBar.foreground", mutedText)
    readonly property color panel:         c("sideBar.background", "#252526")
    readonly property color popup:         c("menu.background", panel)
    readonly property color border:        c("widget.border", "#454545")
    readonly property color popupBorder:   c("menu.border", border)
    readonly property color accent:        c("button.background", "#0e639c")
    readonly property color hover:         c("list.hoverBackground", "#2a2d2e")
    readonly property color control:       c("input.background", "#3c3c3c")
    readonly property color mutedText:     c("descriptionForeground", "#9d9d9d")
    readonly property color faintText:     c("disabledForeground", "#656565")
    readonly property color selection:     c("focusBorder", "#f39c12")
    readonly property color marked:        c("terminal.ansiBrightCyan", "#4dd0e1")
    readonly property color edge:          c("editorLineNumber.foreground", "#858585")
    readonly property color badge:         c("badge.background", "#4d4d4d")
    readonly property color badgeText:     c("badge.foreground", "#ffffff")
    readonly property color error:         c("errorForeground", "#f48771")

    // Палітра вершин — з ANSI-кольорів термінала (є в кожній темі VS Code)
    readonly property var nodePalette: [
        c("terminal.ansiBlue",          "#3d7bd9"),
        c("terminal.ansiRed",           "#e74c3c"),
        c("terminal.ansiGreen",         "#27ae60"),
        c("terminal.ansiYellow",        "#f39c12"),
        c("terminal.ansiMagenta",       "#9b59b6"),
        c("terminal.ansiCyan",          "#1abc9c"),
        c("terminal.ansiBrightMagenta", "#e84393"),
        c("terminal.ansiWhite",         "#95a5a6")
    ]
}
