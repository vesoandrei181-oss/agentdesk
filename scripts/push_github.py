"""把仓库推到 GitHub：建远程仓库（若不存在）→ 设置 remote → push。

用法（token 从环境变量读，不要写进命令历史）：
    $env:GH_TOKEN = "ghp_xxx"
    python scripts/push_github.py            # 默认仓库名 agentdesk，公开
    python scripts/push_github.py --name agentdesk --private

需要的 token 权限：repo（classic）或 Contents + Administration（fine-grained）。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

API = "https://api.github.com"


def call(method: str, path: str, token: str, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        f"{API}{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "agentdesk-push",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    r = subprocess.run(["git", *args], text=True, capture_output=True, encoding="utf-8")
    if check and r.returncode != 0:
        print(r.stdout)
        print(r.stderr)
        raise SystemExit(f"git {' '.join(args)} 失败")
    return r


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="agentdesk")
    ap.add_argument("--private", action="store_true", help="建私有仓库（评审核需要访问权限时反而麻烦）")
    ap.add_argument("--description", default="智协台 AgentDesk：把一场会开成能追踪的决议、待办和可引用的知识")
    args = ap.parse_args()

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("缺少 GH_TOKEN 环境变量")
        return 2

    status, me = call("GET", "/user", token)
    if status != 200:
        print(f"token 无效：{status} {me}")
        return 2
    login = me["login"]
    print(f"账号：{login}")

    status, repo = call("GET", f"/repos/{login}/{args.name}", token)
    if status == 200:
        print(f"仓库已存在：{repo['html_url']}")
        full = repo["full_name"]
    else:
        status, repo = call(
            "POST", "/user/repos", token,
            {
                "name": args.name,
                "description": args.description,
                "private": args.private,
                "has_issues": True,
                "has_wiki": False,
                "auto_init": False,
            },
        )
        if status not in (201, 200):
            print(f"建仓失败：{status} {repo}")
            return 1
        full = repo["full_name"]
        print(f"已创建：{repo['html_url']}")

    remote = f"https://{login}:{token}@github.com/{full}.git"
    git("remote", "remove", "origin", check=False)
    git("remote", "add", "origin", remote)
    git("push", "-u", "origin", "main")
    # 推完把带 token 的 remote 换回干净地址，免得留在 .git/config 里
    git("remote", "set-url", "origin", f"https://github.com/{full}.git")
    print(f"完成：https://github.com/{full}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
