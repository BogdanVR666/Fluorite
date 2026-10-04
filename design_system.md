# Fluorite

Інтерфейс Fluorite — візуального редактора графів на PySide6 і QML (Qt Quick). Вершини й ребра створюються мишкою, групуються в класи з власним дизайном, а граф зберігається в JSON. Інтерфейс темний, плаский і стриманий, щоб найяскравішим на екрані був сам граф із кольоровими вершинами й ребрами.

## Основи змісту

- **Мова.** Інтерфейс український. Підписи полів — короткі іменники: *Текст*, *Опис*, *Форма*, *Колір*, *Клас*, *Лінія*, *Товщина*. Дії — дієслова: *Видалити*, *Скасувати*, *З'єднати з класом…*.
- **Терміни.** *Вершина* і *Ребро*; *Клас* — іменований стиль, спільний для багатьох вершин чи ребер; *Група* — згорнута метавершина.
- **Підказки пояснюють жести.** Допоміжний текст називає жест і його результат, наприклад: «Подвійний клік — перейменувати, ⋮⋮ чи Alt+↑/↓ — перемістити, Backspace — видалити». Між жестом і дією ставиться тире.
- **Статус-бар.** Унизу ліворуч — кількість вершин, ребер і компонент зв'язності кольором `mutedText`, праворуч — остання дія кольором `statusText`.

## Візуальні основи

### Модель теми
Усі кольори беруться з `qml/Theme.qml`, який читає **стандартні ключі тем VS Code** (`editor.background`, `button.background`, `menu.border`…). Цілу кольорову тему VS Code можна підключити через `Theme.load(json)`, не змінюючи компонентів. У нотатці до кожного токена вказано його ключ VS Code. Значення тут — стандартна тема застосунку. Лише `marked` у стандартній темі не задано, тому він бере запасне значення з коду, `#4dd0e1`.

### Поверхні

- `background` — полотно графа; `panel` (панель класів) і `statusBar` мають той самий колір.
- `popup` — усе, що «спливає»: контекстні меню, випадні списки й діалоги. Завжди з рамкою 1px `popupBorder`. Модальні діалоги затемнюють застосунок кольором `modal-scrim`.
- `control` — заливка інтерактивних елементів у спокої, `hover` — при наведенні, `accent` — натиснутий або вибраний елемент. Вибрана плитка варіанта втрачає рамку; невибрана має рамку 1px `border`.

### Виділення та фокус
У Fluorite два кольори виділення, і вони означають різне:

- `marked` (блакитний) — **вибране або у фокусі**: кільце `stroke-ring` (2px) навколо виділених вершин, підкреслення поля у фокусі, рамка відкритого випадного списку, рамка виділення (обвідка `marked` поверх `marked-fill`) і виділення тексту (`marked-text-selection`).
- `selection` (помаранчевий) — лише для **ребра, яке зараз тягнуть** правою кнопкою миші.

### Палітра графа
Вершини й ребра фарбуються у вісім кольорів, від `palette-blue` до `palette-grey`, які відповідають ключам ANSI-кольорів терміналу в темі. `palette-blue` — стандартний колір нових класів. Підписи завжди кольору `foreground` з тонким контуром `background` на 38%. Зелений, жовтий, бірюзовий і сірий мають контраст з білим нижче 3:1, тож тримаються на цьому контурі. Підписи вершин лишаються жирними (`node-label`).

### Форма
Розміри задано токенами. Відступи й радіуси зведено до єдиної шкали; решту значень взято точно з QML і `graphs.py`.

- **Відступи — сітка 4px, чотири кроки:** `space-xs` (4px) — щільне всередині списків і рядків; `space-sm` (8px) — пов'язане між собою: підпис і його поле, плитки, кнопки поруч; `space-md` (12px) — групи й контейнери: поля меню й панелі, проміжки між групами, бічні відступи кнопок; `space-lg` (16px) — поля діалогу. Правило для меню й панелей: між групами `space-md`, від підпису до його елемента `space-sm`.
- **Радіуси — три значення:** `radius-sm` (4px) — дрібне: чекбокс, пункти списку; `radius-md` (8px) — усе, що клікають або що лежить на полотні: кнопки, списки, плитки, рядки класів, квадратні вершини; `radius-lg` (12px) — плаваючі поверхні: меню й діалоги. Круглі вершини, кружечки кольорів і бейджі заокруглені повністю. Обводка навколо елемента бере радіус елемента плюс відступ до нього (кільце виділення: `radius-md` + 6px), тож кути лишаються концентричними.
- Значення в коді Fluorite зараз розкидані ширше (2, 6, 10, 18px і радіуси 6, 9, 10px); система округлює їх до цієї шкали. Щоб застосунок збігався із системою, ці числа треба замінити в QML.
- **Розміри:** елементи керування заввишки `control-height` (32px); плитки варіантів — `option-tile` (38px) у меню і `option-tile-sm` (34px) у панелі класів; вершина — `node-height` (44px); панель класів — `panel-width` (210px).
- **Лінії:** рамки `stroke-hairline` (1px), контур вершини й підкреслення поля — `stroke-node` (2px), кільце виділення — `stroke-ring` (2px). Ребра мають три товщини `edge-width-*` і пунктири `edge-dash`, `edge-dot`.
- Текстові поля без рамки, лише з підкресленням: `border` у спокої і `marked` у фокусі.
- Тіней і градієнтів немає. Глибину дає поверхня `popup` з рамкою.
- Неактивні елементи мають прозорість 40%.
- Зміна кольору при наведенні триває 100 мс.

