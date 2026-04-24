from __future__ import annotations

import concurrent.futures
import datetime
import socket
import ssl
import subprocess
import sys
import uuid
from typing import Any

import httpx

from oclaw.runtime.tools.base import ToolSpec


def dns_lookup_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        domain = args.get("domain")
        if not domain:
            return {"ok": False, "error": "domain is required"}
        try:
            ips = socket.gethostbyname_ex(domain)[2]
            return {"ok": True, "domain": domain, "ips": ips, "count": len(ips)}
        except Exception as e:
            return {"ok": False, "error": f"DNS resolution failed: {e}"}

    return ToolSpec(
        name="dns_lookup",
        description="Resolve a domain name to IPv4 addresses (A records via system resolver).",
        parameters={
            "type": "object",
            "properties": {
                "domain": {"type": "string", "description": "Domain name (e.g. example.com)."},
            },
            "required": ["domain"],
            "additionalProperties": False,
        },
        handler=handler,
    )


def ssl_check_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        domain = args.get("domain")
        port = int(args.get("port") or 443)
        if not domain:
            return {"ok": False, "error": "domain is required"}
        try:
            context = ssl.create_default_context()
            with socket.create_connection((domain, port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=domain) as ssock:
                    cert = ssock.getpeercert()
                    not_before = datetime.datetime.strptime(cert["notBefore"], "%b %d %H:%M:%S %Y %Z")
                    not_after = datetime.datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")
                    remaining_days = (not_after - datetime.datetime.utcnow()).days
                    subject = dict(x[0] for x in cert["subject"])
                    issuer = dict(x[0] for x in cert["issuer"])
                    return {
                        "ok": True,
                        "domain": domain,
                        "issuer": issuer.get("commonName"),
                        "issued_to": subject.get("commonName"),
                        "valid_from": not_before.strftime("%Y-%m-%d"),
                        "valid_until": not_after.strftime("%Y-%m-%d"),
                        "remaining_days": remaining_days,
                        "is_expired": remaining_days < 0,
                    }
        except Exception as e:
            return {"ok": False, "error": f"SSL check failed: {e}"}

    return ToolSpec(
        name="ssl_cert_check",
        description="Inspect the TLS certificate presented by host:port (default 443).",
        parameters={
            "type": "object",
            "properties": {
                "domain": {"type": "string", "description": "Server hostname."},
                "port": {"type": "integer", "description": "TCP port. Default 443."},
            },
            "required": ["domain"],
            "additionalProperties": False,
        },
        handler=handler,
    )


def port_check_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        host = args.get("host")
        port = int(args.get("port"))
        protocol = str(args.get("protocol") or "tcp").lower()
        timeout = float(args.get("timeout") or 2.0)
        if not host or not port:
            return {"ok": False, "error": "host and port are required"}
        if protocol == "tcp":
            try:
                with socket.create_connection((host, port), timeout=timeout):
                    return {"ok": True, "host": host, "port": port, "protocol": "TCP", "status": "open"}
            except socket.timeout:
                return {"ok": True, "host": host, "port": port, "protocol": "TCP", "status": "timeout"}
            except Exception as e:
                return {"ok": True, "host": host, "port": port, "protocol": "TCP", "status": "closed", "error": str(e)}
        if protocol == "udp":
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(timeout)
                sock.sendto(b"", (host, port))
                try:
                    sock.recvfrom(1024)
                    return {"ok": True, "host": host, "port": port, "protocol": "UDP", "status": "open", "received": True}
                except socket.timeout:
                    return {"ok": True, "host": host, "port": port, "protocol": "UDP", "status": "open|filtered"}
                except Exception as e:
                    return {"ok": True, "host": host, "port": port, "protocol": "UDP", "status": "closed", "error": str(e)}
                finally:
                    sock.close()
            except Exception as e:
                return {"ok": False, "error": f"UDP check failed: {e}"}
        return {"ok": False, "error": f"Unsupported protocol: {protocol}"}

    return ToolSpec(
        name="port_check",
        description="Test whether a TCP or UDP port appears open on a host.",
        parameters={
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "Hostname or IP address."},
                "port": {"type": "integer", "description": "Port number."},
                "protocol": {"type": "string", "enum": ["tcp", "udp"], "description": "tcp or udp. Default tcp."},
                "timeout": {"type": "number", "description": "Timeout in seconds. Default 2.0."},
            },
            "required": ["host", "port"],
            "additionalProperties": False,
        },
        handler=handler,
    )


