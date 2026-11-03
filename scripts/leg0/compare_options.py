"""Leg 0 base comparison: option (a) transformers PR and option (b) standalone port vs vLLM 0.33.0.

Usage: compare_options.py VLLM_PORT HF_HUB_DIR
Reads vLLM prompt_logprobs (top-5 per prompt position), scores both options at the same positions,
and reports agreement plus time and memory. Run with vLLM serving at loops 4, per_loop.
"""
import glob, json, sys, time, urllib.request
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
sys.path.insert(0, "scripts/leg0")
from dory_standalone import Dory

REV = "f6c832e6963ddb74f62c75813a3e8c74b1af67b1"
MODEL = "nvidia/NVIDIA-Nemotron-Labs-Dory1.0-4B-BF16"
PORT, HUB = sys.argv[1], sys.argv[2]
PROMPTS = json.load(open("src/smoke_prompts.json"))
tok = AutoTokenizer.from_pretrained(MODEL, revision=REV)

def vllm_top5(ids):
    body = {"model": MODEL, "prompt": ids, "max_tokens": 1, "temperature": 0, "prompt_logprobs": 5}
    req = urllib.request.Request(f"http://localhost:{PORT}/v1/completions", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    pl = json.load(urllib.request.urlopen(req, timeout=600))["choices"][0]["prompt_logprobs"]
    out = []
    for entry in pl[1:]:  # first position has no logprobs
        out.append({int(k): float(v["logprob"]) for k, v in entry.items()})
    return out

hf = AutoModelForCausalLM.from_pretrained(MODEL, revision=REV, dtype=torch.bfloat16, n_recurrent_loops=4).cuda().eval()
snap = glob.glob(f"{HUB}/models--nvidia--NVIDIA-Nemotron-Labs-Dory1.0-4B-BF16/snapshots/{REV}")[0]
sa = Dory(snap)

res = {"a": {"diffs": [], "top1": 0, "n": 0, "time": 0.0}, "b": {"diffs": [], "top1": 0, "n": 0, "time": 0.0}}
ab_diffs = []
for p in PROMPTS:
    ids = tok(p, return_tensors="pt").input_ids[0]
    ref = vllm_top5(ids.tolist())
    n = len(ref)
    ids_c = ids.cuda()
    with torch.no_grad():
        t = time.time()
        la = torch.log_softmax(hf(input_ids=ids_c[None], use_cache=False).logits[0].float(), -1)
        torch.cuda.synchronize(); res["a"]["time"] += time.time() - t
        t = time.time()
        lb_logits, _ = sa.forward(ids_c, loops=4)
        torch.cuda.synchronize(); res["b"]["time"] += time.time() - t
        lb = torch.log_softmax(lb_logits, -1)
    ab_diffs.append((la[:n] - lb[:n]).abs().max().item())
    for key, lp in (("a", la), ("b", lb)):
        for pos in range(n):
            # position pos predicts token pos+1 of the prompt; vLLM top-5 at pos is ref[pos]
            r = ref[pos]
            for tid, v in r.items():
                res[key]["diffs"].append(abs(float(lp[pos, tid]) - v))
            res[key]["top1"] += int(lp[pos].argmax().item() == max(r, key=r.get))
            res[key]["n"] += 1

for key, name in (("a", "option (a) transformers PR"), ("b", "option (b) standalone port")):
    d = torch.tensor(res[key]["diffs"])
    print(f"{name}: positions={res[key]['n']} top1_agree_vs_vllm={res[key]['top1']/res[key]['n']:.4f} "
          f"logprob_abs_diff_vs_vllm mean={d.mean():.4f} max={d.max():.4f} p99={d.quantile(0.99):.4f} "
          f"forward_time_s_total={res[key]['time']:.2f}")
print(f"option (a) vs (b) max abs logprob diff over all vocab, all prompts: {max(ab_diffs):.4f}")
print("peak_gpu_gb", round(torch.cuda.max_memory_allocated() / 1e9, 2))
