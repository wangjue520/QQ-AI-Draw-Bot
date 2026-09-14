# QQ-AI-画图机器人（跑图姬）

QQ 出图机器人：群里 @它说"画一个佩丽卡"，自动优化提示词、自动触发角色 LoRA、调用本地 WebUI Forge 出图并发回群里。后端**不限模型**（Anima / SDXL / Pony / Illustrious / Flux，Forge 支持的都能跑）。自带 **Web 控制台**：画风、LoRA、角色字典、提示词规则、QQ 账号全部网页里管理。

> **English — QQ-AI-Draw-Bot**: an AI image-generation bot for QQ groups. `@bot draw <prompt>` → LLM prompt optimization → character LoRA auto-trigger → local Stable Diffusion (WebUI Forge) → image sent back to the group. Model-agnostic (Anima / SDXL / Pony / Illustrious / Flux). Ships with a web console (styles / LoRAs / character dictionary / QQ account management). Built on NapCat (OneBot 11).

## 系统组成

```
群友 @机器人 "画一个佩丽卡"
        │  WebSocket(8080)
   ┌────┴─────┐
   │  NapCat  │  托管 QQ 小号（OneBot 11 反向 WS）
   └────┬─────┘
        │
   ┌────┴───────────┐
   │  bot.py 机器人  │  队列调度 · 提示词优化 · LoRA 匹配
   └───┬────────┬───┘
       │        │
  xAI API    Forge 7860（本地出图；网页手点永远优先）
  (grok)          │
              图片发回群里 + 控制台留档
```

| 组件 | 说明 | 端口 |
|---|---|---|
| Forge | 本地 AI 画图（WebUI Forge / a1111 系） | 7860 |
| NapCat | QQ 协议端，托管机器人小号 | WebUI 6099 |
| 机器人 | 本项目 | QQ 8080 / 控制台 8081 |
| xAI | 提示词优化、模糊分辨率换算 | 云端 |

## 部署

1. **Python 3.10+**（安装时勾选 Add to PATH）
2. 安装 WebUI Forge，确认 `webui-user.bat` 的启动参数里有 **`--api`**（没有就加上，重启 Forge）
3. 安装 NapCat，登录 **QQ 小号**，WebUI → 网络配置 → 新建 **WebSocket 客户端**：`ws://127.0.0.1:8080`，消息格式 **Array**，启用
   > ⚠️ 第三方协议端有封号风险，务必用小号
   >
   > ⚠️ **机器人小号不要在电脑的日常 QQ 客户端里登录**。QQ 同账号不能两处同时在线：小号在普通 QQ 里挂着，NapCat 就永远上不了线（现象：不出二维码、或提示"当前账号已登录，无法重复登录"）。日常 QQ 只登大号，小号专号专用只给 NapCat。控制台"QQ 账号"页可查看绑定状态。
4. 把 `data/config.example.json` 复制为 `data/config.json`，填：
   - `llm.api_key`：xAI 的 key（`xai-` 开头，https://console.x.ai 生成）
   - `lora.dir`：Forge 的 `models\Lora` 完整路径
5. 双击 **`启动机器人.bat`**：自动装依赖、拉起 Forge/NapCat、自动登录小号、启动机器人
6. 浏览器打开控制台 `http://127.0.0.1:8081`

启动成功的标志：机器人窗口出现 `[QQ] NapCat 已接入`。
关闭：关机器人窗口，或双击 `停止机器人.bat`（只杀 bot.py，不误杀其他 Python）。

## 群里指令

| 指令 | 效果 |
|---|---|
| `@机器人 画 画面描述` | AI 优化 + 自动触发 LoRA + 跑图 |
| `@机器人 画 厚涂 横 一个少女` | 画风 + 构图自由组合 |
| `@机器人 生图 英文tag` | 跳过优化直接跑 |
| `@机器人 再来` | 同提示词换种子重 roll |
| `@机器人 画风` / `帮助` | 画风列表 / 说明 |

私聊机器人直接发指令（不用 @）。多任务自动排队。

### 尺寸写法

| 写法 | 行为 |
|---|---|
| `画 1000x1400 少女` | 精准尺寸，直接生效，**不调 AI** |
| `画 1080p 少女`（支持 480p~4k） | 模糊说法，AI 换算成模型能跑的尺寸 |
| `画 横` / `竖` / `方` | 固定构图 |
| 组合 `画 横 1080p 少女` | 横竖关键词优先 |

### 优先级

**在 Forge 网页里手点的生成永远优先**：机器人提交前探测 Forge，本地在跑就排队等待，并提示"Forge 正在跑本地任务，排队等待中…"。

## Web 控制台（http://127.0.0.1:8081）

| 页签 | 功能 |
|---|---|
| 跑图 / 队列 | 手动跑图、**Forge 实时进度条与预览图**、队列、历史出图 |
| 画风预设 | 增删改画风，保存即生效 |
| LoRA 管理 | 扫描、触发词、中文别名、权重、开关 |
| 角色字典 | 搜索 / 新增 / 删除 / **批量导入** |
| 优化提示词 | 修改发给大模型的 system prompt |
| 设置 | key、代理、Forge 地址、LoRA 目录、生成参数 |
| Forge WebUI | 内嵌整个 Forge，可直接操作 |
| QQ 账号 | 查看绑定、一键切换账号（免扫码）、设置自动登录 |

## LoRA 自动触发原理

1. 群友说"画一个**佩丽卡**" → 角色字典命中 → tag `perlica (arknights)`
2. AI 优化提示词时强制使用该 tag
3. 扫描所有 LoRA 的 `.civitai.info`（C站下载自带），命中训练词 → 自动拼 `<lora:xxx:0.8>`
4. 群里提示"自动触发 LoRA：xxx"

对不上时：在 LoRA 管理里给该 LoRA 加**中文别名**，或往字典里补角色名。

## 常见问题

- **卡在 `[QQ] 等待 NapCat 连接`**：NapCat 没开/没登录，重跑启动器即可自动补起
- **NapCat 不出二维码 / 提示"当前账号已登录，无法重复登录"**：机器人小号被登在日常 QQ 里了——去日常 QQ 退出该小号，NapCat 即可上线（控制台"QQ 账号"页也能看到状态）
- **登录卡死/失败**：杀 NapCat 时要用任务管理器结束它整棵进程树（`taskkill /T`），残留 QQ 进程会抢登录状态
- **提示词优化失败**：检查 key（xai- 开头）；key 无效不影响跑图，只是跳过优化
- **图片发不出**：升级 NapCat；避免刷屏触发风控
- **端口冲突**：8080/8081 在控制台"设置"里改；NapCat 的 WS 地址同步改

## 文件说明

| 文件 | 作用 |
|---|---|
| `启动机器人.bat` | 一键启动 Forge + NapCat + 机器人（路径在 bat 头部按实际环境修改） |
| `停止机器人.bat` | 只结束 bot.py 进程 |
| `napcat_auto_login.py` | 启动器调用的 NapCat 自动登录脚本 |
| `bot.py / core.py / qq.py / panel.py` | 机器人源码 |
| `web/index.html` | 控制台页面 |
| `data/` | 配置、角色字典、画风预设（config.json 不入库） |
| `outputs/` | 出图存档 |

## 免责说明

QQ 协议端（NapCat 等）属于第三方实现，存在账号风控/封禁风险，请仅用于小号并遵守相关法律法规与平台规则。本项目仅供学习与技术交流。
