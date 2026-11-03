# EXPERIMENTS

Run the legs in order. Each leg ends at a GATE (see CLAUDE.md, Operating rules). All runtime numbers here are **guesses** made before any measurement. Replace them with Leg 0 measurements in each PREREG.

There is no fixed GPU-hour cap. The run lasts until Collin stops it (see CLAUDE.md, Run window). Because it can end at any time, push results as they land, and size each leg so it produces a usable result early (slim pass first).

## Leg overview

| Leg | Name | Wall-clock hours (guess) | Gate |
|---|---|---|---|
| 0 | Setup and smoke test | 3 | Coherent output in all 8 settings, throughput logged |
| 1 | Reproduce card baselines | 8 | IFBench and GPQA within ~2 pts of card, or CI overlaps |
| 2 | Loop sweep: depth vs length vs width | 24 | Slim pass stable across seeds before the full matrix |
| 3 | Implicit routing and adaptive exit | 14 | Pareto plots for 3b/3c vs fixed loops, with CIs |
| 4 | Agent harness, task bank, dev baseline | 12 | Bank frozen, tool-call parse failure rate under 3% |
| 5 | Claude improves the harness, sealed holdout | 14 | Holdout results recorded verbatim, no reruns |
| 6 | Write-up | 1 | `runs/FINAL_REPORT.md` pushed |

Total guess: about 76 hours, roughly 3 days.

**Throughput guess**, for planning only. Single-stream decode is bound by memory bandwidth (GB10 is about 273 GB/s). Bytes read per token grow with layer-passes (36 at 1 loop, 96 at 4 loops), so expect very roughly 30 tok/s single-stream at 1 loop and about 2.5x slower at 4 loops. Batched aggregate throughput is much higher. Measure both in Leg 0.

**Cost metric used everywhere:** compute = generated tokens x layer-passes per token, with layer-passes = 16 + 20 x loops (card-style blocks; see MODEL_FACTS.md). Report prompt tokens x layer-passes separately as a secondary metric. Also report wall-clock and mean GPU power.

---

## Leg 0: Setup and smoke test

**Goal.** A working, pinned inference stack on GB10, sanity output at every loop/KV setting, measured throughput, and a decision on the Leg 3 code base.

**Steps.**
1. Environment setup from CLAUDE.md, including cache redirects. Record the free disk and baseline `nvidia-smi`.
2. Inference stack, in this order. Stop at the first one that works and record why the earlier ones failed:
   1. `pip install vllm==0.33.0` in `../artifacts/venv`. This release contains the merged Dory PR and ships an aarch64 wheel. Confirm `vllm/model_executor/models/dory.py` exists in the install.
   2. vLLM built from the PR's merge commit `75fc05a53a366068f534a61ab3ee6b50485419f2` with `VLLM_USE_PRECOMPILED=1`.
   3. NVIDIA's vLLM container for DGX Spark from nvcr.io, if a tag that includes Dory support exists. Check the image's vLLM version or commit before relying on it.
   4. vLLM built from source at the pinned commit (slow, uses disk; estimate both before starting).
   5. The card's PR install: `VLLM_USE_PRECOMPILED=1 pip install "git+https://github.com/vllm-project/vllm.git@refs/pull/60149/head"`.

   If all fail, stop and ask. Do not fall back to llama.cpp without asking.
3. Download the BF16 checkpoint at the revision in MODEL_FACTS.md (about 8 GB) into `$HF_HOME`. NVFP4 waits until Leg 2.
4. Smoke test.
   - Prompts: 5 fixed prompts, committed in `src/smoke_prompts.json`. Cover arithmetic, a short code task, instruction following with a format constraint, a factual question, and a 2-turn chat.
   - Settings: loops {1, 2, 3, 4} x KV {per_loop, last_loop} = 8 settings. Card sampling, fixed seed, max_tokens 4096.
   - Record per setting: output text (to artifacts), output and reasoning token counts, single-stream tokens/s, batched tokens/s (batch 32 and 64, same prompts repeated), and peak memory (`nvidia-smi` and `free -m`).
