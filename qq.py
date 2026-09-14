# -*- coding: utf-8 -*-
"""QQ 接入层：NapCat (OneBot 11 反向 WebSocket)"""

import asyncio
import json
import re
import time

import websockets

import core

HELP_TEXT = (
    "【跑图姬使用说明】\n"
    "@我 画 画面描述 —— AI自动优化提示词后跑图\n"
    "@我 画 厚涂 横 一个少女 —— 画风(可省) + 构图随意组合\n"
    "@我 画 1000x1400 描述 —— 精准分辨率，直接生效\n"
    "@我 画 1080p 描述（480p~4k都行）—— 模糊分辨率，AI自动换算\n"
    "@我 生图 英文tag —— 不优化，直接按你写的tag跑\n"
    "@我 再来 —— 用上一条提示词重roll一张\n"
    "@我 画风 —— 查看可用画风列表\n"
    "@我 帮助 —— 本说明\n"
    "示例：@我 画 厚涂 横 1080p 一个在雨中撑伞的少女"
)

SIZES = {
    "横": (1344, 768), "横图": (1344, 768),
    "竖": (768, 1344), "竖图": (768, 1344),
    "方": (1024, 1024), "方图": (1024, 1024),
}

# 精准分辨率：出现在任意位置都直接解析，不调大模型
SIZE_ANYWHERE_RE = re.compile(r"(\d{3,4})\s*[x×*]\s*(\d{3,4})")
# 模糊分辨率：交给大模型判断
FUZZY_SIZE_TOKENS = ("1080p", "1440p", "900p", "720p", "540p", "480p", "2k", "4k")


def _clean(text):
    return re.sub(r"\s+", " ", text).strip()


def extract_size_anywhere(text):
    m = SIZE_ANYWHERE_RE.search(text)
    if not m:
        return None, text
    w = max(512, min(1536, int(m.group(1))))
    h = max(512, min(1536, int(m.group(2))))
    return (w, h), _clean(text[:m.start()] + " " + text[m.end():])


def extract_fuzzy_size(text):
    for tok in FUZZY_SIZE_TOKENS:
        m = re.search(r"(?<![a-z0-9])" + re.escape(tok) + r"(?![a-z0-9])", text, re.I)
        if m:
            return tok.lower(), _clean(text[:m.start()] + " " + text[m.end():])
    return None, text

LAST_JOB = {}    # user_id -> 上次跑图数据（重roll用）
LAST_TIME = {}   # user_id -> 冷却计时


# ========== 指令解析 ==========

def strip_prefix(text, keywords):
    for kw in keywords:
        if text == kw:
            return ""
        if text.startswith(kw):
            rest = text[len(kw):]
            if rest[:1] in (" ", "　", ",", "，", ":", "："):
                return rest[1:].strip()
    return None


def parse_command(text):
    t = text.strip().lstrip("/").strip()
    if not t:
        return {"cmd": "help"}
    if t in ("帮助", "help", "菜单", "功能"):
        return {"cmd": "help"}
    if t in ("画风", "风格", "styles", "style"):
        return {"cmd": "styles"}
    rest = strip_prefix(t, ("再来一张", "再画一张", "再来", "重roll", "reroll"))
    if rest is not None:
        return {"cmd": "reroll"}
    for kws, mode in ((("生图", "原tag", "raw"), "raw"), (("画", "draw", "绘图"), "draw")):
        rest = strip_prefix(t, kws)
        if rest is not None:
            if not rest:
                return {"cmd": "help"}
            style, rest = match_style(rest)
            size, rest = match_size(rest)
            style2, rest = match_style(rest)
            if style2:
                style = style2
            if size is None:
                size, rest = extract_size_anywhere(rest)
            hint, rest = extract_fuzzy_size(rest)
            if size is None:
                size, rest = match_size(rest)
            if not rest:
                return {"cmd": "help"}
            return {"cmd": "draw", "mode": mode, "style": style, "size": size,
                    "size_hint": hint if size is None else None, "content": rest}
    if t.startswith("画") and len(t) > 1 and t[:2] != "画风":
        content = t[1:].strip()
        size, content = extract_size_anywhere(content)
        hint, content = extract_fuzzy_size(content)
        if size is None:
            size, content = match_size(content)
        return {"cmd": "draw", "mode": "draw", "style": None, "size": size,
                "size_hint": hint if size is None else None, "content": content}
    return {"cmd": "unknown"}


def match_style(rest):
    presets = core.load_presets()
    for name in sorted(presets.keys(), key=len, reverse=True):
        if rest.startswith(name):
            tail = rest[len(name):]
            if not tail:
                return name, ""
            if tail[:1] in (" ", "　", ",", "，"):
                return name, tail[1:].strip()
    return None, rest


def match_size(rest):
    for kw in sorted(SIZES.keys(), key=len, reverse=True):
        if rest.startswith(kw):
            tail = rest[len(kw):]
            if tail[:1] in (" ", "　", ",", "，"):
                return SIZES[kw], tail[1:].strip()
    m = re.match(r"^(\d{3,4})\s*[x×*]\s*(\d{3,4})[\s，,]+", rest)
    if m:
        w = max(512, min(1536, int(m.group(1))))
        h = max(512, min(1536, int(m.group(2))))
        return (w, h), rest[m.end():].strip()
    return None, rest


