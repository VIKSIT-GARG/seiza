# ────────────── seiza. // A system of my own. — Fish Configuration ──────────────

# Source base CachyOS fish configuration if available
if test -f /usr/share/cachyos-fish-config/cachyos-config.fish
    source /usr/share/cachyos-fish-config/cachyos-config.fish
end

# Essential Environment Variables
set -gx GSK_RENDERER gl
set -gx EDITOR micro
set -gx VISUAL micro
set -gx PYTHONNOUSERSITE 1
set -gx UV_LINK_MODE copy

# OpenCode flags
set -gx OPENCODE_ENABLE_EXA 1
set -gx OPENCODE_EXPERIMENTAL_LSP_TOOL 1

# Ensure user binary paths
fish_add_path -m $HOME/.local/bin
fish_add_path $HOME/.cargo/bin
fish_add_path $HOME/.opencode/bin
fish_add_path $HOME/.spicetify

# Node.js fast environment (fnm)
if type -q fnm
    fnm env --use-on-cd 2>/dev/null | source
end

# Starship Prompt initialization
if type -q starship
    starship init fish | source
end

# OpenClaw completions if present
if test -f "$HOME/.openclaw/completions/openclaw.fish"
    source "$HOME/.openclaw/completions/openclaw.fish"
end

# ─────────────────────────────────────────────────────────────
# SYSTEM MAINTENANCE & PACKAGE MANAGEMENT
# ─────────────────────────────────────────────────────────────

alias syscheck="~/.local/bin/syscheck"
alias cachyos-stabilize="~/.local/bin/cachyos-stabilize"
alias uptime-check="~/.local/bin/uptime-check"
alias gpu-log="~/.local/bin/gpu-log"
alias theme-sync="~/.local/bin/theme-sync"
alias snap="~/.local/bin/snap"

function update --description "Update mirrors and system packages safely"
    echo -e "\033[1;34m==> Checking CachyOS & Arch updates...\033[0m"
    paru -Syu $argv
end

function clean-cache --description "Safely clean pacman package cache"
    if type -q paccache
        sudo paccache -rk2
    else
        sudo pacman -Sc
    end
end

function orphans --description "Safely list unneeded orphan packages"
    set -l list (pacman -Qdtq 2>/dev/null)
    if test -n "$list"
        echo -e "\033[1;33mOrphaned packages found:\033[0m"
        pacman -Qdt
    else
        echo -e "\033[1;32mNo orphaned packages found.\033[0m"
    end
end

function failed-services --description "List failed system and user systemd services"
    echo -e "\033[1;34m==> Failed System Services:\033[0m"
    systemctl --failed
    echo -e "\033[1;34m==> Failed User Services:\033[0m"
    systemctl --user --failed
end

# ─────────────────────────────────────────────────────────────
# HARDWARE & PROCESS MONITORING
# ─────────────────────────────────────────────────────────────

alias gpu="watch -n 1 nvidia-smi"
alias cpu-top="ps aux --sort=-%cpu | head -n 11"
alias mem-top="ps aux --sort=-%mem | head -n 11"
alias ports="sudo ss -tulpn"

function myip --description "Display local and external IP addresses"
    set -l local_ip (ip -brief address show | awk '{print $1 " -> " $3}')
    echo -e "\033[1;34mLocal IPs:\033[0m"
    for ip in $local_ip
        echo "  $ip"
    end
    echo -e "\033[1;34mExternal IP:\033[0m"
    curl -s ifconfig.me
    echo ""
end

# ─────────────────────────────────────────────────────────────
# seiza. DESKTOP & WALLPAPERS
# ─────────────────────────────────────────────────────────────

alias welcome="seiza welcome"
alias sz="seiza"

function wall --description "Cycle to next wallpaper and synchronize theme"
    noctalia msg wallpaper-next
    sleep 0.4
    theme-sync
end

function wall-random --description "Switch to random wallpaper and synchronize theme"
    noctalia msg wallpaper-random
    sleep 0.4
    theme-sync
end

alias widgets="noctalia msg desktop-widgets-toggle-edit"
alias rice-backup="~/.local/bin/rice-backup"
alias rice-restore="~/.local/bin/rice-restore"

function reload-desktop --description "Reload Niri and Noctalia configurations safely"
    niri msg action load-config-file 2>/dev/null
    noctalia msg config-reload 2>/dev/null
    noctalia msg templates-apply 2>/dev/null
    echo -e "\033[1;32m✓ Niri & Noctalia reloaded\033[0m"
