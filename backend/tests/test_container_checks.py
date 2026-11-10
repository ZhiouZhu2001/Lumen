"""Failure-boundary checks for the disposable Docker diagnostic."""

import json
from copy import deepcopy

import pytest

from scripts.check_container_stack import (
    OWNER,
    CheckFailed,
    StackCheck,
    require_owner,
    validate_config,
)

PROJECT = "lumen-container-check-0123456789ab"


def test_network_inventory_accepts_host_networks_without_ipam_config():
    check = StackCheck.__new__(StackCheck)

    def docker(*args):
        if args[:3] == ("network", "ls", "-q"):
            return "host bridge"
        return json.dumps(
            [{"IPAM": {"Config": None}}]
            if args[-1] == "host"
            else [{"IPAM": {"Config": [{"Subnet": "172.30.20.0/28"}]}}]
        )

    check.docker = docker
    assert str(check.free_subnet()) == "172.30.21.0/28"


@pytest.mark.parametrize(
    "labels,project",
    [
        ({}, PROJECT),
        ({OWNER: "lumen"}, PROJECT),
        ({OWNER: "lumen"}, "lumen"),
    ],
)
def test_cleanup_never_accepts_normal_or_unowned_resources(labels, project):
    with pytest.raises(CheckFailed, match="Refusing to remove"):
        require_owner(labels, project)


def config():
    return {
        "services": {
            "postgres": {},
            "redis": {},
            "frontend": {"environment": {"BACKEND_URL": "http://backend:8000"}},
            "backend": {
                "environment": {
                    "DAILY_AI_CALL_CAP": "100",
                    "TRUSTED_PROXY_IPS": '["172.30.20.2"]',
                }
            },
            "caddy": {"ports": [{"host_ip": "127.0.0.1"}]},
        }
    }


@pytest.mark.parametrize(
    "change",
    ["public_port", "model_key", "catalog_key", "frontend_secret", "proxy_range"],
)
def test_bad_check_configuration_fails_before_building_or_starting(change):
    value = deepcopy(config())
    if change == "public_port":
        value["services"]["backend"]["ports"] = [{"host_ip": "0.0.0.0"}]
    elif change in {"model_key", "catalog_key"}:
        name = "OPENAI_API_KEY" if change == "model_key" else "GOOGLE_BOOKS_API_KEY"
        value["services"]["backend"]["environment"][name] = "forbidden-test-value"
    elif change == "frontend_secret":
        value["services"]["frontend"]["environment"]["DATABASE_URL"] = (
            "forbidden-test-value"
        )
    else:
        value["services"]["backend"]["environment"]["TRUSTED_PROXY_IPS"] = (
            '["172.30.20.0/28"]'
        )
    with pytest.raises(CheckFailed):
        validate_config(value, "172.30.20.2")


def test_foreign_network_attachment_prevents_any_cleanup_command():
    check = StackCheck.__new__(StackCheck)
    check.project = PROJECT
    calls = []

    def docker(*args):
        calls.append(args)
        if args[:3] == ("network", "ls", "-q"):
            return "owned-network"
        if args[:2] == ("network", "inspect"):
            return json.dumps(
                [{"Labels": {OWNER: PROJECT}, "Containers": {"foreign": {}}}]
            )
        if args[0] == "inspect":
            return json.dumps([{"Config": {"Labels": {OWNER: "another-project"}}}])
        return ""

    check.docker = docker
    check.compose = lambda *args: pytest.fail("Unsafe cleanup was invoked")
    with pytest.raises(CheckFailed, match="Refusing to remove"):
        check.cleanup()
    assert not any(args[0] in {"rm", "down"} for args in calls)
