# QQ-AI-画图机器人（跑图姬）

QQ 出图机器人：群里 @它说"画一个佩丽卡"，自动优化提示词、自动触发角色 LoRA、调用你电脑上的本地 WebUI Forge 出图并发回群里。后端**不限模型**（Anima / SDXL / Pony / Illustrious / Flux，Forge 支持的都能跑）。自带 **Web 控制台**：画风、LoRA、角色字典、提示词规则、QQ 账号全部网页里管理。

> **English — QQ-AI-Draw-Bot**: an AI image-generation bot for QQ groups. `@bot 画 <prompt>` → LLM prompt optimization → character LoRA auto-trigger → local Stable Diffusion (WebUI Forge) → image sent back to the group. Model-agnostic (Anima / SDXL / Pony / Illustrious / Flux). Ships with a web console (styles / LoRAs / character dictionary / QQ account management). Built on NapCat (OneBot 11).

## 它是怎么工作的

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

| 组件 | 是什么 | 端口 |
|---|---|---|
| Forge | 本地 AI 画图软件（WebUI Forge / a1111 系） | 7860 |
| NapCat | QQ 协议端，托管机器人小号 | WebUI 6099 |
| 机器人 | 本项目 bot.py | QQ 8080 / 控制台 8081 |
| xAI | 提示词优化、模糊分辨率换算 | 云端 API |

## 部署前要准备什么

| # | 需要 | 说明 |
|---|---|---|
| 1 | Windows 10/11 电脑 | Mac / Linux 暂不支持 |
| 2 | NVIDIA 显卡 | 显存 6G 能起步、8G 以上舒服；跑 Flux 这类新大模型建议 12G+ |
| 3 | 硬盘空间 30G+ | Forge 本体 + 大模型 |
| 4 | 一个 QQ **小号** | ⚠️ 第三方协议端有封号风险，务必用小号，大号只在自己 QQ 里用 |
| 5 | xAI API key | https://console.x.ai 生成；不填也能跑图，只是跳过 AI 优化 |

> 全程不需要懂代码。照着下面 5 步做，每步做完都有"✅ 怎么算成功"。

---

## 第 1 步 · 安装 Python（约 5 分钟）

1. 打开 <https://www.python.org/downloads/>，点页面上那个黄色大按钮 **Download Python 3.12.x**
2. 双击下载好的 `.exe` 安装包，**第一屏最下面有一个勾选框 `Add python.exe to PATH`，务必打勾 ☑**，然后再点 `Install Now`
   > ⚠️ 漏勾这一步 = 之后启动会报"`没找到 Python`"。卸载重装、打上勾即可
3. 验证：按键盘 `Win + R`，输入 `cmd`，回车，在弹出的黑色窗口里输入：
   ```
   python --version
   ```
   显示 `Python 3.12.x` 就是成功了 ✅

## 第 2 步 · 部署 Forge（用配套的 Forge WebUI 启动器）