5. Template switches. Check whether vLLM honors `chat_template_kwargs` `enable_thinking: false` and `medium_effort: true`: inspect the rendered prompt and the output length. This decides which LENGTH levers Leg 2 can use.
6. **Leg 3 base decision.** Evaluate two options and pick one, with reasons in the report:
   - (a) `transformers` from PR huggingface/transformers#50099 pinned to a SHA (check it installs cleanly next to the chosen vLLM, ideally in a separate venv), loading the BF16 checkpoint.
   - (b) a standalone PyTorch forward ported from vLLM's `dory.py`.

   Criteria: loads the real checkpoint, exposes per-loop hidden states without invasive patches, runs 4 loops on a 4K-token sequence on GB10. Leg 3 adds a numerical parity gate against vLLM either way.
7. Pin everything in `runs/leg0/PINS.md`: vLLM version and commit, transformers SHA if used, torch and CUDA, container digests, checkpoint revisions.

**GATE.** Coherent output in all 8 settings (judge this yourself and paste one output per setting into REPORT.md), throughput and memory logged, Leg 3 base chosen.

---

## Leg 1: Reproduce card baselines

**Goal.** Show that the stack and harness reproduce NVIDIA's numbers before trusting anything new.

**Matrix.**
- Tasks: IFBench, GPQA Diamond (no tools).
- Settings: loops {1, 2, 4}, KV per_loop (assumed card setting, see MODEL_FACTS.md), BF16, temperature 1.0, top_p 0.95.
- Seeds: at least 3 (GPQA has 198 items; use 4 to 8 seeds if budget allows).
- Max tokens: from the NVIDIA template config. Record the value and the truncation rate.

