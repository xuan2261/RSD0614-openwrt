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
cp "$PORT_DIR/seed-rsd0614-initramfs.config" "$OPENWRT_DIR/.config"
cd "$OPENWRT_DIR"; STAGE=defconfig; make defconfig; python3 "$PORT_DIR/check_config.py" .config; cp .config "$OUT_DIR/openwrt.config"
STAGE=download; make download V=s
STAGE=compile; make -j"$JOBS" V=s
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
