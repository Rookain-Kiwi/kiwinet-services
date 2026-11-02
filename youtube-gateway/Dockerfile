ARG DEBIAN_IMAGE=debian:stable-slim@sha256:13e0a2e78aa0554ad5ff66e4e260c6dbcdff807eb1f39d43b9fb0288aae88b04

FROM ${DEBIAN_IMAGE} AS fetch
ARG YTDLP_VERSION=2026.10.26
ARG YTDLP_SHA256=e51e69e89489f199530f13d32a4342da3ddb2cf34842f364603a066db05afbf3
ARG DENO_VERSION=2.9.8
ARG DENO_SHA256=e890975bc2549807bbcc0b584ffafda72cc7c93349dd99c80483dd784f6c4609
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl unzip \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /dl
RUN curl -fsSLO https://github.com/yt-dlp/yt-dlp/releases/download/${YTDLP_VERSION}/yt-dlp \
 && echo "${YTDLP_SHA256}  yt-dlp" | sha256sum -c - \
 && curl -fsSLO https://github.com/denoland/deno/releases/download/v${DENO_VERSION}/deno-x86_64-unknown-linux-gnu.zip \
 && echo "${DENO_SHA256}  deno-x86_64-unknown-linux-gnu.zip" | sha256sum -c - \
 && unzip deno-x86_64-unknown-linux-gnu.zip deno \
 && chmod 755 deno yt-dlp

FROM ${DEBIAN_IMAGE}
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates ffmpeg python3 \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --gid 1001 gateway \
 && useradd --uid 1001 --gid 1001 --no-create-home --home-dir /tmp --shell /usr/sbin/nologin gateway
COPY --from=fetch /dl/deno /dl/yt-dlp /usr/local/bin/
COPY server.py /usr/local/bin/server.py
RUN chmod 755 /usr/local/bin/server.py
USER 1001:1001
ENV HOME=/tmp DENO_DIR=/tmp/deno XDG_CACHE_HOME=/tmp/cache PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ENTRYPOINT ["python3", "/usr/local/bin/server.py"]