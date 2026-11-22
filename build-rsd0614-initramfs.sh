#!/usr/bin/env bash
# Dedicated Linux-volume build. Never communicates with the router.
set -Eeuo pipefail
PORT_DIR="${PORT_DIR:-/port}"
WORK_DIR="${WORK_DIR:-/work}"
OUT_DIR="${OUT_DIR:-/out}"
JOBS="${JOBS:-2}"
[[ "$JOBS" =~ ^[1-8]$ ]] || { echo 'JOBS must be 1..8'; exit 2; }
[[ "$(id -u)" != 0 ]] || { echo 'Do not compile OpenWrt as root'; exit 2; }
mkdir -p "$WORK_DIR" "$OUT_DIR"
exec > >(tee -a "$OUT_DIR/build.log") 2>&1
STAGE=preflight
on_exit() {
    local rc=$?
    trap - EXIT
    printf 'stage=%s\nexit_code=%s\nram_boot_authorized=false\n' "$STAGE" "$rc" > "$OUT_DIR/STATUS.txt"
    if (( rc != 0 )); then echo "BUILD STOPPED: stage=$STAGE exit=$rc. Keep this log; do not boot a candidate."; fi
    exit "$rc"
}
trap on_exit EXIT
exec 9>"$WORK_DIR/.rsd0614-build.lock"
flock -n 9 || { echo 'Another RSD0614 build holds this volume'; exit 2; }
probe="$(mktemp -d "$WORK_DIR/.case-check.XXXXXX")"
printf A > "$probe/A"; printf b > "$probe/a"
[[ "$(cat "$probe/A")" == A ]] || { echo 'Case-sensitive Linux filesystem required'; exit 2; }
rm -f "$probe/A" "$probe/a"; rmdir "$probe"
python3 "$PORT_DIR/run_tests.py"
DONOR_COMMIT=229536d89c25a676417717304fcef386a53a7875
BASE_COMMIT=8a0ccb93f3431bcf8f5c5d03d4acc2c8e442de67
DONOR_DIR="$WORK_DIR/donor"; OPENWRT_DIR="$WORK_DIR/openwrt"
fingerprint="$(cd "$PORT_DIR"; sha256sum RSD0614.dts seed-rsd0614-initramfs.config apply_rsd0614_profile.py harden_source.py patches/*.patch SOURCE_LOCK.json | sha256sum | cut -d' ' -f1)"
project_commit="${PROJECT_COMMIT:-}"
if [[ -z "$project_commit" ]]; then project_commit="$(git -C "$PORT_DIR" rev-parse HEAD 2>/dev/null || true)"; fi
[[ -n "$project_commit" ]] || project_commit=NOT_AVAILABLE
builder_image_id="${BUILDER_IMAGE_ID:-NOT_RECORDED}"
printf '%s\n' "$fingerprint" > "$OUT_DIR/PORT_INPUT_FINGERPRINT.txt"
if [[ -f "$WORK_DIR/.port-fingerprint" ]]; then
    [[ "$(cat "$WORK_DIR/.port-fingerprint")" == "$fingerprint" ]] || { echo 'Port inputs differ from this workspace. Preserve it and use a new work volume.'; exit 2; }
