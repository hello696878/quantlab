"""Pure policy mutations; real Compose compilation is a separate retained check."""
from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.db_free
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("demo_compose_policy", ROOT / "scripts/validate_demo_compose.py")
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


def effective():
    services = {}
    for name, folder, memory, pids, tool, url, command in (
        ("demo-backend", "backend", 512, 96, "python", "http://127.0.0.1:8000/ready", policy.COMMAND),
        ("demo-frontend", "frontend", 768, 128, "node", "http://127.0.0.1:3000/api/ready", policy.FRONT_COMMAND),
    ):
        services[name] = {"build": {"context": str(ROOT / folder), "dockerfile": "Dockerfile.read-only-demo"},
            "image": f"quantlab-{name}:p70-unit", "command": command[:], "user": "10001:10001", "read_only": True,
            "init": True, "cap_drop": ["ALL"], "security_opt": ["no-new-privileges:true"], "tmpfs": policy.TMPFS[:],
            "cpus": 1.0, "mem_limit": str(memory * 1024**2), "pids_limit": pids, "entrypoint": None,
            "ulimits": {"nofile": {"soft": 1024, "hard": 1024}}, "restart": "no",
            "logging": {"driver": "local", "options": {"max-size": "5m", "max-file": "2"}},
            "healthcheck": {"test": ["CMD", tool, "-c" if tool == "python" else "-e", policy.HEALTH_BACKEND if folder == "backend" else policy.HEALTH_FRONTEND],
                            "interval": "30s", "timeout": "3s", "retries": 3, "start_period": "30s"}}
    back, front = services["demo-backend"], services["demo-frontend"]
    back.update(environment={"QUANTLAB_SERVING_MODE": "read_only_demo", "QUANTLAB_DEMO_CORPUS": "/corpus/v1",
        "QUANTLAB_DEMO_CORPUS_ID": "a" * 64, "QUANTLAB_DEMO_HOSTS": "demo-backend,127.0.0.1,localhost",
        "QUANTLAB_DEMO_ORIGINS": "http://127.0.0.1:3180"}, networks={"demo_private": None},
        volumes=[{"type": "volume", "source": "demo_corpus", "target": "/corpus", "read_only": True, "volume": {"nocopy": True}}])
    front.update(environment={"BACKEND_URL": policy.BACKEND, "NEXT_PUBLIC_QUANTLAB_EXPECTED_MODE": "read_only_demo",
        "QUANTLAB_EXPECTED_CORPUS_ID": "a" * 64}, networks={"demo_private": None, "demo_edge": None},
        ports=[{"host_ip": "127.0.0.1", "target": 3000, "published": "3180", "protocol": "tcp"}],
        depends_on={"demo-backend": {"condition": "service_healthy"}})
    front["build"]["args"] = {"BACKEND_URL": policy.BACKEND, "NEXT_PUBLIC_QUANTLAB_EXPECTED_MODE": "read_only_demo"}
    return {"services": services, "networks": {"demo_private": {"internal": True, "ipam": {}}, "demo_edge": {"ipam": {}}},
            "volumes": {"demo_corpus": {"external": True, "name": "quantlab-p70-unit-evidence"}}}


def test_static_policy_accepts_only_bounded_non_runtime_claims():
    result = policy.validate(effective(), ROOT)
    assert result["runtime_verified"] is False and result["frontend_egress_blocked"] is False
    policy.validate_sources(ROOT)


@pytest.mark.parametrize("target,key,value", [
    ("demo-backend", "ports", [{"target": 8000, "published": "8000"}]),
    ("demo-backend", "user", "0:0"), ("demo-frontend", "user", "root"),
    ("demo-backend", "read_only", False), ("demo-frontend", "cap_drop", []),
    ("demo-backend", "security_opt", []), ("demo-backend", "privileged", True),
    ("demo-frontend", "tmpfs", ["/app:rw"]), ("demo-backend", "mem_limit", 0),
    ("demo-frontend", "pids_limit", 0), ("demo-backend", "cpus", 0),
    ("demo-backend", "command", ["uvicorn", "app.main:app"]),
    ("demo-backend", "healthcheck", {"test": ["CMD", "curl", "localhost"]}),
    ("demo-frontend", "volumes", [{"type": "bind", "source": "C:/quantlab", "target": "/app"}]),
    ("demo-backend", "network_mode", "host"),
    ("demo-backend", "entrypoint", ["sh"]),
])
def test_rejects_privilege_command_mount_and_budget_regressions(target, key, value):
    config = effective()
    config["services"][target][key] = value
    with pytest.raises(ValueError): policy.validate(config, ROOT)


@pytest.mark.parametrize("mutation", ["inherited", "writable", "copyup", "bind", "socket", "mode", "pin", "provider",
    "public_front", "wrong_build_proxy", "wrong_build_mode", "wrong_runtime_proxy", "private_network", "extra_network", "init_dependency", "build_context", "disabled_health", "substituted_health"])
def test_rejects_topology_and_mode_regressions(mutation):
    config = deepcopy(effective())
    back, front = config["services"]["demo-backend"], config["services"]["demo-frontend"]
    if mutation == "inherited": config["services"]["backend"] = deepcopy(back)
    elif mutation == "writable": back["volumes"][0]["read_only"] = False
    elif mutation == "copyup": back["volumes"][0]["volume"]["nocopy"] = False
    elif mutation == "bind": back["volumes"][0]["type"] = "bind"
    elif mutation == "socket": back["volumes"].append({"source": "/var/run/docker.sock", "target": "/var/run/docker.sock", "type": "bind"})
    elif mutation == "mode": back["environment"]["QUANTLAB_SERVING_MODE"] = "local"
    elif mutation == "pin": back["environment"].pop("QUANTLAB_DEMO_CORPUS_ID")
    elif mutation == "provider": back["environment"]["GLOBE_FRED_ENABLED"] = "true"
    elif mutation == "public_front": front["ports"][0]["host_ip"] = "0.0.0.0"
    elif mutation == "wrong_build_proxy": front["build"]["args"]["BACKEND_URL"] = "http://localhost:8000"
    elif mutation == "wrong_build_mode": front["build"]["args"]["NEXT_PUBLIC_QUANTLAB_EXPECTED_MODE"] = "local"
    elif mutation == "wrong_runtime_proxy": front["environment"]["BACKEND_URL"] = "http://backend:8000"
    elif mutation == "private_network": config["networks"]["demo_private"]["internal"] = False
    elif mutation == "extra_network": back["networks"]["demo_edge"] = None
    elif mutation == "init_dependency": back["depends_on"] = {"prepare": {"condition": "service_completed_successfully"}}
    elif mutation == "build_context": front["build"]["context"] = str(ROOT)
    elif mutation == "disabled_health": back["healthcheck"]["disable"] = True
    else: back["healthcheck"]["test"][3] += "; print('unsupported extra operation')"
    with pytest.raises(ValueError): policy.validate(config, ROOT)
