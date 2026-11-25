#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# seiza. // A system of my own.
# Safe, idempotent CachyOS -> seiza. Wayland Workstation Installer
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_PATH="${BASH_SOURCE[0]:-}"
REPO_DIR=""
if [ -n "$SCRIPT_PATH" ] && [ -f "$SCRIPT_PATH" ]; then
  REPO_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
fi

if [ -z "$REPO_DIR" ] || [ ! -d "${REPO_DIR}/config" ] || [ ! -d "${REPO_DIR}/local" ]; then
  # Bootstrapped via curl | bash: clone or update the repository and re-exec
  if ! command -v git >/dev/null 2>&1; then
    echo "Installing git for bootstrap..."
    sudo pacman -S --needed --noconfirm git
  fi
  CLONE_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/seiza-repo"
  if [ -d "${CLONE_DIR}/.git" ]; then
    git -C "$CLONE_DIR" pull --ff-only
  else
    mkdir -p "$(dirname "$CLONE_DIR")"
    git clone https://github.com/VIKSIT-GARG/seiza.git "$CLONE_DIR"
  fi
  exec bash "${CLONE_DIR}/run.sh" "$@"
fi
BACKUP_ROOT="${HOME}/.config/rice_backups"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="${BACKUP_ROOT}/pre_seiza_install_${TIMESTAMP}"

DRY_RUN=0
SKIP_PACKAGES=0
NO_BACKUP=0
AUTO_YES=0
FORCE_DISPLAY=0
WITH_BROWSER=0
SET_SHELL=0
DO_RESTORE=0

CYAN='\033[38;2;156;201;255m'
LAVENDER='\033[38;2;196;181;253m'
MINT='\033[38;2;156;224;194m'
AMBER='\033[38;2;245;214;168m'
RED='\033[38;2;242;143;173m'
DIM='\033[38;2;108;118;153m'
BOLD='\033[1m'
NC='\033[0m'

log()  { printf "${LAVENDER}✦${NC} %s\n" "$*"; }
ok()   { printf "${MINT}✓${NC} %s\n" "$*"; }
warn() { printf "${AMBER}!${NC} %s\n" "$*"; }
err()  { printf "${RED}✗${NC} %s\n" "$*" >&2; }

usage() {
  cat <<'EOF'
seiza. // CachyOS -> Niri + Noctalia Workstation Transformer

Usage:
  ./run.sh [options]

Options:
  --dry-run          Preview installation steps without modifying your system
  --skip-packages    Install configs, scripts, wallpapers & GUIs without pacman
  --no-backup        Skip creating a pre-install configuration backup
  --force-display    Overwrite ~/.config/niri/cfg/display.kdl even if present
  --with-browser     Install firefox if no Wayland browser is currently installed
  --set-shell        Switch default login shell to fish after setup
  --restore          Launch interactive rollback/restore helper
  -y, --yes          Assume yes to non-destructive package prompts
  -h, --help         Show this help message
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run)        DRY_RUN=1 ;;
    --skip-packages)  SKIP_PACKAGES=1 ;;
    --no-backup)      NO_BACKUP=1 ;;
    --force-display)  FORCE_DISPLAY=1 ;;
    --with-browser)   WITH_BROWSER=1 ;;
    --set-shell)      SET_SHELL=1 ;;
    --restore)        DO_RESTORE=1 ;;
    -y|--yes)         AUTO_YES=1 ;;
    -h|--help)        usage; exit 0 ;;
    *)                err "Unknown flag: $1"; usage; exit 1 ;;
  esac
  shift
done

if [ "$DO_RESTORE" -eq 1 ]; then
  if [ -x "${HOME}/.local/bin/rice-restore" ]; then
    exec "${HOME}/.local/bin/rice-restore"
  elif [ -L "${BACKUP_ROOT}/latest_pre_seiza" ] && [ -x "${BACKUP_ROOT}/latest_pre_seiza/rollback.sh" ]; then
    exec "${BACKUP_ROOT}/latest_pre_seiza/rollback.sh"
  else
    err "No seiza backup found under ${BACKUP_ROOT}."
    exit 1
  fi
fi

if [ "$EUID" -eq 0 ]; then
  err "Do not run ./run.sh as root/sudo. Run as your normal user; sudo will be requested only for pacman."
  exit 1
fi