def port_scan_tool() -> ToolSpec:
    COMMON_PORTS = [21, 22, 23, 25, 53, 80, 110, 143, 443, 445, 1433, 1521, 3306, 3389, 5432, 6379, 8080, 27017]

    def scan_port(host: str, port: int, timeout: float) -> int | None:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return port
        except Exception:
            return None

    def handler(args: dict[str, Any]) -> dict[str, Any]:
        host = args.get("host")
        start_port = args.get("start_port")
        end_port = args.get("end_port")
        ports_to_scan = args.get("ports")
        timeout = float(args.get("timeout") or 0.5)
        max_threads = int(args.get("max_threads") or 20)
        if not host:
            return {"ok": False, "error": "host is required"}
        if ports_to_scan:
            ports = [int(p) for p in ports_to_scan]
        elif start_port is not None and end_port is not None:
            s, e = int(start_port), int(end_port)
            if e - s > 1000:
                return {"ok": False, "error": "Cannot scan more than 1000 ports in one call"}
            ports = list(range(s, e + 1))
        else:
            ports = COMMON_PORTS
        open_ports: list[int] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_threads) as executor:
            future_to_port = {executor.submit(scan_port, host, port, timeout): port for port in ports}
            for future in concurrent.futures.as_completed(future_to_port):
                result = future.result()
                if result is not None:
                    open_ports.append(result)
        open_ports.sort()
        return {
            "ok": True,
            "host": host,
            "open_ports": open_ports,
            "scanned_count": len(ports),
            "open_count": len(open_ports),
            "status": "completed",
        }

    return ToolSpec(
        name="port_scan",
        description="Scan TCP ports on a host (common ports, a numeric range, or an explicit list).",
        parameters={
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "Hostname or IP address."},
                "start_port": {"type": "integer", "description": "Start of port range (inclusive)."},
                "end_port": {"type": "integer", "description": "End of port range (inclusive)."},
                "ports": {"type": "array", "items": {"type": "integer"}, "description": "Explicit list of ports to scan."},
                "timeout": {"type": "number", "description": "Per-port timeout in seconds. Default 0.5."},
                "max_threads": {"type": "integer", "description": "Maximum concurrent probes. Default 20."},
            },
            "required": ["host"],
            "additionalProperties": False,
        },
        handler=handler,
    )


def local_net_info_tool() -> ToolSpec:
    def get_mac_address() -> str:
        return ":".join(["{:02x}".format((uuid.getnode() >> i) & 0xFF) for i in range(0, 8 * 6, 8)][::-1])

    def get_public_ip() -> str:
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get("https://api64.ipify.org?format=json")
                return str(resp.json().get("ip") or "Unknown")
        except Exception:
            return "Unknown"

    def get_gateway() -> str:
        try:
            if sys.platform == "win32":
                output = subprocess.check_output("route print 0.0.0.0", shell=True).decode("gbk", errors="replace")
                for line in output.splitlines():
                    if "0.0.0.0" in line and "On-link" not in line:
                        parts = line.split()
                        if len(parts) >= 3:
                            return parts[2]
            else:
                output = subprocess.check_output("ip route show default", shell=True).decode(errors="replace")
                return output.split()[2]
        except Exception:
            return "Unknown"

    def handler(args: dict[str, Any]) -> dict[str, Any]:
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            mac = get_mac_address()
            gateway = get_gateway()
            public_ip = get_public_ip()
            return {
                "ok": True,
                "hostname": hostname,
                "local_ip": local_ip,
                "public_ip": public_ip,
                "mac_address": mac,
                "gateway": gateway,
                "platform": sys.platform,
            }
        except Exception as e:
            return {"ok": False, "error": f"Failed to read local network info: {e}"}

    return ToolSpec(
        name="get_local_net_info",
        description="Summarize local hostname, IPs, MAC, default gateway, and OS platform (best-effort).",
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
        handler=handler,
    )


__all__ = ["dns_lookup_tool", "ssl_check_tool", "port_check_tool", "port_scan_tool", "local_net_info_tool"]