## Іконографія
Набору іконок у Fluorite немає. Варіанти малюються символами Unicode кольором `foreground`: ● ■ — форми вершин, ── ╌╌ ┈┈ — стилі ліній, ──▶ — напрямлене ребро, ▾ — стрілка випадного списку, ✓ — чекбокс, ⋮⋮ — ручка перетягування. Товщина ребра показується смужками заввишки 2.5, 4 і 6px.

## Не синхронізовано

- **Токени**: тіней у коді немає. Тривалості анімацій (100 і 120 мс) описано словами, бо система не має для них окремого типу токенів.

## Токени

### Кольори

| Токен | Значення | Застосування |
| --- | --- | --- |
| `background` | `#222222` | Graph canvas / window background. VS Code key editor.background. |
| `foreground` | `#ffffff` | Primary text and node labels on background, panel, popup and control (15.9:1 on background). VS Code key editor.foreground. |
| `toolbar` | `#2a2a3d` | Title bar / toolbar surface. VS Code key titleBar.activeBackground. |
| `statusBar` | `#222222` | Bottom status bar (vertex, edge and component counts). VS Code key statusBar.background. |
| `statusText` | `#a0a0c0` | Text in the status bar (6.3:1 on statusBar). VS Code key statusBar.foreground. |
| `panel` | `#222222` | Class panel (side bar) surface. VS Code key sideBar.background. |
| `popup` | `#26263a` | Context menus, dropdown lists and ConfirmDialog surface. VS Code key menu.background. |
| `border` | `#44445e` | 1px control borders, idle underline of LineField/TextBox, dividers in the class panel. Decorative: 1.7:1 on background, below the 3:1 control-border target (kept from source). VS Code key widget.border. |
| `popupBorder` | `#44445e` | 1px border and dividers inside popups and menus. VS Code key menu.border. |
| `accent` | `#3d7bd9` | Pressed button, selected option tile, current class row, checked checkbox. foreground on accent is 4.2:1: fine for the 12–14px bold labels used, borderline for regular body text (kept from source). VS Code key button.background. |
| `hover` | `#3a3a52` | Hover fill for buttons, option tiles, list rows and the dropdown. VS Code key list.hoverBackground. |
| `control` | `#2f2f45` | Idle fill of buttons, option tiles, dropdowns and the checkbox box. VS Code key input.background. |
| `mutedText` | `#a5a5d7` | Field labels (Текст, Колір, Клас…), dialog body text, dropdown arrow. 6.8:1 on background, 6.3:1 on popup, 5.6:1 on control. VS Code key descriptionForeground. |
| `faintText` | `#8585b7` | Placeholders, hints and the drag grip in the class panel. 4.6:1 on background, 4.2:1 on popup, 3.7:1 on control: fine for hints on the panel, keep essential text in mutedText inside popups. VS Code key disabledForeground. |
| `selection` | `#f39c12` | Highlight stroke of the edge being drawn (ПКМ-drag). VS Code key focusBorder. |
| `marked` | `#4dd0e1` | Selected-node ring (3px), focused underline of fields, open dropdown border, rubber-band selection border. Not set by the bundled theme: the Theme.qml fallback for terminal.ansiBrightCyan. |
| `marked-fill` | `rgba(77, 208, 225, 0.12)` | Fill of the rubber-band selection rectangle on the canvas (marked at 12%). |
| `marked-text-selection` | `rgba(77, 208, 225, 0.45)` | Text selection highlight in LineField, TextBox and the inline node label editor (marked at 45%). |
| `edge` | `#7f8fd9` | Default edge stroke and the outline of node badges. VS Code key editorLineNumber.foreground. |
| `badge` | `#2a2a3d` | Fill of the degree and member-count badges on nodes. VS Code key badge.background. |
| `badgeText` | `#ffffff` | Number inside node badges (14:1 on badge). VS Code key badge.foreground. |
| `error` | `#ff6767` | Destructive actions: the Видалити button text and ConfirmDialog confirm text. 5.2:1 on popup, 4.6:1 on control. VS Code key errorForeground. |
| `node-stroke` | `rgba(255, 255, 255, 0.78)` | 2px node outline at rest (foreground at 78%); full foreground on hover. |
| `modal-scrim` | `rgba(0, 0, 0, 0.35)` | Overlay behind a modal ConfirmDialog. |
| `palette-blue` | `#3d7bd9` | Node/edge palette 1 and the default class colour. terminal.ansiBlue. White label 4.2:1. |
| `palette-red` | `#e74c3c` | Node/edge palette 2. terminal.ansiRed. White label 3.8:1. |
| `palette-green` | `#27ae60` | Node/edge palette 3. terminal.ansiGreen. White label 2.9:1: relies on the dark label outline. |
| `palette-yellow` | `#f39c12` | Node/edge palette 4. terminal.ansiYellow. White label 2.2:1: relies on the dark label outline. |
| `palette-magenta` | `#9b59b6` | Node/edge palette 5. terminal.ansiMagenta. White label 4.7:1. |
| `palette-cyan` | `#1abc9c` | Node/edge palette 6. terminal.ansiCyan. White label 2.4:1: relies on the dark label outline. |
| `palette-pink` | `#e84393` | Node/edge palette 7. terminal.ansiBrightMagenta. White label 3.7:1. |
| `palette-grey` | `#95a5a6` | Node/edge palette 8. terminal.ansiWhite. White label 2.6:1: relies on the dark label outline. |

