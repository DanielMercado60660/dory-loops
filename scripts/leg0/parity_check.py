"""Compare top-5 next-token logprobs: vLLM endpoint (argv[1] port) vs transformers PR at 4 loops."""
import json, sys, urllib.request, torch
from transformers import AutoModelForCausalLM, AutoTokenizer
REV = "f6c832e6963ddb74f62c75813a3e8c74b1af67b1"
MODEL = "nvidia/NVIDIA-Nemotron-Labs-Dory1.0-4B-BF16"
PROMPT = "What is 17 * 23? Answer with just the number."
port = sys.argv[1]
body = {"model": MODEL, "prompt": PROMPT, "max_tokens": 1, "temperature": 0, "logprobs": 5}
req = urllib.request.Request(f"http://localhost:{port}/v1/completions", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
v = json.load(urllib.request.urlopen(req, timeout=600))["choices"][0]["logprobs"]["top_logprobs"][0]
tok = AutoTokenizer.from_pretrained(MODEL, revision=REV)
model = AutoModelForCausalLM.from_pretrained(MODEL, revision=REV, dtype=torch.bfloat16, n_recurrent_loops=4).cuda().eval()
ids = tok(PROMPT, return_tensors="pt").input_ids.cuda()
with torch.no_grad():
    lp = torch.log_softmax(model(input_ids=ids, use_cache=False).logits[0, -1].float(), -1)
top = torch.topk(lp, 5)
tf = {tok.decode([int(i)]): round(float(p), 3) for p, i in zip(top.values, top.indices)}
print("vllm:", {k: round(x, 3) for k, x in v.items()})
print("transformers:", tf)
