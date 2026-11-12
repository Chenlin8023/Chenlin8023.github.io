# -*- coding: utf-8 -*-
"""通过 GitHub REST API 提交本地 commit（github.com:443 被封锁时的绕行）。"""
import base64
import json
import subprocess
import sys
import urllib.request

REPO = "Chenlin8023/Chenlin8023.github.io"
BASE = "3827842"  # 仅用于本地 diff（远端 base 由 API 实时读取）          # 远端当前 master
ROOT = r"D:/WorkBudy/iOS-Tweaks/root-site"
MSG = "repo: MUtool 2.2.80-12（修复悬浮窗位置漂移与双行渲染，用户实机确认）"


def api(method, path, payload=None):
    token = subprocess.check_output(["gh", "auth", "token"], text=True).strip()
    url = "https://api.github.com" + path
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())


def main():
    # 远端当前 ref
    ref = api("GET", f"/repos/{REPO}/git/ref/heads/master")
    base_sha = ref["object"]["sha"]
    print("remote master:", base_sha)
    base_commit = api("GET", f"/repos/{REPO}/git/commits/{base_sha}")
    base_tree = base_commit["tree"]["sha"]
    print("base tree:", base_tree)

    # 本地相对 base 的变更
    out = subprocess.check_output(
        ["git", "-C", ROOT, "diff", "--name-status", BASE, "HEAD"], text=True)
    changes = []
    for line in out.splitlines():
        st, path = line.split("\t", 1)
        changes.append((st, path))
    print("changed:", changes)

    entries = []
    for st, path in changes:
        if st == "D":
            entries.append({"path": path, "mode": "100644", "type": "blob", "sha": None})
            continue
        full = ROOT + "/" + path
        data = open(full, "rb").read()
        b64 = base64.b64encode(data).decode()
        blob = api("POST", f"/repos/{REPO}/git/blobs",
                   {"content": b64, "encoding": "base64"})
        entries.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        print("blob", path, blob["sha"][:12], len(data))

    tree = api("POST", f"/repos/{REPO}/git/trees",
               {"base_tree": base_tree, "tree": entries})
    commit = api("POST", f"/repos/{REPO}/git/commits",
                 {"message": MSG, "tree": tree["sha"], "parents": [base_sha]})
    print("new commit:", commit["sha"])

    api("PATCH", f"/repos/{REPO}/git/refs/heads/master",
        {"sha": commit["sha"], "force": False})
    print("ref updated ->", commit["sha"])


if __name__ == "__main__":
    main()