### Відступи
A 4px grid with four steps. Inside a menu or panel: sm between a label and its control, md between groups and around the content, lg for dialogs.

| Токен | Значення | Застосування |
| --- | --- | --- |
| `space-xs` | `4px` | Tight: padding and gaps inside a dropdown list, gaps between class rows, field padding, the left inset of class rows. |
| `space-sm` | `8px` | Related things: a label and its control, option tiles and swatches, dialog buttons, the parts of a class row, a checkbox and its label. |
| `space-md` | `12px` | Groups and containers: padding of menus, the class panel and the status bar; gaps between groups; horizontal padding of buttons and dropdowns. |
| `space-lg` | `16px` | Roomy containers: padding of ConfirmDialog. |

### Радіуси
Three radii plus round. A ring or list drawn around an element gets the element's radius plus the gap between them, so the corners stay concentric.

| Токен | Значення | Застосування |
| --- | --- | --- |
| `radius-sm` | `4px` | Small parts: the checkbox, items inside a dropdown list (8px list radius minus its 4px padding). |
| `radius-md` | `8px` | Everything you click or that sits on the canvas: buttons, dropdowns and their list, option tiles, tabs, class rows, square nodes and group layers. |
| `radius-lg` | `12px` | Floating surfaces: node and edge menus, ConfirmDialog. |

### Розміри
Fixed sizes of controls and surfaces from qml/*.qml.

| Токен | Значення | Застосування |
| --- | --- | --- |
| `control-height` | `32px` | FlatButton and DropDown height. |
| `list-item-height` | `30px` | Dropdown list items and the Вершини / Ребра family tabs. |
| `class-row-height` | `36px` | A row in the class panel list. |
| `option-tile` | `38px` | Square option tiles (shape, line, width) and colour swatches in node and edge menus. |
| `option-tile-sm` | `34px` | Option tiles and colour swatches in the class panel. |
| `direction-tile-width` | `52px` | Directed / undirected tiles in the class panel (34px tall). |
| `node-height` | `44px` | Node height and minimum width; a circle node is a 44px disc. |
| `badge-size` | `18px` | Degree and member-count badges on nodes. |
| `checkbox-size` | `16px` | Checkbox box in ConfirmDialog. |
| `panel-width` | `210px` | Class panel width. |
| `dialog-width` | `340px` | ConfirmDialog width. |
| `menu-min-width` | `150px` | Minimum width of node and edge menus. |
| `dropdown-min-width` | `120px` | Minimum width of DropDown. |
| `dropdown-list-max-height` | `240px` | Maximum height of an open dropdown list before it scrolls. |
| `description-height` | `56px` | Height of the description box in the node menu. |

### Лінії (stroke)
Line widths and edge geometry from qml/*.qml and graphs.py (EdgeLayer).

| Токен | Значення | Застосування |
| --- | --- | --- |
| `stroke-hairline` | `1px` | Control and popup borders, dividers, badge outline, rubber-band border. |
| `stroke-node` | `2px` | Node outline and the underline of LineField / TextBox. |
| `stroke-ring` | `2px` | Selection ring around nodes, border of the chosen colour swatch, the edge being drawn. |
| `edge-width-thin` | `2.5px` | Default edge width (class Звичайне). |
| `edge-width-medium` | `4px` | Medium edge width; edge-class glyphs turn bold from here. |
| `edge-width-thick` | `6px` | Thick edge width. |
| `edge-dash` | `8 6` | Dashed edge: 8px dash, 6px gap, flat caps. |
| `edge-dot` | `2 5` | Dotted edge: 2px dot, 5px gap, flat caps. |
| `edge-draft-dash` | `6 5` | The edge being drawn: selection colour, 3px wide, 6px dash, 5px gap. |
| `edge-parallel-step` | `14px` | Spacing between parallel edges of different classes on the same pair; they bow out as quadratic curves. |
| `arrow-angle` | `26deg` | Angle of each arrowhead barb from the edge line. |
| `arrow-barb-base` | `7px` | Barb length is 7px + 1.8 × edge width; barbs are open lines with round caps, tip on the node's 22px radius. |
