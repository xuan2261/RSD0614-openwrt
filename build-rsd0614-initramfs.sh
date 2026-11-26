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
WIFI_DRIVER_COMMIT=1529557b0936019462c4b24f98bc8436d359bd3a
LUCI_COMMIT=f25285a6c26e8776f153994704710cb8e51fad91
PACKAGES_COMMIT=6df6880800397ab3821572c6c5ad18e300374d9e
DONOR_DIR="$WORK_DIR/donor"; OPENWRT_DIR="$WORK_DIR/openwrt"; WIFI_DIR="$WORK_DIR/wifi-driver"; LUCI_DIR="$WORK_DIR/feed-luci"; PACKAGES_DIR="$WORK_DIR/feed-packages"
fingerprint="$(cd "$PORT_DIR"; sha256sum RSD0614.dts seed-rsd0614-initramfs.config apply_rsd0614_profile.py harden_source.py build-rsd0614-initramfs.sh packages/rtl8192cd-rsd0614/Makefile patches/*.patch SOURCE_LOCK.json | sha256sum | cut -d' ' -f1)"
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
STAGE=wifi_driver_stage
checkout_exact "$WIFI_DIR" https://github.com/tobyw121/Openwrt_RTL.git "$WIFI_DRIVER_COMMIT"
rm -rf "$OPENWRT_DIR/package/kernel/rtl8192cd-rsd0614"
mkdir -p "$OPENWRT_DIR/package/kernel/rtl8192cd-rsd0614/src"
cp "$PORT_DIR/packages/rtl8192cd-rsd0614/Makefile" "$OPENWRT_DIR/package/kernel/rtl8192cd-rsd0614/Makefile"
cp -a "$WIFI_DIR/package/kernel/rtl8192cd-rtl8197f/src/." "$OPENWRT_DIR/package/kernel/rtl8192cd-rsd0614/src/"
patch -d "$OPENWRT_DIR/package/kernel/rtl8192cd-rsd0614/src" -p1 -F0 -i "$PORT_DIR/patches/rtl8192cd-4.14-rsd0614.patch"
mkdir -p "$OPENWRT_DIR/package/network/utils/iwinfo/patches"
cp "$PORT_DIR/patches/iwinfo-wext-rsd0614.patch" "$OPENWRT_DIR/package/network/utils/iwinfo/patches/999-rsd0614-wext-rtl8192cd-compat.patch"
STAGE=feeds_stage
checkout_exact "$LUCI_DIR" https://github.com/openwrt/luci.git "$LUCI_COMMIT"
checkout_exact "$PACKAGES_DIR" https://github.com/openwrt/packages.git "$PACKAGES_COMMIT"
printf 'src-link luci %s\nsrc-link packages %s\n' "$LUCI_DIR" "$PACKAGES_DIR" > "$OPENWRT_DIR/feeds.conf"
(
    cd "$OPENWRT_DIR"
    ./scripts/feeds update luci packages
    ./scripts/feeds install luci luci-base luci-mod-admin-full luci-theme-bootstrap luci-app-firewall luci-proto-ppp luci-proto-relay cgi-io
)
python3 - "$OPENWRT_DIR/feeds/luci/modules/luci-mod-network/htdocs/luci-static/resources/view/network/wireless.js" <<'PY'
import pathlib, sys
p = pathlib.Path(sys.argv[1])
text = p.read_text()

