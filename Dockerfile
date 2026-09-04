FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    libreoffice \
    libreoffice-writer \
    libreoffice-calc \
    libreoffice-impress \
    pandoc \
    ffmpeg \
    tesseract-ocr \
    imagemagick \
    calibre \
    libgl1 \
    libegl1 \
    libxkbcommon-x11-0 \
    libxcb-cursor0 \
    libxcb-icccm4 \
    libxcb-keysyms1 \
    libxcb-shape0 \
    libxcb-xinerama0 \
    libxcb-randr0 \
    libxcb-sync1 \
    libxcb-util1 \
    libxcb-xfixes0 \
    libxcb-xkb1 \
    libxcb1 \
    libfontconfig1 \
    libfreetype6 \
    libdbus-1-3 \
    ca-certificates \
    xauth \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV VIRTUAL_ENV=/opt/localconvert/venv
RUN python3 -m venv "$VIRTUAL_ENV"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

COPY requirements.txt /opt/localconvert/requirements.txt
RUN pip install --no-cache-dir -r /opt/localconvert/requirements.txt

COPY app/ /opt/localconvert/app/

WORKDIR /opt/localconvert

ENV LOCALCONVERT_OUTPUT_DIR=/output \
    LOCALCONVERT_CONFIG_DIR=/config

RUN mkdir -p /output /config /workspace

ENTRYPOINT ["python3", "-m", "app.main"]