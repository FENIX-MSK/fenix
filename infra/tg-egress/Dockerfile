# Outbound tunnel to Telegram: AmneziaWG client + SOCKS5 proxy for the bot.
# The VPS cannot reach Telegram directly; only Telegram subnets go through the tunnel.

FROM alpine:3.19 AS microsocks
ARG MICROSOCKS_VERSION=1.0.5
RUN apk add --no-cache build-base \
 && wget -qO- "https://github.com/rofl0r/microsocks/archive/refs/tags/v${MICROSOCKS_VERSION}.tar.gz" | tar xz \
 && make -C "microsocks-${MICROSOCKS_VERSION}" \
 && install -m 755 "microsocks-${MICROSOCKS_VERSION}/microsocks" /usr/local/bin/microsocks

# amneziavpn/amneziawg-go:latest as of 2026-08-28 (Alpine 3.19, amneziawg-tools v3.1)
FROM amneziavpn/amneziawg-go@sha256:cbafc02b8373a83f428272db6d8001b37bc02e6211cbd8c0cb4e2e3759b12b72
COPY --from=microsocks /usr/local/bin/microsocks /usr/local/bin/microsocks
COPY entrypoint.sh /entrypoint.sh
EXPOSE 1080
HEALTHCHECK --interval=60s --timeout=20s --start-period=20s --retries=3 \
  CMD wget -q -T 15 -O /dev/null https://api.telegram.org/ || exit 1
ENTRYPOINT ["/entrypoint.sh"]
