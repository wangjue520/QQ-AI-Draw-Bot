# -*- coding: utf-8 -*-
"""等 NapCat 起来后：自动登录小号（免扫码）+ 自动配置反向 WS（ws://127.0.0.1:8080）。"""
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
WS_URL = "ws://127.0.0.1:8080"


def post(ep, payload, cred=None, timeout=60):
    headers = {"Content-Type": "application/json"}
    if cred:
        headers["Authorization"] = f"Bearer {cred}"
    req = urllib.request.Request(
        f"http://127.0.0.1:6099/api/{ep}",
        data=json.dumps(payload).encode(),
        headers=headers, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def wait_login(cred, tries=15, interval=4):
    """SetQuickLogin 成功后账号还要几秒才真正上线，轮询等待"""
    for _ in range(tries):
        try:
            if post("QQLogin/CheckLoginStatus", {}, cred)["data"].get("isLogin"):
                return True
        except Exception:
            pass
        time.sleep(interval)
    return False


def ensure_ob11_ws(cred):
    """确保 NapCat 网络配置里有指向机器人的反向 WS；已存在则跳过。"""
    try:
        cfg = post("OB11Config/GetConfig", {}, cred)["data"]
        net = cfg.setdefault("network", {})
        clients = net.get("websocketClients") or []
        if any(c.get("url") == WS_URL for c in clients):
            print(f"反向 WS 已存在：{WS_URL}")
            return
        clients.append({
            "name": "qq-anima-bot",
            "url": WS_URL,
            "messagePostFormat": "array",
            "reportSelfMessage": False,
            "reconnectInterval": 5000,
            "token": "",
            "debug": False,
            "heartInterval": 30000,
            "enable": True,
        })
        net["websocketClients"] = clients
        r = post("OB11Config/SetConfig", {"config": json.dumps(cfg, ensure_ascii=False)}, cred)
        print("已自动配置反向 WS：", WS_URL, r.get("message", ""))
    except Exception as e:
        print(f"自动配置反向 WS 失败（可手动在 NapCat 控制台-网络配置添加 {WS_URL}）：{e}")


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
        ensure_ob11_ws(cred)
        print("NapCat 已在线")
        return 0
    for attempt in range(3):
        try:
            r = post("QQLogin/SetQuickLogin", {"uin": UIN}, cred, timeout=60)
            print("SetQuickLogin:", r.get("message"))
            if r.get("code") == 0:
                if wait_login(cred):
                    ensure_ob11_ws(cred)
                return 0
        except Exception as e:
            print(f"SetQuickLogin 第 {attempt + 1} 次失败：{e}")
        time.sleep(10)
    return 1


if __name__ == "__main__":
    sys.exit(main())
