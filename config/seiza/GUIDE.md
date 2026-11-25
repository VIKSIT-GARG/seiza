# seiza. — A system of my own.

Personal operating environment built on **CachyOS**, **Niri 26.04 (Wayland)**, **Noctalia Shell 5.5.0**, **Alacritty**, **Fish**, and **Starship** — combining midnight obsidian depth, pastel celestial accents, and an integrated developer & AI workstation toolkit.

---

## Keybindings (All base Niri bindings preserved)

| Shortcut | Action |
| :--- | :--- |
| `Super + Space` | **Universal Command Centre** (`seiza palette` — apps, files, calc, clips, bookmarks, workspaces, commands) |
| `Super + G` | **AI, ML & System Health Dashboard** (`seiza dashboard`) |
| `Super + P` | **Wayland Display Studio** (`seiza display`) |
| `Super + Shift + Enter` | **Welcome Terminal** (`seiza welcome` with wide/compact Fastfetch) |
| `Super + /` | **Searchable Keybind Cheatsheet** (`seiza keys --gui`) |
| `Super + Alt + N` | **Focus Studio** (`seiza studio` — quick notes, Pomodoro, clipboard snippets) |
| `Super + Alt + W` | **Workspace Preset Switcher** (`seiza workspace`) |
| `Super + Alt + C` | **Screen Color Picker** (`seiza color` -> copies `#RRGGBB`) |
| `Super + Alt + O` | **Screen Region OCR** (`seiza ocr` — uses `tesseract` if installed, otherwise copies region image) |
| `Super + Alt + R` | **Screen Recorder Toggle** (`seiza record toggle`) |
| `Super + Return` | Alacritty Terminal |
| `Super + Ctrl + Return` | Noctalia App Launcher |
| `Super + N` / `Super + Shift + N` | Noctalia Control Center / Notifications |
| `Super + S` / `Super + \`` | Quake Scratchpad Terminal |
| `Super + Shift + V` | Noctalia Clipboard History |
| `Ctrl + Shift + 4` / `Super + Shift + A` | Region Screenshot / Screenshot Annotate |

---

## `seiza` CLI Toolkit

Run `seiza help` at any time:

- **Core & Diagnostics:** `seiza welcome`, `seiza status [--json]`, `seiza doctor`, `seiza network [--ping|--ports]`
- **AI & GPU:** `seiza gpu [--watch|--gui|--json]`, `seiza gpu --estimate <paramsB> --quant <q> --ctx <tokens>`, `seiza dashboard`
- **Safe Updates & Upgrade Receipts:** `seiza update [--check|--receipts|--last]`
  - Receipts are archived under `~/.local/state/seiza/receipts/` (`receipt_*.json` and `.md`), capturing timestamps, duration, upgraded/installed/removed package versions, disk delta, alerts, and Snapper/Limine snapshot IDs.
- **Maintenance:** `seiza clean [--dry-run]` (always previews and prompts before removing caches or orphans)
- **Displays:** `seiza display [list|internal|extend|mirror|present|profiles]` (GUI includes visual layout canvas and 15-second auto-revert confirmation)
- **Workspaces:** `seiza workspace [development|ai-research|electronics|focus|everyday|--list]`
- **Theme:** `seiza theme [status|seiza|dynamic|next|prev|random|list|set <path>]`
- **Productivity:** `seiza palette`, `seiza studio`, `seiza notes`, `seiza pomodoro`, `seiza snippets [list|add|copy|clear-history]`, `seiza color`, `seiza ocr`, `seiza record`, `seiza keys [query|--gui|--fuzzel]`
- **Snapshots & Rollback:** `seiza backup [name]`, `seiza restore [name|--list]`
