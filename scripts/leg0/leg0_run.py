"""Leg 0 runner. Usage: leg0_run.py PORT LOOPS KV OUTDIR

Single-stream pass over src/smoke_prompts.json, batched passes at 32 and 64
(same prompts cycled), memory sampled from `free -m` during each batched
pass, and the template-switch probe at loop 1. Writes results.jsonl.
"""
import json, subprocess, sys, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

PORT, LOOPS, KV, OUT = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
MODEL = "nvidia/NVIDIA-Nemotron-Labs-Dory1.0-4B-BF16"
PROMPTS = json.load(open("src/smoke_prompts.json"))
URL = f"http://localhost:{PORT}/v1/chat/completions"


def chat(prompt, extra=None):
    body = {"model": MODEL, "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 4096, "temperature": 1.0, "top_p": 0.95, "top_k": 0, "seed": 0}
    body.update(extra or {})
    req = urllib.request.Request(URL, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t = time.time()
    r = json.load(urllib.request.urlopen(req, timeout=1800))
    c = r["choices"][0]
    m = c["message"]
    return {"content": m.get("content"),
            "reasoning": m.get("reasoning") or m.get("reasoning_content"),
            "finish": c["finish_reason"],
            "completion_tokens": r["usage"]["completion_tokens"],
            "latency_s": round(time.time() - t, 2)}


def mem_used_mb():
    out = subprocess.run(["free", "-m"], capture_output=True, text=True).stdout.splitlines()[1]
    return int(out.split()[2])


def batched(n):
    prompts = [PROMPTS[i % len(PROMPTS)] for i in range(n)]
    peak = [mem_used_mb()]
    stop = threading.Event()

    def sample():
        while not stop.is_set():
            peak[0] = max(peak[0], mem_used_mb())
            time.sleep(1)

    th = threading.Thread(target=sample, daemon=True)
    th.start()
    t = time.time()
    with ThreadPoolExecutor(max_workers=n) as ex:
        res = list(ex.map(chat, prompts))
    wall = time.time() - t
    stop.set()
    th.join()
    toks = sum(x["completion_tokens"] for x in res)
    return {"kind": f"batch{n}", "requests": n, "wall_s": round(wall, 2),
            "completion_tokens": toks, "agg_tok_s": round(toks / wall, 2),
            "finish": sorted({x["finish"] for x in res}), "peak_used_mb": peak[0]}


rows = []
base = {"loops": LOOPS, "kv": KV}
single = []
for i, p in enumerate(PROMPTS):
    r = chat(p)
    single.append(r)
    rows.append({**base, "kind": "single", "prompt_idx": i, **r})
toks = sum(x["completion_tokens"] for x in single)
lat = sum(x["latency_s"] for x in single)
rows.append({**base, "kind": "single_summary", "completion_tokens": toks,
             "tok_s": round(toks / lat, 2), "finish": sorted({x["finish"] for x in single})})
for n in (32, 64):
    rows.append({**base, **batched(n)})
if LOOPS == 1 and KV == "per_loop":
    for label, extra in [("enable_thinking_false", {"chat_template_kwargs": {"enable_thinking": False}}),
                         ("medium_effort_true", {"chat_template_kwargs": {"medium_effort": True}})]:
        r = chat(PROMPTS[1], extra)
        rows.append({**base, "kind": "template_switch", "switch": label, **r})
with open(f"{OUT}/results_loops{LOOPS}_{KV}.jsonl", "w") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")
print("wrote", len(rows), "rows")
