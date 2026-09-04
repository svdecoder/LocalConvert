#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT_DIR="${OUTPUT_DIR:-${SCRIPT_DIR}/output}"
CONFIG_DIR="${CONFIG_DIR:-${SCRIPT_DIR}/docker-config}"

mkdir -p "$OUTPUT_DIR" "$CONFIG_DIR"

# ── Help ──────────────────────────────────────────────────────────────

usage() {
    cat <<EOF
Usage: ./docker-run.sh [COMMAND]

Commands:
  build         Build the Docker image
  run           Run with X11 forwarding (Linux desktop, default)
  novnc         Run with noVNC (headless / remote access, port 6080)
  stop          Stop running container
  clean         Remove container, image, and local output/config dirs

Examples:
  ./docker-run.sh build && ./docker-run.sh run
  OUTPUT_DIR=~/converted ./docker-run.sh run
EOF
    exit 0
}

# ── Build ─────────────────────────────────────────────────────────────

build() {
    echo "=== Building LocalConvert Docker image ==="
    docker compose -f "$SCRIPT_DIR/docker-compose.yml" build localconvert
    echo "Build complete. Run './docker-run.sh run' to start."
}

build_novnc() {
    echo "=== Building LocalConvert Docker image (VNC variant) ==="
    docker compose -f "$SCRIPT_DIR/docker-compose.yml" build localconvert-novnc
    echo "Build complete. Run './docker-run.sh novnc' to start."
}

# ── Run (X11 forwarding) ──────────────────────────────────────────────

run() {
    if [ ! -d /tmp/.X11-unix ]; then
        echo "ERROR: X11 socket (/tmp/.X11-unix) not found."
        echo "This mode requires a running X server (Linux desktop)."
        echo "For headless/remote use: ./docker-run.sh novnc"
        exit 1
    fi

    xhost +local:docker >/dev/null 2>&1 || true

    local xauth_path="${XAUTHORITY:-${HOME}/.Xauthority}"
    export XAUTHORITY="$xauth_path"
    export OUTPUT_DIR OUTPUT_DIR CONFIG_DIR

    echo "=== Starting LocalConvert (X11 mode) ==="
    echo "Output files will appear in: $OUTPUT_DIR"
    echo ""
    docker compose -f "$SCRIPT_DIR/docker-compose.yml" run --rm localconvert
}

run_novnc() {
    export OUTPUT_DIR OUTPUT_DIR CONFIG_DIR

    echo "=== Starting LocalConvert (noVNC mode) ==="
    echo "Open http://localhost:6080 in your browser"
    echo "Output files will appear in: $OUTPUT_DIR"
    echo ""
    docker compose -f "$SCRIPT_DIR/docker-compose.yml" up localconvert-novnc
}

stop() {
    docker compose -f "$SCRIPT_DIR/docker-compose.yml" down
}

clean() {
    stop
    docker compose -f "$SCRIPT_DIR/docker-compose.yml" down -v --rmi all 2>/dev/null || true
    echo "Removed containers, images, and volumes."
}

"${1:-run}"