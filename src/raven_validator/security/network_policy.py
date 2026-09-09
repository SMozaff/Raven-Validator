"""URL/network safety policy for imported public candidates."""
from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit


class UnsafeNetworkTarget(ValueError):
    pass


_BLOCKED_HOSTS = {"localhost", "localhost.localdomain", "metadata.google.internal"}


def _blocked_ip(ip: ipaddress._BaseAddress) -> bool:  # type: ignore[attr-defined]
    return any((ip.is_private, ip.is_loopback, ip.is_link_local, ip.is_reserved, ip.is_multicast, ip.is_unspecified))


@dataclass
class NetworkPolicy:
    allow_private: bool = False
    resolve_dns: bool = True

    def validate_url(self, url: str) -> str:
        p = urlsplit(url.strip())
        if p.scheme not in {"http", "https"} or not p.hostname:
            raise UnsafeNetworkTarget("Only absolute http(s) URLs are allowed")
        host = p.hostname.lower().strip(".")
        if not self.allow_private:
            if host in _BLOCKED_HOSTS or host.endswith(".localhost"):
                raise UnsafeNetworkTarget(f"Local/private hostname blocked: {host}")
            try:
                ip = ipaddress.ip_address(host)
            except ValueError:
                ip = None
            if ip is not None and _blocked_ip(ip):
                raise UnsafeNetworkTarget(f"Private/local address blocked: {ip}")
            if self.resolve_dns:
                try:
                    infos = socket.getaddrinfo(host, p.port or (443 if p.scheme == "https" else 80), type=socket.SOCK_STREAM)
                except socket.gaierror as exc:
                    raise UnsafeNetworkTarget(f"DNS resolution failed for {host}: {exc}") from exc
                for info in infos:
                    try:
                        resolved = ipaddress.ip_address(info[4][0])
                    except ValueError:
                        continue
                    if _blocked_ip(resolved):
                        raise UnsafeNetworkTarget(f"Hostname resolves to private/local address: {resolved}")
        return url

    def redirected_url(self, current: str, location: str) -> str:
        target = urljoin(current, location)
        return self.validate_url(target)
