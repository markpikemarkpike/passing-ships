#!/usr/bin/env python3
"""Read the heartbeat, decide what is wrong, and say so once. Runs on GitHub (watch.yml).

One issue per trouble, opened when it starts and closed, with a comment, when it ends.
GitHub mails you about both; its phone app will push them. Nothing here touches the house."""
import datetime, json, os, subprocess, sys

STALE_H = 7                      # two missed heartbeats and a bit
TROUBLES = {"frame": "Passing Ships: the frame has gone silent",
            "radio": "Passing Ships: the frame cannot reach the radio",
            "board": "Passing Ships: the radio's receiver is not answering",
            "antenna": "Passing Ships: the radio has heard nothing for a long time",
            "paint": "Passing Ships: the frame is on but the painter has stopped"}


def when(s):
    try:
        t = datetime.datetime.fromisoformat(s)
        return t if t.tzinfo else None
    except (TypeError, ValueError):
        return None


def wrong(st, now):
    """{trouble: sentence}. A frame that is off can say nothing about the radio."""
    t = when(st.get("at")) if isinstance(st, dict) else None
    if t is None:
        return {"frame": "There is no readable heartbeat."}
    age = (now - t).total_seconds() / 3600.0
    if age > STALE_H:
        return {"frame": "Last heard from it %s, %.0f hours ago. Is it plugged in? Is the wifi up?"
                         % (t.strftime("%a %-d %b at %-I:%M %p"), age)}
    out, r = {}, st.get("radio") if isinstance(st.get("radio"), dict) else {}
    if not r.get("reachable"):
        out["radio"] = "The frame is fine, but the radio Pi does not answer. Check its plug and the wifi."
    elif r.get("verdict") == "FAULT":
        out["board"] = "The radio Pi is on, but the receiver board did not answer after a restart. Reseat the board."
    elif r.get("verdict") == "DEAF":
        out["antenna"] = ("Nothing heard in %s hours, longer than any quiet spell lately, and a restart did not help. "
                          "Check the antenna and the coax." % r.get("silent_h"))
    ran = st.get("ran_last")
    try:
        gap = (t.replace(tzinfo=None) - datetime.datetime.fromisoformat(ran)).total_seconds() / 3600.0
        if gap > 3:
            out["paint"] = "The hourly painter last ran %.0f hours before the last heartbeat." % gap
    except (TypeError, ValueError):
        pass
    return out


def plan(bad, open_issues):
    """[('open', key, text)] and [('close', key, number)] from what is wrong and what is already said."""
    do = [("open", k, v) for k, v in bad.items() if k not in open_issues]
    # a silent frame says nothing about the others: leave those open until it speaks
    if "frame" not in bad:
        do += [("close", k, n) for k, n in open_issues.items() if k not in bad]
    return do


def gh(*a):
    return subprocess.run(["gh", *a], check=True, capture_output=True, text=True).stdout


def main():
    try:
        st = json.load(open(sys.argv[1]))
    except Exception:
        st = None
    titles = {v: k for k, v in TROUBLES.items()}
    found = json.loads(gh("issue", "list", "--state", "open", "--limit", "100", "--json", "number,title"))
    have = {titles[i["title"]]: i["number"] for i in found if i["title"] in titles}
    for what, key, x in plan(wrong(st, datetime.datetime.now(datetime.timezone.utc)), have):
        if what == "open":
            print(gh("issue", "create", "--title", TROUBLES[key], "--body", x, "--assignee", os.environ["OWNER"]))
        else:
            gh("issue", "close", str(x), "--comment", "Back to normal.")
            print("closed", key)


if __name__ == "__main__":
    main()
