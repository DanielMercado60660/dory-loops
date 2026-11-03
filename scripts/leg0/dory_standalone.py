"""Leg 0 base option (b): standalone PyTorch forward for Dory, ported from vLLM 0.33.0 dory.py.

Prefill only (no KV cache): each loop attends over the full sequence with its own K/V,
which is what per_loop KV mode computes. Returns per-loop states h_k (loop outputs) so
no patching is needed to read them.
"""
import glob, json, math, sys, time
import torch
import torch.nn.functional as F
from safetensors import safe_open

EPS = 1e-6


def justnorm(x):
    xf = x.float()
    return (xf * torch.rsqrt(xf.pow(2).sum(-1, keepdim=True) + EPS)).to(x.dtype)


def slerp_alpha(a, b, alpha, alpha_scale):
    lr = (alpha.float() * alpha_scale).abs()
    ya, yb = justnorm(a).float(), justnorm(b).float()
    return justnorm(ya + lr * (yb - ya)).to(a.dtype)


def rope(x, pos, theta):
    # neox-style rotate_half, full rotary (partial_rotary_factor 1.0)
    d = x.shape[-1]
    inv = 1.0 / (theta ** (torch.arange(0, d, 2, device=x.device, dtype=torch.float32) / d))
    ang = pos.float()[:, None] * inv[None, :]
    cos, sin = ang.cos().to(x.dtype)[:, None, :], ang.sin().to(x.dtype)[:, None, :]
    x1, x2 = x[..., : d // 2], x[..., d // 2 :]
    return torch.cat([x1 * cos - x2 * sin, x2 * cos + x1 * sin], dim=-1)


class Dory:
    def __init__(self, snap, device="cuda", dtype=torch.bfloat16):
        self.cfg = json.load(open(f"{snap}/config.json"))
        c = self.cfg
        self.H, self.nh, self.nkv, self.hd = c["hidden_size"], c["num_attention_heads"], c["num_key_value_heads"], c["head_dim"]
        self.std = c["initializer_range"]
        self.alpha_scale = c["ngpt_alpha_init"] / self.std
        self.sw = c["sliding_window"]
        self.n_in, self.n_rec, self.n_out = c["n_input_layers"], c["n_recurrent_layers"], c["n_output_layers"]
        self.types = c["layer_types"]
        self.sqk_factor = self.hd ** 0.5 / self.std
        g0 = c["attention_output_gate_logit_scale_init"] or self.H ** 0.5
        self.sg_factor = g0 ** 0.5 / self.std
        self.suv_factor = self.H ** 0.5
        self.logit_div = self.std
        W = {}
        for f in sorted(glob.glob(f"{snap}/*.safetensors")):
            with safe_open(f, "pt") as s:
                for k in s.keys():
                    W[k] = s.get_tensor(k).to(device=device, dtype=dtype)
        self.W = W
        self.device = device

    def attn(self, i, h, pos, mask_full, mask_slide):
        p = f"backbone.layers.{i}.mixer."
        W = self.W
        T = h.shape[0]
        q = (h @ W[p + "q_proj.weight"].T).view(T, self.nh, self.hd)
        k = (h @ W[p + "k_proj.weight"].T).view(T, self.nkv, self.hd)
        v = (h @ W[p + "v_proj.weight"].T).view(T, self.nkv, self.hd)
        gate = h @ W[p + "g_proj.weight"].T
        layer_type = self.types[i]
        theta = self.cfg["rope_parameters"][layer_type]["rope_theta"]
        q = rope(q, pos, theta)
        k = rope(k, pos, theta)
        sqk = (W[p + "sqk"].float() * self.sqk_factor).view(self.nh, self.hd)
        q = (sqk.square() * justnorm(q).float()).to(h.dtype)
        k = justnorm(k)
        rep = self.nh // self.nkv
        k = k.repeat_interleave(rep, dim=1)
        v = v.repeat_interleave(rep, dim=1)
        q, k, v = q.transpose(0, 1)[None], k.transpose(0, 1)[None], v.transpose(0, 1)[None]
        mask = mask_slide if layer_type == "sliding_attention" else mask_full
        out = F.scaled_dot_product_attention(q, k, v, attn_mask=mask, scale=1.0 / math.sqrt(self.hd))
        out = out[0].transpose(0, 1).reshape(T, self.nh * self.hd)
        sg = (W[p + "s_gate"].float() * self.sg_factor).square()
        out = (out.float() * torch.sigmoid(gate.float() * sg)).to(h.dtype)
        out = justnorm(out)
        return out @ W[p + "o_proj.weight"].T

    def mlp(self, i, h):
        p = f"backbone.layers.{i}.mixer."
        W = self.W
        g = h @ W[p + "gate_proj.weight"].T
        u = h @ W[p + "up_proj.weight"].T
        g = (g.float() * (W[p + "suv_gate"].float() * self.suv_factor)).to(h.dtype)
        u = (u.float() * (W[p + "suv_up"].float() * self.suv_factor)).to(h.dtype)
        m = justnorm((F.silu(g.float()) * u.float()).to(h.dtype))
        return m @ W[p + "down_proj.weight"].T

    def layer(self, i, h, pos, mf, ms):
        if self.types[i] == "mlp":
            return slerp_alpha(h, self.mlp(i, h), self.W[f"backbone.layers.{i}.mlp_alpha"], self.alpha_scale)
        return slerp_alpha(h, self.attn(i, h, pos, mf, ms), self.W[f"backbone.layers.{i}.attn_alpha"], self.alpha_scale)

    @torch.no_grad()
    def forward(self, ids, loops):
        """ids: 1-D tensor. Returns (logits, [h_1..h_loops]) where h_k is the recurrent output after loop k."""
        T = ids.shape[0]
        pos = torch.arange(T, device=self.device)
        causal = torch.ones(T, T, dtype=torch.bool, device=self.device).tril()
        dist = pos[:, None] - pos[None, :]
        slide = causal & (dist < self.sw)
        mf = causal[None, None]
        ms = slide[None, None]
        h = self.W["backbone.embeddings.weight"][ids]
        for i in range(self.n_in):
            h = self.layer(i, h, pos, mf, ms)
        input_h = h
        state = input_h
        per_loop = []
        rs, re = self.n_in, self.n_in + self.n_rec
        for _ in range(loops):
            h = justnorm(state + input_h)
            for i in range(rs, re):
                h = self.layer(i, h, pos, mf, ms)
            state = justnorm(h)
            per_loop.append(state)
        h = state
        for i in range(re, re + self.n_out):
            h = self.layer(i, h, pos, mf, ms)
        scale = self.W["lm_head.logit_scale"].float() / self.logit_div
        logits = (h @ self.W["lm_head.weight"].T).float() * scale
        return logits, per_loop


if __name__ == "__main__":
    REV = "f6c832e6963ddb74f62c75813a3e8c74b1af67b1"
    snap = glob.glob(f"{sys.argv[1]}/models--nvidia--NVIDIA-Nemotron-Labs-Dory1.0-4B-BF16/snapshots/{REV}")[0]
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained("nvidia/NVIDIA-Nemotron-Labs-Dory1.0-4B-BF16", revision=REV)
    t = time.time()
    m = Dory(snap)
    print("load_s", round(time.time() - t, 1))
    ids = tok("What is 17 * 23? Answer with just the number.", return_tensors="pt").input_ids[0].cuda()
    logits, per = m.forward(ids, loops=4)
    lp = torch.log_softmax(logits[-1], -1)
    top = torch.topk(lp, 5)
    print("standalone:", {tok.decode([int(i)]): round(float(p), 3) for p, i in zip(top.values, top.indices)})
    print("loop states:", len(per), tuple(per[0].shape))
    torch.cuda.reset_peak_memory_stats()
    big = torch.randint(100, 20000, (4096,), device="cuda")
    torch.cuda.synchronize(); t = time.time()
    m.forward(big, loops=4); torch.cuda.synchronize()
    print("forward_4k_4loops_s", round(time.time() - t, 2), "peak_gb", round(torch.cuda.max_memory_allocated() / 1e9, 2))