printf "\n${LAVENDER}${BOLD}  ✦ seiza.${NC} ${DIM}//${NC} A system of my own.\n"
printf "${DIM}  Minimalist celestial CachyOS + Niri + Noctalia installer${NC}\n\n"

if [ -r /etc/os-release ]; then
  . /etc/os-release
  if [ "${ID:-}" != "cachyos" ] && [ "${ID:-}" != "arch" ] && [[ "${ID_LIKE:-}" != *"arch"* ]]; then
    warn "Detected OS '${PRETTY_NAME:-unknown}'. Designed for CachyOS / Arch Linux."
  else
    ok "Detected ${PRETTY_NAME:-Arch Linux}"
  fi
fi

# ── Package Lists (Verified Arch / CachyOS repositories) ──────────────────────
CORE_PKGS=(
  niri
  noctalia
  alacritty
  fish
  starship
  fastfetch
  fuzzel
  wl-mirror
  wlr-randr
  grim
  wl-clipboard
  cliphist
  wtype
  libnotify
  brightnessctl
  pavucontrol
  playerctl
  gpu-screen-recorder
  polkit-kde-agent
  xdg-desktop-portal-gtk
  xdg-desktop-portal-gnome
)

TOOL_PKGS=(
  python
  python-pyqt6
  python-psutil
  python-rich
  python-pillow
  python-gobject
  micro
  btop
  eza
  bat
  fzf
  yazi
  fd
  ripgrep
  pacman-contrib
  nautilus
  cava
  zathura
  zathura-pdf-mupdf
  tesseract
  tesseract-data-eng
)

THEME_PKGS=(
  adw-gtk-theme
  papirus-icon-theme
  capitaine-cursors
  ttf-jetbrains-mono-nerd
  adwaita-fonts
)

install_packages() {
  if [ "$SKIP_PACKAGES" -eq 1 ]; then
    warn "Skipping pacman package installation (--skip-packages)."
    return 0
  fi
  if ! command -v pacman >/dev/null 2>&1; then
    warn "pacman not found; skipping package installation."
    return 0
  fi

  local candidates=("${CORE_PKGS[@]}" "${TOOL_PKGS[@]}" "${THEME_PKGS[@]}")
  if [ "$WITH_BROWSER" -eq 1 ]; then
    if ! command -v zen-browser >/dev/null 2>&1 && ! command -v firefox >/dev/null 2>&1 && ! command -v chromium >/dev/null 2>&1 && ! command -v brave >/dev/null 2>&1; then
      candidates+=(firefox)
    fi
  fi

  local installable=()
  local skipped=()
  for pkg in "${candidates[@]}"; do
    if pacman -Si "$pkg" >/dev/null 2>&1; then
      installable+=("$pkg")
    else
      skipped+=("$pkg")
    fi
  done

  if [ "${#skipped[@]}" -gt 0 ]; then
    warn "Skipping packages unavailable in enabled repos: ${skipped[*]}"
  fi

  log "Syncing & installing ${#installable[@]} verified CachyOS/Arch packages (--needed)..."
  if [ "$DRY_RUN" -eq 1 ]; then
    printf "  [dry-run] sudo pacman -Syu --needed %s\n" "${installable[*]}"
    return 0
  fi

  local noconf=()
  [ "$AUTO_YES" -eq 1 ] && noconf=(--noconfirm)
  sudo pacman -Syu --needed "${noconf[@]}" "${installable[@]}"
  ok "System packages installed cleanly."
}

