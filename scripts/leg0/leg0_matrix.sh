#!/bin/bash
# Serve each setting, run leg0_run.py, stop the server. Run from the repo root on the GB10.
set -u
OUT=${OUT:-runs/leg0/results}
mkdir -p "$OUT"
for LK in "1 per_loop" "1 last_loop" "2 per_loop" "2 last_loop" "3 per_loop" "3 last_loop" "4 per_loop" "4 last_loop"; do
  set -- $LK; L=$1; KV=$2
  pkill -f "vllm serve.*--port 8001"; sleep 15
  setsid nohup vllm serve nvidia/NVIDIA-Nemotron-Labs-Dory1.0-4B-BF16 --revision f6c832e6963ddb74f62c75813a3e8c74b1af67b1 --port 8001 --max-model-len 16384 --gpu-memory-utilization 0.6 --hf-overrides "{\"n_recurrent_loops\": $L, \"recurrent_kv_cache_mode\": \"$KV\"}" --reasoning-parser nemotron_v3 --tool-call-parser qwen3_coder --enable-auto-tool-choice > "$OUT/vllm_loops${L}_${KV}.log" 2>&1 < /dev/null &
  for i in $(seq 1 120); do curl -s -m 2 localhost:8001/health -o /dev/null && break; sleep 5; done
  python3 scripts/leg0/leg0_run.py 8001 "$L" "$KV" "$OUT" > "$OUT/run_loops${L}_${KV}.log" 2>&1
  echo "done $L $KV rc=$?" >> "$OUT/progress.txt"
done
pkill -f "vllm serve.*--port 8001"
echo ALL_DONE >> "$OUT/progress.txt"
