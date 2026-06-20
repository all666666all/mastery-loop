# mastery-loop

*[English](README.md) · 中文*

**把任何学习材料变成"真的能让你记住"的间隔重复系统——而不是又一堆好看的笔记。**

`mastery-loop` 是一个可移植的 AI **技能（skill）**：一份 `SKILL.md` + 一个小而经过测试的 Python 引擎。把它对准课件（PPTX）、教材 PDF、笔记、转写稿，或一整个课程文件夹。它先建一张由浅入深的**学习地图**，然后每天跑一个简短的**主动回忆循环**——由真正的遗忘曲线调度器驱动，带交错练习、费曼自检、校准和错题驱动复习——并且会**适应每个学习者的学习方式**。为完全零基础的初学者设计。

> 诚实的承诺：不是"快 10 倍"，而是**每小时学到的东西留存得更久**——办法是把"真正有效但费劲"的六件事变成最省力的路径。

---

## 为什么需要它

开源 AI 学习工具清晰地分成两派，而"记住"恰恰死在两派中间的缝里：

| 流派 | 代表 | 做对了什么 | 缺了什么 |
|---|---|---|---|
| **生成器** | book-to-skill、ko-lesson、NotebookLM 克隆、PDF→Anki 工具 | 把材料变成笔记/卡片/测验 | 没有调度器、没有回忆循环——"做出材料" ≠ "学会了" |
| **调度器** | Anki、Obsidian-Spaced-Repetition | 真正的 SM-2/FSRS 遗忘曲线复习 | 没有 AI——每张卡都要你手写 |

几乎没有东西**两者兼有**，还放在你自己拥有的文件里、做成即插即用的技能。`mastery-loop` 就是这座桥：AI 生成 **加** 真调度器，合进一个每日循环。

## 怎么用

你永远只做两件事，用你自己的语言：

1. **"帮我学 ‹某主题›"** → 它读你的材料，建地图（由浅入深），为第一单元写主动回忆题（每题都先过一道**验证门**，杜绝把错题刷上几周），然后开始教第一块。
2. **"今天"**（每天约 15–30 分钟）→ 它从调度器取出今天**交错排列**的队列，先问你再给答案，给你判分，当场纠错（高信心的错误有特殊处理），再小剂量加新内容，告诉你哪里"自以为会其实不会"，并**把它学到的关于你的东西沉淀下来**，让明天更聪明。

你不碰文件、脚本、JSON，也不用 Obsidian。全程在对话里完成。你的知识库是你完全拥有的纯 Markdown + JSON（兼容 Obsidian，但 Obsidian 是可选的）。

## 安装（平台无关）

`mastery-loop` 是一个标准技能文件夹，放到你的 agent 查找技能的位置即可：

- **Claude Code：** `git clone https://github.com/<你>/mastery-loop ~/.claude/skills/mastery-loop`
- **Codex：** `git clone https://github.com/<你>/mastery-loop ~/.codex/skills/mastery-loop`
- **Claude Cowork / 桌面端：** 从 releases 安装 `mastery-loop.skill` 包，或把文件夹放进你的技能目录。

然后说：*"用 mastery-loop 帮我学 ‹你的主题›。"*

依赖：`python3`（调度器仅用标准库）。要导入二进制格式，按你的材料类型装对应读取库：`pip install pypdf`（PDF）、`python-pptx`（幻灯片）、`ebooklib`（EPUB）。PPTX/EPUB/TXT 有零依赖回退；**PDF 需要 pdftotext / pypdf / pdfminer 之一**。万一抽取失败，agent 会直接读文件——抽取只是便利，不是必经关卡。

## 目录结构

```
mastery-loop/
├── SKILL.md                  # 技能本体：完整的循环
├── scripts/
│   ├── scheduler.py          # SRS 引擎（FSRS-5 默认 + SM-2，纯标准库）
│   ├── fsrs.py               # FSRS-5 调度数学（可独立自检）
│   └── extract.py            # 材料 → 文本（PDF / PPTX / EPUB / TXT，带回退）
├── references/
│   ├── pedagogy.md           # 六大机制 + 科学依据（先读这个）
│   ├── item-writing.md       # 怎么写"真正能教会人"的题
│   └── scheduler.md          # 调度器完整命令参考
├── templates/                # 地图 / 学习者档案 / 约束 / 会话日志
└── tests/
    └── test_scheduler.py     # 运行：`python3 tests/test_scheduler.py`
```

## 引擎

`scheduler.py` 掌管所有"时机和状态"，这样模型永远不用去猜"他是不是已经忘了？"（这个问题 LLM 跨会话答得很不一致）。默认运行 **FSRS-5**——现代调度器，通过建模记忆的*稳定度*和*难度*，在同等留存下比 SM-2 少约 20–30% 的复习量（用 `--algorithm sm2` 仍可切回 SM-2）——再加三项有证据支撑的增强：

- **考试地平线缩放**——把间隔压向截止日，保证每题在考前都还有一次间隔复习（绝不变成临时抱佛脚式的倾倒）；
- **高信心错误处理**——"自信却答错"是最容易修好的错误（hypercorrection），它会被尽快重测并换个问法；
- **交错**——每日队列混合主题，让你练的是"**选**哪个方法"，而不是机械执行熟悉的那个。

引擎是确定性的、有单元测试（`tests/test_scheduler.py`）。

## 设计原则

- **对话是界面，文件是存储。** 初学者不该为了学习先去学 Obsidian。循环在对话里跑，文件只是你拥有的、可移植的持久状态。
- **每日循环，绝不"一次性生成全部"。** 全量预生成感觉很高效，实则导致死记硬背式突击。本技能从设计上拒绝它。
- **存任何东西前先过验证门。** 错题会被刷上好几周，所以生成的题在入库前要对照原文自我反驳。
- **系统会复利。** 每次会话都会更新学习者档案和约束文件（从真实错误里提炼的规则），下次自动加载——用得越多，越懂怎么教**你**。
- **诚实的教学法。** 检索、间隔、交错、讲解、反馈、纠错——都是有真证据的方法。不搞"学习风格"，不吹"快 10 倍"。

## 致谢与灵感

站在三个优秀开源项目的肩膀上——并补上它们共同缺失的那一环（没有"留存循环"）：
[ko-lesson](https://github.com/Liunian06/ko-lesson)（来源标注纪律、反馈闭环）、
[book-to-skill](https://github.com/virgiliojr94/book-to-skill)（先抽取后综合、按需引用文件、token 预算）、
[knowledge-wiki-template](https://github.com/CatChen/knowledge-wiki-template)（确定性引擎 / LLM 判断分工、增量状态、维护型技能）。

教学法依据：Roediger & Karpicke (2006)、Karpicke & Roediger (2008)、Dunlosky 等 (2013)、
Cepeda 等 (2006/2008)、Rohrer & Taylor (2007)、Bjork & Bjork (2011)、Metcalfe（hypercorrection）、
Wilson 等 (2019)。详见 `references/pedagogy.md`。

## 许可证

MIT，见 [LICENSE](LICENSE)。
