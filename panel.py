# -*- coding: utf-8 -*-
"""Web 控制台：HTTP API + 静态页面（aiohttp）"""

import base64
import hashlib
import io
import json
import time
from pathlib import Path

from aiohttp import web
import httpx
import qrcode

import core

BASE_DIR = Path(__file__).resolve().parent
INDEX_HTML = BASE_DIR / "web" / "index.html"
NAPCAT_WEBUI_JSON = BASE_DIR / "NapCat" / "Shell" / "config" / "webui.json"


# ========== 状态 / 跑图 ==========

async def api_status(request):
    data = core.queue_status()
    data["llm_ok"] = core.llm_available()
    data["lora_dir"] = core.CFG["lora"].get("dir", "")
    data["webui"] = core.CFG["webui"]["base_url"]
    return web.json_response(data)


async def api_draw(request):
    body = await request.json()
    content = (body.get("content") or "").strip()
    if not content:
        return web.json_response({"ok": False, "msg": "提示词不能为空"})
    job = {
        "source": "web",
        "user_name": "网页",
        "time": time.strftime("%H:%M:%S"),
        "style": body.get("style") or core.CFG["bot"].get("default_style", "默认"),
        "size": body.get("size"),
        "content": content,
        "mode": body.get("mode", "draw"),
        "state": "queued",
    }
    n = await core.enqueue(job)
    return web.json_response({"ok": True, "queue_pos": n})


async def api_progress(request):
    """代理 Forge /sdapi/v1/progress，给控制台显示实时跑图进度"""
    url = core.CFG["webui"]["base_url"].rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=10) as cli:
            r = await cli.get(f"{url}/sdapi/v1/progress")
            return web.json_response(r.json())
    except Exception as e:
        return web.json_response({"error": str(e)}, status=502)


# ========== Forge 模型 / VAE ==========

FORGE_URL = lambda: core.CFG["webui"]["base_url"].rstrip("/")


async def api_forge_models(request):
    """Forge 当前模型 + 可选列表（模型=sd-models；VAE/文本编码器=forge附加模块，分目录列出）"""
    try:
        async with httpx.AsyncClient(timeout=15) as cli:
            opts = (await cli.get(f"{FORGE_URL()}/sdapi/v1/options")).json()
            models = (await cli.get(f"{FORGE_URL()}/sdapi/v1/sd-models")).json()
        preset = opts.get("forge_preset", "")
        checkpoint = opts.get(f"forge_checkpoint_{preset}") or opts.get("sd_model_checkpoint", "")
        modules = [str(m) for m in (opts.get(f"forge_additional_modules_{preset}") or [])]

        # 定位 models 目录：优先用 LoRA 目录推（可靠），否则用现有模块路径推
        models_root = None
        lora_dir = core.CFG["lora"].get("dir", "")
        if lora_dir and Path(lora_dir).parent.is_dir():
            models_root = Path(lora_dir).parent
        else:
            for m in modules:
                p = Path(m).parent
                if p.name.lower() in ("vae", "text_encoder"):
                    models_root = p.parent
                    break
        vae_dir = str(models_root / "VAE") if models_root else ""
        te_dir = str(models_root / "text_encoder") if models_root else ""

        def _files(d):
            if not d or not Path(d).is_dir():
                return []
            return sorted(p.name for p in Path(d).iterdir()
                          if p.is_file() and p.suffix.lower() in (".safetensors", ".ckpt", ".pt"))

        cur_vae, cur_te, other = [], [], []
        for m in modules:
            p = Path(m)
            if vae_dir and p.parent == Path(vae_dir):
                cur_vae.append(p.name)
            elif te_dir and p.parent == Path(te_dir):
                cur_te.append(p.name)
            else:
                other.append(m)
        return web.json_response({
            "preset": preset,
            "checkpoint": checkpoint,
            "checkpoints": [{"name": m.get("model_name", ""), "title": m.get("title", "")}
                            for m in models],
            "vae_dir": vae_dir,
            "vaes": _files(vae_dir),
            "vae_current": cur_vae,
            "te_dir": te_dir,
            "tes": _files(te_dir),
            "te_current": cur_te,
            "other_modules": other,
        })
    except Exception as e:
        return web.json_response({"error": str(e)}, status=502)


