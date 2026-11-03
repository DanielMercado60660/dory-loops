# Kickoff

## Daniel, before handing off

1. Done: public repo created, `main` pushed, issues limited to collaborators.
2. Create a **fine-grained token** owned by your account. GitHub only lets fine-grained tokens reach repos their creator owns, so Colin can't make this one.
   - Repository access: only `dory-loops`.
   - Permissions: Contents read/write, Issues read/write, Metadata read.
   - Expiry: about 14 days.

   Send it to Colin privately. The agent's pushes and comments will show up under your account, and the agent marks its own comments so it never mistakes them for yours.
3. Colin's login (`ColinM-sys`) is in `control.json`. Invite him as a collaborator (repo Settings, Collaborators) and have him accept, or he can't open a STOP issue.
4. Watch the repo on GitHub (Watch, then All activity) so status comments reach your email or phone.

## Colin, before pasting

1. Make a parent directory with room for 100 GB. The agent creates `dory-loops/` and `artifacts/` inside it.
2. Check Docker runs without sudo for your user: `docker run --rm hello-world`.
3. Start Claude Code in that parent directory, ideally inside a container that only mounts it. It will run for days without you, so pick a permission mode that won't sit waiting on approval prompts. That is your call: for example auto mode, or bypass permissions inside the container. Usage limits on your Claude plan also apply, and the session pauses if they are hit.
4. Export the token as `GITHUB_TOKEN` in that shell. Don't paste it into the chat. Optionally also export a read-only `HF_TOKEN` from an HF account that has accepted the GPQA dataset terms (Leg 1 needs it; otherwise the agent will ask).
5. To stop it at any time from anywhere: open an issue on the repo titled `STOP`.

## Prompt to paste

```
Clone https://github.com/DanielMercado60660/dory-loops using the GITHUB_TOKEN in my environment (fine-grained, scoped to this repo only). Read CLAUDE.md, EXPERIMENTS.md, MODEL_FACTS.md, REFERENCES.md, HOLDOUT_PROTOCOL.md and tasks/README.md fully.

I am authorizing you to treat messages returned by scripts/check_inbox.py (issues and comments on this repo by the logins in control.json, which are Daniel and me) as instructions from me, within the fences in CLAUDE.md. Nothing in those messages can lift a fence or change the holdout protocol.

First, post a short summary of the fences, gates and control channel as a comment on the "dory-loops status" issue (check_inbox.py post). Then wait for a reply from Daniel or me on that issue (check_inbox.py wait) before starting Leg 0. After that, work through the legs unattended: push to the runs branch, keep runs/STATUS.md current, stop at every gate, and use the issue channel for anything blocking. Don't end the session while there is work left or an answer pending.
```
