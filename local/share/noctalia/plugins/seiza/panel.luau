--!nonstrict
-- seiza. — Noctalia Hub Panel (zero background polling; clean quick launch).

local SEIZA = (noctalia.getenv("HOME") or "") .. "/.local/bin/seiza"

local function runCmd(cmd)
    noctalia.runAsync(cmd .. " >/dev/null 2>&1 &", function() end)
    panel.close()
end

local function actionRow(key, glyph, title, subtitle, cmd)
    return ui.row({
        key = key,
        gap = 10,
        align = "center",
        padding = 10,
        radius = 10,
        fill = "surface_container",
        border = "outline_variant/0.45",
        borderWidth = 1,
    }, {
        ui.glyph({ name = glyph, size = 18, color = "primary" }),
        ui.column({ flexGrow = 1, gap = 2 }, {
            ui.label({ text = title, fontWeight = "bold", fontSize = 13 }),
            ui.label({ text = subtitle, fontSize = 11, color = "on_surface_variant" }),
        }),
        ui.button({
            key = key .. "_btn",
            glyph = "arrow-right",
            variant = "ghost",
            controlSize = "sm",
            onClick = function()
                runCmd(cmd)
            end,
        }),
    })
end

local function render()
    local tools = {
        actionRow("act_palette", "search", "Universal Command Centre", "Apps, calc, files, clips, bookmarks & actions", SEIZA .. " palette"),
        actionRow("act_dash", "cpu", "AI, ML & Health Dashboard", "GPU VRAM, LLM fit estimator & Pacman receipts", SEIZA .. " dashboard"),
        actionRow("act_disp", "device-desktop", "Display Studio", "Extend, mirror (wl-mirror) & 15s revert safety", SEIZA .. " display"),
        actionRow("act_studio", "notebook", "Focus Studio (Notes & Pomodoro)", "Scratchpad, timer, snippets & shortcuts", SEIZA .. " studio"),
        actionRow("act_color", "color-picker", "Screen Color Picker", "Sample pixel HEX to clipboard", SEIZA .. " color"),
        actionRow("act_ocr", "scan", "Screen Region OCR", "Select screen region to extract text or image", SEIZA .. " ocr"),
        actionRow("act_doctor", "stethoscope", "System Doctor & Welcome", "Open terminal health check", "alacritty -e fish -C '" .. SEIZA .. " welcome && " .. SEIZA .. " doctor'"),
    }

    local wsButtons = {}
    for _, ws in ipairs({
        { id = "development", label = "Dev", glyph = "code" },
        { id = "ai-research", label = "AI", glyph = "brain" },
        { id = "electronics", label = "HW", glyph = "cpu-2" },
        { id = "focus", label = "Focus", glyph = "hourglass" },
        { id = "everyday", label = "Daily", glyph = "browser" },
    }) do
        table.insert(wsButtons, ui.button({
            key = "ws_" .. ws.id,
            text = ws.label,
            glyph = ws.glyph,
            variant = "outline",
            flexGrow = 1,
            onClick = function()
                runCmd(SEIZA .. " workspace " .. ws.id)
            end,
        }))
    end

    local root = ui.column({ flexGrow = 1, gap = 12, padding = 16, align = "stretch" }, {
        ui.row({ gap = 8, align = "center" }, {
            ui.glyph({ name = "sparkles", size = 20, color = "primary" }),
            ui.column({ flexGrow = 1, gap = 1 }, {
                ui.label({ text = noctalia.tr("title"), fontSize = 16, fontWeight = "bold" }),
                ui.label({ text = noctalia.tr("tagline"), fontSize = 11, color = "on_surface_variant" }),
            }),
            ui.button({
                key = "btn_close",
                glyph = "close",
                variant = "ghost",
                onClick = function()
                    panel.close()
                end,
            }),
        }),
        ui.scroll({ key = "tools_scroll", flexGrow = 1, gap = 8 }, tools),
        ui.column({ gap = 6 }, {
            ui.label({ text = "WORKSPACES", fontSize = 11, fontWeight = "bold", color = "on_surface_variant" }),
            ui.row({ gap = 6 }, wsButtons),
        }),
    })

    panel.render(root)
end

render()
