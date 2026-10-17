# claude-inkling

A [Claude Code](https://code.claude.com/docs/en/overview) status line that gives you an inkling of what a session costs, how full its context is, and how much you've spent this month.

```
alice-42 · Opus 5.5 high · session $1.84 · ctx 117k of 1M (12%), was 312k · month $412 of $1,000 (41%)
```

It sits on the line under the Claude Code prompt and updates as you work. Cephalopods squirt ink when they want to slip away, and this one is meant to help you see when a session has gotten big enough to slip away from with `/compact` or `/clear`.

## What it shows

| Segment | Meaning | Source |
|---|---|---|
| `alice-42` | The session's name, the one other local sessions see it by. Omitted if Claude Code hasn't named it. | `~/.claude/sessions/*.json` |
| `Opus 5.5 high` | Model and effort level. Follows `/model` and `/effort`. | Claude Code (stdin) |
| `session $1.84` | This session's cost so far, as Claude Code computes it at list prices. | Claude Code (stdin) |
| `ctx 117k of 1M (12%)` | Tokens sent with each request right now (system prompt, tools, memory, conversation) and the model's context window. | Claude Code (stdin) |
| `, was 312k` | Shown for 15 minutes after context drops by 20% or more in the same terminal pane, so you can see what `/compact`, `/clear`, or resuming a handoff bought you. | inkling |
| `month $412 of $1,000 (41%)` | Your account's spend this month against its limit. Covers every machine and claude.ai, not just this one. Omitted for accounts without usage-based spend. | Anthropic usage endpoint |

Every request resends the whole context, so the `ctx` number is a decent proxy for what each reply costs. A fresh session usually starts somewhere around 30-50k tokens (instructions, tool definitions, memory), which is the floor `/clear` can get you back to.

## Install

Requires macOS, Python 3.8+, and a recent Claude Code (one that passes `context_window` and `effort` to status line commands).

```bash
git clone https://github.com/anthonyeleven/claude-inkling.git ~/git/claude-inkling
```

Then add this to `~/.claude/settings.json`, adjusting the path to `python3` if yours lives elsewhere:

```json
"statusLine": {
  "type": "command",
  "command": "python3 -I ~/git/claude-inkling/inkling.py",
  "padding": 0
}
```

Claude Code picks the change up on its own; if a running session doesn't, restart it.

## How the monthly figure works

Claude Code passes the session numbers directly. The monthly number comes from the same Anthropic endpoint the desktop app uses for its usage display (`https://api.anthropic.com/api/oauth/usage`):

- inkling reads Claude Code's own login token from the macOS keychain (`Claude Code-credentials`) each time it refreshes. The token is sent only to `api.anthropic.com` and is never written anywhere.
- It checks at most every 5 minutes, and only while a Claude Code session is drawing its status line. The check runs in a detached background process, so the status line never waits on the network.
- If checks keep failing, the last good figure stays up with its age, e.g. `(as of 9:41 AM)`.

The endpoint is not documented, so a future change on Anthropic's side could break the month segment. The rest of the line doesn't depend on it.

## Context drop log

Every drop of 20% or more is appended to `~/.cache/inkling/drops.log`:

```
2026-10-17 10:43 AM 208k -> 41k (same session) session 1c4f…
2026-10-17 2:12 PM 133k -> 36k (new session) session 9e07…
```

`same session` is a `/compact` (manual or automatic). `new session` is a `/clear`, a resume, or a fresh start in the same pane. Panes are told apart by iTerm2's `ITERM_SESSION_ID`, falling back to Claude Code's session ID in other terminals.

## Files it writes

All under `~/.cache/inkling/`: the cached monthly spend (`spend.json`), a timestamp of the last refresh attempt, one small state file per pane, and `drops.log`. Delete the directory any time.

## Uninstall

Remove the `statusLine` entry from `~/.claude/settings.json` and delete `~/.cache/inkling/`.

## See also

[hex/iTerm2-claude-status](https://github.com/hex/iTerm2-claude-status) takes the other approach: Claude Code hooks push the model and a context bar into iTerm2's own status bar instead of Claude Code's status line.

## License

MIT. See [LICENSE](LICENSE).