async def api_forge_models_set(request):
    """切换 Forge 当前预设的 checkpoint / VAE / 文本编码器（文本编码器 Flux、Qwen 类模型才需要）"""
    body = await request.json()
    try:
        async with httpx.AsyncClient(timeout=30) as cli:
            opts = (await cli.get(f"{FORGE_URL()}/sdapi/v1/options")).json()
            preset = opts.get("forge_preset", "")
            old_modules = [str(m) for m in (opts.get(f"forge_additional_modules_{preset}") or [])]
            payload = {}
            ckpt = (body.get("checkpoint") or "").strip()
            if ckpt:
                payload[f"forge_checkpoint_{preset}"] = ckpt

            vae_dir = (body.get("vae_dir") or "").strip()
            te_dir = (body.get("te_dir") or "").strip()
            new_vae = (body.get("vae") or "").strip()
            new_te = [str(x).strip() for x in (body.get("te") or []) if str(x).strip()]

            keep = []
            for m in old_modules:
                p = Path(m)
                if vae_dir and p.parent == Path(vae_dir):
                    continue  # 旧的 VAE 由本次选择接管
                if te_dir and p.parent == Path(te_dir):
                    continue  # 旧的 TE 由本次选择接管
                keep.append(m)
            modules = keep[:]
            if te_dir:
                modules += [str(Path(te_dir) / t) for t in new_te]
            if vae_dir and new_vae:
                modules.append(str(Path(vae_dir) / new_vae))
            payload[f"forge_additional_modules_{preset}"] = modules

            if not payload:
                return web.json_response({"ok": False, "msg": "没有要修改的项"})
            r = await cli.post(f"{FORGE_URL()}/sdapi/v1/options", json=payload)
            if r.status_code != 200:
                return web.json_response({"ok": False, "msg": f"Forge 返回 {r.status_code}"})
        return web.json_response({"ok": True, "applied": {k: (v if not isinstance(v, list) else f"{len(v)} 个模块") for k, v in payload.items()}})
    except Exception as e:
        return web.json_response({"ok": False, "msg": str(e)})


# ========== QQ 账号（代理 NapCat WebUI） ==========

async def _nc_post(ep, payload):
    """带鉴权调用 NapCat WebUI API（token 从 webui.json 读）"""
    cfg = json.loads(NAPCAT_WEBUI_JSON.read_text(encoding="utf-8"))
    token = cfg["token"]
    h = hashlib.sha256((token + ".napcat").encode()).hexdigest()
    async with httpx.AsyncClient(timeout=15) as cli:
        r = await cli.post(f"http://127.0.0.1:6099/api/auth/login",
                           json={"hash": h, "totpCode": ""})
        cred = r.json()["data"]["Credential"]
        r = await cli.post(f"http://127.0.0.1:6099/api/{ep}", json=payload,
                           headers={"Authorization": f"Bearer {cred}"})
        return r.json()


async def api_qq_accounts(request):
    """当前登录账号 + 可快速登录的账号列表"""
    try:
        info = await _nc_post("QQLogin/GetQQLoginInfo", {})
        quick = await _nc_post("QQLogin/GetQuickLoginListNew", {})
        status = await _nc_post("QQLogin/CheckLoginStatus", {})
        cur = info.get("data") if info.get("code") == 0 else None
        entries = quick.get("data") or []
        if cur and not any(str(e.get("uin")) == str(cur.get("uin")) for e in entries):
            entries.insert(0, {"uin": cur.get("uin"), "nickName": cur.get("nick"),
                               "isQuickLogin": False})
        auto_login = ""
        try:
            auto_login = str(json.loads(NAPCAT_WEBUI_JSON.read_text(encoding="utf-8"))
                             .get("autoLoginAccount", "") or "")
        except Exception:
            pass
        return web.json_response({
            "current": cur,
            "online": bool((status.get("data") or {}).get("isLogin")),
            "accounts": entries,
            "auto_login": auto_login,
        })
    except Exception as e:
        return web.json_response({"error": str(e)}, status=502)


async def api_qq_autologin(request):
    """设置一键启动时自动登录的 QQ 账号（写 NapCat webui.json）"""
    body = await request.json()
    uin = str(body.get("uin", "")).strip()
    try:
        r = await _nc_post("QQLogin/SetQuickLoginQQ", {"uin": uin})
        if r.get("code") == 0:
            return web.json_response({"ok": True})
        return web.json_response({"ok": False, "msg": r.get("message", "设置失败")})
    except Exception as e:
        return web.json_response({"ok": False, "msg": str(e)})