freq_snippet = """
\t\t\tif (uci.get('wireless', section_id, 'type') == 'rtl8192cd') {
\t\t\t\tvar is5g = (uci.get('wireless', section_id, 'hwmode') == '11a' ||
\t\t\t\t            +(uci.get('wireless', section_id, 'band') || 0) >= 64 ||
\t\t\t\t            uci.get('wireless', section_id, 'phy') == 'wlan0');
\t\t\t\thtmodelist.HT20 = true;
\t\t\t\thtmodelist.HT40 = true;
\t\t\t\tif (is5g) {
\t\t\t\t\thtmodelist.VHT20 = true;
\t\t\t\t\thtmodelist.VHT40 = true;
\t\t\t\t\thtmodelist.VHT80 = true;
\t\t\t\t\tif (this.channels['11a'].length == 0) {
\t\t\t\t\t\t[ 36, 40, 44, 48, 149, 153, 157, 161, 165 ].forEach(L.bind(function(ch) {
\t\t\t\t\t\t\tthis.channels['11a'].push(ch, '%d (%d Mhz)'.format(ch, 5000 + ch * 5), true);
\t\t\t\t\t\t}, this));
\t\t\t\t\t}
\t\t\t\t\tif (this.channels['11a'][0] !== 'auto')
\t\t\t\t\t\tthis.channels['11a'].unshift('auto', 'auto', true);
\t\t\t\t} else {
\t\t\t\t\tif (this.channels['11g'].length == 0) {
\t\t\t\t\t\tfor (var ch = 1; ch <= 11; ch++)
\t\t\t\t\t\t\tthis.channels['11g'].push(ch, '%d (%d Mhz)'.format(ch, 2407 + ch * 5), true);
\t\t\t\t\t}
\t\t\t\t\tif (this.channels['11g'][0] !== 'auto')
\t\t\t\t\t\tthis.channels['11g'].unshift('auto', 'auto', true);
\t\t\t\t}
\t\t\t}
"""

if "uci.get('wireless', section_id, 'type') == 'rtl8192cd'" not in text:
    freq_anchor = """\t\t\tvar htmodelist = L.toArray(data[0] ? data[0].getHTModes() : null)
\t\t\t\t.reduce(function(o, v) { o[v] = true; return o }, {});
"""
    if text.count(freq_anchor) != 1:
        raise SystemExit(f"Expected single htmodelist anchor in {p}, found {text.count(freq_anchor)}")
    text = text.replace(freq_anchor, freq_anchor + freq_snippet, 1)

    modes_old = """\t\t\tvar hwmodelist = L.toArray(data[0] ? data[0].getHWModes() : null)
\t\t\t\t.reduce(function(o, v) { o[v] = true; return o }, {});

\t\t\tthis.modes = [
\t\t\t\t'', 'Legacy', true,
\t\t\t\t'n', 'N', hwmodelist.n,
\t\t\t\t'ac', 'AC', hwmodelist.ac
\t\t\t];
"""
    modes_new = """\t\t\tvar hwmodelist = L.toArray(data[0] ? data[0].getHWModes() : null)
\t\t\t\t.reduce(function(o, v) { o[v] = true; return o }, {});
\t\t\tif (uci.get('wireless', section_id, 'type') == 'rtl8192cd') {
\t\t\t\thwmodelist.n = true;
\t\t\t\tif (uci.get('wireless', section_id, 'hwmode') == '11a' ||
\t\t\t\t    +(uci.get('wireless', section_id, 'band') || 0) >= 64 ||
\t\t\t\t    uci.get('wireless', section_id, 'phy') == 'wlan0')
\t\t\t\t\thwmodelist.ac = true;
\t\t\t}

\t\t\tthis.modes = [
\t\t\t\t'', 'Legacy', true,
\t\t\t\t'n', 'N', hwmodelist.n,
\t\t\t\t'ac', 'AC', hwmodelist.ac
\t\t\t];
"""
    if text.count(modes_old) != 1:
        raise SystemExit(f"Expected single hwmodelist anchor in {p}, found {text.count(modes_old)}")
    text = text.replace(modes_old, modes_new, 1)

    write_old = """\twrite: function(section_id, value) {
\t\tuci.set('wireless', section_id, 'htmode', value[0] || null);
\t\tuci.set('wireless', section_id, 'hwmode', value[1]);
\t\tuci.set('wireless', section_id, 'channel', value[2]);
\t}"""
    write_new = """\twrite: function(section_id, value) {
\t\tif (uci.get('wireless', section_id, 'type') == 'rtl8192cd') {
\t\t\tuci.set('wireless', section_id, 'htmode', value[0] || 'NONE');
\t\t\tif (value[1])
\t\t\t\tuci.set('wireless', section_id, 'hwmode', value[1]);
\t\t\tif (value[2])
\t\t\t\tuci.set('wireless', section_id, 'channel', value[2]);
\t\t\treturn;
\t\t}
\t\tuci.set('wireless', section_id, 'htmode', value[0] || null);
\t\tuci.set('wireless', section_id, 'hwmode', value[1]);
\t\tuci.set('wireless', section_id, 'channel', value[2]);
\t}"""
    if text.count(write_old) != 1:
        raise SystemExit(f"Expected single CBIWifiFrequencyValue.write anchor in {p}, found {text.count(write_old)}")
    text = text.replace(write_old, write_new, 1)

