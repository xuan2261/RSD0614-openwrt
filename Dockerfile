FROM debian:bullseye
ARG DEBIAN_SNAPSHOT=20260901T000000Z
COPY apt-bootstrap.sh /usr/local/sbin/rsd0614-apt-bootstrap
RUN sh /usr/local/sbin/rsd0614-apt-bootstrap "$DEBIAN_SNAPSHOT" \
    && groupadd --gid 1000 builder \
    && useradd --uid 1000 --gid 1000 --create-home --shell /bin/bash builder
USER builder
ENV HOME=/home/builder LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONDONTWRITEBYTECODE=1
WORKDIR /work