_QR_CACHE = {"img": None, "ts": 0.0}


async def api_qq_qrcode(request):
    """需要扫码时返回二维码图片(dataURL)；已登录返回 needed=False。
    带 90 秒缓存，避免页面轮询把二维码刷得没法扫。"""
    try:
        cfg = json.loads(NAPCAT_WEBUI_JSON.read_text(encoding="utf-8"))
        token = cfg["token"]
        h = hashlib.sha256((token + ".napcat").encode()).hexdigest()
        async with httpx.AsyncClient(timeout=15) as cli:
            cred = (await cli.post("http://127.0.0.1:6099/api/auth/login",
                                   json={"hash": h, "totpCode": ""})).json()["data"]["Credential"]
            head = {"Authorization": f"Bearer {cred}"}
            st = (await cli.post("http://127.0.0.1:6099/api/QQLogin/CheckLoginStatus",
                                 json={}, headers=head)).json()["data"]
        if st.get("isLogin"):
            _QR_CACHE.update(img=None, ts=0.0)
            return web.json_response({"needed": False})
        refresh = request.query.get("refresh") == "1"
        if refresh or not _QR_CACHE["img"] or time.time() - _QR_CACHE["ts"] > 90:
            r = await _nc_post("QQLogin/RefreshQRcode", {})
            url = r["data"]["qrcodeurl"]
            buf = io.BytesIO()
            qrcode.make(url).save(buf, format="PNG")
            _QR_CACHE["img"] = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
            _QR_CACHE["ts"] = time.time()
        return web.json_response({"needed": True, "img": _QR_CACHE["img"]})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=502)


async def api_qq_switch(request):
    """切换 NapCat 登录的 QQ 账号（快速登录）"""
    body = await request.json()
    uin = str(body.get("uin", "")).strip()
    if not uin:
        return web.json_response({"ok": False, "msg": "缺少 uin"})
    try:
        r = await _nc_post("QQLogin/SetQuickLogin", {"uin": uin})
        if r.get("code") == 0:
            return web.json_response({"ok": True})
        return web.json_response({"ok": False, "msg": r.get("message", "切换失败")})
    except Exception as e:
        return web.json_response({"ok": False, "msg": str(e)})


# ========== 画风预设 ==========

async def api_get_presets(request):
    return web.json_response(core.load_presets())


async def api_save_preset(request):
    body = await request.json()
    name = (body.get("name") or "").strip()
    if not name:
        return web.json_response({"ok": False, "msg": "名字不能为空"})
    presets = core.load_presets()
    presets[name] = {
        "description": body.get("description", ""),
        "positive": body.get("positive", ""),
        "negative": body.get("negative", ""),
    }
    core.save_presets(presets)
    return web.json_response({"ok": True})


async def api_delete_preset(request):
    body = await request.json()
    presets = core.load_presets()
    presets.pop(body.get("name", ""), None)
    core.save_presets(presets)
    return web.json_response({"ok": True})


# ========== 优化提示词 ==========

async def api_get_prompt(request):
    return web.json_response({"prompt": core.get_optimizer_prompt()})


async def api_save_prompt(request):
    body = await request.json()
    text = (body.get("prompt") or "").strip()
    if not text:
        return web.json_response({"ok": False, "msg": "内容不能为空"})
    core.save_optimizer_prompt(text)
    return web.json_response({"ok": True})


# ========== LoRA ==========

async def api_get_loras(request):
    loras = core.scan_loras(core.CFG["lora"].get("dir", ""))
    return web.json_response({"loras": list(loras.values())})


async def api_update_lora(request):
    body = await request.json()
    stem = body.get("stem")
    if not stem:
        return web.json_response({"ok": False, "msg": "缺少 stem"})
    patch = {}
    if "enabled" in body:
        patch["enabled"] = bool(body["enabled"])
    if "weight" in body:
        patch["weight"] = max(0.0, min(2.0, float(body["weight"])))
    if "aliases" in body:
        patch["aliases"] = [a.strip() for a in body["aliases"] if str(a).strip()]
    core.update_lora(stem, patch)
    return web.json_response({"ok": True})


