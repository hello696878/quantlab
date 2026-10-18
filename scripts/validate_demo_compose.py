"""Static policy check for Docker Compose's resolved JSON, not runtime acceptance."""
import argparse
import json
from pathlib import Path
import re

BACKEND = "http://demo-backend:8000"
COMMAND = ["python", "-m", "uvicorn", "app.serving:create_app", "--factory", "--host", "0.0.0.0",
           "--port", "8000", "--workers", "1", "--no-access-log", "--no-proxy-headers"]
FRONT_COMMAND = ["node", "node_modules/next/dist/bin/next", "start", "--hostname", "0.0.0.0", "--port", "3000"]
TMPFS = ["/tmp:rw,noexec,nosuid,nodev,size=64m,mode=1777"]
HEALTH_BACKEND = "import json,os,urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8000/ready',timeout=2); d=json.loads(r.read(2049)); assert d=={'status':'ready','policy':'read_only_demo_v1','corpus_id':os.environ['QUANTLAB_DEMO_CORPUS_ID']}"
HEALTH_FRONTEND = "fetch('http://127.0.0.1:3000/api/ready',{signal:AbortSignal.timeout(2000)}).then(async r=>{if(!r.ok)throw Error();const d=await r.json();if(d.status!=='ready'||d.policy!=='read_only_demo_v1'||d.corpus_id!==process.env.QUANTLAB_EXPECTED_CORPUS_ID)throw Error()}).catch(()=>process.exit(1))"
FIELDS = {"build", "image", "command", "user", "init", "read_only", "cap_drop", "security_opt", "tmpfs",
          "cpus", "mem_limit", "pids_limit", "ulimits", "environment", "volumes", "networks", "ports",
          "depends_on", "healthcheck", "logging", "restart", "entrypoint"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate(config, repo):
    """Closed local topology. No Docker invocation, app import or database access."""
    require(isinstance(config, dict) and set(config) <= {"name", "services", "networks", "volumes"}, "Unexpected top-level configuration")
    services = config.get("services", {})
    require(set(services) == {"demo-backend", "demo-frontend"}, "Unexpected or inherited services")
    back, front = services["demo-backend"], services["demo-frontend"]
    ports = front.get("ports", [])
    require(len(ports) == 1 and ports[0].get("host_ip") == "127.0.0.1" and ports[0].get("target") == 3000
            and ports[0].get("protocol") == "tcp" and str(ports[0].get("published", "")).isdigit(), "Frontend must publish one loopback TCP port")
    port = str(ports[0]["published"])
    require(1024 <= int(port) <= 65535, "Frontend port outside local operator range")
    require(not back.get("ports"), "Backend port publication is prohibited")
    identity = back.get("environment", {}).get("QUANTLAB_DEMO_CORPUS_ID", "")
    require(isinstance(identity, str) and re.fullmatch(r"[0-9a-f]{64}", identity), "Missing full corpus identity")
    require(back["environment"] == {
        "QUANTLAB_SERVING_MODE": "read_only_demo", "QUANTLAB_DEMO_CORPUS": "/corpus/v1",
        "QUANTLAB_DEMO_CORPUS_ID": identity, "QUANTLAB_DEMO_HOSTS": "demo-backend,127.0.0.1,localhost",
        "QUANTLAB_DEMO_ORIGINS": f"http://127.0.0.1:{port}"}, "Backend mode, path, host/origin or provider environment mismatch")
    require(front.get("environment") == {"BACKEND_URL": BACKEND, "NEXT_PUBLIC_QUANTLAB_EXPECTED_MODE": "read_only_demo",
                                           "QUANTLAB_EXPECTED_CORPUS_ID": identity}, "Frontend runtime/build-mode mismatch")
    require(back.get("command") == COMMAND and front.get("command") == FRONT_COMMAND, "Unsupported serving command")
    tags = []
    for name, service, memory, pids, folder, probe in (
        ("demo-backend", back, 512 * 1024**2, 96, "backend", ["CMD", "python", "-c", HEALTH_BACKEND]),
        ("demo-frontend", front, 768 * 1024**2, 128, "frontend", ["CMD", "node", "-e", HEALTH_FRONTEND]),
    ):
        require(not set(service) - FIELDS, f"Unexpected service fields: {name}")
        require(service.get("entrypoint") is None, f"Entrypoint override prohibited: {name}")
        require(service.get("user") == "10001:10001" and service.get("read_only") is True
                and service.get("init") is True, f"Non-root/read-only/init required: {name}")
        require(service.get("cap_drop") == ["ALL"] and service.get("security_opt") == ["no-new-privileges:true"], f"Privilege restriction mismatch: {name}")
        require(service.get("tmpfs") == TMPFS, f"Unexpected writable temporary mounts: {name}")
        require(float(service.get("cpus", 0)) == 1 and str(service.get("mem_limit")) == str(memory) and service.get("pids_limit") == pids, f"Resource budget mismatch: {name}")
        require(service.get("ulimits") == {"nofile": {"soft": 1024, "hard": 1024}}, f"Descriptor budget mismatch: {name}")
        require(service.get("restart") == "no" and service.get("logging") == {"driver": "local", "options": {"max-size": "5m", "max-file": "2"}}, f"Restart/log budget mismatch: {name}")
        health = service.get("healthcheck", {})
        require(set(health) == {"test", "interval", "timeout", "retries", "start_period"} and health["test"] == probe
                and health.get("interval") == "30s" and health.get("timeout") == "3s"
                and health.get("retries") == 3 and health.get("start_period") == "30s", f"Missing bounded image-available readiness probe: {name}")
        image = re.fullmatch(r"quantlab-" + name + r":([a-z0-9][a-z0-9._-]{0,63})", service.get("image", ""))
        require(image is not None, f"Expected explicit owned image tag: {name}")
        tags.append(image[1])
        build = service.get("build", {})
        require(set(build) == ({"context", "dockerfile"} if folder == "backend" else {"context", "dockerfile", "args"})
                and Path(build["context"]).resolve() == (repo / folder).resolve()
                and build["dockerfile"] == "Dockerfile.read-only-demo", f"Unexpected build context/recipe: {name}")
    require(tags[0] == tags[1], "Image tags must identify the same owned build set")
    require(front["build"]["args"] == {"BACKEND_URL": BACKEND, "NEXT_PUBLIC_QUANTLAB_EXPECTED_MODE": "read_only_demo"}, "Frontend baked proxy/mode mismatch")
    volumes = back.get("volumes", [])
    require(len(volumes) == 1 and volumes[0] == {"type": "volume", "source": "demo_corpus", "target": "/corpus",
                                               "read_only": True, "volume": {"nocopy": True}}, "Only read-only nocopy corpus volume is permitted")
    require(not front.get("volumes"), "Frontend mounts are prohibited")
    require(set(back.get("networks", {})) == {"demo_private"} and set(front.get("networks", {})) == {"demo_private", "demo_edge"}, "Unexpected network membership")
    networks = config.get("networks", {})
    require(set(networks) == {"demo_private", "demo_edge"} and networks["demo_private"].get("internal") is True
            and set(networks["demo_private"]) <= {"name", "internal", "ipam"} and set(networks["demo_edge"]) <= {"name", "ipam"}
            and not networks["demo_private"].get("ipam") and not networks["demo_edge"].get("ipam"), "Expected private internal network and explicit frontend edge")
    corpus = config.get("volumes", {})
    require(set(corpus) == {"demo_corpus"} and set(corpus["demo_corpus"]) == {"name", "external"}
            and corpus["demo_corpus"]["external"] is True
            and re.fullmatch(r"quantlab-p70-[a-z0-9-]{8,64}", corpus["demo_corpus"]["name"]), "Expected uniquely owned external corpus volume")
    require(not back.get("depends_on") and set(front.get("depends_on", {})) == {"demo-backend"}
            and front["depends_on"]["demo-backend"].get("condition") == "service_healthy", "Serving must not invoke preparation")
    return {"schema": "demo_compose_static_v1", "services": sorted(services), "frontend_port": port,
            "corpus_id": identity, "volume": corpus["demo_corpus"]["name"], "runtime_verified": False,
            "frontend_egress_blocked": False}


def validate_sources(repo):
    for folder in ("backend", "frontend"):
        text = (repo / folder / "Dockerfile.read-only-demo").read_text(encoding="utf-8")
        require([line for line in text.splitlines() if line.startswith("USER ")] == ["USER 10001:10001"], "Dedicated runtime USER mismatch")
        require("COPY . ." not in text and not any(line.startswith("ADD ") for line in text.splitlines()), "Broad Docker copy/add is prohibited")
        command = next(line[4:] for line in text.splitlines() if line.startswith("CMD "))
        require(json.loads(command) == (COMMAND if folder == "backend" else FRONT_COMMAND), "Dockerfile command mismatch")
    back = (repo / "backend/Dockerfile.read-only-demo").read_text()
    front = (repo / "frontend/Dockerfile.read-only-demo").read_text()
    require("mkdir /corpus && chown 10001:10001 /corpus" in back and "COPY app ./app" in back, "Preparation volume ownership/source contract missing")
    require("--engine-strict" in front and "ARG BACKEND_URL=http://demo-backend:8000" in front
            and "ARG NEXT_PUBLIC_QUANTLAB_EXPECTED_MODE=read_only_demo" in front
            and "node container/check-demo-build.cjs .next/routes-manifest.json > demo-build-contract.json" in front
            and "/app/demo-build-contract.json" in front, "Missing frontend engine/compiled-artifact contract")
    for folder, patterns in (("backend", {".env", ".env.*", "data/", "*.db", "*.db-*"}),
                             ("frontend", {".env", ".env.*", ".env.local", "node_modules/", ".next/"})):
        require(patterns <= set((repo / folder / ".dockerignore").read_text().splitlines()), "Required context exclusion patterns missing")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("configuration", type=Path)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        require(args.configuration.stat().st_size <= 1024 * 1024, "Oversized effective configuration")
        result = validate(json.loads(args.configuration.read_text(encoding="utf-8-sig")), args.repo)
        validate_sources(args.repo)
    except (OSError, ValueError, KeyError, TypeError, StopIteration, AttributeError):
        parser.exit(2, "Demo effective configuration refused; inspect the retained configuration against the local policy.\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
