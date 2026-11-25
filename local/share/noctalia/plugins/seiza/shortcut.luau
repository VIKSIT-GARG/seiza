--!nonstrict
-- seiza. — Control Center quick tile (zero polling, launches Hub panel or Command Centre).

local function seizaBin()
    return (noctalia.getenv("HOME") or "") .. "/.local/bin/seiza"
end

shortcut.setLabel(noctalia.tr("shortcut_label"))
shortcut.setIcon("sparkles", "sparkles")
shortcut.setActive(true)
shortcut.setEnabled(true)

function onClick()
    noctalia.togglePanel("viksit-garg/seiza:hub")
end

function onRightClick()
    noctalia.runAsync(seizaBin() .. " palette >/dev/null 2>&1 &", function() end)
end