fi
checkout_exact() {
    local directory=$1 url=$2 commit=$3 actual origin
    if [[ ! -d "$directory/.git" ]]; then
        if [[ -d "$directory" ]] && [[ -n "$(ls -A "$directory")" ]]; then echo "Non-Git directory is not empty: $directory"; return 2; fi
        git init "$directory"; git -C "$directory" remote add origin "$url"
    fi
    origin="$(git -C "$directory" remote get-url origin)"; [[ "$origin" == "$url" ]] || return 2
    if actual="$(git -C "$directory" rev-parse --verify HEAD 2>/dev/null)"; then [[ "$actual" == "$commit" ]] || return 2; else git -C "$directory" fetch --depth=1 origin "$commit"; git -C "$directory" checkout --detach FETCH_HEAD; fi
    [[ "$(git -C "$directory" rev-parse HEAD)" == "$commit" ]]
}
STAGE=donor_checkout; checkout_exact "$DONOR_DIR" https://github.com/ADCDS/openwrt-dlink-dir842-r1.git "$DONOR_COMMIT"
STAGE=profile; python3 "$PORT_DIR/apply_rsd0614_profile.py" --repo "$DONOR_DIR" --port-dir "$PORT_DIR"
STAGE=base_checkout; checkout_exact "$OPENWRT_DIR" https://github.com/ggbruno/openwrt "$BASE_COMMIT"
cp -a "$DONOR_DIR/files/." "$OPENWRT_DIR/"
STAGE=source_isolation; python3 "$PORT_DIR/harden_source.py" --tree "$OPENWRT_DIR" --port "$PORT_DIR" --audit "$WORK_DIR/source-audit" | tee "$OUT_DIR/SOURCE_HARDENING.txt"
printf '%s\n' "$fingerprint" > "$WORK_DIR/.port-fingerprint"
zst_decompress() {
    local src=$1
    if command -v zstd >/dev/null 2>&1; then
        zstd -dc "$src"
    elif [[ -x "$OPENWRT_DIR/staging_dir/host/bin/zstd" ]]; then
        "$OPENWRT_DIR/staging_dir/host/bin/zstd" -dc "$src"
    else
        python3 -c '
import ctypes, sys
lib = ctypes.CDLL("libzstd.so.1")
class Buf(ctypes.Structure):
    _fields_ = [("p", ctypes.c_void_p), ("size", ctypes.c_size_t), ("pos", ctypes.c_size_t)]
lib.ZSTD_isError.argtypes = [ctypes.c_size_t]; lib.ZSTD_isError.restype = ctypes.c_uint
lib.ZSTD_getErrorName.argtypes = [ctypes.c_size_t]; lib.ZSTD_getErrorName.restype = ctypes.c_char_p
lib.ZSTD_createDStream.argtypes = []; lib.ZSTD_createDStream.restype = ctypes.c_void_p
lib.ZSTD_initDStream.argtypes = [ctypes.c_void_p]; lib.ZSTD_initDStream.restype = ctypes.c_size_t
lib.ZSTD_decompressStream.argtypes = [ctypes.c_void_p, ctypes.POINTER(Buf), ctypes.POINTER(Buf)]; lib.ZSTD_decompressStream.restype = ctypes.c_size_t
lib.ZSTD_freeDStream.argtypes = [ctypes.c_void_p]; lib.ZSTD_freeDStream.restype = ctypes.c_size_t
dctx = lib.ZSTD_createDStream(); lib.ZSTD_initDStream(dctx)
out_b = ctypes.create_string_buffer(1048576)
try:
    with open(sys.argv[1], "rb") as fi:
        while True:
            ch = fi.read(262144)
            if not ch: break
            in_b = ctypes.create_string_buffer(ch, len(ch))
            ib = Buf(ctypes.cast(in_b, ctypes.c_void_p), len(ch), 0)
            while ib.pos < ib.size:
                ob = Buf(ctypes.cast(out_b, ctypes.c_void_p), len(out_b), 0)
                rc = lib.ZSTD_decompressStream(dctx, ctypes.byref(ob), ctypes.byref(ib))
                if lib.ZSTD_isError(rc): raise RuntimeError(lib.ZSTD_getErrorName(rc).decode())
                if ob.pos: sys.stdout.buffer.write(out_b.raw[:ob.pos])
    sys.stdout.buffer.flush()
finally:
    lib.ZSTD_freeDStream(dctx)
' "$src"
    fi
}
zst_compress() {
    local dst=$1
    if command -v zstd >/dev/null 2>&1; then
        zstd -T0 -3 -f -o "$dst"
    elif [[ -x "$OPENWRT_DIR/staging_dir/host/bin/zstd" ]]; then
        "$OPENWRT_DIR/staging_dir/host/bin/zstd" -T0 -3 -f -o "$dst"
    else
        python3 -c '
import ctypes, sys
lib = ctypes.CDLL("libzstd.so.1")
class Buf(ctypes.Structure):
    _fields_ = [("p", ctypes.c_void_p), ("size", ctypes.c_size_t), ("pos", ctypes.c_size_t)]
lib.ZSTD_isError.argtypes = [ctypes.c_size_t]; lib.ZSTD_isError.restype = ctypes.c_uint
lib.ZSTD_getErrorName.argtypes = [ctypes.c_size_t]; lib.ZSTD_getErrorName.restype = ctypes.c_char_p
lib.ZSTD_createCStream.argtypes = []; lib.ZSTD_createCStream.restype = ctypes.c_void_p
lib.ZSTD_initCStream.argtypes = [ctypes.c_void_p, ctypes.c_int]; lib.ZSTD_initCStream.restype = ctypes.c_size_t
lib.ZSTD_compressStream.argtypes = [ctypes.c_void_p, ctypes.POINTER(Buf), ctypes.POINTER(Buf)]; lib.ZSTD_compressStream.restype = ctypes.c_size_t
lib.ZSTD_endStream.argtypes = [ctypes.c_void_p, ctypes.POINTER(Buf)]; lib.ZSTD_endStream.restype = ctypes.c_size_t
lib.ZSTD_freeCStream.argtypes = [ctypes.c_void_p]; lib.ZSTD_freeCStream.restype = ctypes.c_size_t
cctx = lib.ZSTD_createCStream(); lib.ZSTD_initCStream(cctx, 3)
out_b = ctypes.create_string_buffer(1048576)
try:
    with open(sys.argv[1], "wb") as fo:
        while True:
            ch = sys.stdin.buffer.read(262144)
            if not ch: break
            in_b = ctypes.create_string_buffer(ch, len(ch))
            ib = Buf(ctypes.cast(in_b, ctypes.c_void_p), len(ch), 0)
            while ib.pos < ib.size:
                ob = Buf(ctypes.cast(out_b, ctypes.c_void_p), len(out_b), 0)
                rc = lib.ZSTD_compressStream(cctx, ctypes.byref(ob), ctypes.byref(ib))
                if lib.ZSTD_isError(rc): raise RuntimeError(lib.ZSTD_getErrorName(rc).decode())
                if ob.pos: fo.write(out_b.raw[:ob.pos])
        while True:
            ob = Buf(ctypes.cast(out_b, ctypes.c_void_p), len(out_b), 0)
            rc = lib.ZSTD_endStream(cctx, ctypes.byref(ob))
            if lib.ZSTD_isError(rc): raise RuntimeError(lib.ZSTD_getErrorName(rc).decode())
            if ob.pos: fo.write(out_b.raw[:ob.pos])
            if rc == 0: break
finally:
    lib.ZSTD_freeCStream(cctx)
' "$dst"
    fi
}
save_toolchain_seed() {
    local dest=$1 tmp="${1}.tmp.$$" list
    list="$(mktemp "$WORK_DIR/.seed-list.XXXXXX")"
    (
        cd "$OPENWRT_DIR"
        for d in staging_dir/host staging_dir/hostpkg staging_dir/toolchain-*; do
            [[ -d "$d" ]] && printf '%s\0' "$d"
        done
        for d in build_dir/host build_dir/hostpkg build_dir/toolchain-*; do
            [[ -d "$d" ]] && find "$d" -maxdepth 2 -type f -name '.*' -size 0 -print0
        done
    ) > "$list"
    if [[ -s "$list" ]]; then
        tar -C "$OPENWRT_DIR" --null -T "$list" -cf - | zst_compress "$tmp"
        mv -f "$tmp" "$dest"
    fi
    rm -f "$list" "$tmp"
    chmod -R a+rX "$CACHE_DIR" 2>/dev/null || true
}
cp "$PORT_DIR/seed-rsd0614-initramfs.config" "$OPENWRT_DIR/.config"
cd "$OPENWRT_DIR"; STAGE=defconfig; make defconfig; python3 "$PORT_DIR/check_config.py" .config; cp .config "$OUT_DIR/openwrt.config"
need_seed_refresh=0
if [[ -n "${CACHE_DIR:-}" ]]; then
    STAGE=cache_hydrate
    mkdir -p "$CACHE_DIR/dl" "$CACHE_DIR/seed" "$OPENWRT_DIR/dl"
    tc_key="$( { printf '%s\n%s\n' "$BASE_COMMIT" "$builder_image_id"; grep -E '^CONFIG_(ARCH|CPU_TYPE|TARGET_ARCH_PACKAGES|GCC_VERSION|MUSL|BINUTILS|GDB|CCACHE|AUTOREMOVE)' .config || true; } | sha256sum | cut -d' ' -f1 )"
    tc_seed="$CACHE_DIR/seed/toolchain-$tc_key.tar.zst"
    cp -an "$CACHE_DIR/dl/." "$OPENWRT_DIR/dl/" 2>/dev/null || true
    if [[ -s "$tc_seed" ]]; then
        echo "CACHE_HYDRATE: hit $tc_seed"
        zst_decompress "$tc_seed" | tar -C "$OPENWRT_DIR" -xf -
        sleep 1
        find "$OPENWRT_DIR/build_dir/host" "$OPENWRT_DIR/build_dir/hostpkg" "$OPENWRT_DIR"/build_dir/toolchain-* -maxdepth 2 -type f -name '.prepared*' -exec touch -c {} + 2>/dev/null || true
        find "$OPENWRT_DIR/build_dir/host" "$OPENWRT_DIR/build_dir/hostpkg" "$OPENWRT_DIR"/build_dir/toolchain-* -maxdepth 2 -type f -name '.configured*' -exec touch -c {} + 2>/dev/null || true
        find "$OPENWRT_DIR/build_dir/host" "$OPENWRT_DIR/build_dir/hostpkg" "$OPENWRT_DIR"/build_dir/toolchain-* -maxdepth 2 -type f -name '.built*' -exec touch -c {} + 2>/dev/null || true
        touch -c "$OPENWRT_DIR/staging_dir/host/.prepared" "$OPENWRT_DIR"/staging_dir/toolchain-*/info.mk 2>/dev/null || true
        find "$OPENWRT_DIR/staging_dir/host/stamp" "$OPENWRT_DIR/staging_dir/hostpkg/stamp" "$OPENWRT_DIR"/staging_dir/toolchain-*/stamp -type f -exec touch -c {} + 2>/dev/null || true
        [[ -d "$OPENWRT_DIR/staging_dir/hostpkg" ]] || need_seed_refresh=1
    else
        echo "CACHE_HYDRATE: miss $tc_seed"
        need_seed_refresh=1
    fi
