"""inkling: a Claude Code status line with session cost, context size, and monthly spend.

The session, model, and context figures come from Claude Code on stdin. The monthly
figure comes from Anthropic's usage endpoint (the one the desktop app uses), cached
and refreshed in a detached child at most every REFRESH seconds so the status line
never waits. Accounts without usage-based spend (or without a claude.ai login) just
don't get the month segment.

Pass --color to show the model, effort, session cost, and the two percentages in green.

Context drops of DROP_FRACTION or more in the same iTerm pane are shown as
"was N" for SHOW_DROP seconds and appended to drops.log, tagged "same session"
(/compact) or "new session" (/clear, resume, a fresh start).
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

CACHE_DIR = os.path.expanduser("~/.cache/inkling")
CACHE = os.path.join(CACHE_DIR, "spend.json")
ATTEMPT = os.path.join(CACHE_DIR, "last-attempt")
DROPS_LOG = os.path.join(CACHE_DIR, "drops.log")
REFRESH = 300
STALE = 1800
DROP_FRACTION = 0.2
SHOW_DROP = 900
COLOR = "--color" in sys.argv


def save_spend(spend):
    tmp = CACHE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(spend, f)
    os.replace(tmp, CACHE)


def refresh():
    raw = subprocess.run(
        ["/usr/bin/security", "find-generic-password", "-s", "Claude Code-credentials", "-w"],
        capture_output=True, text=True, timeout=10,
    ).stdout
    try:
        token = json.loads(raw)["claudeAiOauth"]["accessToken"]
    except (ValueError, KeyError, TypeError):
        save_spend(None)
        return
    req = urllib.request.Request(
        "https://api.anthropic.com/api/oauth/usage",
        headers={"Authorization": "Bearer " + token, "anthropic-beta": "oauth-2025-04-20"},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        save_spend(json.load(r).get("spend"))


def maybe_spawn_refresh():
    try:
        if time.time() - os.path.getmtime(ATTEMPT) < REFRESH:
            return
    except OSError:
        pass
    open(ATTEMPT, "w").close()
    subprocess.Popen(
        [sys.executable, "-I", os.path.abspath(__file__), "--refresh"],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def green(s):
    """Wrap a value in ANSI green when --color is given."""
    return f"\033[32m{s}\033[0m" if COLOR else s


def money(m, cents=False):
    v = m["amount_minor"] / 10 ** m.get("exponent", 2)
    return f"${v:,.2f}" if cents else f"${v:,.0f}"


def tokens(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.3g}M"
    if n >= 1000:
        return f"{n / 1000:.0f}k"
    return str(n)


def context_text(data):
    cw = data.get("context_window") or {}
    used = cw.get("total_input_tokens") or 0
    size = cw.get("context_window_size")
    if not cw.get("current_usage") or not used:
        return "ctx …"
    pct = cw.get("used_percentage")
    if pct is None and size:
        pct = round(100 * used / size)
    text = f"ctx {tokens(used)}"
    if size:
        text += f" of {tokens(size)} ({green(f'{pct}%')})"
    was = track_drop(data.get("session_id"), used)
    if was:
        text += f", was {tokens(was)}"
    return text


def track_drop(session_id, used):
    """Remember this pane's context; return the pre-drop size while a recent drop is shown."""
    pane = os.environ.get("ITERM_SESSION_ID") or session_id or "unknown"
    state_path = os.path.join(CACHE_DIR, "pane-" + re.sub(r"[^A-Za-z0-9_.-]", "_", pane) + ".json")
    try:
        with open(state_path) as f:
            state = json.load(f)
    except (OSError, ValueError):
        state = {}
    now = time.time()
    prev = state.get("used")
    if prev and used <= prev * (1 - DROP_FRACTION):
        kind = "same session" if state.get("session_id") == session_id else "new session"
        state["drop"] = {"from": prev, "at": now}
        with open(DROPS_LOG, "a") as f:
            f.write(f"{time.strftime('%Y-%m-%d %-I:%M %p')} {tokens(prev)} -> {tokens(used)} "
                    f"({kind}) session {session_id}\n")
    state.update(used=used, session_id=session_id)
    tmp = state_path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f)
    os.replace(tmp, state_path)
    drop = state.get("drop")
    if drop and now - drop["at"] < SHOW_DROP:
        return drop["from"]
    return None


def session_name(session_id):
    """The peer name Claude Code gives this session (e.g. alice-42), from ~/.claude/sessions."""
    sessions = os.path.expanduser("~/.claude/sessions")
    try:
        names = [n for n in os.listdir(sessions) if re.fullmatch(r"\d+\.json", n)]
    except OSError:
        return None
    for n in names:
        try:
            with open(os.path.join(sessions, n)) as f:
                d = json.load(f)
        except (OSError, ValueError):
            continue
        if d.get("sessionId") == session_id:
            return d.get("name")
    return None


def month_text():
    try:
        with open(CACHE) as f:
            spend = json.load(f)
        age = time.time() - os.path.getmtime(CACHE)
    except (OSError, ValueError):
        return "month …"
    if not spend or not spend.get("used"):
        return None
    text = f"month {money(spend['used'])}"
    if spend.get("limit"):
        text += f" of {money(spend['limit'])} ({green(str(spend.get('percent', 0)) + '%')})"
    if age > STALE:
        text += time.strftime(" (as of %-I:%M %p)", time.localtime(time.time() - age))
    return text


def main():
    if "--refresh" in sys.argv:
        refresh()
        return
    os.makedirs(CACHE_DIR, exist_ok=True)
    try:
        data = json.load(sys.stdin)
    except ValueError:
        data = {}
    session = (data.get("cost") or {}).get("total_cost_usd")
    parts = [f"session {green(f'${session:,.2f}')}" if session is not None else "session …"]
    model = " ".join(green(s) for s in filter(None, [(data.get("model") or {}).get("display_name"),
                                   (data.get("effort") or {}).get("level")]))
    if model:
        parts.insert(0, model)
    name = session_name(data.get("session_id"))
    if name:
        parts.insert(0, name)
    parts.append(context_text(data))
    maybe_spawn_refresh()
    month = month_text()
    if month:
        parts.append(month)
    print(" · ".join(parts))


main()