def extract_text_and_at(message, self_id):
    if isinstance(message, str):
        at_me = bool(self_id) and f"[CQ:at,qq={self_id}]" in message
        text = re.sub(r"\[CQ:[^\]]+\]", " ", message)
        return text.strip(), at_me
    text_parts, at_me = [], False
    for seg in message if isinstance(message, list) else []:
        stype, data = seg.get("type"), seg.get("data", {})
        if stype == "at" and str(data.get("qq")) == str(self_id):
            at_me = True
        elif stype == "text":
            text_parts.append(data.get("text", ""))
    return "".join(text_parts).strip(), at_me


# ========== OneBot 收发 ==========

async def call_api(ws, action, params):
    await ws.send(json.dumps({"action": action, "params": params, "echo": str(time.time())}))


async def send_msg(ws, msg_type, target, segments):
    if msg_type == "group":
        await call_api(ws, "send_group_msg", {"group_id": target, "message": segments})
    else:
        await call_api(ws, "send_private_msg", {"user_id": target, "message": segments})


def check_auth(ws):
    token = core.CFG["onebot"].get("access_token", "").strip()
    if not token:
        return True
    req = getattr(ws, "request", None)
    if req is not None:
        path, headers = req.path, req.headers
    else:
        path = getattr(ws, "path", "") or ""
        headers = getattr(ws, "request_headers", {}) or {}
    if f"access_token={token}" in path:
        return True
    try:
        return headers.get("Authorization", "") == f"Bearer {token}"
    except AttributeError:
        return False


async def on_message(ws, evt):
    self_id = evt.get("self_id")
    msg_type = evt.get("message_type")
    if msg_type not in ("group", "private"):
        return
    text, at_me = extract_text_and_at(evt.get("message"), self_id)
    if msg_type == "group" and not at_me:
        return
    if not text:
        return

    cmd = parse_command(text)
    user_id = evt.get("user_id")
    target = evt.get("group_id") if msg_type == "group" else user_id

    async def reply(text_, at=True):
        segs = []
        if msg_type == "group" and at:
            segs.append({"type": "at", "data": {"qq": str(user_id)}})
        segs.append({"type": "text", "data": {"text": text_}})
        await send_msg(ws, msg_type, target, segs)

    if cmd["cmd"] == "help":
        await reply(HELP_TEXT)
        return
    if cmd["cmd"] == "styles":
        presets = core.load_presets()
        lines = ["【可用画风】"] + [f"· {n}：{p.get('description', '')}" for n, p in presets.items()]
        lines.append("用法：@我 画 画风名 画面描述")
        await reply("\n".join(lines))
        return
    if cmd["cmd"] == "unknown":
        await reply("没看懂指令，@我 帮助 查看用法")
        return

    cooldown = float(core.CFG["bot"].get("cooldown_seconds", 3))
    now = time.time()
    if now - LAST_TIME.get(user_id, 0) < cooldown:
        await reply(f"太快了，{int(cooldown)} 秒内只能发一次任务")
        return
    LAST_TIME[user_id] = now

    job = {
        "source": "qq",
        "user_name": str(user_id),
        "time": time.strftime("%H:%M:%S"),
        "style": cmd.get("style") or core.CFG["bot"].get("default_style", "默认"),
        "size": cmd.get("size"),
        "content": cmd.get("content", ""),
        "mode": cmd.get("mode", "draw"),
    }

    if cmd["cmd"] == "reroll":
        last = LAST_JOB.get(user_id)
        if not last:
            await reply("你还没有跑过图，先@我 画 一张吧")
            return
        job["mode"] = "reroll"
        job["reroll_data"] = last

    async def notify_text(t):
        await reply(t, at=False)

    async def notify_image(b64, _fname):
        await send_msg(ws, msg_type, target, [{"type": "image", "data": {"file": f"base64://{b64}"}}])

    job["notify"] = notify_text
    job["notify_image"] = notify_image

    n = await core.enqueue(job)
    if n > 1:
        await reply(f"已加入队列，前面还有 {n - 1} 个任务", at=False)
    # 记录供重roll（完成时由 run_job 填充 core）
    orig_run = job

    async def _remember():
        while orig_run.get("state") not in ("done", "failed"):
            await asyncio.sleep(0.5)
        if orig_run.get("state") == "done":
            LAST_JOB[user_id] = {
                "core": orig_run.get("core", ""),
                "style": orig_run.get("style"),
                "size": orig_run.get("size"),
            }

    asyncio.create_task(_remember())


async def handler(ws):
    if not check_auth(ws):
        await ws.close(code=4401, reason="bad token")
        return
    peer = getattr(ws, "remote_address", "?")
    print(f"[QQ] NapCat 已接入 {peer}", flush=True)
    try:
        async for raw in ws:
            try:
                evt = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(evt, dict):
                continue
            if evt.get("post_type") == "message":
                asyncio.create_task(on_message(ws, evt))
    finally:
        print(f"[QQ] NapCat 连接断开 {peer}", flush=True)


async def serve():
    host = core.CFG["onebot"]["ws_host"]
    port = int(core.CFG["onebot"]["ws_port"])
    async with websockets.serve(handler, host, port, max_size=64 * 1024 * 1024):
        print(f"[QQ] 等待 NapCat 连接：ws://{host}:{port}", flush=True)
        await asyncio.Future()
