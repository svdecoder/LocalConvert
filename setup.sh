#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/venv"

# ── helpers ───────────────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { printf "${CYAN}  [*]${NC} %s\n" "$*"; }
ok()    { printf "${GREEN}  [✓]${NC} %s\n" "$*"; }
warn()  { printf "${YELLOW}  [!]${NC} %s\n" "$*"; }
err()   { printf "${RED}  [✗]${NC} %s\n" "$*"; }
step()  { printf "\n${GREEN}═══ %s ═══${NC}\n\n" "$*"; }
banner() {
    printf "${CYAN}"
    echo "  ╔══════════════════════════════════════════╗"
    echo "  ║          LocalConvert Setup              ║"
    echo "  ║  Install all dependencies automatically  ║"
    echo "  ╚══════════════════════════════════════════╝"
    printf "${NC}\n"
}

# ── privilege check ────────────────────────────────────────────────────

ensure_sudo() {
    if [ "$(id -u)" -eq 0 ]; then
        return 0
    fi
    if command -v sudo &>/dev/null; then
        info "Some system packages may require admin privileges."
        sudo -v || true
    fi
}

run_sudo() {
    if [ "$(id -u)" -eq 0 ]; then
        "$@"
    elif command -v sudo &>/dev/null; then
        sudo "$@"
    else
        "$@"
    fi
}

# ── OS detection ───────────────────────────────────────────────────────

detect_os() {
    case "$(uname -s)" in
        Linux)
            OS="linux"
            if   command -v apt         &>/dev/null; then PKG_MGR="apt"
            elif command -v dnf         &>/dev/null; then PKG_MGR="dnf"
            elif command -v pacman      &>/dev/null; then PKG_MGR="pacman"
            elif command -v zypper      &>/dev/null; then PKG_MGR="zypper"
            else PKG_MGR="unknown"; fi
            ;;
        Darwin)
            OS="macos"
            if command -v brew &>/dev/null; then PKG_MGR="brew"; else PKG_MGR="unknown"; fi
            ;;
        *)
            OS="unknown"
            PKG_MGR="unknown"
            ;;
    esac

    if [ "$PKG_MGR" = "unknown" ] && [ "$OS" != "unknown" ]; then
        warn "Could not detect a supported package manager on $OS."
        warn "You will need to install system tools manually."
        warn "See: https://github.com/svdecoder/localconvert#readme"
    fi
}

# ── Python venv + pip packages ─────────────────────────────────────────

setup_python_venv() {
    step "1/2  Python virtual environment"

    local python_cmd=""
    for cmd in python3 python; do
        if command -v "$cmd" &>/dev/null; then
            local ver
            ver=$("$cmd" -c 'import sys; print(sys.version_info[:2])' 2>/dev/null || true)
            # Check major >= 3 and minor >= 10
            local major minor
            major=$(echo "$ver" | grep -oP '\d+' | head -1)
            minor=$(echo "$ver" | grep -oP '\d+' | tail -1)
            if [ "$major" -ge 3 ] 2>/dev/null && [ "$minor" -ge 10 ] 2>/dev/null; then
                python_cmd="$cmd"
                break
            fi
        fi
    done

    if [ -z "$python_cmd" ]; then
        err "Python >= 3.10 not found. Install Python 3.10+ and re-run."
        case "$PKG_MGR" in
            apt)    echo "    sudo apt install python3 python3-venv python3-pip" ;;
            dnf)    echo "    sudo dnf install python3 python3-pip" ;;
            pacman) echo "    sudo pacman -S python python-pip" ;;
            brew)   echo "    brew install python@3" ;;
        esac
        exit 1
    fi
    ok "Found: $python_cmd ($("$python_cmd" --version 2>&1))"

    if [ -d "$VENV_DIR" ]; then
        info "Virtual environment already exists at ${VENV_DIR}"
        info "Use --recreate to rebuild it from scratch."
    else
        info "Creating virtual environment..."
        "$python_cmd" -m venv "$VENV_DIR"
        ok "Virtual environment created at ${VENV_DIR}"
    fi

    # shellcheck disable=SC1091
    source "${VENV_DIR}/bin/activate"

    info "Upgrading pip..."
    pip install --upgrade pip --quiet

    info "Installing Python packages from requirements.txt..."
    pip install -r "${SCRIPT_DIR}/requirements.txt"

    ok "Python packages installed"
    deactivate
}

recreate_venv() {
    step "Recreating virtual environment"
    if [ -d "$VENV_DIR" ]; then
        info "Removing existing venv..."
        rm -rf "$VENV_DIR"
    fi
    setup_python_venv
}

# ── system tools ───────────────────────────────────────────────────────

command_exists() { command -v "$1" &>/dev/null; }