# ========== 角色字典 ==========

async def api_get_dict(request):
    q = (request.query.get("q") or "").lower()
    entries = core.load_dict_entries()
    if q:
        entries = [e for e in entries
                   if q in e["tag"].lower() or q in e.get("series", "").lower()
                   or any(q in n.lower() for n in e.get("names", []))]
    try:
        limit = max(1, min(int(request.query.get("limit", 200)), 10000))
    except (TypeError, ValueError):
        limit = 200
    return web.json_response({"total": len(core.load_dict_entries()), "entries": entries[:limit]})


async def api_add_dict(request):
    body = await request.json()
    tag = (body.get("tag") or "").strip().lower().replace(" ", "_")
    if not tag:
        return web.json_response({"ok": False, "msg": "tag 不能为空"})
    entries = core.load_dict_entries()
    if any(e["tag"] == tag for e in entries):
        return web.json_response({"ok": False, "msg": "该 tag 已存在"})
    entries.append({
        "tag": tag,
        "series": body.get("series", ""),
        "names": [n.strip() for n in body.get("names", []) if str(n).strip()],
    })
    core.save_dict_entries(entries)
    return web.json_response({"ok": True})


async def api_delete_dict(request):
    body = await request.json()
    tag = body.get("tag", "")
    entries = [e for e in core.load_dict_entries() if e["tag"] != tag]
    core.save_dict_entries(entries)
    return web.json_response({"ok": True})


# ========== 设置 ==========

SAFE_KEYS = ("onebot", "webui", "gen", "bot", "lora", "web")


async def api_get_settings(request):
    out = {k: core.CFG.get(k) for k in SAFE_KEYS}
    llm = dict(core.CFG["llm"])
    key = llm.get("api_key", "")
    llm["api_key"] = (key[:6] + "****" + key[-4:]) if len(key) > 12 else ("*" * len(key))
    llm["has_key"] = bool(key)
    out["llm"] = llm
    return web.json_response(out)


async def api_save_settings(request):
    body = await request.json()
    for section in SAFE_KEYS + ("llm",):
        if section not in body or not isinstance(body[section], dict):
            continue
        for k, v in body[section].items():
            if section == "llm" and k == "api_key" and ("****" in str(v) or not str(v).strip()):
                continue  # 没改 key 就保留原值
            core.CFG[section][k] = v
    core.save_config()
    return web.json_response({"ok": True})


# ========== 页面 ==========

async def index(request):
    return web.FileResponse(INDEX_HTML)


def make_app():
    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/api/status", api_status)
    app.router.add_post("/api/draw", api_draw)
    app.router.add_get("/api/progress", api_progress)
    app.router.add_get("/api/qq/accounts", api_qq_accounts)
    app.router.add_post("/api/qq/switch", api_qq_switch)
    app.router.add_post("/api/qq/autologin", api_qq_autologin)
    app.router.add_get("/api/qq/qrcode", api_qq_qrcode)
    app.router.add_get("/api/forge_models", api_forge_models)
    app.router.add_post("/api/forge_models", api_forge_models_set)
    app.router.add_get("/api/presets", api_get_presets)
    app.router.add_post("/api/presets/save", api_save_preset)
    app.router.add_post("/api/presets/delete", api_delete_preset)
    app.router.add_get("/api/optimizer_prompt", api_get_prompt)
    app.router.add_post("/api/optimizer_prompt", api_save_prompt)
    app.router.add_get("/api/loras", api_get_loras)
    app.router.add_post("/api/loras/update", api_update_lora)
    app.router.add_get("/api/dict", api_get_dict)
    app.router.add_post("/api/dict/add", api_add_dict)
    app.router.add_post("/api/dict/delete", api_delete_dict)
    app.router.add_get("/api/settings", api_get_settings)
    app.router.add_post("/api/settings", api_save_settings)
    app.router.add_static("/outputs/", core.OUT_DIR, show_index=False)
    return app


async def serve():
    host = core.CFG["web"].get("host", "127.0.0.1")
    port = int(core.CFG["web"].get("port", 8081))
    runner = web.AppRunner(make_app())
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    print(f"[Web] 控制台已启动：http://{host}:{port}", flush=True)
    return f"http://{host}:{port}"
