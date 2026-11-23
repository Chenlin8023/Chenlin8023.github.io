#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把本地相对远端的变更经 GitHub Data API 推上 master（github.com:443 不通时用）。

与 tools/push_via_api.py 的区别：不写死 base/message，远端 ref 现取；
base 树与本地 commit 树必须一致（先判「假分叉」），否则拒绝推送。
推送成功后尝试在本地复刻同一个 commit，使本地与远端重新对齐。

用法：
    python tools/push_commit_api.py --diff-base 8562522 --head HEAD --message "…"
"""

import argparse
import base64
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_REPO = "Chenlin8023/Chenlin8023.github.io"
BRANCH = "master"


def git(*args, binary=False):
    out = subprocess.check_output(["git", "-C", ROOT] + list(args))
    return out if binary else out.decode("utf-8").rstrip("\n")


def token():
    return subprocess.check_output(["gh", "auth", "token"], text=True).strip()


def api(method, path, payload=None, retries=3):
    tok = token()
    data = json.dumps(payload).encode() if payload is not None else None
    last = None
    for attempt in range(1, retries + 1):
        req = urllib.request.Request("https://api.github.com" + path, data=data, method=method)
        req.add_header("Authorization", "Bearer " + tok)
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        if data:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                body = resp.read()
            return json.loads(body.decode()) if body else {}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")
            raise SystemExit("!! API %s %s -> %s: %s" % (method, path, exc.code, detail))
        except Exception as exc:  # 网络抖动重试
            last = exc
            print("   retry %d/%d after %s" % (attempt, retries, exc))
            time.sleep(2 * attempt)
    raise SystemExit("!! API %s %s failed: %s" % (method, path, last))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=DEFAULT_REPO)
    ap.add_argument("--diff-base", required=True,
                    help="本地 commit：其树必须等于远端 master 的树（假分叉时的对位点）")
    ap.add_argument("--head", default="HEAD")
    ap.add_argument("--message", default=None, help="推送用的 commit message")
    ap.add_argument("--message-from", default=None,
                    help="从本地某个 commit 取 message（避免控制台中文编码问题）")
    ap.add_argument("--no-align", action="store_true", help="只在远端提交，不动本地 ref")
    args = ap.parse_args()

    if args.message_from:
        args.message = git("log", "-1", "--pretty=%B", args.message_from)
    if not args.message:
        raise SystemExit("!! 需要 --message 或 --message-from")
    message = args.message.rstrip("\n") + "\n"

    ref = api("GET", "/repos/%s/git/ref/heads/%s" % (args.repo, BRANCH))
    base_sha = ref["object"]["sha"]
    base_tree = api("GET", "/repos/%s/git/commits/%s" % (args.repo, base_sha))["tree"]["sha"]
    local_tree = git("rev-parse", args.head + "^{tree}")
    diff_base_tree = git("rev-parse", args.diff_base + "^{tree}")
    print("remote master: %s (tree %s)" % (base_sha[:12], base_tree[:12]))
    print("local head   : %s (tree %s)" % (git("rev-parse", args.head)[:12], local_tree[:12]))
    if diff_base_tree != base_tree:
        raise SystemExit("!! 对位失败：%s 的树 %s != 远端树 %s；先 fetch 对齐再说"
                         % (args.diff_base, diff_base_tree, base_tree))
    if local_tree == base_tree:
        raise SystemExit("!! 本地 %s 与远端同树，没有要推的改动" % args.head)

    out = git("diff", "--name-status", args.diff_base, args.head)
    entries = []
    for line in out.splitlines():
        status, path = line.split("\t", 1)
        if status.startswith("D"):
            entries.append({"path": path, "mode": "100644", "type": "blob", "sha": None})
            print("  del  %s" % path)
            continue
        data = git("show", "%s:%s" % (args.head, path), binary=True)
        blob = api("POST", "/repos/%s/git/blobs" % args.repo,
                   {"content": base64.b64encode(data).decode(), "encoding": "base64"})
        mode = git("ls-tree", args.head, "--", path).split()[0]
        entries.append({"path": path, "mode": mode, "type": "blob", "sha": blob["sha"]})
        print("  %s %s %7d -> %s" % (status, path, len(data), blob["sha"][:10]))

    tree = api("POST", "/repos/%s/git/trees" % args.repo,
               {"base_tree": base_tree, "tree": entries})
    identity = {"name": "Chenlin8023", "email": "2215119421@qq.com",
                "date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    commit = api("POST", "/repos/%s/git/commits" % args.repo,
                 {"message": message, "tree": tree["sha"], "parents": [base_sha],
                  "author": identity, "committer": identity})
    new_sha = commit["sha"]
    print("new commit: %s" % new_sha)
    api("PATCH", "/repos/%s/git/refs/heads/%s" % (args.repo, BRANCH),
        {"sha": new_sha, "force": False})
    print("ref updated: %s -> %s" % (BRANCH, new_sha))

    if args.no_align:
        return
    # 本地复刻同一个 commit（树/父/身份/时间/消息一致 -> 同 sha）
    msg_path = os.path.join(ROOT, ".git", "PUSH_MSG")
    with open(msg_path, "w", encoding="utf-8", newline="\n") as fp:
        fp.write(message)
    env = dict(os.environ)
    env.update({
        "GIT_AUTHOR_NAME": identity["name"], "GIT_AUTHOR_EMAIL": identity["email"],
        "GIT_AUTHOR_DATE": identity["date"],
        "GIT_COMMITTER_NAME": identity["name"], "GIT_COMMITTER_EMAIL": identity["email"],
        "GIT_COMMITTER_DATE": identity["date"],
    })
    local_sha = subprocess.check_output(
        ["git", "-C", ROOT, "commit-tree", commit["tree"]["sha"], "-p", base_sha, "-F", msg_path],
        env=env, text=True).strip()
    os.remove(msg_path)
    print("local  replay: %s" % local_sha)
    if local_sha == new_sha:
        subprocess.check_call(["git", "-C", ROOT, "reset", "--soft", new_sha])
        subprocess.check_call(["git", "-C", ROOT, "update-ref",
                               "refs/remotes/origin/" + BRANCH, new_sha])
        print("== 本地已对齐远端（sha 一致）==")
    else:
        print("!! 本地复刻 sha 不一致，保持现状；等 443 恢复后 fetch 再对齐")


if __name__ == "__main__":
    main()