install_apt() {
    local packages=()
    command_exists soffice      || packages+=(libreoffice)
    command_exists pandoc       || packages+=(pandoc)
    command_exists ffmpeg       || packages+=(ffmpeg)
    command_exists tesseract    || packages+=(tesseract-ocr)
    command_exists ebook-convert || packages+=(calibre)
    # ImageMagick is optional — install if user wants full support
    command_exists magick && command_exists convert || packages+=(imagemagick)

    if [ ${#packages[@]} -eq 0 ]; then
        ok "All system tools already installed"
        return
    fi
    info "Installing: ${packages[*]}"
    run_sudo apt update -qq && run_sudo apt install -y "${packages[@]}"
}

install_dnf() {
    local packages=()
    command_exists soffice      || packages+=(libreoffice)
    command_exists pandoc       || packages+=(pandoc)
    command_exists ffmpeg       || packages+=(ffmpeg-free)
    command_exists tesseract    || packages+=(tesseract)
    command_exists ebook-convert && : || warn "Calibre not available via DNF — install from https://calibre-ebook.com/download"
    command_exists magick && command_exists convert || packages+=(ImageMagick)

    if [ ${#packages[@]} -eq 0 ]; then
        ok "All system tools already installed"
        return
    fi
    info "Installing: ${packages[*]}"
    run_sudo dnf install -y "${packages[@]}"
}

install_pacman() {
    local packages=()
    command_exists soffice      || packages+=(libreoffice-fresh)
    command_exists pandoc       || packages+=(pandoc)
    command_exists ffmpeg       || packages+=(ffmpeg)
    command_exists tesseract    || packages+=(tesseract)
    command_exists ebook-convert || packages+=(calibre)
    command_exists magick && command_exists convert || packages+=(imagemagick)

    if [ ${#packages[@]} -eq 0 ]; then
        ok "All system tools already installed"
        return
    fi
    info "Installing: ${packages[*]}"
    run_sudo pacman -S --noconfirm --needed "${packages[@]}"
}

install_brew() {
    info "Installing with Homebrew..."

    command_exists soffice      || brew install --cask libreoffice 2>/dev/null || true
    command_exists pandoc       || brew install pandoc
    command_exists ffmpeg       || brew install ffmpeg
    command_exists tesseract    || brew install tesseract
    command_exists ebook-convert || brew install --cask calibre 2>/dev/null || true
    command_exists magick && command_exists convert || brew install imagemagick

    ok "Homebrew packages processed"
}

install_system_tools() {
    step "2/2  System tools (LibreOffice, Pandoc, Calibre, FFmpeg, ...)"

    case "$PKG_MGR" in
        apt)    install_apt ;;
        dnf)    install_dnf ;;
        pacman) install_pacman ;;
        brew)   install_brew ;;
        *)      warn "No supported package manager detected. Install these manually:"
                echo "  - LibreOffice  (https://www.libreoffice.org/download/)"
                echo "  - Pandoc       (https://pandoc.org/installing.html)"
                echo "  - Calibre      (https://calibre-ebook.com/download)"
                echo "  - FFmpeg       (https://ffmpeg.org/download.html)"
                echo "  - Tesseract    (https://github.com/tesseract-ocr/tesseract)"
                echo "  - ImageMagick  (https://imagemagick.org/script/download.php)"
                ;;
    esac
}

# ── verify ─────────────────────────────────────────────────────────────

verify_installation() {
    step "Verification"

    local all_ok=true

    check() {
        if command_exists "$1"; then
            ok "$1  ✓"
        else
            warn "$1  ✗  (not found)"
            all_ok=false
        fi
    }

    check soffice
    check pandoc
    check ffmpeg
    check ffprobe
    check tesseract
    check ebook-convert
    check magick || check convert

    # Python venv
    if [ -f "${VENV_DIR}/bin/python" ]; then
        ok "Python venv  (${VENV_DIR})"
    else
        warn "Python venv  (missing)"
        all_ok=false
    fi

    echo ""
    if $all_ok; then
        ok "All dependencies verified!"
    else
        warn "Some dependencies are missing — see warnings above."
        info "Missing tools will disable their respective conversions."
        info "Re-run this script after installing missing tools manually."
    fi
}

print_next_steps() {
    step "Ready"
    echo "  Activate the virtual environment and run LocalConvert:"
    echo ""
    echo "    source venv/bin/activate"
    echo "    python -m app.main"
    echo ""
    echo "  Or run without activating first:"
    echo ""
    echo "    venv/bin/python -m app.main"
    echo ""
    echo "  Or run the tests:"
    echo ""
    echo "    source venv/bin/activate"
    echo "    python -m pytest app/tests/ -q"
    echo ""
}

# ── main ───────────────────────────────────────────────────────────────

main() {
    banner
    detect_os
    ensure_sudo

    if [ "${1:-}" = "--recreate" ]; then
        recreate_venv
    else
        setup_python_venv
    fi

    install_system_tools
    verify_installation
    print_next_steps
}

main "$@"