# -*- coding: utf-8 -*-
"""
跑图姬 · QQ 出图机器人 · 主入口
启动三部分：QQ 接入（NapCat）+ Web 控制台 + 跑图队列
"""

import asyncio
import sys
import threading
import webbrowser

try:
    import websockets  # noqa: F401
    import httpx       # noqa: F401
    import aiohttp     # noqa: F401
except ImportError:
    sys.exit("缺少依赖，请先双击 启动机器人.bat（会自动装依赖）")

import core
import qq
import panel


async def guarded(coro, name):
    try:
        await coro
    except Exception as e:
        print(f"[{name}] 启动失败：{e}（其余模块不受影响）", flush=True)


async def main():
    # 必须持有任务强引用，否则会被 GC 回收导致 QQ/Web 服务偶发消失
    tasks = [
        asyncio.create_task(core.worker()),
        asyncio.create_task(guarded(qq.serve(), "QQ")),
    ]
    url = await panel.serve()
    print("=" * 50, flush=True)
    print("  跑图姬已启动", flush=True)
    print(f"  Web 控制台：{url}", flush=True)
    print(f"  提示词优化：{'已启用' if core.llm_available() else '未启用（在 Web 控制台-设置里填 key）'}", flush=True)
    lora_dir = core.CFG["lora"].get("dir", "")
    n = len(core.scan_loras(lora_dir)) if lora_dir else 0
    print(f"  LoRA：{f'已扫描到 {n} 个' if lora_dir else '未设置目录（Web 控制台-设置里填）'}", flush=True)
    print("=" * 50, flush=True)
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("已退出")
