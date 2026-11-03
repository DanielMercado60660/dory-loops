#!/usr/bin/env python3
"""Create a run directory and record the environment.

Usage:
  python scripts/new_run.py --leg 0 --name smoke \
      --checkpoint nvidia/NVIDIA-Nemotron-Labs-Dory1.0-4B-BF16 \
      [--config my_config.yaml] [--llamacpp-dir ../artifacts/llama.cpp-dory]

Creates runs/legN/<YYYYMMDD-HHMM>_<name>/ with config.yaml, env.json,
an empty results.jsonl and a summary.md stub, then prints the path.
Standard library only. Every probe is best effort: a missing tool is
recorded as null, never a crash.
"""

import argparse
import datetime as dt
import getpass
import hashlib
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
from importlib import metadata
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SECRET_PAT = re.compile(r"TOKEN|KEY|SECRET|PASSWORD|PASS|AUTH|CRED", re.I)
ENV_PREFIXES = ("HF_", "VLLM_", "CUDA_", "NCCL_", "TORCH", "TRITON", "PYTORCH_", "XDG_CACHE", "TMPDIR", "PIP_CACHE", "DORY_", "ART")

CONFIG_TEMPLATE = """\
# Fill in every field needed to rerun this run exactly.
leg: {leg}
name: {name}
model:
  repo: nvidia/NVIDIA-Nemotron-Labs-Dory1.0-4B-BF16
  revision: null          # commit SHA, see MODEL_FACTS.md / runs/leg0/PINS.md
  precision: bf16         # bf16 | mxfp8 | nvfp4
loops: null               # n_recurrent_loops: 1 | 2 | 3 | 4 (always explicit, config default is 2)
kv_mode: null             # per_loop | last_loop
sampling:
  temperature: 1.0
  top_p: 0.95
  top_k: 0
  max_tokens: null
  seeds: []
chat_template_kwargs: {{}}
task:
  name: null
  version: null
  item_selection: null    # explicit IDs file or rule + seed
harness:
  name: null
  version: null
notes: ""
"""


def run(cmd, timeout=60):
    """Run a command, return stripped stdout or None."""
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return out.stdout.strip() if out.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def pkg_info(name):
    """Version and, for VCS installs, the commit SHA from direct_url.json."""
    try:
        dist = metadata.distribution(name)
    except metadata.PackageNotFoundError:
        return None
    info = {"version": dist.version, "commit": None, "url": None}
    try:
        raw = dist.read_text("direct_url.json")
        if raw:
            du = json.loads(raw)
            info["url"] = du.get("url")
            info["commit"] = (du.get("vcs_info") or {}).get("commit_id")
    except (OSError, ValueError):
        pass
    return info


def torch_cuda():
    code = "import json,torch;print(json.dumps({'torch':torch.__version__,'cuda':torch.version.cuda,'cudnn':torch.backends.cudnn.version(),'gpu':torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,'capability':torch.cuda.get_device_capability(0) if torch.cuda.is_available() else None}))"
    out = run([sys.executable, "-c", code], timeout=120)
    try:
        return json.loads(out) if out else None
    except ValueError:
        return None


def git_info(path):
    sha = run(["git", "-C", str(path), "rev-parse", "HEAD"])
    if sha is None:
        return None
    dirty = run(["git", "-C", str(path), "status", "--porcelain"])
    branch = run(["git", "-C", str(path), "rev-parse", "--abbrev-ref", "HEAD"])
    return {"sha": sha, "branch": branch, "dirty": bool(dirty)}


def hf_cache_dir():
    if os.environ.get("HF_HUB_CACHE"):
        return Path(os.environ["HF_HUB_CACHE"])
    if os.environ.get("HF_HOME"):
        return Path(os.environ["HF_HOME"]) / "hub"
    return Path.home() / ".cache" / "huggingface" / "hub"


def checkpoint_info(spec):
    """spec is 'org/name' or 'org/name@revision'. Resolve via the local HF cache."""
    repo, _, requested = spec.partition("@")
    entry = {"repo": repo, "requested_revision": requested or None, "resolved_revision": None, "snapshots": []}
    cache = hf_cache_dir() / ("models--" + repo.replace("/", "--"))
    ref_name = requested or "main"
    ref = cache / "refs" / ref_name
    if ref.is_file():
        entry["resolved_revision"] = ref.read_text().strip()
    elif re.fullmatch(r"[0-9a-f]{40}", ref_name or ""):
        entry["resolved_revision"] = ref_name
    snaps = cache / "snapshots"
    if snaps.is_dir():
        entry["snapshots"] = sorted(p.name for p in snaps.iterdir())
    if not entry["resolved_revision"]:
        entry["warning"] = "not found in local HF cache; record the revision manually"
    return entry


