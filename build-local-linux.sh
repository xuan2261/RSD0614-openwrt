#!/usr/bin/env bash
# Local Linux / Cloud VM Docker build wrapper for RSD0614 initramfs.
# Uses an ephemeral clean work volume per run + persistent host CACHE_DIR.
# Never communicates with a physical router.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ "$HERE" == *,* ]]; then
    echo 'ERROR: Repository path must not contain a comma.' >&2
    exit 2
fi

CACHE_ROOT="${RSD0614_CACHE_ROOT:-$HOME/.cache/rsd0614-openwrt}"
BUILDER_IMAGE="${BUILDER_IMAGE:-rsd0614-openwrt-builder:v5.1}"
BUILDER_ARCHIVE="$CACHE_ROOT/builder/builder.tar.zst"
HOST_CACHE_DIR="$CACHE_ROOT/cache"

DEFAULT_JOBS="$(nproc 2>/dev/null || echo 2)"
if (( DEFAULT_JOBS > 8 )); then DEFAULT_JOBS=8; fi
if (( DEFAULT_JOBS < 1 )); then DEFAULT_JOBS=1; fi
JOBS="${JOBS:-$DEFAULT_JOBS}"
[[ "$JOBS" =~ ^[1-8]$ ]] || { echo 'ERROR: JOBS must be 1..8' >&2; exit 2; }

RUN_ID="$(date -u +%Y%m%d-%H%M%S)-$$"
RUN_DIR_NAME="${OUT_SUBDIR:-$RUN_ID}"
LOGS_DIR="$HERE/logs"
OUT_DIR="$HERE/out/$RUN_DIR_NAME"
mkdir -p "$LOGS_DIR" "$CACHE_ROOT/builder" "$HOST_CACHE_DIR/dl" "$HOST_CACHE_DIR/seed"
chmod 0777 "$HOST_CACHE_DIR" "$HOST_CACHE_DIR/dl" "$HOST_CACHE_DIR/seed"

command -v docker >/dev/null 2>&1 || { echo 'ERROR: docker CLI not found.' >&2; exit 2; }
command -v zstd >/dev/null 2>&1 || { echo 'ERROR: zstd CLI not found (e.g. sudo apt-get install -y zstd).' >&2; exit 2; }

if [[ "${REBUILD_BUILDER:-0}" == 1 ]] || ! docker image inspect "$BUILDER_IMAGE" >/dev/null 2>&1; then
    if [[ "${REBUILD_BUILDER:-0}" != 1 && -s "$BUILDER_ARCHIVE" ]]; then
        echo "Loading persisted builder image from $BUILDER_ARCHIVE..." | tee "$LOGS_DIR/$RUN_ID-builder.log"
        zstd -dc "$BUILDER_ARCHIVE" | docker load | tee -a "$LOGS_DIR/$RUN_ID-builder.log"
    else
        build_args=(build --platform=linux/amd64 --progress=plain --pull --build-arg DEBIAN_SNAPSHOT=20260901T000000Z -t "$BUILDER_IMAGE")
        if [[ "${REBUILD_BUILDER:-0}" == 1 ]]; then
            build_args+=(--no-cache)
        fi
        build_args+=("$HERE")
        docker "${build_args[@]}" 2>&1 | tee "$LOGS_DIR/$RUN_ID-builder.log"
        tmp_archive="$BUILDER_ARCHIVE.tmp.$$"
        docker save "$BUILDER_IMAGE" | zstd -T0 -3 -f -o "$tmp_archive"
        mv -f "$tmp_archive" "$BUILDER_ARCHIVE"
    fi
else
    existing_id="$(docker image inspect "$BUILDER_IMAGE" --format '{{.Id}}')"
    printf 'Reusing verified-family builder: %s\n' "$existing_id" > "$LOGS_DIR/$RUN_ID-builder.log"
fi

SMOKE='set -eu; test "$(id -u)" = 1000; python2 --version; python3 --version; git --version; command -v gcc; command -v make; command -v flock; cat /opt/rsd0614/debian-snapshot.txt'
docker run --rm --platform=linux/amd64 --network=none "$BUILDER_IMAGE" sh -c "$SMOKE" 2>&1 | tee "$LOGS_DIR/$RUN_ID-builder-smoke.log"

BUILDER_IMAGE_ID="$(docker image inspect "$BUILDER_IMAGE" --format '{{.Id}}')"
[[ -n "$BUILDER_IMAGE_ID" ]] || { echo 'ERROR: Unable to record builder image ID.' >&2; exit 2; }
printf '%s\n' "$BUILDER_IMAGE_ID" > "$LOGS_DIR/$RUN_ID-builder-image-id.txt"
echo 'BUILDER EXECUTION PASS on this Docker engine.'

if [[ "${BUILDER_ONLY:-0}" == 1 ]]; then
    echo 'Builder check completed. No source checkout, firmware compile, or router access was performed.'
    exit 0
fi

PROJECT_COMMIT="${PROJECT_COMMIT:-$(git -C "$HERE" rev-parse HEAD 2>/dev/null || echo NOT_AVAILABLE)}"
WORK_VOLUME="rsd0614-openwrt-v562-work-${RUN_ID}"

cleanup_volume() {
    docker volume rm -f "$WORK_VOLUME" >/dev/null 2>&1 || true
}
trap cleanup_volume EXIT

docker volume create --label "rsd0614.work=v5.6.2-ephemeral" "$WORK_VOLUME" >/dev/null
docker run --rm --platform=linux/amd64 --network=none --user 0:0 \
    --mount "type=volume,source=$WORK_VOLUME,target=/work" \
    "$BUILDER_IMAGE" sh -c 'set -eu; chown 1000:1000 /work; chmod u+rwx /work' 2>&1 | tee "$LOGS_DIR/$RUN_ID-volume-init.log"

mkdir -p "$OUT_DIR"
chmod 0777 "$OUT_DIR"

tls_args=()
if [[ -r /etc/ssl/certs/ca-certificates.crt ]]; then
    tls_args+=(
        --mount "type=bind,source=/etc/ssl/certs/ca-certificates.crt,target=/etc/ssl/certs/ca-certificates.crt,readonly"
        -e SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
        -e GIT_SSL_CAINFO=/etc/ssl/certs/ca-certificates.crt
        -e CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
    )
fi

docker run --rm --platform=linux/amd64 --user 1000:1000 \
    --mount "type=volume,source=$WORK_VOLUME,target=/work" \
    --mount "type=bind,source=$HERE,target=/port,readonly" \
    --mount "type=bind,source=$OUT_DIR,target=/out" \
    -v "$HOST_CACHE_DIR:/cache" \
    -e CACHE_DIR=/cache \
    "${tls_args[@]}" \
    --env "JOBS=$JOBS" \
    --env "BUILDER_IMAGE_ID=$BUILDER_IMAGE_ID" \
    --env "PROJECT_COMMIT=$PROJECT_COMMIT" \
    --workdir /work \
    "$BUILDER_IMAGE" bash /port/build-rsd0614-initramfs.sh 2>&1 | tee "$LOGS_DIR/$RUN_ID-openwrt.log"

echo "Candidate and evidence: $OUT_DIR"
echo 'Do not load or execute the candidate on the router. Binary review is still required.'