snippet = """\t\t\t\telse if (hwtype == 'rtl8192cd') {
\t\t\t\t\tcrypto_modes.push(['psk2',      'WPA2-PSK',                    35]);
\t\t\t\t\tcrypto_modes.push(['psk-mixed', 'WPA-PSK/WPA2-PSK Mixed Mode', 22]);
\t\t\t\t\tcrypto_modes.push(['psk',       'WPA-PSK',                     21]);
\t\t\t\t}
"""
if "crypto_modes.push(['psk2',      'WPA2-PSK',                    35]);\n\t\t\t\t\tcrypto_modes.push(['psk-mixed'" not in text or "\t\t\t\telse if (hwtype == 'rtl8192cd') {\n\t\t\t\t\tcrypto_modes.push" not in text:
    anchor = """\t\t\t\telse if (hwtype == 'broadcom') {
\t\t\t\t\tcrypto_modes.push(['psk2',     'WPA2-PSK',                    33]);
\t\t\t\t\tcrypto_modes.push(['psk+psk2', 'WPA-PSK/WPA2-PSK Mixed Mode', 22]);
\t\t\t\t\tcrypto_modes.push(['psk',      'WPA-PSK',                     21]);
\t\t\t\t}
"""
    if text.count(anchor) != 1:
        raise SystemExit(f"Expected single broadcom crypto_modes anchor in {p}, found {text.count(anchor)}")
    text = text.replace(anchor, anchor + snippet, 1)

dev_snippet = """\t\t\t\telse if (hwtype == 'rtl8192cd') {
\t\t\t\t\to = ss.taboption('advanced', CBIWifiCountryValue, 'country', _('Country Code'));
\t\t\t\t\to.wifiNetwork = radioNet;

\t\t\t\t\to = ss.taboption('advanced', form.Flag, 'noscan', _('Force 40MHz mode'), _('Always use 40MHz channels even if the secondary channel overlaps.'));
\t\t\t\t\to.rmempty = true;

\t\t\t\t\to = ss.taboption('advanced', form.Value, 'beacon_int', _('Beacon Interval'));
\t\t\t\t\to.datatype = 'range(15,65535)';
\t\t\t\t\to.placeholder = 100;
\t\t\t\t\to.rmempty = true;

\t\t\t\t\to = ss.taboption('advanced', form.Value, 'dtim_period', _('DTIM Interval'), _('Delivery Traffic Indication Message Interval'));
\t\t\t\t\to.optional = true;
\t\t\t\t\to.placeholder = 1;
\t\t\t\t\to.datatype = 'range(1,255)';
\t\t\t\t}
"""
if "\t\t\t\telse if (hwtype == 'rtl8192cd') {\n\t\t\t\t\to = ss.taboption('advanced', CBIWifiCountryValue" not in text:
    dev_anchor = """\t\t\t\t\to = ss.taboption('advanced', form.Value, 'beacon_int', _('Beacon Interval'));
\t\t\t\t\to.datatype = 'range(15,65535)';
\t\t\t\t\to.placeholder = 100;
\t\t\t\t\to.rmempty = true;
\t\t\t\t}
"""
    if text.count(dev_anchor) != 1:
        raise SystemExit(f"Expected single device beacon_int anchor in {p}, found {text.count(dev_anchor)}")
    text = text.replace(dev_anchor, dev_anchor + dev_snippet, 1)

