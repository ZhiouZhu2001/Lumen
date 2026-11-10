"""Build and check an owned disposable Compose stack without live API keys.

Run from any directory with Python 3.12 and Docker Compose. Only the standard
library is required on the host. Diagnostic routes are mounted into a temporary
replacement backend, never added to the production application or image.
"""

import argparse
import hashlib
import http.client
import ipaddress
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from time import perf_counter
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
SERVICES = {"postgres", "redis", "backend", "frontend", "caddy"}
OWNER = "com.docker.compose.project"


class CheckFailed(Exception):
    """A configuration, protocol or resource-ownership check failed."""


def require(condition, message):
    if not condition:
        raise CheckFailed(message)


def require_owner(labels, project):
    require(
        re.fullmatch(r"lumen-container-check-[0-9a-f]{12}", project)
        and labels.get(OWNER) == project,
        "Refusing to remove a resource outside the owned disposable project",
    )


def validate_config(config, proxy_ip):
    services = config["services"]
    require(set(services) == SERVICES, "Expected exactly five services")
    for name in SERVICES - {"caddy"}:
        require(not services[name].get("ports"), "Only Caddy may publish base ports")
    ports = services["caddy"].get("ports", [])
    require(
        ports and all(p.get("host_ip") == "127.0.0.1" for p in ports),
        "Check ports must remain on loopback",
    )
    environment = services["backend"]["environment"]
    require(
        not environment.get("OPENAI_API_KEY")
        and not environment.get("GOOGLE_BOOKS_API_KEY"),
        "Live API keys are forbidden in the check",
    )
    require(
        int(environment["DAILY_AI_CALL_CAP"]) == 100, "The daily cap must remain 100"
    )
    require(
        json.loads(environment["TRUSTED_PROXY_IPS"]) == [proxy_ip],
        "Trust only the controlled Caddy address",
    )
    require(
        set(services["frontend"].get("environment", {})) == {"BACKEND_URL"},
        "The frontend must receive only its internal backend origin",
    )


