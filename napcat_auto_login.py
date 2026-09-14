# -*- coding: utf-8 -*-
"""等 NapCat 起来后，用 webui.json 里配置的 autoLoginAccount 快速登录。"""
import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
CFG = json.loads((BASE / "NapCat" / "Shell" / "config" / "webui.json").read_text(encoding="utf-8"))
UIN = str(CFG.get("autoLoginAccount", "")).strip()
TOKEN = CFG["token"]
HASH = hashlib.sha256((TOKEN + ".napcat").encode()).hexdigest()


def post(ep, payload, cred=None, timeout=60):
    headers = {"Content-Type": "application/json"}
    if cred:
        headers["Authorization"] = f"Bearer {cred}"
    req = urllib.request.Request(
        f"http://127.0.0.1:6099/api/{ep}",
        data=json.dumps(payload).encode(),
        headers=headers, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def main():
    if not UIN:
        print("未配置 autoLoginAccount，跳过自动登录")
        return 0
    cred = None
    for _ in range(40):          # 最多等 ~3 分钟
        try:
            r = post("auth/login", {"hash": HASH, "totpCode": ""})
            cred = r["data"]["Credential"]
            break
        except Exception:
            time.sleep(4)
    if not cred:
        print("NapCat WebUI 未就绪")
        return 1
    st = post("QQLogin/CheckLoginStatus", {}, cred)["data"]
    if st.get("isLogin"):
        print("NapCat 已在线")
        return 0
    for attempt in range(3):
        try:
            r = post("QQLogin/SetQuickLogin", {"uin": UIN}, cred, timeout=60)
            print("SetQuickLogin:", r.get("message"))
            if r.get("code") == 0:
                return 0
        except Exception as e:
            print(f"SetQuickLogin 第 {attempt + 1} 次失败：{e}")
        time.sleep(10)
    return 1


if __name__ == "__main__":
    sys.exit(main())
