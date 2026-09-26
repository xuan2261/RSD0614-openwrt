#!/bin/sh
# Legacy builder only. Repository signatures and package hashes remain mandatory.
set -eu

validate_timestamp() {
    printf '%s\n' "$1" | grep -Eq '^[0-9]{8}T[0-9]{6}Z$' || {
        echo 'ERROR: snapshot must have YYYYMMDDHHMMSSZ format' >&2
        return 2
    }
}

print_sources() {
    ts=$1
    transport=$2
    validate_timestamp "$ts"
    case "$transport" in http|https) ;; *) return 2 ;; esac
    opt='check-valid-until=no signed-by=/usr/share/keyrings/debian-archive-keyring.gpg'
    printf 'deb [%s] %s://snapshot.debian.org/archive/debian/%s/ bullseye main\n' "$opt" "$transport" "$ts"
    printf 'deb [%s] %s://snapshot.debian.org/archive/debian/%s/ bullseye-updates main\n' "$opt" "$transport" "$ts"
    printf 'deb [%s] %s://snapshot.debian.org/archive/debian-security/%s/ bullseye-security main\n' "$opt" "$transport" "$ts"
}

if [ "${1:-}" = '--print-sources' ]; then
    [ "$#" = 3 ] || exit 2
    print_sources "$2" "$3"
    exit 0
fi

[ "$#" = 1 ] || { echo 'Usage: apt-bootstrap.sh YYYYMMDDTHHMMSSZ' >&2; exit 2; }
SNAPSHOT=$1
validate_timestamp "$SNAPSHOT"
[ "$(id -u)" = 0 ] || { echo 'Run inside the builder image as root.' >&2; exit 2; }
[ "$(dpkg --print-architecture)" = amd64 ] || { echo 'Builder requires linux/amd64.' >&2; exit 2; }
[ -r /usr/share/keyrings/debian-archive-keyring.gpg ] || exit 2

rm -f /etc/apt/sources.list.d/*.list /etc/apt/sources.list.d/*.sources
mkdir -p /etc/apt/apt.conf.d
cat > /etc/apt/apt.conf.d/80-rsd0614-retry <<'EOF'
Acquire::Retries "3";
Acquire::http::Timeout "45";
Acquire::https::Timeout "45";
Acquire::http::No-Cache "true";
Acquire::https::No-Cache "true";
Acquire::AllowInsecureRepositories "false";
APT::Get::AllowUnauthenticated "false";
EOF

install_phase() {
    attempt=1
    while [ "$attempt" -le 3 ]; do
        echo "=== APT snapshot $SNAPSHOT attempt $attempt/3 ==="
        rm -rf /var/lib/apt/lists/*
        if apt-get --error-on=any update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "$@"; then
            return 0
        fi
        [ "$attempt" -lt 3 ] || break
        sleep 5
        attempt=$((attempt + 1))
    done
    echo 'ERROR: signed snapshot installation failed; no insecure fallback was used.' >&2
    return 100
}

print_sources "$SNAPSHOT" http > /etc/apt/sources.list
install_phase ca-certificates
print_sources "$SNAPSHOT" https > /etc/apt/sources.list
install_phase build-essential clang flex bison g++ gawk gcc-multilib g++-multilib gettext git libncurses5-dev libssl-dev rsync unzip zlib1g-dev file wget curl subversion swig time xsltproc libelf-dev bc python3 python2 python-is-python2 ca-certificates ccache quilt device-tree-compiler xz-utils bzip2 gzip tar patch perl make diffutils zip util-linux
mkdir -p /opt/rsd0614
printf '%s\n' "$SNAPSHOT" > /opt/rsd0614/debian-snapshot.txt
dpkg-query -W -f='${binary:Package}\t${Version}\n' > /opt/rsd0614/builder-packages.tsv
cp /etc/apt/sources.list /opt/rsd0614/sources.list
rm -rf /var/lib/apt/lists/*