fi
STAGE=download; make download V=s
if [[ -n "${CACHE_DIR:-}" ]]; then
    cp -au "$OPENWRT_DIR/dl/." "$CACHE_DIR/dl/" 2>/dev/null || true
    if [[ ! -s "$tc_seed" ]]; then
        STAGE=toolchain; make -j"$JOBS" tools/compile toolchain/compile V=s
        STAGE=cache_save_toolchain; save_toolchain_seed "$tc_seed"
    fi
fi
STAGE=compile; make -j"$JOBS" V=s
if [[ -n "${CACHE_DIR:-}" ]]; then
    STAGE=cache_save
    cp -au "$OPENWRT_DIR/dl/." "$CACHE_DIR/dl/" 2>/dev/null || true
    if [[ "$need_seed_refresh" == 1 || ! -s "$tc_seed" ]]; then
        save_toolchain_seed "$tc_seed"
    else
        chmod -R a+rX "$CACHE_DIR" 2>/dev/null || true
    fi
fi
STAGE=build_evidence; python3 "$PORT_DIR/export_build_evidence.py" "$OPENWRT_DIR" "$OUT_DIR" --log "$OUT_DIR/build.log" --port-fingerprint "$fingerprint" --project-commit "$project_commit" --builder-image-id "$builder_image_id"
STAGE=artifact_screen; TARGET="$OPENWRT_DIR/bin/targets/realtek/rtl8197f"
mapfile -d '' -t images < <(find "$TARGET" -maxdepth 1 -type f -iname '*rsd0614*initramfs-kernel.bin' -print0)
[[ "${#images[@]}" == 1 ]] || { echo "Expected exactly one candidate; found ${#images[@]}"; exit 3; }
IMAGE="${images[0]}"; cp "$IMAGE" "$OUT_DIR/"
python3 "$PORT_DIR/verify_rsd0614_initramfs.py" "$OUT_DIR/$(basename "$IMAGE")" | tee "$OUT_DIR/VERIFY.txt"
STAGE=deep_offline_audit; python3 "$PORT_DIR/deep_audit.py" "$OUT_DIR/$(basename "$IMAGE")" --json "$OUT_DIR/BINARY_AUDIT.json" | tee "$OUT_DIR/BINARY_AUDIT.txt"
cp "$PORT_DIR/SOURCE_LOCK.json" "$OUT_DIR/"
if [[ -r /opt/rsd0614/builder-packages.tsv ]]; then cp /opt/rsd0614/builder-packages.tsv "$OUT_DIR/"; fi
{
 echo 'COMPILE=PASS'; echo 'ARTIFACT_SCREEN=PASS'; echo 'OFFLINE_STRUCTURAL_AUDIT=PASS'; echo 'BOOT_QUALIFICATION=NOT_YET_VERIFIED'; echo 'RAM_BOOT_AUTHORIZED=NO'; echo "donor_commit=$DONOR_COMMIT"; echo "base_commit=$BASE_COMMIT"; echo "port_input_fingerprint=$fingerprint"; echo "project_commit=$project_commit"; echo "builder_image_id=$builder_image_id"; sha256sum "$OUT_DIR/$(basename "$IMAGE")"; stat -c 'size=%s' "$OUT_DIR/$(basename "$IMAGE")";
} > "$OUT_DIR/BUILD_RESULT.txt"
STAGE=finished_candidate_requires_review
echo 'COMPILE FINISHED. Candidate requires binary review; do not load or execute it on the router.'