class StackCheck:
    def __init__(self, directory):
        self.project = "lumen-container-check-" + uuid4().hex[:12]
        self.directory = Path(directory)
        self.report = {
            "target": "isolated_container_ci",
            "project": self.project,
            "model_requests": 0,
            "catalog_requests": 0,
            "full_live_recommendation_gate": False,
            "checks": {},
        }
        self.environment = os.environ.copy()
        network = self.free_subnet()
        self.proxy_ip = str(network.network_address + 2)
        values = {
            "POSTGRES_USER": "lumen_check",
            "POSTGRES_PASSWORD": "check_only",
            "POSTGRES_DB": "lumen_check",
            "OPENAI_API_KEY": "",
            "GOOGLE_BOOKS_API_KEY": "",
            "LLM_MODEL": "openai:gpt-5.4-mini",
            "DAILY_AI_CALL_CAP": "100",
            "LUMEN_BIND_ADDRESS": "127.0.0.1",
            "LUMEN_HTTP_PORT": "0",
            "LUMEN_HTTPS_PORT": "0",
            "LUMEN_SITE_ADDRESS": ":80",
            "LUMEN_PROXY_SUBNET": str(network),
            "LUMEN_PROXY_DYNAMIC_RANGE": str(list(network.subnets(new_prefix=29))[1]),
            "LUMEN_PROXY_IP": self.proxy_ip,
        }
        self.environment.update(values)
        env_file = self.directory / "check.env"
        env_file.write_text(
            "".join(f"{k}={v}\n" for k, v in values.items()), encoding="utf-8"
        )
        env_file.chmod(0o600)
        self.base = [
            "compose",
            "--project-directory",
            str(ROOT),
            "--env-file",
            str(env_file),
            "-p",
            self.project,
            "-f",
            str(ROOT / "docker-compose.yml"),
        ]

    def docker(self, *args, timeout=180):
        result = subprocess.run(
            ["docker", *args],
            cwd=ROOT,
            env=self.environment,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        require(
            result.returncode == 0,
            f"Docker command failed: {args[0]}\n{result.stdout[-6000:]}\n{result.stderr[-6000:]}",
        )
        return result.stdout.strip()

    def compose(self, *args, timeout=180):
        return self.docker(*self.base, *args, timeout=timeout)

    def free_subnet(self):
        networks = []
        for identifier in self.docker("network", "ls", "-q").split():
            info = json.loads(self.docker("network", "inspect", identifier))[0]
            networks.extend(
                ipaddress.ip_network(c["Subnet"])
                for c in ((info.get("IPAM") or {}).get("Config") or [])
                if c.get("Subnet")
            )
        for index in range(20, 250):
            candidate = ipaddress.ip_network(f"172.30.{index}.0/28")
            if not any(
                candidate.overlaps(other) for other in networks if other.version == 4
            ):
                return candidate
        raise CheckFailed("No unused diagnostic subnet available")

    def passed(self, name, details=True):
        self.report["checks"][name] = details
        print(f"PASS {name}", flush=True)

    def request(self, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=15)
        try:
            payload = json.dumps(body).encode() if body is not None else None
            outgoing = dict(headers or {})
            if payload is not None:
                outgoing["Content-Type"] = "application/json"
            connection.request(
                "POST" if body is not None else "GET", path, payload, outgoing
            )
            response = connection.getresponse()
            return (
                response.status,
                {k.lower(): v for k, v in response.getheaders()},
                response.read().decode(),
            )
        finally:
            connection.close()

    def resource(self, service):
        identifier = self.compose("ps", "-a", "-q", service)
        require(bool(identifier), f"Missing {service} container")
        info = json.loads(self.docker("inspect", identifier))[0]
        require_owner(info["Config"]["Labels"], self.project)
        return info

    def refresh_port(self):
        # Docker may allocate a different ephemeral host port after a restart.
        address = self.compose("port", "caddy", "80")
        require(address.startswith("127.0.0.1:"), "Unexpected published address")
        self.port = int(address.rsplit(":", 1)[1])

    def run(self):
        config = json.loads(self.compose("config", "--format", "json"))
        validate_config(config, self.proxy_ip)
        self.passed("isolated_config_and_credentials")
        self.compose("build", "backend", "frontend", timeout=600)
        self.passed("production_images_built")
        self.compose("up", "-d", "--wait", "--wait-timeout", "150", timeout=180)
        images = {}
        for service in sorted(SERVICES):
            info = self.resource(service)
            require(
                info["State"]["Health"]["Status"] == "healthy", f"Unhealthy {service}"
            )
            images[service] = info["Image"]
        self.report["image_ids"] = images
        self.passed("five_services_healthy")
        self.refresh_port()
        self.compose(
            "exec",
            "-T",
            "caddy",
            "caddy",
            "validate",
            "--config",
            "/etc/caddy/Caddyfile",
        )
        require(
            self.compose("exec", "-T", "backend", "id", "-u") == "10001",
            "Backend must be non-root",
        )
        require(
            self.compose("exec", "-T", "frontend", "id", "-u") == "1000",
            "Frontend must be non-root",
        )
        self.compose(
            "exec",
            "-T",
            "backend",
            "python",
            "-c",
            "from pathlib import Path; assert not list(Path('/app').rglob('.env*')); "
            "assert not Path('/app/tests').exists(); "
            "assert not Path('/app/scripts/container_probe.py').exists()",
        )
        self.passed("caddy_validation_nonroot_and_runtime_exclusions")
        require(self.request("/api/health")[0] == 200, "API health failed")
        for locale in ["en", "es"]:
            status, _, html = self.request("/" + locale)
            require(
                status == 200 and f'lang="{locale}"' in html, "Localized page failed"
            )
            assets = re.findall(
                r'(?:src|href)="([^"\s]+\.(?:js|css)(?:\?[^"\s]*)?)"', html
            )
            require(bool(assets), "No static assets found")
            for asset in assets[:3]:
                require(
                    asset.startswith("/")
                    and self.request(asset.replace("&amp;", "&"))[0] == 200,
                    "Static asset failed",
                )
        require(
            self.request("/api/books/9780307474728")[0] == 404,
            "Missing book must return 404",
        )
        require(
            self.request("/api/books/9780307474729")[0] == 422,
            "Invalid ISBN must return 422",
        )
        self.passed("localized_pages_assets_and_api_routing")
        body = {"query": "container check request", "language": "en"}
        for index in range(21):
            status, headers, payload = self.request(
                "/api/search",
                body,
                {
                    "Accept": "text/event-stream",
                    "X-Forwarded-For": f"198.51.100.{index + 1}",
                    "Forwarded": "for=203.0.113.7",
                    "X-Real-IP": "192.0.2.8",
                },
            )
            require(
                status == (503 if index < 20 else 429),
                "Budget/admission boundary changed",
            )
            if index < 20:
                require(
                    json.loads(payload)["detail"]["code"] == "upstream_unavailable",
                    "Missing budget must fail closed",
                )
            else:
                require(int(headers["retry-after"]) > 0, "Missing Retry-After")
        require(
            self.compose(
                "exec",
                "-T",
                "postgres",
                "psql",
                "-U",
                "lumen_check",
                "-d",
                "lumen_check",
                "-Atc",
                "SELECT count(*) FROM ai_daily_usage",
            )
            == "0",
            "The missing ledger must not be automatically initialized",
        )
        self.passed("missing_budget_and_forged_headers_cannot_bypass_hourly_limit")
        receipt = json.loads(
            self.compose(
                "run",
                "--rm",
                "--no-deps",
                "backend",
                "python",
                "-m",
                "scripts.budget_admin",
                "block-today",
                "--confirm-ai-workers-stopped",
                "--output",
                "/tmp/container-check-budget.json",
            )
        )
        require(
            receipt["stored_used"] == receipt["daily_cap"] == 100,
            "Unexpected test floor",
        )
        self.resource("redis")
        self.compose("rm", "--stop", "--force", "--volumes", "redis")
        self.compose("up", "-d", "--wait", "redis")
        self.compose("restart", "backend", "frontend", "caddy")
        self.compose("up", "-d", "--wait", "--wait-timeout", "150")
        self.refresh_port()
        status, _, payload = self.request(
            "/api/search", body, {"Accept": "text/event-stream"}
        )
        require(
            status == 503 and "daily AI limit" in payload,
            "Redis loss reset the AI guard",
        )
        self.passed(
            "redis_loss_and_restarts_preserve_durable_budget",
            {"synthetic_floor": 100, "actual_model_attempts": 0},
        )
        self.probe()

    def probe(self):
        override = self.directory / "probe.json"
        override.write_text(
            json.dumps(
                {
                    "services": {
                        "backend": {
                            "command": [
                                "uvicorn",
                                "container_probe:app",
                                "--app-dir",
                                "/probe",
                                "--host",
                                "0.0.0.0",
                                "--port",
                                "8000",
                                "--no-proxy-headers",
                                "--no-access-log",
                            ],
                            "environment": {"PYTHONPATH": "/app"},
                            "restart": "no",
                            "volumes": [
                                {
                                    "type": "bind",
                                    "source": str(
                                        Path(__file__).with_name("container_probe.py")
                                    ),
                                    "target": "/probe/container_probe.py",
                                    "read_only": True,
                                }
                            ],
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        self.compose("-f", str(override), "up", "-d", "--wait", "--wait-timeout", "150")
        self.refresh_port()
        values = []
        for forged in ["198.51.100.8", "invalid", "203.0.113.9, 192.0.2.1"]:
            status, _, payload = self.request(
                "/api/__container_identity",
                headers={
                    "X-Forwarded-For": forged,
                    "Forwarded": "for=198.51.100.9",
                    "X-Real-IP": "192.0.2.7",
                },
            )
            require(status == 200, "Identity probe failed")
            result = json.loads(payload)
            require(
                result["peer"] == self.proxy_ip
                and result["other_hints_absent"]
                and result["effective"] == result["forwarded"]
                and result["effective"] not in forged,
                "Untrusted identity hint survived",
            )
            values.append(result["effective"])
        require(len(set(values)) == 1, "Forged hints changed the effective identity")
        self.passed("synthetic_forwarding_identity")
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=80)
        events, times = [], []
        started = perf_counter()
        try:
            connection.request(
                "GET",
                "/api/__container_stream",
                headers={"Accept-Encoding": "gzip, br"},
            )
            response = connection.getresponse()
            require(
                response.status == 200
                and response.getheader("Content-Encoding") is None
                and response.getheader("Content-Type", "").startswith(
                    "text/event-stream"
                )
                and "no-transform" in response.getheader("Cache-Control", "")
                and response.getheader("X-Accel-Buffering") == "no",
                "Streaming headers changed",
            )
            while line := response.readline():
                if line.startswith(b"event:"):
                    events.append(line[6:].decode().strip())
                    times.append(round((perf_counter() - started) * 1000, 2))
        finally:
            connection.close()
        require(
            events == ["status", "done"] and times[0] < 2000 and times[1] >= 65000,
            "Delayed SSE was buffered, interrupted or incomplete",
        )
        self.passed(
            "synthetic_65_second_sse",
            {"events": events, "frame_ms": times, "real_first_book_measurement": False},
        )

    def cleanup(self):
        for kind in ["container", "network", "volume"]:
            listing = [kind, "ls", "-q"] + (["-a"] if kind == "container" else [])
            for identifier in self.docker(
                *listing, "--filter", f"label={OWNER}={self.project}"
            ).split():
                info = json.loads(self.docker(kind, "inspect", identifier))[0]
                labels = (
                    info["Config"]["Labels"] if kind == "container" else info["Labels"]
                )
                require_owner(labels, self.project)
                if kind == "network":
                    for endpoint in info.get("Containers", {}):
                        attached = json.loads(self.docker("inspect", endpoint))[0]
                        require_owner(attached["Config"]["Labels"], self.project)
        self.compose("down", "--volumes", "--remove-orphans")
        for kind in ["container", "network", "volume"]:
            listing = [kind, "ls", "-q"] + (["-a"] if kind == "container" else [])
            require(
                not self.docker(*listing, "--filter", f"label={OWNER}={self.project}"),
                "Owned disposable resources remain",
            )
        self.passed("owned_resources_removed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with (
        args.output.open("x", encoding="utf-8") as output,
        tempfile.TemporaryDirectory(prefix="lumen-container-check-") as directory,
    ):
        check = None
        report = {
            "target": "isolated_container_ci",
            "passed": False,
            "model_requests": 0,
            "catalog_requests": 0,
            "full_live_recommendation_gate": False,
            "checks": {},
        }
        try:
            check = StackCheck(directory)
            report = check.report
            check.run()
            report["passed"] = True
        except (
            CheckFailed,
            OSError,
            ValueError,
            TypeError,
            KeyError,
            subprocess.TimeoutExpired,
        ) as error:
            report.update(
                passed=False, error_kind=type(error).__name__, error=str(error)
            )
            if check is not None:
                try:
                    report["diagnostic_tail"] = check.compose(
                        "logs", "--no-color", "--tail", "30"
                    )[-12000:]
                except (CheckFailed, OSError, subprocess.TimeoutExpired):
                    report["diagnostic_tail"] = "Container logs unavailable"
        finally:
            if check is not None:
                try:
                    check.cleanup()
                except (CheckFailed, OSError, subprocess.TimeoutExpired) as error:
                    report.update(passed=False, cleanup_error=str(error))
        report["limitations"] = [
            "Synthetic transport only; not the live recommendation gate.",
            "Local HTTP checks do not establish production DNS/TLS or capacity.",
        ]
        report["source_sha256_lf"] = {
            p.relative_to(ROOT).as_posix(): hashlib.sha256(
                p.read_text("utf-8").replace("\r\n", "\n").encode()
            ).hexdigest()
            for p in [
                Path(__file__),
                Path(__file__).with_name("container_probe.py"),
                ROOT / "docker-compose.yml",
                ROOT / "Caddyfile",
            ]
        }
        json.dump(report, output, indent=2)
        output.write("\n")
        print(json.dumps(report, indent=2), flush=True)
        return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
