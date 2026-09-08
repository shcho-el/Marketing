# -*- coding: utf-8 -*-
"""
지금 돌고 있는 코드가 어느 시점 것인지 화면에 밝힌다.

바로가기로 앱을 열면 코드가 낡았는지 알 방법이 없다. 새로 만든 기능이
화면에 없으면 "구현이 안 됐다"로 보이지, "내 PC 코드가 옛날 것"으로는
보이지 않는다. 그래서 버전을 상단에 띄우고, 받아 둔 최신본보다 뒤처져
있으면 몇 개 뒤처졌는지 함께 알린다.

네트워크는 쓰지 않는다. 마지막으로 받아 둔 원격 참조와만 비교하므로
값이 바로 나온다. 실제로 새것을 받아오는 일은 update.bat / launch.bat 몫이다.
"""

import os
import subprocess

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_cache = None


def _git(*args):
    try:
        out = subprocess.run(
            ("git",) + args,
            cwd=_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def stamp(refresh: bool = False) -> dict:
    """{commit, date, branch, behind, ok} — git이 없으면 ok=False."""
    global _cache
    if _cache is not None and not refresh:
        return _cache

    commit = _git("rev-parse", "--short", "HEAD")
    if not commit:
        _cache = {"ok": False, "commit": "", "date": "", "branch": "", "behind": 0}
        return _cache

    date = _git("log", "-1", "--format=%cd", "--date=format:%m월 %d일 %H:%M")
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")

    behind = 0
    if branch and branch != "HEAD":
        # 원격 참조가 없으면(한 번도 fetch 안 함) 비교하지 않는다.
        if _git("rev-parse", "--verify", "--quiet", f"origin/{branch}"):
            count = _git("rev-list", "--count", f"HEAD..origin/{branch}")
            if count.isdigit():
                behind = int(count)

    _cache = {
        "ok": True,
        "commit": commit,
        "date": date,
        "branch": branch,
        "behind": behind,
    }
    return _cache