backup_existing() {
  if [ "$NO_BACKUP" -eq 1 ]; then
    warn "Skipping backup snapshot (--no-backup)."
    return 0
  fi

  log "Creating pre-install configuration snapshot: ${BACKUP_DIR}"
  if [ "$DRY_RUN" -eq 1 ]; then
    printf "  [dry-run] Backup ~/.config & ~/.local/bin -> %s\n" "$BACKUP_DIR"
    return 0
  fi

  mkdir -p "${BACKUP_DIR}/config" "${BACKUP_DIR}/local_bin" "${BACKUP_DIR}/noctalia_state"
  for item in niri noctalia alacritty starship.toml fish fastfetch gtk-3.0 gtk-4.0 kdeglobals fuzzel micro zathura cava seiza; do
    if [ -e "${HOME}/.config/${item}" ]; then
      cp -a "${HOME}/.config/${item}" "${BACKUP_DIR}/config/"
    fi
  done
  if [ -d "${HOME}/.local/state/noctalia" ]; then
    cp -a "${HOME}/.local/state/noctalia/." "${BACKUP_DIR}/noctalia_state/" || true
  fi
  if [ -d "${HOME}/.local/bin" ]; then
    for f in seiza theme-sync syscheck gpu-log uptime-check snap rice-backup rice-restore clipboard-picker universal-clip niri-scratchpad; do
      [ -e "${HOME}/.local/bin/${f}" ] && cp -a "${HOME}/.local/bin/${f}" "${BACKUP_DIR}/local_bin/"
    done
  fi

  cat > "${BACKUP_DIR}/rollback.sh" <<'ROLLEOF'
#!/usr/bin/env bash
set -euo pipefail
BK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "Restoring pre-seiza backup from ${BK_DIR}..."
for item in "${BK_DIR}/config"/*; do
  [ -e "$item" ] || continue
  base=$(basename "$item")
  rm -rf "${HOME}/.config/${base}"
  cp -a "$item" "${HOME}/.config/${base}"
done
mkdir -p "${HOME}/.local/state/noctalia" "${HOME}/.local/bin"
cp -a "${BK_DIR}/noctalia_state/." "${HOME}/.local/state/noctalia/" 2>/dev/null || true
cp -a "${BK_DIR}/local_bin/." "${HOME}/.local/bin/" 2>/dev/null || true
niri msg action load-config-file >/dev/null 2>&1 || true
noctalia msg config-reload >/dev/null 2>&1 || true
echo "Rollback complete."
ROLLEOF
  chmod +x "${BACKUP_DIR}/rollback.sh"
  ln -sfn "${BACKUP_DIR}" "${BACKUP_ROOT}/latest_pre_seiza"
  ok "Backup ready (rollback script: ${BACKUP_DIR}/rollback.sh)"
}

install_template() {
  local src="$1"
  local dst="$2"
  mkdir -p "$(dirname "$dst")"
  sed "s|__HOME__|${HOME}|g" "$src" > "$dst"
}

deploy_files() {
  log "Deploying seiza. wallpapers, configurations, toolkit & Noctalia plugin..."
  if [ "$DRY_RUN" -eq 1 ]; then
    printf "  [dry-run] Install wallpapers -> %s/Pictures/Wallpapers/Seiza/\n" "$HOME"
    printf "  [dry-run] Deploy configs -> %s/.config/\n" "$HOME"
    printf "  [dry-run] Deploy CLI + PyQt6 suite -> %s/.local/{bin,lib/seiza,share}\n" "$HOME"
    return 0
  fi

  # Wallpapers & screenshots directory
  mkdir -p "${HOME}/Pictures/Wallpapers/Seiza" "${HOME}/Pictures/Screenshots"
  cp -a "${REPO_DIR}/assets/wallpapers/"*.png "${HOME}/Pictures/Wallpapers/Seiza/"

  # Config directories (preserve existing display.kdl unless forced/missing)
  local had_display=0
  local saved_display=""
  if [ -f "${HOME}/.config/niri/cfg/display.kdl" ] && [ "$FORCE_DISPLAY" -eq 0 ]; then
    had_display=1
    saved_display="$(cat "${HOME}/.config/niri/cfg/display.kdl")"
  fi

  mkdir -p "${HOME}/.config"
  while IFS= read -r -d '' src_file; do
    rel="${src_file#${REPO_DIR}/config/}"
    dst="${HOME}/.config/${rel}"
    install_template "$src_file" "$dst"
  done < <(find "${REPO_DIR}/config" -type f -print0)

  if [ "$had_display" -eq 1 ]; then
    printf "%s\n" "$saved_display" > "${HOME}/.config/niri/cfg/display.kdl"
    log "Preserved existing ~/.config/niri/cfg/display.kdl (pass --force-display to replace)."
  fi

  # Local scripts & seiza Python package
  mkdir -p "${HOME}/.local/bin" "${HOME}/.local/lib/seiza"
  cp -a "${REPO_DIR}/local/bin/." "${HOME}/.local/bin/"
  chmod +x "${HOME}/.local/bin/"{seiza,theme-sync,syscheck,gpu-log,uptime-check,snap,rice-backup,rice-restore,clipboard-picker,universal-clip,niri-scratchpad}
  cp -a "${REPO_DIR}/local/lib/seiza/." "${HOME}/.local/lib/seiza/"

  # Desktop entries (templated with real $HOME)
  mkdir -p "${HOME}/.local/share/applications"
  for dfile in "${REPO_DIR}/local/share/applications/"*.desktop; do
    install_template "$dfile" "${HOME}/.local/share/applications/$(basename "$dfile")"
  done

  # Noctalia plugin (viksit-garg/seiza)
  mkdir -p "${HOME}/.local/share/noctalia/plugins/seiza"
  cp -a "${REPO_DIR}/local/share/noctalia/plugins/seiza/." "${HOME}/.local/share/noctalia/plugins/seiza/"

  # Clipboard systemd user units
  mkdir -p "${HOME}/.config/systemd/user"
  cp -a "${REPO_DIR}/systemd/user/"*.service "${HOME}/.config/systemd/user/"

  ok "All configuration files and tools deployed."
}

activate_and_validate() {
  if [ "$DRY_RUN" -eq 1 ]; then
    log "[dry-run] Would validate configs, compile Python toolkit, enable user services, and reload Niri/Noctalia."
    return 0
  fi

  log "Validating configurations and compiling Python toolkit..."
  python3 -m py_compile "${HOME}/.local/lib/seiza/"*.py "${HOME}/.local/bin/seiza"
  command -v niri >/dev/null 2>&1 && niri validate >/dev/null && ok "niri config validated"
  command -v noctalia >/dev/null 2>&1 && noctalia config validate >/dev/null && ok "noctalia config validated"
  command -v noctalia >/dev/null 2>&1 && noctalia plugins lint "${HOME}/.local/share/noctalia/plugins/seiza" >/dev/null && ok "noctalia plugin validated"
  command -v fish >/dev/null 2>&1 && fish -n "${HOME}/.config/fish/config.fish" "${HOME}/.config/fish/conf.d/seiza_theme.fish" && ok "fish syntax validated"
  command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "${HOME}/.local/share/applications" || true

  if systemctl --user status >/dev/null 2>&1; then
    systemctl --user daemon-reload || true
    systemctl --user enable --now cliphist-text.service cliphist-image.service 2>/dev/null || true
    ok "Clipboard history watchers enabled (cliphist)"
  fi

  if [ -n "${WAYLAND_DISPLAY:-}" ]; then
    niri msg action load-config-file >/dev/null 2>&1 || true
    if command -v noctalia >/dev/null 2>&1 && pgrep -u "$USER" noctalia >/dev/null 2>&1; then
      noctalia msg color-scheme-set custom seiza >/dev/null 2>&1 || true
      noctalia msg config-reload >/dev/null 2>&1 || true
      noctalia msg plugins enable viksit-garg/seiza >/dev/null 2>&1 || true
      noctalia msg templates-apply >/dev/null 2>&1 || true
    fi
    [ -x "${HOME}/.local/bin/theme-sync" ] && "${HOME}/.local/bin/theme-sync" >/dev/null 2>&1 || true
    ok "Live desktop session synchronized."
  else
    warn "No active Wayland session detected; run 'niri-session' or log into Niri to launch desktop."
  fi

  if [ "$SET_SHELL" -eq 1 ] && command -v fish >/dev/null 2>&1; then
    local fish_path
    fish_path="$(command -v fish)"
    if [ "${SHELL:-}" != "$fish_path" ]; then
      chsh -s "$fish_path"
      ok "Default login shell set to ${fish_path}."
    fi
  fi

  if command -v nvidia-smi >/dev/null 2>&1; then
    local pmode
    pmode=$(nvidia-smi --query-gpu=persistence_mode --format=csv,noheader 2>/dev/null | head -n1 | xargs || true)
    if [ "$pmode" = "Disabled" ]; then
      warn "NVIDIA GPU detected with persistence_mode Disabled (optional: sudo systemctl enable --now nvidia-persistenced)."
    fi
  fi
}

main() {
  backup_existing
  install_packages
  deploy_files
  activate_and_validate

  printf "\n${MINT}${BOLD}✓ seiza. setup complete!${NC}\n"
  printf "  • Run ${CYAN}seiza welcome${NC} or ${CYAN}seiza help${NC} to explore the CLI.\n"
  printf "  • Press ${LAVENDER}Super + Space${NC} for the Universal Command Centre.\n"
  printf "  • Press ${LAVENDER}Super + G${NC} for the AI & System Health Dashboard.\n"
  printf "  • Rollback anytime with ${CYAN}%s/rollback.sh${NC}\n\n" "${BACKUP_DIR}"
}

main
