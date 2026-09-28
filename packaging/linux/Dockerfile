FROM python:3.13-slim-bookworm
ENV DEBIAN_FRONTEND=noninteractive PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    binutils patchelf desktop-file-utils dpkg-dev squashfs-tools file \
    xvfb xauth ca-certificates fonts-dejavu-core \
    libegl1 libgl1 libopengl0 libdbus-1-3 libfontconfig1 libfreetype6 libgssapi-krb5-2 \
    libglib2.0-0 libxkbcommon0 libxkbcommon-x11-0 libxcb-cursor0 \
    libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-render-util0 \
    libxcb-shape0 libxcb-xinerama0 libxcb-xfixes0 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /workspace
COPY packaging/linux/requirements-build.txt /tmp/requirements-build.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements-build.txt
COPY . /workspace
RUN python -m pip install --no-deps .
CMD ["python", "tools/build_linux.py"]
