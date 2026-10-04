# ROADMAP коду Fluorite

Карта проєкту: від `uv run main.py` до останнього числа, яке змінює вигляд інтерфейсу.
Читати згори вниз — це порядок, у якому дані проходять крізь програму.

```
main.py ──► GraphBackend (graphs.py) ──► QML (qml/main.qml)
               │  ├─ Document (document.py)
               │  │    ├─ FluoriteGraph (FluoriteGraph.py)  — смисл графа
               │  │    └─ View (view.py)                    — вигляд графа
               │  ├─ History (history.py)                   — Ctrl+Z
               │  ├─ storage (storage.py)                   — JSON
               │  └─ NodesModel                             — вершини для Repeater
               └─ EdgeLayer (graphs.py)                     — малює ребра (QQuickPaintedItem)
```

---

## 1. Точка входу — `main.py`

| Рядок | Що відбувається |
|---|---|
| `QGuiApplication(sys.argv)` | Qt-застосунок |
| `setOrganizationName/ApplicationName("Fluorite")` | шлях для `QtCore.Settings` → `~/.config/Fluorite/Fluorite.conf` (там живе «Більше не питати» з `ConfirmDialog`) |
| `qmlRegisterType(EdgeLayer, "Graphs", 1, 0, "EdgeLayer")` | QML-тип `EdgeLayer`, імпорт `import Graphs` у `main.qml` |
| `backend = GraphBackend()` | один на весь застосунок; всередині створює `Document`, `NodesModel`, `History`, таймери |
| `rootContext().setContextProperty("backend", backend)` | глобальне ім'я `backend` у **всіх** QML-файлах |
| `engine.load(qml/main.qml)` | вікно; якщо QML не зібрався — `return 1` |

Залежність одна: `pyside6` (`pyproject.toml`, Python ≥ 3.13).

---

## 2. Модель даних (без Qt)

### 2.1 `FluoriteGraph.py` — смисл графа
Тимчасова копія бібліотеки FluoriteGraph. Усі записи `frozen` — змінити запис означає замінити його.

- `NodeType(name, nodes: {id: Node})`, `Node(name, description, node_id)`.
- `EdgeType(name, directed, edges: {id: Edge})`, `Edge(node_in, node_out, description, edge_id)`.
  **Напрям ребра — властивість типу**, не ребра.
- `Hyperedge(name, description, children, hyperedge_id)` — склад групи; вкладеність перевіряється на DAG (`_reaches`).
- `FluoriteGraph(nodes, edges, hyperedges)` — словники за назвою типу / id.
- Глобальний лічильник `_counter` видає id **усім** сутностям (вершинам, ребрам, гіперребрам).