mode_old = """\t\t\t\to = ss.taboption('general', form.ListValue, 'mode', _('Mode'));
\t\t\t\to.value('ap', _('Access Point'));
\t\t\t\to.value('sta', _('Client'));
\t\t\t\to.value('adhoc', _('Ad-Hoc'));
"""
mode_new = """\t\t\t\to = ss.taboption('general', form.ListValue, 'mode', _('Mode'));
\t\t\t\to.value('ap', _('Access Point'));
\t\t\t\to.value('sta', _('Client'));
\t\t\t\tif (hwtype != 'rtl8192cd') {
\t\t\t\t\to.value('adhoc', _('Ad-Hoc'));
\t\t\t\t}
"""
if mode_new not in text:
    if text.count(mode_old) != 1:
        raise SystemExit(f"Expected single mode ListValue anchor in {p}, found {text.count(mode_old)}")
    text = text.replace(mode_old, mode_new, 1)

iface_snippet = """\t\t\t\telse if (hwtype == 'rtl8192cd') {
\t\t\t\t\tvar rtl_bssid = ss.children.filter(function(c) { return c.option == 'bssid' })[0];
\t\t\t\t\tif (rtl_bssid)
\t\t\t\t\t\trtl_bssid.depends('mode', 'sta');

\t\t\t\t\to = ss.taboption('general', form.Flag, 'hidden', _('Hide <abbr title="Extended Service Set Identifier">ESSID</abbr>'));
\t\t\t\t\to.depends('mode', 'ap');

\t\t\t\t\to = ss.taboption('advanced', form.Flag, 'isolate', _('Isolate Clients'), _('Prevents client-to-client communication'));
\t\t\t\t\to.depends('mode', 'ap');

\t\t\t\t\to = ss.taboption('advanced', form.Value, 'maxassoc', _('Max Clients'), _('Maximum number of associated clients (0 = unlimited)'));
\t\t\t\t\to.depends('mode', 'ap');
\t\t\t\t\to.optional = true;
\t\t\t\t\to.placeholder = 0;
\t\t\t\t\to.datatype = 'uinteger';

\t\t\t\t\to = ss.taboption('advanced', form.Flag, 'nat25_disable', _('Disable NAT2.5 L2 Bridge'), _('Disable driver L2 address translation on bridged client links (leave unchecked for automatic mode).'));
\t\t\t\t\to.depends('mode', 'sta');
\t\t\t\t\to.rmempty = true;
\t\t\t\t}
"""
if "\t\t\t\telse if (hwtype == 'rtl8192cd') {\n\t\t\t\t\tvar rtl_bssid =" not in text:
    iface_anchor = """\t\t\t\t\to = ss.taboption('advanced', form.Flag, 'disassoc_low_ack', _('Disassociate On Low Acknowledgement'), _('Allow AP mode to disconnect STAs based on low ACK condition'));
\t\t\t\t\to.default = o.enabled;
\t\t\t\t}
"""
    if text.count(iface_anchor) != 1:
        raise SystemExit(f"Expected single iface disassoc_low_ack anchor in {p}, found {text.count(iface_anchor)}")
    text = text.replace(iface_anchor, iface_anchor + iface_snippet, 1)

wep_old = """\t\t\t\tcrypto_modes.push(['wep-open',   _('WEP Open System'), 11]);
\t\t\t\tcrypto_modes.push(['wep-shared', _('WEP Shared Key'),  10]);
\t\t\t\tcrypto_modes.push(['none',       _('No Encryption'),   0]);
"""
wep_new = """\t\t\t\tif (hwtype != 'rtl8192cd') {
\t\t\t\t\tcrypto_modes.push(['wep-open',   _('WEP Open System'), 11]);
\t\t\t\t\tcrypto_modes.push(['wep-shared', _('WEP Shared Key'),  10]);
\t\t\t\t}
\t\t\t\tcrypto_modes.push(['none',       _('No Encryption'),   0]);
"""
if wep_new not in text:
    if text.count(wep_old) != 1:
        raise SystemExit(f"Expected single wep crypto_modes anchor in {p}, found {text.count(wep_old)}")
    text = text.replace(wep_old, wep_new, 1)

