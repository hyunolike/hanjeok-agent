<div align="center">

<a href="https://agent.hanjeok.com"><img src="docs/media/hanjeok-guide.jpg" alt="Hanjeok Agent — 一只手持卡片的绿色叶子角色,下方是名称和地址 agent.hanjeok.com" width="820"></a>

# Hanjeok Agent

**问哪里拥挤,也看到答案从何而来。**

旅行服务 [Hanjeok(韩寂)](https://hanjeok.com) 的导览智能体。它把查询的每一步展示在屏幕上,<br/>
并且只引用为这个问题实际取到的内容来回答。

[English](./README.md) · [한국어](./README.ko.md) · [日本語](./README.ja.md) · **中文**

[![演示](https://img.shields.io/badge/演示-agent.hanjeok.com-172033?style=for-the-badge&logo=googlechrome&logoColor=white)](https://agent.hanjeok.com/en/ask)

![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-1C3C3C?logo=langchain&logoColor=white)
![Neo4j](https://img.shields.io/badge/Neo4j-5.26-4581C3?logo=neo4j&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-16-000000?logo=nextdotjs&logoColor=white)
![Cloud Run](https://img.shields.io/badge/Cloud_Run-4285F4?logo=googlecloud&logoColor=white)

<sub>本文档译自<a href="./README.md">英文版</a>。内容如有出入,以英文版为准。界面与回答以韩语和英语提供。</sub>

</div>

<br/>

<div align="center">

https://github.com/user-attachments/assets/26f0ab43-0959-49cb-a4f1-9dcf554d93a3

<sub>20 秒,有声音,录自运行在真实 Hanjeok 数据上的线上站点。</sub>

</div>

<br/>

## 🧭 它回答什么问题

"这周六不去景福宫,有没有安静一点的地方?"

搜索框答不了这个问题。它需要连续做三件事:找到地点,查看那一天的拥挤预报,再取得服务为该地点排出的替代地点。答案回来之后,还会剩下一个问题:**这是谁说的?**

| 架在数据库上的聊天框 | Hanjeok Agent |
| :-- | :-- |
| 模型写出答案,用户只能相信 | 走过的每一步都在屏幕上,并写明每一步取到了什么 |
| 模型挑选听起来不错的 | 排名由服务决定,模型既不重排也不挑选 |
| 流畅的答案可能毫无依据 | 只能引用本次问题取到的内容,否则不显示答案 |
| "没有数据"悄悄变成"大概没问题" | 没有预报的地点如实说不知道,绝不说它清静 |

<br/>

## ✨ 可以做什么

<table>
  <tr>
    <td width="52%" valign="top"><img src="docs/images/guide/screens/steps.png" alt="正在处理问题的提问界面:读取问题、查找地点两个步骤已完成。"></td>
    <td valign="top">

### 提问,并看它如何查找

- 带上地点和日期,用平常的话来问。
- 问题**先按规则**读取:是哪个地点、哪一天、是不是它能回答的问题。这一步不调用模型。
- 每完成一次查询就出现一个步骤。被拒绝的查询也会显示,并附上原因。

</td>
  </tr>
  <tr>
    <td valign="top"><img src="docs/images/guide/screens/answer.png" alt="一张回答卡片,带有一个标着 Hanjeok record 的引用标签。"></td>
    <td valign="top">

### 得到可以核对的答案

- 引用分两种:事实由 **Hanjeok 记录**支撑,服务为何这样看待该事实由**政策文档**支撑。
- 答案在显示前要经过检查。引用了本次问题没有取到的内容就无法通过;允许重写一次,仍不通过则什么都不显示。
- 票价、营业时间、"帮我改一下排名"这类请求会被拒绝,并告诉你可以改问什么。

</td>
  </tr>
  <tr>
    <td valign="top"><img src="docs/images/guide/screens/path.png" alt="路径视图:最上方是景福宫,下面是带排名编号的替代地点,右侧是地区,左侧是政策文档。"></td>
    <td valign="top">

### 查看答案走过的路径

- 以图和列表展示答案涉及的地点、关联和文档。
- 替代地点**按 Hanjeok 给出的排名**排列,界面不会重新排序。
- 只画取到的内容,不会为了让图更饱满而添加。

</td>
  </tr>
  <tr>
    <td valign="top"><img src="docs/images/guide/screens/eval.png" alt="评估页面:分数表中未能评分的单元格写着 Not scored 及原因。"></td>
    <td valign="top">

### 读懂它答得怎么样

- 同一批问题用两种检索方式作答:**仅文本相似度**,以及**再沿关联链接走一步**。
- 每个分数都标明是由多少道题算出的。
- 算不出的分数写作**"Not scored"**并说明原因,绝不写成 0。

</td>
  </tr>
</table>

也可以不提问,直接[浏览某个地点的相邻地点](https://agent.hanjeok.com/en/graph?place=653)。

<br/>

## ⚙️ 一个问题是怎样被处理的

<div align="center">
<img src="docs/images/guide/question-flow.png" alt="从左到右六个步骤:问题、按规则读取、选择查询、撰写答案、引用关卡、答案加引用加路径。按规则读取可能分流到拒绝或反问。选择查询经由代码执行到达 Neo4j 图和 Hanjeok API。引用关卡可以退回重写一次,两次被拒则不显示任何内容。" width="820">
</div>

无论走图中的哪条路,都遵守五条规则。

1. **模型不写查询语句。** 它从七种查询中选一种,由代码校验输入并执行固定的读取。
2. **模型不做排名。** 列表按 Hanjeok 的顺序带编号送达,并按原顺序传递。
3. **无法靠猜 ID 触达某个地点。** 查询只接受本次问题已经找到的地点。
4. **未经验证的文字不会出现在屏幕上。** 答案不逐字流出,而是通过引用检查后整体发送。
5. **预算是固定的。** 查询 3 轮、回答 1 次、重写 1 次,共 60 秒。

<br/>

## 🏗 系统架构

<div align="center">
<img src="docs/images/guide/architecture.png" alt="四列:访问者的浏览器;Vercel 上的 Next.js 界面;一个 Cloud Run 容器,内含 FastAPI、MCP 服务器、LangGraph 智能体、七种查询、引用关卡、Neo4j 和嵌入模型;外部服务 NVIDIA NIM 与 Hanjeok API。底部一条是构建阶段:Hanjeok 数据库、导出脚本、JSONL 与清单、校验、内置于镜像的图。" width="820">
</div>

**智能体不持有 Hanjeok 数据库的任何凭据。** 数据只通过两条途径进入:

- **变化缓慢的数据以文件形式交付。** Hanjeok 一侧的脚本导出公开的旅游数据表,且只导出允许列表中的列。智能体校验哈希、行数和列,只要出现一个预期之外的列就拒绝整个文件。图在构建容器镜像时由该文件生成。
- **与日期绑定的数据在提问时获取。** 拥挤预报和替代地点来自两个只读的 Hanjeok 接口。地点详情接口每调用一次就会记录一次浏览,因此从不调用。

有三个部分用的是库而非本仓库自写的代码:步骤的推送、"你指的是哪一个地点?"的暂停与恢复、一次访问中此前问题的记忆,由 LangGraph 的流、`interrupt` 和检查点承担;相似度检索由 neo4j-graphrag 的 `VectorCypherRetriever` 完成;MCP 服务器提供四个只读工具,让其他程序(将来是 Hanjeok 后端)可以向智能体提问。

<br/>

## 📊 目前测量过的内容

测得不多,并如实写明。

| | |
| :-- | :-- |
| **已部署服务中的数据** | 地点 13,403 个、关联链接 45,244 条、活动 353 个,于 2026-10-14 从 Hanjeok 导出 |
| **测试** | 后端 408 个(无需网络和密钥)、真实 Neo4j 上 16 个、前端 246 个 |
| **从零唤醒** | 约 30 秒(Neo4j 19 秒,服务器 10 秒) |
| **唤醒后的一次提问** | 6 到 9 秒;模型提供方限流时最长 56 秒 |

已公开的评估是**针对 40 个虚构地点的合成数据的 12 道题**,未运行 RAGAS 评判。

| | 仅文本相似度 | 再沿关联链接 |
| :-- | :-: | :-: |
| 取到所需记录的比例,第 1 次 | 0.75(10 题) | 0.92(10 题) |
| 取到所需记录的比例,第 2 次 | 0.75(10 题) | 0.82(10 题) |
| 不应回答的问题被拒绝 | 2 题中 2 题 | 2 题中 2 题 |

> [!NOTE]
> **尚未完成。** 针对真实数据的 60 道题,以及 RAGAS 分数。评判运行过一次,但在与其他项目共用的模型密钥下,72 个请求只有 1 个得到答复,其余都被限流。评估页面把这些单元格显示为"Not scored"。

> [!WARNING]
> **出现过错误答案通过引用检查的情况。** 在真实数据上,智能体曾把替代地点说成"由近到远"(实际按 Hanjeok 的评分排序),也曾在没有取得预报的情况下称某个海水浴场"今天很清静"。两次引用的都是确实取到的记录,但说法超出了记录本身。已在提示词中加入规则。六条禁止行为规则目前还无法统计这两种情况。

<br/>

## 🛠 技术栈

| 领域 | 所用技术 |
| :-- | :-- |
| 智能体服务 | Python 3.13 · FastAPI · LangGraph(流、`interrupt`、检查点)· LangChain |
| 图与检索 | Neo4j 5.26 · neo4j-graphrag `VectorCypherRetriever` · multilingual-e5-large(1024 维,本地) |
| 模型 | NVIDIA NIM nemotron,结构化输出 |
| 与其他程序的连接 | MCP 服务器,四个只读工具 |
| 评估 | RAGAS · 基于记录 ID 的精确率与召回率 · 六个基于规则的禁止行为计数器 |
| 界面 | Next.js 16 · React 19 · Tailwind 4 |
| 部署 | Cloud Run(服务与 Neo4j 同在一个容器)· Vercel · Cloud Build |
| 追踪 | Langfuse,仅在配置密钥后启用 |

<br/>

## 🗂 仓库导览

| 路径 | 内容 |
| :-- | :-- |
| [`bench/src/guide/`](bench/src/guide/) | 智能体本体:范围规则、查询、LangGraph 循环、引用关卡、API、MCP 服务器、评估 |
| [`bench/tests/`](bench/tests/) | 单元、契约与 Neo4j 集成测试,以及用虚构地点制作的合成导出文件 |
| [`bench/Dockerfile`](bench/Dockerfile) · [`bench/deploy/`](bench/deploy/) | 装有服务、Neo4j 和预构建图的镜像 |
| [`frontend/`](frontend/) | 四个界面 |
| [`specs/002-hanjeok-guide-agent/`](specs/002-hanjeok-guide-agent/) | 规格、调研决策、数据模型、契约、任务 |
| [`docs/prd/`](docs/prd/hanjeok-guide-agent.md) | 产品需求(韩语) |
| [`docs/deploy.md`](docs/deploy.md) | 部署方式及实际执行的命令(韩语) |
| [`server/`](server/) | 早先的行程解说服务(Kotlin、Spring AI),见下文 |

### 在代码中阅读核心思路

- [`scope.py`](bench/src/guide/scope.py):调用模型之前对问题所做的判断
- [`lookups.py`](bench/src/guide/lookups.py):七种查询及各自拒绝的情况
- [`agent.py`](bench/src/guide/agent.py):LangGraph 循环、暂停、预算
- [`citations.py`](bench/src/guide/citations.py):引用关卡
- [`export.py`](bench/src/guide/export.py):拒绝与清单不符的导出文件
- [`forbidden.py`](bench/src/guide/forbidden.py):按规则统计的六种禁止行为

<br/>

## 🚀 在本地运行

只启动界面,回放预先录制的响应。需要 Node 22 和 pnpm。

```bash
cd frontend
pnpm install
pnpm dev          # http://localhost:3000/en/ask
```

用合成数据启动服务。需要 Python 3.13、uv 和 Docker。

```bash
cd bench
docker compose up -d
uv sync
uv run guide refresh --export tests/fixtures/hanjeok-export
GUIDE_LIVE_MODE=replay uv run uvicorn guide.api:app --port 8090   # 回答需要 NVIDIA_API_KEY

uv run pytest                    # 408 个测试,无需网络
uv run guide mcp                 # 以 MCP 方式提供同一个智能体(stdio)
```

要让界面连接服务,请用 `NEXT_PUBLIC_GUIDE_BASE_URL=http://localhost:8090 pnpm dev` 启动。

<br/>

## ⚠️ 已知限制

- **闲置之后的第一个问题要等约 30 秒。** 服务会缩减到零;界面会提示正在唤醒。
- **模型密钥与其他项目共用。** 遇到限流时,提问会变慢或失败。
- **两个字的地名采用保守匹配。** 即便如此,"在地图上离得近的地方"里的"지도(地图)"仍会被读成同名的岛屿。
- **访问记录和用量上限保存在内存中。** 因此服务只运行一个实例。
- **导览角色的图片**由 Codex 图像生成制作。未进行商标和 AI 生成图像的版权审查,作者于 2026-10-14 决定公开。记录见 [`provenance.json`](design/guide-character/v1/provenance.json)。

<br/>

## 📚 早先的组成部分:行程解说服务

在导览智能体之前,本仓库只解说一件事:Hanjeok 后端已经生成的旅行行程,就在显示该行程的界面上解说。该服务(Kotlin、Spring AI)如今仍运行在 [agent.hanjeok.com](https://agent.hanjeok.com)。其完整说明,包括统计八种禁止行为的测试框架以及最终选定 `gpt-4o` 的模型对比,均原样保留。

**[行程解说服务 README →](docs/explainer/README.md)** · [한국어](docs/explainer/README.ko.md)

<br/>

## 👤 作者

<div align="center">

| <img src="https://github.com/hyunolike.png" width="120" height="120"> |
| :---: |
| [hyunolike](https://github.com/hyunolike) |

</div>

本项目是 2026 年开源 AI 智能体全栈课程的项目作品。后续事项在 [issues](https://github.com/hyunolike/hanjeok-agent/issues) 中跟踪。

## 📄 许可证

[MIT](LICENSE) — © 2026 hyunolike.
