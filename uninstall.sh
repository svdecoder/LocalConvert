#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/venv"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { printf "${CYAN}  [*]${NC} %s\n" "$*"; }
ok()    { printf "${GREEN}  [OK]${NC} %s\n" "$*"; }
warn()  { printf "${YELLOW}  [!]${NC} %s\n" "$*"; }
step()  { printf "\n${GREEN}=== %s ===${NC}\n\n" "$*"; }

banner() {
    printf "${CYAN}"
    echo "  +------------------------------------------+"
    echo "  |       LocalConvert Uninstaller           |"
    echo "  +------------------------------------------+"
    printf "${NC}\n"
}

ensure_sudo() {
    if [ "$(id -u)" -eq 0 ]; then return 0; fi
    if command -v sudo &>/dev/null; then
        sudo -v || true
    fi
}

run_sudo() {
    if [ "$(id -u)" -eq 0 ]; then "$@"
    elif command -v sudo &>/dev/null; then sudo "$@"
    else "$@"
    fi
}

detect_os() {
    case "$(uname -s)" in
        Linux)
            if   command -v apt         &>/dev/null; then PKG_MGR="apt"
            elif command -v dnf         &>/dev/null; then PKG_MGR="dnf"
            elif command -v pacman      &>/dev/null; then PKG_MGR="pacman"
            elif command -v zypper      &>/dev/null; then PKG_MGR="zypper"
            else PKG_MGR="unknown"; fi
            ;;
        Darwin)
            command -v brew &>/dev/null && PKG_MGR="brew" || PKG_MGR="unknown"
            ;;
        *)
            PKG_MGR="unknown"
            ;;
    esac
}

confirm() {
    echo ""
    warn "This will remove the Python virtual environment and system tools."
    warn "Packages: LibreOffice, Pandoc, Calibre, FFmpeg, Tesseract, ImageMagick"
    echo ""
    read -rp "  Continue? [y/N] " yn
    case "$yn" in
        [yY]|[yY][eE][sS]) return 0 ;;
        *) info "Aborted."; exit 0 ;;
    esac
}

remove_venv() {
    step "1/2  Python virtual environment"
    if [ -d "$VENV_DIR" ]; then
        info "Removing $VENV_DIR ..."
        rm -rf "$VENV_DIR"
        ok "Virtual environment removed"
    else
        ok "No virtual environment found"
    fi
}

remove_apt() {
    local pkgs=(libreoffice pandoc ffmpeg calibre tesseract-ocr imagemagick)
    local to_remove=()
    for pkg in "${pkgs[@]}"; do
        dpkg -s "$pkg" &>/dev/null && to_remove+=("$pkg")
    done
    if [ ${#to_remove[@]} -eq 0 ]; then
        ok "No system packages to remove"
        return
    fi
    info "Removing: ${to_remove[*]}"
    for pkg in "${to_remove[@]}"; do
        run_sudo apt remove -y "$pkg" 2>/dev/null || true
    done
    run_sudo apt autoremove -y
    ok "System packages removed"
}

remove_dnf() {
    local pkgs=(libreoffice pandoc ffmpeg-free tesseract ImageMagick)
    local to_remove=()
    for pkg in "${pkgs[@]}"; do
        rpm -q "$pkg" &>/dev/null && to_remove+=("$pkg")
    done
    if [ ${#to_remove[@]} -eq 0 ]; then
        ok "No system packages to remove"
        return
    fi
    info "Removing: ${to_remove[*]}"
    for pkg in "${to_remove[@]}"; do
        run_sudo dnf remove -y "$pkg" 2>/dev/null || true
    done
    ok "System packages removed"
}

remove_pacman() {
    local pkgs=(libreoffice-fresh pandoc ffmpeg calibre tesseract imagemagick)
    local to_remove=()
    for pkg in "${pkgs[@]}"; do
        pacman -Qi "$pkg" &>/dev/null && to_remove+=("$pkg")
    done
    if [ ${#to_remove[@]} -eq 0 ]; then
        ok "No system packages to remove"
        return
    fi
    info "Removing: ${to_remove[*]}"
    for pkg in "${to_remove[@]}"; do
        run_sudo pacman -Rns --noconfirm "$pkg" 2>/dev/null || true
    done
    ok "System packages removed"
}

remove_brew() {
    info "Uninstalling Homebrew casks/formulae..."
    brew uninstall --cask libreoffice 2>/dev/null || true
    brew uninstall pandoc ffmpeg tesseract imagemagick 2>/dev/null || true
    brew uninstall --cask calibre 2>/dev/null || true
    ok "Homebrew packages processed"
}

remove_unknown() {
    warn "Could not detect package manager. Remove these manually:"
    echo "  - LibreOffice"
    echo "  - Pandoc"
    echo "  - Calibre"
    echo "  - FFmpeg"
    echo "  - Tesseract"
    echo "  - ImageMagick"
}

remove_system_tools() {
    step "2/2  System tools"
    case "$PKG_MGR" in
        apt)    remove_apt ;;
        dnf)    remove_dnf ;;
        pacman) remove_pacman ;;
        brew)   remove_brew ;;
        *)      remove_unknown ;;
    esac
}

print_done() {
    step "Done"
    ok "LocalConvert dependencies have been uninstalled."
    echo ""
    info "Config folder (~/.config/LocalConvert/) left untouched."
    echo "  Remove manually: rm -rf ~/.config/LocalConvert"
    echo ""
    info "Docker output/config folders left untouched."
    echo "  Remove manually: rm -rf ./output ./docker-config"
}

main() {
    banner
    detect_os
    ensure_sudo
    confirm
    remove_venv
    remove_system_tools
    print_done
}

main