def nvidia():
    smi = shutil.which("nvidia-smi")
    if not smi:
        return None
    query = run([smi, "--query-gpu=name,driver_version,memory.total,power.limit", "--format=csv,noheader"])
    full = run([smi])
    cuda = None
    if full:
        m = re.search(r"CUDA Version:\s*([\d.]+)", full)
        cuda = m.group(1) if m else None
    return {"query": query, "cuda_driver_api": cuda, "full": full}


def scrub(text):
    """The repo is public: replace hostname, home path and username with neutral tokens."""
    host = socket.gethostname()
    if host:
        tag = "host-" + hashlib.sha256(host.encode()).hexdigest()[:8]
        text = text.replace(host, tag)
        short = host.split(".")[0]
        if len(short) >= 3:
            text = re.sub(r"(?<![A-Za-z0-9])" + re.escape(short) + r"(?![A-Za-z0-9])", tag, text)
    home = str(Path.home())
    if len(home) > 1:
        text = text.replace(home, "~")
    try:
        user = getpass.getuser()
    except Exception:
        user = ""
    if len(user) >= 3:
        text = re.sub(r"(?<![A-Za-z0-9])" + re.escape(user) + r"(?![A-Za-z0-9])", "<user>", text)
    return text


def safe_env():
    out = {}
    for k, v in sorted(os.environ.items()):
        if k.startswith(ENV_PREFIXES) and not SECRET_PAT.search(k):
            out[k] = v
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--leg", type=int, required=True, choices=range(0, 7))
    ap.add_argument("--name", required=True, help="short name: lowercase letters, digits, - and _")
    ap.add_argument("--config", help="YAML file to copy as config.yaml (otherwise a template is written)")
    ap.add_argument("--checkpoint", action="append", default=[], help="HF repo id, optionally @revision. Repeatable.")
    ap.add_argument("--llamacpp-dir", help="path to a llama.cpp checkout, if used")
    ap.add_argument("--extra-git", action="append", default=[], help="NAME=PATH of another checkout to record. Repeatable.")
    ap.add_argument("--root", default=str(REPO_ROOT), help="repo root (default: this repo)")
    args = ap.parse_args()

    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,47}", args.name):
        ap.error("--name must match [a-z0-9][a-z0-9_-]{0,47}")

    root = Path(args.root).resolve()
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M")
    run_dir = root / "runs" / f"leg{args.leg}" / f"{stamp}_{args.name}"
    if run_dir.exists():
        sys.exit(f"error: {run_dir} already exists. Wait a minute or pick another name.")
    run_dir.mkdir(parents=True)

    if args.config:
        shutil.copyfile(args.config, run_dir / "config.yaml")
    else:
        (run_dir / "config.yaml").write_text(CONFIG_TEMPLATE.format(leg=args.leg, name=args.name))

    extra = {}
    for item in args.extra_git:
        name, _, path = item.partition("=")
        extra[name] = git_info(path) if path else None

    freeze = run([sys.executable, "-m", "pip", "freeze", "--all"], timeout=120)
    env = {
        "run_id": run_dir.name,
        "leg": args.leg,
        "created_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "host": socket.gethostname(),  # replaced by scrub() before writing
        "platform": {"system": platform.system(), "release": platform.release(), "machine": platform.machine(), "python": sys.version.split()[0], "executable": sys.executable},
        "git": {
            "repo": git_info(root),
            "llama_cpp": git_info(args.llamacpp_dir) if args.llamacpp_dir else None,
            **extra,
        },
        "packages": {p: pkg_info(p) for p in ("vllm", "transformers", "torch", "flashinfer-python", "nemo-evaluator", "nemo-skills", "mini-swe-agent")},
        "torch_cuda": torch_cuda(),
        "nvcc": run(["nvcc", "--version"]),
        "nvidia_smi": nvidia(),
        "checkpoints": [checkpoint_info(c) for c in args.checkpoint],
        "env": safe_env(),
        "pip_freeze": freeze.splitlines() if freeze else None,
    }
    (run_dir / "env.json").write_text(scrub(json.dumps(env, indent=2)) + "\n")
    (run_dir / "results.jsonl").touch()
    (run_dir / "summary.md").write_text(
        f"# {run_dir.name}\n\n"
        "Status: running\n\n"
        "## Headline (95% bootstrap CI)\n\n| Setting | n items | Score | CI |\n|---|---|---|---|\n\n"
        "## Oddities\n\n## Raw outputs\n\n`../artifacts/" + run_dir.name + "/`\n"
    )

    warnings = []
    if env["git"]["repo"] and env["git"]["repo"]["dirty"]:
        warnings.append("repo has uncommitted changes; commit code before runs that use it")
    for c in env["checkpoints"]:
        if c.get("warning"):
            warnings.append(f"{c['repo']}: {c['warning']}")
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    print(run_dir)


if __name__ == "__main__":
    main()
