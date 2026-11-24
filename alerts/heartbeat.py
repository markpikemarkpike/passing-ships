#!/usr/bin/env python3
"""I'm alive: one small file, pushed to a branch called heartbeat in your private archive.

Runs on the frame every 3 hours (heartbeat.timer). alerts/watch.yml, on GitHub's own
computers, reads it and opens an issue when it goes stale, so a power cut at the house is
noticed by something that is not at the house. One commit, replaced each time: the branch
never grows. It carries times and the radio's self-test; no keys, no addresses."""
import datetime, json, os, re, subprocess, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (HERE, os.path.dirname(HERE)):
    if os.path.exists(os.path.join(p, "curator.py")):
        sys.path.insert(0, p)
REPO = os.environ.get("ARCHIVE_REPO_DIR", os.path.expanduser("~/archive-repo"))
REMOTE = os.environ.get("ARCHIVE_REMOTE", "")
KEY = os.environ.get("ARCHIVE_KEY", os.path.expanduser("~/.ssh/id_archive"))
HOSTS = os.environ.get("ARCHIVE_HOSTS", os.path.expanduser("~/.ssh/known_hosts_github"))


def status(now):
    import curator
    st = curator.load_state()
    out = {"at": now.astimezone().isoformat(timespec="seconds"), "painted_last": st.get("since"),
           "ran_last": st.get("last_run_at"), "radio": {"reachable": False}}
    try:
        out["radio"] = {"reachable": True, "ships": len(curator.read_feed())}
        h = curator.read_health()
        out["radio"].update(verdict=h.get("verdict", ""), silent_h=h.get("silent_h"))
    except Exception:
        pass
    return out


def git(*a, **k):
    return subprocess.run(["git", "-C", REPO, *a], check=True, capture_output=True, text=True, timeout=120, **k).stdout.strip()


def push(text):
    blob = git("hash-object", "-w", "--stdin", input=text)
    tree = git("mktree", input="100644 blob %s\tstatus.json\n" % blob)
    env = dict(os.environ, GIT_AUTHOR_NAME="the frame", GIT_AUTHOR_EMAIL="frame@passing-ships.invalid",
               GIT_COMMITTER_NAME="the frame", GIT_COMMITTER_EMAIL="frame@passing-ships.invalid",
               GIT_SSH_COMMAND="ssh -i %s -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=20 "
                               "-o UserKnownHostsFile=%s -o StrictHostKeyChecking=yes" % (KEY, HOSTS))
    sha = git("commit-tree", tree, "-m", "alive", env=env)
    git("push", "-q", "--force", REMOTE or "origin", sha + ":refs/heads/heartbeat", env=env)
    return sha


if __name__ == "__main__":
    s = json.dumps(status(datetime.datetime.now()), indent=1)
    print(s)
    if "--dry-run" not in sys.argv:
        print("heartbeat", push(s)[:10])