# Fix upstream LuCI 19.07 Join Network bug: Array.filter() returns truthy [] so
# is_sae was always true on WPA2-PSK networks, forcing encryption='sae'.
join_fixes = [
    (
        "is_psk = (enc && Array.isArray(enc.wpa) && L.toArray(enc.authentication).filter(function(a) { return a == 'psk' })),",
        "is_psk = (enc && Array.isArray(enc.wpa) && L.toArray(enc.authentication).filter(function(a) { return a == 'psk' }).length > 0),",
    ),
    (
        "is_sae = (enc && Array.isArray(enc.wpa) && L.toArray(enc.authentication).filter(function(a) { return a == 'sae' }));",
        "is_sae = (enc && Array.isArray(enc.wpa) && L.toArray(enc.authentication).filter(function(a) { return a == 'sae' }).length > 0);",
    ),
    (
        "is_psk = (enc && Array.isArray(enc.wpa) && L.toArray(enc.authentication).filter(function(a) { return a == 'psk' || a == 'sae' })),",
        "is_psk = (enc && Array.isArray(enc.wpa) && L.toArray(enc.authentication).filter(function(a) { return a == 'psk' || a == 'sae' }).length > 0),",
    ),
]
for old_j, new_j in join_fixes:
    if new_j not in text:
        if text.count(old_j) != 1:
            raise SystemExit(f"Expected single Join filter anchor in {p}, found {text.count(old_j)}: {old_j}")
        text = text.replace(old_j, new_j, 1)

p.write_text(text)
updated = p.read_text()
assert "hwtype == 'rtl8192cd'" in updated
assert "hwtype != 'rtl8192cd'" in updated
assert "htmodelist.VHT80 = true;" in updated
assert "uci.get('wireless', section_id, 'type') == 'rtl8192cd'" in updated
assert "'maxassoc'" in updated
assert "rtl_bssid.depends('mode', 'sta');" in updated
assert "unshift('auto', 'auto', true);" in updated
assert ".filter(function(a) { return a == 'sae' }).length > 0" in updated
print("LUCI_WIRELESS_JS_RTL8192CD: PASS")
PY
python3 - "$OPENWRT_DIR/package/network/services/dropbear/files/dropbear.init" <<'PY'
import pathlib, sys
p = pathlib.Path(sys.argv[1])
text = p.read_text()
if "\nSTART=98\n" not in text:
    if text.count("\nSTART=19\n") != 1:
        raise SystemExit(f"Expected single START=19 anchor in {p}")
    text = text.replace("\nSTART=19\n", "\nSTART=98\n", 1)
    p.write_text(text)
assert "\nSTART=98\n" in p.read_text()
print("DROPBEAR_DEFERRED_START_98: PASS")
PY
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
 echo 'COMPILE=PASS'; echo 'ARTIFACT_SCREEN=PASS'; echo 'OFFLINE_STRUCTURAL_AUDIT=PASS'; echo 'BOOT_QUALIFICATION=NOT_YET_VERIFIED'; echo 'RAM_BOOT_AUTHORIZED=NO'; echo "donor_commit=$DONOR_COMMIT"; echo "base_commit=$BASE_COMMIT"; echo "wifi_driver_commit=$WIFI_DRIVER_COMMIT"; echo "luci_commit=$LUCI_COMMIT"; echo "packages_commit=$PACKAGES_COMMIT"; echo "port_input_fingerprint=$fingerprint"; echo "project_commit=$project_commit"; echo "builder_image_id=$builder_image_id"; sha256sum "$OUT_DIR/$(basename "$IMAGE")"; stat -c 'size=%s' "$OUT_DIR/$(basename "$IMAGE")";
} > "$OUT_DIR/BUILD_RESULT.txt"
STAGE=finished_candidate_requires_review
echo 'COMPILE FINISHED. Candidate requires binary review; do not load or execute it on the router.'