**Harness.**
- Prefer NeMo Evaluator (Docker is expected to work on GB10), using NVIDIA's published Nemotron Nano / Nemotron 3 configs as the template. Point it at the local vLLM endpoint.
- If its images are not available for aarch64, fall back to NeMo Skills.
- If neither works, stop and ask (don't hand-roll a scorer without approval).
- GPQA on HF is gated. If `HF_TOKEN` is missing or lacks access, open a blocking issue asking Collin or Daniel to accept the terms on their HF account and provide a read-only `HF_TOKEN`.

**Targets.**

| Task | 1 loop | 2 loops | 4 loops |
|---|---|---|---|
| IFBench | 74.29 | 77.94 | 79.0 |
| GPQA Diamond | 69.19 | 72.41 | 72.16 |

Not in Leg 1 but on the card for later reference: AA-LCR 63 / 71 / 73, SciCode 27.3 / 34.94 / 35.11.

**Metrics.** Accuracy with 95% bootstrap CI per setting, mean output tokens, truncation rate, tokens/s.

**GATE.** Each of the 6 values is within ~2 points of the card, or its 95% CI covers the card value. If not, stop and report. Check prompt template, max tokens, answer extraction and KV mode before concluding anything. Do not proceed.

---

## Leg 2: Loop sweep (depth vs length vs width)

**Goal.** Characterize what extra depth buys per task type, and compare DEPTH (loops) with LENGTH (reasoning token budget) and WIDTH (majority vote) at matched compute.

**Tasks.**

| Task | Type | Size used | Notes |
|---|---|---|---|
| MATH-500 | math | 500 (slim 100) | exact match after normalization |
| AIME 2024 + 2025 | hard math | 60 | needs many samples, n = 8 |
| GPQA Diamond | science MCQ | 198 | reuse Leg 1 setup |
| LiveCodeBench | code | most recent release subset, ideally problems dated after June 2026 (after the post-training data cutoff, May 2026) | record the date window and version |
| IFEval | instruction following | 541 | |
| MMLU-Pro subset | knowledge control | ~1000, stratified by category, fixed seed | preferred over SimpleQA, which needs an LLM judge (no external APIs allowed) |
| RULER | long context | 32K and 128K, subset of task types, ~50 samples per type at 32K, fewer at 128K | pin the generator commit |

**Axes.**
- **Depth:** loops {1, 2, 3, 4}.
- **KV:** {per_loop, last_loop}.
- **Length:** reasoning budget caps. Primary: a two-phase cap (generate up to B thinking tokens, then close with `</think>` and generate the answer) with B in {1K, 2K, 4K, 8K, uncapped}. Secondary, if Leg 0 shows it works: the `medium_effort` template switch.
- **Width:** majority vote n in {1, 4, 8}, computed by subsampling from 8 stored samples per item. Bootstrap over subsets as well as items. Charge the cost as n x single-sample cost.
- **Precision:** BF16 vs NVFP4 (W4A16), on the MATH-500 slim set + GPQA only, loops {1, 2, 4}.

The full factorial does not fit the 24-hour estimate. **Use this priority order and cut from the bottom** (plan the cuts in PREREG from Leg 0 throughput):
1. Depth core: all tasks except RULER x loops {1,2,3,4} x per_loop. n = 8 on AIME and GPQA, n = 4 on MATH-500, n = 3 elsewhere.
2. Width: no extra compute, derived from 1.
3. KV: last_loop at loops {2, 4} on MATH-500 slim + GPQA, and on RULER (step 6).
4. Length: caps at loops {1, 2, 4} on MATH-500 slim, GPQA, AIME.
5. LiveCodeBench at loops {1, 2, 4} if it was cut from step 1.
6. RULER 32K at loops {1, 2, 4} x both KV modes, then 128K at loops {1, 4} x both KV modes.
7. Precision.

**Metrics.**
- Accuracy with 95% CI per (task, setting).
- Mean output and reasoning tokens.
- Truncation rate.
- Compute (layer-passes x generated tokens), wall-clock, mean power.
- **Accuracy vs compute Pareto curve per task**, with all depth, length and width points on one plot and CIs as error bars.

**Hypotheses.**
- **H2.1.** The knowledge control (MMLU-Pro subset) stays flat across loops: the loop 4 vs loop 1 difference CI includes 0. (The card's AA-Omniscience is flat: 10.03 / 10.08 / 10.03.)
- **H2.2.** Math and code gain most from loops 1 to 2, with diminishing returns after: gain(1 to 2) > gain(2 to 4) on MATH-500, AIME and LiveCodeBench.
- **H2.3.** Output tokens fall as loops rise (mean output tokens at loop 4 < loop 1 on reasoning tasks).
- **H2.4.** last_loop matches per_loop at short context (difference CI includes 0 on MATH-500 and GPQA). Test whether it degrades on RULER 128K.
- **Exploratory, no prediction:** at matched compute, which of depth, length and width gives the best accuracy per task type.

**GATE.** Before the full matrix: the slim pass, with at least 2 seeds, gives seed-to-seed variation inside the bootstrap CIs, and parse and truncation rates under 3%. Then run the full matrix and push the Pareto plots (PNG, committed if under 5 MB).

---

## Leg 3: Implicit routing and adaptive exit

**Goal.** Test whether a fixed-depth looped model contains an implicit per-token router, meaning tokens whose prediction is settled after fewer loops, and whether adaptive exit can exploit it. This is likely the most novel leg. Do the literature check in REFERENCES.md first.

**Setup.**
- Use the base chosen in Leg 0 to write a forward that runs 4 loops and, after each loop k in {1, 2, 3, 4}, applies the Output block to get logits p_k, keeping the hidden state h_k (the recurrent-block output, before the Output block).
- Commit the code in `src/`.
- **Entry gate: parity.** On 20 fixed prompts, compare your forward's final logits at loops 1, 2 and 4 with vLLM (prompt logprobs) at the same loop count. Require top-1 agreement of at least 99% and report the max absolute logprob difference. If parity fails, stop and report.
- Note on nGPT: hidden states are normalized, so report cosine distance as well as relative L2 change.

**3a. Convergence probe.**
- Inputs: teacher-forced passes over model-generated outputs from Leg 2 (MATH-500, GPQA, IFEval, MMLU-Pro subset; a few hundred sequences).
- Per token, record:
  - ||h_k - h_{k-1}|| / ||h_{k-1}||
  - cos(h_k, h_{k-1})
  - KL(p_k || p_4)
  - whether argmax p_k equals argmax p_4
- Characterize early-converging tokens by position, token type (punctuation, digits, words, code syntax, reasoning vs answer span) and task.
- Compare with MoR's routing observations (Bae et al. 2025).
- This is a counterfactual "all tokens exit at k" analysis. Say so in the report.

**3b. Zero-training exit (Geiping-style).**
- Rule: during generation, for each token stop looping when KL(p_k || p_{k-1}) < epsilon, with a cap of 4 loops.
- Sweep epsilon over at least 6 values.
- Plot accuracy vs mean loops per token against the fixed-loop baselines (loops 1 to 4) on MATH-500 slim + GPQA, at least 3 seeds.

**3c. Learned exit probe.**
- Freeze Dory. Label = 1 if KL(p_k || p_4) < epsilon.
- Train a linear probe and a small MLP probe (1 hidden layer) on h_k, using an 80/20 train/test split of a prompt set disjoint from all eval sets (for example a MATH train split plus general chat prompts).
- Report probe AUC on held-out prompts, then downstream accuracy vs mean loops on the 3b eval sets.
- **Counts as positive only if it beats 3b**: higher accuracy at matched mean loops, with the paired-difference CI excluding 0.

**KV under early exit.** For tokens that exit at loop k < 4, later tokens attending in deeper loops lack that token's deeper-loop K/V. Compare:
- (i) cache the exit-loop KV for that token in last_loop-style storage (deeper loops read it)
- (ii) recompute the missing loops for that token when a later token needs them

Report accuracy and real cost (layer-passes including recompute) for both.

**3d. Self-speculative decoding.**
- Draft with loop 1, verify with loop 4, same weights. Draft length gamma in {2, 4, 8}.
- Report the acceptance rate per task and the theoretical speedup using the standard formula (Leviathan et al. 2023): `(1 - a^(g+1)) / ((1 - a)(g*c + 1))`, with c = draft/verify cost ratio.
- Note that the verifier's first loop is the draft's computation (same Input block and first loop), so it can be reused, as in LayerSkip. Report c with and without reuse.
- Report measured wall-clock only if implemented efficiently; otherwise say "theoretical only".

**GATE.** Pareto plots (accuracy vs mean loops and vs compute) for 3b and 3c against fixed loops, with 95% CIs, plus a 3a summary figure. All pushed.

---

## Leg 4: Agent harness, task bank, dev baseline

**Goal.** A minimal, reliable coding-agent harness against the local vLLM endpoint, a frozen synthetic dev bank for Leg 5, and a baseline at loops 1, 2 and 4.

**Task sources.** Read `HOLDOUT_PROTOCOL.md` and `tasks/README.md` first. Three sets:
- **Synthetic dev bank:** the agent builds it. This is the main dev set.
- **Real dev:** SWE-bench Verified tasks in the dev bucket of `scripts/split.py`.
- **Real holdout:** never touched until Leg 5.

**4a. Harness.**
- Minimal tools: `bash`, `read_file`, `edit_file` (string replace), `submit`.
- Calls the vLLM OpenAI endpoint with `--reasoning-parser nemotron_v3 --tool-call-parser qwen3_coder --enable-auto-tool-choice` and `extra_body={"chat_template_kwargs": {"force_nonempty_content": True}}`.
- Code in `src/harness/`.
- Reference baseline: mini-SWE-agent (https://github.com/SWE-agent/mini-swe-agent), pinned, run against the same endpoint.
- **Sandbox (fence):** model-written commands run only inside a per-task Docker container: `--network none`, CPU and memory limits, non-root, only the task working copy mounted. Install dependencies at image build time (network allowed then), never at run time.

**4b. Synthetic dev bank.** Build per `tasks/README.md`:
- pilot of 20 tasks, then the bank of about 150
- tune/check split
- validation
- commit and push `runs/leg4/BANK_FREEZE.md` **before any harness-iteration run**

Report the bank's method mix, repo mix and baseline difficulty spread.

**4c. Real dev sanity check.**
- SWE-bench prebuilt images are x86_64 and arm64 support is experimental, so first test native arm64 builds on 3 real dev tasks and measure disk per image.
- Emulation (qemu/binfmt) needs sudo, so it's out.
- Then run a fixed-seed sample of about 30 buildable real dev tasks. Remove each image after its run to stay under the disk budget.
- Card anchors: SWE-bench Verified 50.3 / 59.5 / 61.8 at loops 1 / 2 / 4 with NVIDIA's harness. Ours will differ. Note the gap, don't chase it.
- Unbuildable tasks are listed and excluded.

**Matrix.** Loops {1, 2, 4}, KV per_loop.
- On the bank's tune set: all tasks, 1 seed, plus 3 seeds on a 20-task subset to estimate variance.
- On real dev: the 30-task sample at loops {1, 2, 4}.
- Choose the loop count for Leg 5 in the Leg 4 report (likely 2, the card's default).

**Metrics.** Resolve rate with CI, tool-call parse failure rate, steps per task, tokens per task, compute per task, wall-clock per task. Also the correlation between bank and real-dev resolve rates across loop counts (does the bank rank settings the same way as real tasks?).

**GATE.** Bank frozen and pushed, tool-call parse failure rate under 3% at every loop count, sandbox verified (show that a test command trying network access fails inside the container).

---

## Leg 5: Claude improves the harness, sealed holdout

**Goal.** You (the executing agent) improve Dory's harness using dev tasks only, then test once on real tasks you never touched.

**Steps.**
1. **Iterate on `tune` only.** Each harness change is a commit plus a run on the bank's tune set (or a fixed subset). Log every candidate as a run, including failures. Fair game: prompts, tool design, output parsing and retries, context management, step limits, loop count, KV mode. Changes that read task-specific information (hard-coding repo facts, peeking at fix patches) are not allowed.
2. **Select on `check`.** Pick the final candidate by its `check` score vs baseline, using at most 3 candidate evaluations on `check`, and record all of them. A real-dev sample may be used as a secondary signal.
3. **Freeze.** Commit the candidate. Write and push `runs/leg5/FREEZE.md` (HOLDOUT_PROTOCOL.md rule 3).
4. **Unseal.** Run `scripts/split.py unseal` and post on the status issue. Run the build check on holdout tasks without reading them.
5. **Holdout runs.** Baseline and candidate on all buildable holdout tasks, **once each**, in the order given in FREEZE.md. Project the runtime first and post it on the status issue. This leg may take most of a day.
6. **Record.** Results verbatim in `runs/leg5/`.
7. **Blind review.** Spawn a fresh subagent that has not seen development. Give it only:
   - FREEZE.md
   - the two holdout results.jsonl files and summaries
   - the tune/check score history table
   - CLAIMS.md

   Ask it to recommend promote or reject, with reasons. Save its output verbatim as `runs/leg5/REVIEW.md`.

**Metrics.**
- Paired resolve-rate difference (candidate minus baseline) with 95% CI.
- Parse failures, cost per task.
- Also the tune-to-check-to-holdout drop: how much of the dev gain survived. This is a finding in itself.

**GATE.** Holdout results recorded verbatim, no reruns, review saved.

---

## Leg 6: Write-up

Write `runs/FINAL_REPORT.md`:
- **What holds up:** each claim from CLAIMS.md with a confidence level (high / medium / low), effect size + CI, and run IDs.
- **Novelty assessment, candid:** for each finding, the closest prior work from REFERENCES.md (and anything found in the literature check), and whether it is new, an extension, or a confirmation. Never claim novelty without naming the closest prior work.
- **Limitations:** single model, single machine, harness differences, excluded tasks, budget cuts, deviations from PREREG.
- **What Daniel should verify first:** the 3 to 5 results most likely to be wrong or most important, each with the exact command to reproduce.

Push. Done.