机器人自己不会画图——群里每一张图都是你电脑上的 **WebUI Forge** 画的。部署 Forge 推荐用本项目同作者的 **[forge-webui-launcher](https://github.com/wangjue520/forge-webui-launcher)**：零环境要求，不用预装 Python，国内镜像加速：

1. 打开仓库 → 绿色 `Code` 按钮 → `Download ZIP`，解压到一个**纯英文、不带空格**的路径（例如 `D:\forge-launcher`）
2. 双击 `start一键启动.bat`——如果电脑没装 Python，它会**自动下载便携版**，不用管
3. 在界面里一键部署 Forge（**Neo / Classic 分支都支持**，选哪个本机器人都能连）
4. 启动参数里确认带 **`--api`**（启动器默认会勾上）

**装完验证（两步都要做）**：

1. 浏览器打开 `http://127.0.0.1:7860` → 能看到画图界面 ✅
2. 再打开 `http://127.0.0.1:7860/sdapi/v1/progress` → 显示一段 JSON（有 `progress`、`current_image` 等字段）= API 已开 ✅
   （如果跳回主页 = 没开 `--api`，回去加上参数重启 Forge）

**放模型**：

- 大模型（ckpt/safetensors）→ Forge 目录下的 `models\Stable-diffusion`；LoRA → `models\Lora`
- 模型从 [Civitai](https://civitai.com) / [HuggingFace](https://huggingface.co) 下载；**C 站下的 LoRA 务必把旁边的 `.civitai.info` 一起放进 LoRA 目录**——机器人自动触发 LoRA 全靠读它

> 备用方案：官方一键包 <https://github.com/lllyasviel/stable-diffusion-webui-forge>（解压后先 `update.bat` 再 `run.bat`，参数加 `--api`）。已经装过 A1111 / 旧版 Forge 的不用重装：编辑 `webui-user.bat`，给 `COMMANDLINE_ARGS` 加上 `--api` 重启即可。

## 第 3 步 · 安装 QQ 和 NapCat（约 10 分钟）

> NapCat = 托管 QQ 小号的协议端，机器人通过它收发消息。

1. 装官方 QQ 客户端（<https://im.qq.com>），登录你的**大号**没问题
2. 下载 NapCat：<https://github.com/NapNeko/NapCatQQ/releases>（选最新版的 `NapCat.Shell.zip`），解压出 `Shell` 文件夹，放进**本项目文件夹**里的 `NapCat` 文件夹中。最终要能看到这个文件：
   ```
   本项目文件夹\NapCat\Shell\launcher.bat
   ```
   （如果你拿到的项目压缩包里已经自带 `NapCat` 文件夹，跳过这步）
3. 右键 `NapCat\Shell\launcher.bat` → **以管理员身份运行** → 弹出小号的独立 QQ 登录窗口 → 手机扫码，**扫完记得在手机上点"登录"按钮**
4. 登录成功后，浏览器打开 NapCat 控制台 `http://127.0.0.1:6099`（进入所需 token 记在 `NapCat\Shell\config\webui.json` 里）→ **网络配置** → 新建 **WebSocket 客户端**：
   - URL：`ws://127.0.0.1:8080`
   - 消息格式：**Array**
   - 保存并启用

> ⚠️ **机器人小号不要在日常 QQ 客户端里登录**。同一 QQ 不能两处同时在线：小号挂在普通 QQ 里，NapCat 就永远上不了线（现象：不出二维码、或提示"当前账号已登录"）。日常 QQ 只登大号，小号专号专用只给 NapCat。

## 第 4 步 · 配置机器人（约 5 分钟）

1. 下载本项目：<https://github.com/wangjue520/QQ-AI-Draw-Bot> → 绿色 `Code` 按钮 → `Download ZIP`，解压到一个**纯英文、不带空格**的路径
2. 进 `data` 文件夹，把 `config.example.json` **复制**一份，改名为 `config.json`，右键 → 打开方式 → 记事本：
   - `"api_key"`：填 xAI 的 key（`xai-` 开头，https://console.x.ai 生成）
   - `"dir"`（lora 段下面）：填 Forge 的 LoRA 目录完整路径，例如 `D:\webui-forge\models\Lora`
3. 右键 `启动机器人.bat` → 编辑，把开头两行改成你自己电脑的路径：
   ```bat
   set "FORGE_DIR=D:\webui-forge"                 ← Forge 的目录（里面放着 webui-user.bat 的那一层）
   set "QQ_EXE=C:\Program Files\Tencent\QQ\QQ.exe" ← QQ 的安装位置
   ```
   > 不知道路径怎么填？打开到那个文件夹，**用鼠标点一下文件夹顶部地址栏，路径会整行变蓝，Ctrl+C 复制**，粘贴进 bat 即可。注意：路径里不要带中文和空格。

## 第 5 步 · 一键启动

**双击 `启动机器人.bat`**，它会自动按顺序：

1. 检查并安装 Python 依赖（首次约 1 分钟）
2. Forge 没开就最小化启动它（模型加载约 3 分钟，加载完才能出图）
3. NapCat 没开就最小化启动，并**自动登录小号（免扫码）**
4. 启动机器人本体，并自动打开控制台 `http://127.0.0.1:8081`

启动成功的标志（机器人窗口里依次出现）：

```
[Web] 控制台已启动：http://127.0.0.1:8081
[QQ] 等待 NapCat 连接：ws://127.0.0.1:8080
[QQ] NapCat 已接入
```

看到 **`NapCat 已接入`** 就能去群里 @小号 画图了 ✅（Forge 还在加载模型也不影响，任务会排队等它）

**关闭**：关机器人窗口，或双击 `停止机器人.bat`（只杀 bot.py，不误伤其他 Python 程序）。Forge / NapCat 可以一直挂着；关机前不用特意关什么，下次双击启动器全自动恢复。

---

## 群里怎么用

群聊 **@小号 + 指令**；私聊小号直接发指令（不用 @）。多任务自动排队。

| 指令 | 效果 |
|---|---|
| `@小号 画 画面描述` | AI 优化提示词 + 自动触发角色 LoRA + 跑图 |
| `@小号 画 厚涂 横 一个少女` | 画风 + 构图自由组合 |
| `@小号 生图 英文tag` | 跳过优化直接跑（给会写 tag 的人） |
| `@小号 再来` | 用上一条提示词换种子重 roll |
| `@小号 画风` / `帮助` | 画风列表 / 使用说明 |

### 尺寸写法

| 写法 | 行为 |
|---|---|
| `画 1000x1400 少女` | 精准尺寸，直接生效，**不调 AI** |
| `画 1080p 少女`（支持 480p~4k） | 模糊说法，AI 换算成模型能跑的尺寸 |
| `画 横` / `竖` / `方` | 固定构图 |
| 组合 `画 横 1080p 少女` | 横竖关键词优先 |

### 优先级（重要）

**在 Forge 网页里手点的生成永远优先**：机器人提交前会探测 Forge，本地在跑就排队等待，并提示"Forge 正在跑本地任务，排队等待中…"。多人同时用也自动排队，群里会报"前面还有 N 个任务"。

## Web 控制台（http://127.0.0.1:8081）

启动后浏览器自动打开，所有配置网页里改，保存即生效。

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

## 常见问题（按症状排查）

- **报错"没找到 Python"**：第 1 步没装/漏勾 `Add python.exe to PATH`，重装打勾即可
- **卡在 `[QQ] 等待 NapCat 连接`**：NapCat 没开或没登录 → 重跑启动器，会自动补起并自动登录；别在任务管理器里只杀 NapCat 主进程，会残留孤儿 QQ 进程抢登录状态（要杀就结束整棵进程树）
- **NapCat 不出二维码 / 提示"当前账号已登录，无法重复登录"**：小号被登在日常 QQ 里了——去日常 QQ 退出该小号即可（控制台"QQ 账号"页能看到状态）
- **登录卡死/失败**：任务管理器结束今天新出现的 `QQ.exe`（保留你自己大号的），重跑启动器；扫码入口：小号独立 QQ 窗口（自动刷新）或 `NapCat\Shell\cache\qrcode.png`，扫完**必须在手机上点"登录"**
- **提示词优化失败 / 提示没填 key**：控制台 → 设置 → 检查 xAI 的 key（`xai-` 开头）；key 无效不影响跑图，只是跳过优化
- **跑图没反应 / 报连不上 Forge**：Forge 没开或没开 `--api`——浏览器打开 `http://127.0.0.1:7860/sdapi/v1/progress`，能显示 JSON 才算通
- **图片发不出 / 发得慢**：升级 NapCat；群里发图受 QQ 风控限制，别刷屏
- **端口冲突**：8080/8081 在控制台"设置"里改；NapCat 的 WS 地址同步改（NapCat 控制台 → 网络配置）

## 进阶玩法

- **换一个小号托管**：新号先在 NapCat 里扫码登录一次（进快速登录列表），之后控制台"QQ 账号"页随时一键切换
- **添加新 LoRA**：放进 Forge 的 `models\Lora`，旁边带上 `.civitai.info`（C站下载自带），控制台"LoRA 管理"点"重新扫描"
- **批量补角色字典**：控制台"角色字典"页，批量导入框每行一条：`tag(下划线写法),作品名,中文名,别名1,别名2`
- **改画风**：控制台"画风预设"页。正向里 LoRA 写 `<lora:文件名:权重>`，画师写 `@画师名`，保存后群里立即生效

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
| `NapCat/Shell/` | NapCat 本体（不入库，按第 3 步自行放置） |

## 免责说明

QQ 协议端（NapCat 等）属于第三方实现，存在账号风控/封禁风险，请仅用于小号并遵守相关法律法规与平台规则。本项目仅供学习与技术交流。
