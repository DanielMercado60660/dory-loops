"""Leg 0 base option (a): transformers PR 50099 at fcc6924, BF16 checkpoint."""
import time, torch, json
from transformers import AutoModelForCausalLM, AutoConfig
REV = "f6c832e6963ddb74f62c75813a3e8c74b1af67b1"
MODEL = "nvidia/NVIDIA-Nemotron-Labs-Dory1.0-4B-BF16"
out = {}
cfg = AutoConfig.from_pretrained(MODEL, revision=REV, trust_remote_code=False)
out["config_model_type"] = cfg.model_type
out["n_recurrent_loops_default"] = getattr(cfg, "n_recurrent_loops", None); out["num_hidden_layers"] = cfg.num_hidden_layers
t = time.time()
model = AutoModelForCausalLM.from_pretrained(MODEL, revision=REV, dtype=torch.bfloat16, n_recurrent_loops=4).cuda().eval()
out["load_s"] = round(time.time() - t, 1)
torch.cuda.reset_peak_memory_stats()
ids = torch.randint(100, 20000, (1, 4096), device="cuda")
with torch.no_grad():
    t = time.time()
    o = model(input_ids=ids, output_hidden_states=True, use_cache=False)
    torch.cuda.synchronize()
out["forward_4k_s"] = round(time.time() - t, 2)
out["hidden_states_returned"] = len(o.hidden_states) if o.hidden_states is not None else None
out["logits_shape"] = list(o.logits.shape)
out["peak_gpu_gb"] = round(torch.cuda.max_memory_allocated() / 1e9, 2)
out["finite"] = bool(torch.isfinite(o.logits).all())
print(json.dumps(out, indent=1))