end

# ─────────────────────────────────────────────────────────────
# FILE NAVIGATION & POWER TOOLS
# ─────────────────────────────────────────────────────────────

alias ll="eza -lh --icons --group-directories-first"
alias la="eza -lah --icons --group-directories-first"
alias tree="eza --tree --icons"
alias ..="cd .."
alias ...="cd ../.."
alias ....="cd ../../.."

function md --description "Create directory and enter it"
    mkdir -p $argv[1]; and cd $argv[1]
end

function preview --description "Preview file with syntax highlighting"
    bat --style=numbers,changes --color=always $argv
end

function f --description "Fuzzy find files with live preview"
    set -l file (fzf --preview 'bat --style=numbers --color=always {} 2>/dev/null || cat {} 2>/dev/null' --height=80% --layout=reverse)
    if test -n "$file"
        echo "$file"
    end
end

alias y="yazi"

# ─────────────────────────────────────────────────────────────
# PYTHON & UV WORKFLOW (Zero Clashes, Pure Isolation)
# ─────────────────────────────────────────────────────────────

function py-venv --description "Create an isolated Python venv using uv (default 3.12)"
    set -l pyver "3.12"
    if test (count $argv) -ge 1
        set pyver $argv[1]
    end
    echo -e "\033[1;34m==> Creating clean Python $pyver virtual environment in ./.venv...\033[0m"
    uv venv --python $pyver .venv
    and echo -e "\033[1;32m✓ Virtualenv ready! Activate with: py-activate\033[0m"
end

function py-activate --description "Activate local .venv in current directory"
    if test -f "./.venv/bin/activate.fish"
        source "./.venv/bin/activate.fish"
        echo -e "\033[1;32m✓ Activated .venv (Python $(python --version))\033[0m"
    else
        echo -e "\033[1;31mError: No .venv found in current directory. Run 'py-venv' first.\033[0m"
    end
end

function py-run --description "Run Python script with uv run"
    uv run $argv
end

function pip --description "Smart pip wrapper protecting system environment"
    if test -n "$VIRTUAL_ENV"
        command pip $argv
    else
        echo -e "\033[1;33m⚠ Outside a virtual environment. System Python is protected by PEP 668.\033[0m"
        echo -e "\033[1;34mRecommended workflows:\033[0m"
        echo -e "  • \033[1mpy-venv [3.12]\033[0m       → Create a clean virtualenv in ./.venv"
        echo -e "  • \033[1mpy-activate\033[0m          → Activate ./.venv (pip will then run freely)"
        echo -e "  • \033[1muv pip install ...\033[0m   → Fast, cached package installation"
        echo -e "  • \033[1muv tool install <pkg>\033[0m → Install global CLI tool into an isolated sandbox"
        echo -e "  • \033[1muvx <pkg>\033[0m            → Run a package once without installing"
        echo ""
        if test (count $argv) -gt 0
            read -l -P "Create and activate a Python 3.12 .venv right now to install? [y/N] " confirm
            if test "$confirm" = "y" -o "$confirm" = "Y"
                py-venv 3.12
                py-activate
                uv pip $argv
            end
        end
    end
end

# ─────────────────────────────────────────────────────────────
# INTERACTIVE SHELL GREETING (Lean seiza. greeting; full overview via 'seiza welcome')
# ─────────────────────────────────────────────────────────────
function fish_greeting
    if status is-interactive
        if test "$COLUMNS" -lt 65
            printf "\033[38;2;196;181;253m✦\033[0m \033[1;38;2;238;241;250mseiza\033[1;38;2;242;184;212m.\033[0m\n"
        else
            printf "\033[38;2;196;181;253m✦\033[0m \033[1;38;2;238;241;250mseiza\033[1;38;2;242;184;212m.\033[0m \033[38;2;108;118;153m·\033[0m \033[38;2;166;176;208mA system of my own.\033[0m \033[38;2;108;118;153m· run\033[0m \033[38;2;156;201;255m'seiza welcome'\033[0m\n"
        end
    end
end

set -x PYTORCH_CUDA_ALLOC_CONF expandable_segments:True

set -gx PATH "$HOME/.local/bin" $PATH

# The next line updates PATH for the Google Cloud SDK.

# Optional machine-local secrets or extra tool paths (untracked)
if test -f "$HOME/.config/fish/local.fish"
    source "$HOME/.config/fish/local.fish"
end