### 2.2 `view.py` — як граф показано
- `NodeStyle(shape, color, opacity)`, `EdgeStyle(color, width, line)` — `None` у полі означає «бери з дизайну типу».
- `NODE_DESIGN` / `EDGE_DESIGN` — базовий дизайн нового типу (див. §8).
- `DEFAULT_NODE_TYPE = "Звичайна"`, `DEFAULT_EDGE_TYPE = "Звичайне"`.
- `TypeLook(design, hidden, uid)` — дизайн типу, схованість (око 👁) і незмінний `uid` (для історії й перейменувань).
- `NodeLook(x, y, style)`, `EdgeLook(style)`, `GroupLook(node, collapsed)`.
- `View` — словники типів (**порядок ключів = порядок у панелі**), `defaults` (сім'я → uid стандартного типу), looks вершин/ребер/груп.
- `effective(style, design)` — підсумковий стиль = дизайн типу, перекритий не-`None` полями елемента.

### 2.3 `document.py` — `Document`
Граф + вигляд + індекси. **Усі зміни графа йдуть тільки через нього.**

- Індекси (`reindex()`): `type_of`, `edge_type_of`, `incident` (вершина → ребра), `member_of` (член → група), `group_of_node` (метавершина → група).
- `numbers` — наступні номери автопідписів вершин («1», «2»…) і груп («Група N»).
- Типи: `create_class / update_class / rename_class / remove_class / move_class / set_class_hidden`, `design_map` (для QML додає `directed`).
- Вершини: `add_node`, `set_label`, `set_description`, `move_node`, `set_node_style`, `set_node_class` (скидає перекриття стилю), `remove_node(s)`, `degree`, `component_count` (union-find).
- Ребра: `add_edge` (**одне ребро типу на пару вершин**, у будь-якому напрямі), `bulk_add_edges`, `reverse_edge` (лише для спрямованих), `set_edge_class` (скидає стиль), `set_edge_style`, `shown_edges()` (без схованих типів).
- Групи: `add_group` (≥ 2 видимі вершини → метавершина в центроїді), `remove_group`, `set_collapsed` (при згортанні метавершина їде в центроїд), `_forget_member` (група з < 2 членів розпускається → метавершина в `orphans`).
- **`visual_owner(nid)`** — ключова функція видимості: якою вершиною `nid` зараз показана на екрані (`None` — не видно: схований тип або розгорнута метавершина). Від неї залежать `nodeHidden`, `nodeAt`, рамка, ребра.
- `reserve_ids(last)` — підміна приватного `fg._counter` після відкриття файлу.

### 2.4 `history.py` — Ctrl+Z / Ctrl+Shift+Z
- `snapshot(doc)` — легкий знімок (копія посилань на незмінні записи): `types`, `nodes`, `edges`, `groups`, `numbers`. Тип ідентифікується `uid`.
- `diff(old, new)` — крок = тільки змінені записи `(до, після)`.
- `apply(doc, change, side)` — накат/відкат у 6 етапів (типи → зайві ребра → вершини → ребра → групи → порожні типи), повертає `(added, removed)` вершини для моделі.
- `History` — `deque(maxlen=UNDO_DEPTH)` + redo-стек + `_base` (стан після останнього кроку).
- **Не в історії:** виділення, порядок класів, схованість.

### 2.5 `storage.py` — JSON
- `FORMAT_VERSION = 7`: `{"version", "graph": {node_types, edge_types, hyperedges}, "view": {node, edge, defaults, nodes, edges, groups}, "numbers"}`.
- `graph_from_json` → `_from_v7` або `_from_legacy` (версії 1–6, `_upgrade_v1`). Документ будується окремо і підміняє поточний лише після успішного розбору.
- Приклади у корені: `архітектура.json`, `дефолт_нейронка.json`.

---

## 3. Міст до QML — `graphs.py`

### 3.1 `GraphBackend(QObject)` — контекстна властивість `backend`

**Сигнали → хто слухає:**

| Сигнал | Коли | Слухач у UI |
|---|---|---|
| `graphChanged` | змінилась структура | `EdgeLayer._mark_dirty` (повна перебудова ребер) |
| `edgesChanged` | стиль/напрям ребер | `EdgeLayer._mark_dirty` |
| `nodeMoved(nid, x, y)` | перетягування | `EdgeLayer._node_moved` (рухає лише інцидентні лінії) |
| `classesChanged` | типи змінились | `main.qml → refreshClasses()` → `classList("node"/"edge")` |
| `summaryChanged` | статистика (з тротлінгом `_SUMMARY_MS`) | `backend.stats` у статус-барі + `refreshClasses()` (лічильники) |
| `selectionChanged` | виділення | `backend.selectionCount` |
| `statusChanged` | повідомлення | `backend.status` у статус-барі |

**Властивості:** `nodesModel` (const), `stats`, `status` (порожній → підказка `_HINT`), `selectionCount`.

**Слоти** (позначка ⎌ — декоратор `@_step`, потрапляє в історію; ⎌⇢ — зливається в один крок за ключем):

| Група | Слоти |
|---|---|
| Виділення | `selectNode`, `selectInRect`, `clearSelection`, `isSelected` |
| Класи | `classList`, `createClass` ⎌, `updateClass` ⎌⇢, `renameClass` ⎌, `removeClass` ⎌, `setClassHidden`, `moveClass` |
| Вершини | `addNode` ⎌, `setNodeLabel` ⎌, `setNodeDescription` ⎌⇢, `moveNode` ⎌⇢, `moveSelectionTo` ⎌⇢, `removeNode` ⎌, `removeSelection` ⎌, `setSelectionClass/Shape/Color` ⎌, `setSelectionOpacity` ⎌⇢, `nodeAt`, `nodeInfo` |
| Ребра | `addEdge` ⎌, `removeEdge` ⎌, `setEdgeColor/Width/Line` ⎌, `reverseEdge` ⎌, `setEdgeClass` ⎌, `edgeAt`, `edgeInfo`, `connectClassNodes` ⎌, `connectSelection` ⎌, `connectSelectionToClass` ⎌, `connectSelectionTo` ⎌ |
| Групи | `groupSelection` ⎌, `setGroupCollapsed` ⎌, `ungroup` ⎌ |
| Документ | `clear` ⎌, `saveToFile`, `loadFromFile` (скидає історію), `undo`, `redo` |

**`_step(merge)`**: якщо ключ неперервної дії змінився — комітить попередній; без ключа комітить одразу; з ключем — чекає `_IDLE_MS` тиші. `undo/redo` спершу комітять незавершену дію. `_travel` після відкату точково оновлює модель і шле всі сигнали.

### 3.2 `NodesModel(QAbstractListModel)` — вершини для `Repeater`
Ролі → `required property` у `Node.qml`:

| Роль | Ім'я в QML | Джерело |
|---|---|---|
| NodeIdRole | `nodeId` | id |
| XRole / YRole | `px` / `py` | `NodeLook.x/y` — **центр** вершини |
| LabelRole | `label` | `Node.name` |
| DegreeRole | `degree` | `len(incident)` (враховує сховані ребра) |
| ShapeRole / ColorRole / OpacityRole | `nodeShape` / `nodeColor` / `nodeOpacity` | `effective(style, design)` |
| ClassRole | `nodeClass` | назва типу |
| DescriptionRole | `nodeDescription` | `Node.description` |
| SelectedRole | `nodeSelected` | `_selected` (множина спільна з бекендом) |
| HiddenRole | `nodeHidden` | `visual_owner(nid) != nid` |
| IsGroupRole / MembersRole | `isGroup` / `memberCount` | групи |

Оновлення точкові: `notify_row` (один рядок), `notify_all` (одна роль для всіх), `remove_nodes`/`reset_with` (скидання моделі).

### 3.3 `EdgeLayer(QQuickPaintedItem)` — малювання ребер
Конвеєр одного кадру:

1. `_rebuild()` (коли `_groups is None`): для кожного `shown_edges()` береться `visual_owner` кінців → ребро всередині однієї згорнутої групи чи до невидимої вершини пропускається. Ребра групуються за ключем `(color, width, line, directed)`:
   - пряме → `_groups` (+ вусики стрілки в `_arrows`, `_fit_arrow` відступає на `_NODE_R`);
   - паралельні між тією самою парою → дуга з вигином `_edge_bends` (крок `_BEND_STEP`) → `_curves`.
   - `_incident` — які `QLineF` рухати при перетягуванні вершини.
2. `paint()`: малює у власний ARGB32-буфер (`_buffer`), потім блітить у текстуру.
   - Якщо тягнуть вершини і ребер ≥ `_FAST_EDGES`: нерухомі ребра растеризуються один раз у `_static`, щокадру домальовуються лише рухомі (`_dyn_*`).
   - Шквал оновлень (інтервал < `_BURST_GAP`) → швидкий режим: без антиаліасингу, текстура зменшена до 1× DPR; через `_REFINE_MS` тиші — чистовий кадр.
3. Пера кешуються в `_pens`; пунктир `_DASHES` ділиться на товщину (Qt рахує dash у одиницях товщини).

ЛКМ, наведення й перетягування вершини обробляє `MouseArea` у `Node.qml`. Влучання для ПКМ і рамки виділення рахується в бекенді: `nodeAt` (радіус 26 px), `edgeAt` (допуск 7 px, для дуг — 12 відрізків квадратичної Безьє), `selectInRect`.

---

## 4. Інтерфейс — `qml/`

`qmldir` реєструє: `Node`, `NodeMenu`, `ClassPanel`, `Theme` (singleton), `LineField`, `TextBox`, `FlatButton`, `DropDown`, `ConfirmDialog`. (`EdgeMenu` знаходиться неявно — за іменем файлу в тій самій теці.)

### 4.1 `main.qml` — дерево вікна

```
ApplicationWindow (1100×720, color Theme.background)
├─ Shortcuts: Delete/Backspace (є виділення) → removeSelection
│             Escape → clearSelection
│             Ctrl+Z / Ctrl+Shift+Z (classPanel.keyboard) → undo / redo
├─ footer ToolBar: backend.stats … backend.status (max 600 px, elide)
├─ ClassPanel (зліва, 210 px)
│     nodeClasses/edgeClasses ← refreshClasses()
│     keyboard = нема меню і фокус не в TextInput/TextEdit
│     arrows   = selectionCount === 0
└─ workspace (Item, решта ширини)
   ├─ MouseArea (ЛКМ/ПКМ)       — z-порядок знизу вгору
   ├─ EdgeLayer { source: backend }
   ├─ Shape — пунктир-прев'ю ребра під час ПКМ-перетягу (Theme.selection, 3 px)
   ├─ Repeater { model: backend.nodesModel; delegate: Node { edgeClass } }
   ├─ Rectangle — рамка виділення (z 3, Theme.marked, заливка alpha 0.12)
   ├─ NodeMenu  { classes, selectionCount, edgeClass }
   └─ EdgeMenu  { classes }
```

**Жести полотна** (`MouseArea` у `workspace`):

| Жест | Ланцюжок |
|---|---|
| ЛКМ клік по полю | `finishBandOrClick` → є виділення і нема Shift? `clearSelection` : `addNode(x, y, classPanel.currentNodeClass)` |
| ЛКМ перетяг по полю | `banding` → рамка ≥ 4 px → `selectInRect(…, bandAdditive)` |
| ПКМ по вершині, відпустити на ній | `openNodeMenu` → (виділити, якщо не виділена) → `nodeMenu.refresh()` → `open()` |
| ПКМ перетяг вершина→вершина | прев'ю `Shape` → `addEdge(src, tgt, classPanel.currentEdgeClass)` (напрям = звідки тягнули) |
| ПКМ по ребру | `edgeAt` → `openEdgeMenu` |

`menuX/menuY` — меню відкривається в точці кліку, а якщо не влазить — віддзеркалюється або притискається до краю.

### 4.2 `Node.qml` — делегат вершини
- Розмір: висота 44, ширина `max(44, текст + 20)`; `x/y = px/py − половина`.
- `visible: !nodeHidden`; `z`: 2 при наведенні/редагуванні, інакше 1.
- Шари: рамка виділення (+12 px, `Theme.marked`, 3 px) → тіло (коло, якщо `nodeShape === "circle"`, інакше квадрат з radius 8; рамка 2 px `strokeColor`) **або** «стос» з трьох карток для метавершини групи → підпис (bold 15 px, обведення) → редактор підпису (`TextInput` за подвійним кліком) → бейдж ступеня (праворуч угорі, 18 px) → бейдж кількості членів (ліворуч угорі).
- Клік: `Ctrl+Shift` → `connectSelectionTo`; `Shift` → додати/зняти; інакше вибрати одну.
- Перетяг (`drag.target: node`) → `moveSelectionTo` (якщо виділена й виділених > 1) або `moveNode`.
- Підказка з затримкою 500 мс: «Вершина X • клас • ступінь \n опис» / «Група X • вершин».

### 4.3 `ClassPanel.qml` — ліва панель
**Стан**, яким панель володіє: `family` ("node"/"edge"), `currentNodeClass`, `currentEdgeClass` (`""` — жоден; тоді нові елементи йдуть у стандартний клас), `renaming`, `dragIndex/dragOffset`, і чернетка стилю `newShape/newLine/newWidth/newColor/newOpacity/newDirected`.

Логіка: `editing = currentClass !== ""`. Коли клас обрано, `loadDesign()` переносить його дизайн у чернетку, а кожна зміна чернетки одразу йде в `pushDesign() → backend.updateClass`. Коли не обрано, чернетка — стиль майбутнього класу для `submitNew() → createClass`.

Блоки згори вниз: заголовок «Класи» → вкладки Вершини/Ребра → `ListView` класів (ручка ⋮⋮, гліф стилю, назва / поле перейменування, лічильник, око 👁) → «З'єднати всі» (`connectClassNodes`) → «Клас «X»» / «Новий клас» + поле назви → форма / прозорість (вершини) або лінія / товщина / напрям (ребра) → палітра → «Створити клас» → підказка → 💾 📂 🗑.

Діалоги живуть тут: `FileDialog` збереження/відкриття, `ConfirmDialog` видалення класу (`key: "removeClass"`).

Клавіші (усі за умови `keyboard`; стрілки та Backspace — ще й `arrows`):

| Клавіша | Дія |
|---|---|
| Tab | `toggleFamily` |
| ↑/↓ | `stepClass` (з останнього класу ↓ → поле назви) |
| Alt+↑/↓ | `moveCurrent` |
| Backspace | `removeClass(currentClass)` |
| ←/→ | колір; Shift — форма/лінія; Ctrl — товщина; Ctrl+Shift — напрям |
| Enter | `submitNew` (коли клас не обрано) |

### 4.4 `NodeMenu.qml` / `EdgeMenu.qml` — контекстні меню
Модальні `Popup` (`dim: false`). Після кожної дії викликають `refresh()`, яка перечитує `nodeInfo`/`edgeInfo`; зник елемент — меню закривається.

- **NodeMenu:** заголовок (вершина / група / «Виділено вершин: N») → Розгорнути / Розгрупувати (для метавершини) → Текст (`setNodeLabel` на кожну літеру) → Опис (`setNodeDescription`) → Форма → Колір → Прозорість 10–100 % → Клас → «З'єднати з класом…» → для групи виділених: «З'єднати між собою», «Згорнути у групу» → «Згорнути групу «X»» (якщо вершина — член групи) → Видалити. Форма, колір, прозорість і клас застосовуються через `setSelection*` до **всього** виділення.
- **EdgeMenu:** заголовок `A–B` / `A → B` → Лінія → Товщина → Колір → Клас (невдача відкочує комбобокс) → «⇄ Перевернути напрям» (лише спрямовані) → Видалити.

### 4.5 Спільні компоненти
`LineField` (TextField з лінією знизу), `TextBox` (TextArea, те саме), `FlatButton` (плитка, `textColor`), `DropDown` (ComboBox з темним списком, max 240 px), `ConfirmDialog` (340 px, `ask()` → `confirmed()`, «Більше не питати» через `Settings { category: "confirm" }`).

### 4.6 `Theme.qml` — кольори
Singleton із ключами тем VS Code (`colors`). `c(key, fallback)` перетворює `#RRGGBBAA` → `#AARRGGBB` для Qt. `load(vsTheme)` приймає JSON теми цілком або лише `colors` (з UI поки не викликається).

| Властивість | Ключ VS Code | Де видно |
|---|---|---|
| `background` | `editor.background` | тло вікна, обведення підпису |
| `foreground` | `editor.foreground` | текст, рамка вершини |
| `statusBar` / `statusText` | `statusBar.*` | нижня смуга |
| `panel` | `sideBar.background` | панель класів |
| `popup` / `popupBorder` | `menu.*` | меню, діалоги, роздільники |
| `border` | `widget.border` | рамки плиток |
| `accent` | `button.background` | обрана плитка / рядок / вкладка |
| `hover` | `list.hoverBackground` | наведення |
| `control` | `input.background` | фон плиток |
| `mutedText` / `faintText` | `descriptionForeground` / `disabledForeground` | підписи, підказки |
| `selection` | `focusBorder` | прев'ю нового ребра |
| `marked` | `terminal.ansiBrightCyan` (у вбудованій темі нема → `#4dd0e1`) | рамка виділення вершин і рамка-«гумка» на полі, лінія під полем вводу |
| `edge` | `editorLineNumber.foreground` | обідок бейджів |
| `badge` / `badgeText` | `badge.*` | бейджі ступеня й членів |
| `error` | `errorForeground` | «Видалити» |
| `nodePalette[8]` | `terminal.ansi*` | палітра кольорів у панелі й меню |

---

## 5. Наскрізні сценарії

**Нова вершина.** ЛКМ → `main.qml.finishBandOrClick` → `backend.addNode` (⎌) → `Document.add_node` (підпис з `numbers["node"]`, тип через `resolve_type`) → `NodesModel.append_node` → `Repeater` створює `Node` → `_structure_changed` → `graphChanged` (EdgeLayer) + `summaryChanged` через 100 мс (stats, лічильники класів) → `_commit` → крок історії.

**Зміна стилю класу.** Клік по кольору в панелі → `newColor` → `pushDesign` → `updateClass` (⎌⇢ ключ `('class', family, name)`) → `Document.update_class` → для вершин `notify_all(Shape/Color/Opacity)`, для ребер `edgesChanged` → `classesChanged` → `refreshClasses` → `classes` → `loadDesign`.

**Перетягування.** `Node` drag → `moveNode`/`moveSelectionTo` (⎌⇢ `('move', nid)`) → `notify_row(X, Y)` + `nodeMoved` → `EdgeLayer._node_moved` рухає `QLineF` на місці → кеш `_static` / швидкий режим. Крок історії закривається через 600 мс або наступною дією.

**Відкриття файлу.** 📂 → `FileDialog` → `loadFromFile` → `storage.graph_from_json` → `Document.adopt` → `reset_with` → `History.reset` → усі сигнали.

---

## 6. Що зберігається і де

| Що | Де |
|---|---|
| Граф, вигляд, класи, порядок, схованість, стандартні класи, номери | JSON (формат 7), лише за 💾 |
| «Більше не питати» | `~/.config/Fluorite/Fluorite.conf`, `[confirm]` |
| Історія, виділення, обраний клас панелі, чернетка стилю | лише в пам'яті |

---

## 7. Як додати нове

- **Нову дію над графом:** метод у `Document` → слот у `GraphBackend` з `@Slot(...)` і `@_step()` (або `@_step(merge)` для неперервних) → після зміни повідомити UI (`notify_row`/`notify_all`, `_structure_changed`, `edgesChanged`, `classesChanged`) і `_set_status` → виклик з QML через `backend.<слот>`.
- **Нове поле стилю:** `NodeStyle`/`EdgeStyle` у `view.py` + значення в `NODE_DESIGN`/`EDGE_DESIGN` → роль у `NodesModel` (для вершин) або ключ групування в `EdgeLayer._rebuild` (для ребер) → `nodeInfo`/`edgeInfo` → `design()`/`loadDesign()` у `ClassPanel` → меню. `storage` і `history` підхоплять поле автоматично (`asdict`, порівняння записів).
- **Нову роль вершини:** константа `…Role` + `roleNames` + `data` → `required property` у `Node.qml`.
- **Новий колір теми:** ключ VS Code у `Theme.colors` + `readonly property color … : c(key, fallback)`.

---

## 8. Довідник параметрів, що змінюють UI

### Python

| Параметр | Файл | Значення | На що впливає |
|---|---|---|---|
| `NODE_DESIGN` | `view.py` | circle, `#3d7bd9`, 1.0 | дизайн нового класу вершин |
| `EDGE_DESIGN` | `view.py` | `#7f8fd9`, 2.5, solid | дизайн нового класу ребер |
| `DEFAULT_NODE_TYPE` / `DEFAULT_EDGE_TYPE` | `view.py` | «Звичайна» / «Звичайне» | назви стандартних класів |
| `UNDO_DEPTH` | `history.py` | 10 | глибина Ctrl+Z |
| `_SUMMARY_MS` | `graphs.py` | 100 мс | частота оновлення stats і лічильників класів |
| `_IDLE_MS` | `graphs.py` | 600 мс | пауза, що закриває неперервний крок історії |
| `_HINT` | `graphs.py` | текст | підказка в статус-барі без повідомлення |
| усі тексти `_set_status(...)` | `graphs.py` | — | повідомлення статус-бару |
| `_BEND_STEP` | `graphs.py` | 14 px | відстань між паралельними ребрами |
| `_NODE_R` | `graphs.py` | 22 px | відступ вістря стрілки від центру (= половина 44 px з `Node.qml`) |
| `_BARB_BASE`, `_BARB_K` | `graphs.py` | 7, 1.8 | довжина вусика стрілки = 7 + 1.8·товщина |
| кут вусика | `graphs.py` | 26° | розкриття стрілки (половина кута) |
| радіус `nodeAt` | `graphs.py` | 26 px | влучання в вершину для ПКМ |
| допуск `edgeAt` | `graphs.py` | 7 px | влучання в ребро |
| `_DASHES` | `graphs.py` | dash 8/6, dot 2/5 | малюнок пунктиру ребер |
| кінці ліній | `graphs.py` | FlatCap (тіло), RoundCap (стрілка) | |
| `_FAST_EDGES` | `graphs.py` | 300 | з якої кількості ребер вмикаються кеш і швидкий режим |
| `_BURST_GAP` | `graphs.py` | 0.1 с | що вважати шквалом оновлень |
| `_REFINE_MS` | `graphs.py` | 150 мс | затримка чистового кадру |
| `FORMAT_VERSION` | `storage.py` | 7 | версія файлу |

### QML

| Параметр | Файл | Значення |
|---|---|---|
| розмір вікна, заголовок | `main.qml` | 1100×720, «Fluorite» |
| мінімальна рамка виділення | `main.qml` | 4 px |
| прев'ю ребра | `main.qml` | 3 px, dash `[2, 5/3]`, `Theme.selection` |
| заливка рамки виділення | `main.qml` | `Theme.marked` alpha 0.12, бордюр 1 px |
| ширина статусу | `main.qml` | max 600 px, відступи 12 |
| ширина панелі | `ClassPanel.qml` | 210 px, поля 12, проміжок 10 |
| висота рядка класу | `ClassPanel.qml` | 36 px + spacing 4 (`rowStep`), анімація зсуву 120 мс |
| плитки стилю в панелі | `ClassPanel.qml` | 34×34 (напрям 52×34), колір — коло 34 |
| `shapeDefs`, `lineDefs`, `widthDefs`, `dirDefs` | `ClassPanel.qml`, `NodeMenu.qml`, `EdgeMenu.qml` | ● ■ / ── ╌╌ ┈┈ / 2.5 4 6 / ── ──▶ (**продубльовані** в панелі й меню) |
| стартова чернетка | `ClassPanel.qml` | circle, solid, 2.5, `nodePalette[0]`, 1.0, ненапрямлене |
| `currentNodeClass/currentEdgeClass` на старті | `ClassPanel.qml` | «Звичайна» / «Звичайне» (жорстко, не з `view.py`) |
| гліф класу | `ClassPanel.qml` | 18 px (вершини) / 14 px (ребра, bold якщо товщина ≥ 4); схований — opacity 0.4 |
| вершина | `Node.qml` | 44 px, ширина `текст + 20`, radius квадрата 8 |
| рамка вершини | `Node.qml` | 2 px, `foreground` (alpha 0.78 без наведення) |
| рамка виділення вершини | `Node.qml` | +12 px, 3 px, `Theme.marked` |
| підпис | `Node.qml` | bold 15 px, Outline `background` alpha 0.38 |
| стос групи | `Node.qml` | 3 картки зі зсувом 3.5 px, `Qt.darker` 1.35 / 1.8 |
| бейджі | `Node.qml` | 18 px, шрифт 10, зсув −5 (ступінь) / −7 (члени) |
| затримка підказки | `Node.qml` | 500 мс |
| меню | `NodeMenu.qml`, `EdgeMenu.qml` | min ширина 150, поля 12, radius 10, плитки 38×38 |
| наведення на колір | панель і меню | scale 1.15, 100 мс |
| повзунок прозорості | панель і `NodeMenu` | 0.1 … 1.0 |
| поле опису | `NodeMenu.qml` | висота 56 px, шрифт 12 |
| анімація кольору плиток | усюди | 100 мс |
| `FlatButton` | `FlatButton.qml` | висота 32, radius 8, падінги 10/6 |
| `DropDown` | `DropDown.qml` | 120×32, рядок 30, список max 240 px |
| `ConfirmDialog` | `ConfirmDialog.qml` | ширина 340, padding 18, затемнення black 0.35 |
| усі кольори | `Theme.qml` | див. §4.6 |

---

## 9. Помічені розбіжності в коді

- `EdgeMenu` немає в `qmldir`, хоча решта компонентів там.
- Початкові `currentNodeClass/currentEdgeClass` у `ClassPanel.qml` повторюють `DEFAULT_*_TYPE` з `view.py` рядками; після перейменування стандартного класу чи відкриття файлу вони розходяться (див. «Відомі недоліки» в `UPGRADE.md`).
- `shapeDefs` / `lineDefs` / `widthDefs` визначені двічі (панель і меню), а `_NODE_R` / радіус `nodeAt` залежать від розміру 44 px у `Node.qml` — змінювати треба синхронно. Для широких вершин із довгим підписом стрілка й влучання все одно рахуються за колом 22/26 px.
- `Theme.marked` бере ключ `terminal.ansiBrightCyan`, якого нема у вбудованій темі, тож завжди спрацьовує fallback.
- `Theme.load()` існує, але ніде не викликається (план «UI для тем VS Code» з README).
