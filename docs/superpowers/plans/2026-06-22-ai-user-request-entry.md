# AI 需求澄清问答入口 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地面向策划、美术等非工程用户的 AI 需求澄清问答入口文档，让用户不用自己整理完整需求，由 AI 通过分类型提问脚本逐步问清楚。

**Architecture:** 本计划只修改 Markdown 文档，不修改 Unity 资产和运行时代码。`docs/ai/user-guide.md` 面向用户解释协作方式，`docs/ai/request-templates.md` 面向 Agent 和用户提供分类型提问脚本，`docs/ai/acceptance-checklists.md` 面向验收阶段提供引导式问题，`docs/ai/project-map.md` 与 `docs/ai/workflows.md` 负责把入口挂到现有 AI 文档体系。

**Tech Stack:** Markdown、现有 AI workflow 文档、PowerShell 验证命令、`rg` 文本扫描、`python tools\ai\ai.py workflow`。

---

## 文件结构

- Create: `docs/ai/user-guide.md`
  - 面向策划、美术和不熟悉工程的人，说明“你只要说想法，AI 会继续问”的协作方式。
- Create: `docs/ai/request-templates.md`
  - 提供 UI、Prefab、美术资源、配置、Bug、只读检查六类任务的 AI 提问脚本。
- Create: `docs/ai/acceptance-checklists.md`
  - 提供执行后的引导式验收问题，帮助用户判断是否接受结果。
- Modify: `docs/ai/project-map.md`
  - 在文档地图中加入三个新入口文档。
- Modify: `docs/ai/workflows.md`
  - 增加“非工程用户需求澄清工作流”，声明请求一开始进入 workflow，问答和摘要记录在 workflow 内完成。

## 任务 1：创建用户指南

**Files:**
- Create: `docs/ai/user-guide.md`

- [ ] **Step 1: 创建 `docs/ai/user-guide.md`**

使用 `apply_patch` 新增文件，内容如下：

```markdown
# AI 使用指南

本文给策划、美术和不熟悉工程的人使用。

## 你不需要一次说完整

你可以先用一句话告诉 AI 你的想法，例如：

- 我想做一个背包界面。
- 帮我整理这批图标。
- 这个按钮点了没有反应，帮我看看。
- 解释一下这个 Prefab 是做什么的。

AI 会根据你的描述继续提问。你可以回答“不知道”，AI 会给出建议，或者告诉你这个问题为什么必须确认。

## AI 会怎么帮你问清楚

AI 会先判断你的任务类型：

- 新增或修改 UI。
- 创建或修改 Prefab。
- 导入或整理美术资源。
- 调整数值或配置。
- 复现和修复 Bug。
- 只读解释或检查。

然后 AI 会一轮一轮问你短问题。每轮只问少量问题，优先让你选择，而不是要求你写完整文档。

## 你需要重点确认什么

- 目标：你想让玩家或团队看到什么结果。
- 对象：要改哪个界面、Prefab、资源、配置或功能。
- 路径：如果你知道文件或资源路径，请告诉 AI；不知道也可以说不知道。
- 素材：是否有图片、音效、模型、参考图或现有对象。
- 覆盖：是否允许覆盖、移动或删除已有内容。
- 验收：你准备怎么判断这件事做对了。

## AI 修改前会先总结

在真正修改前，AI 必须把问答结果汇总给你看。摘要至少包括：

- 任务类型。
- 目标。
- 目标对象或建议路径。
- 已确认的信息。
- 仍不确定但可默认处理的信息。
- 风险点。
- 验收方式。

你的请求一开始就应进入项目规定的 workflow。需求澄清和摘要也在 workflow 内完成；你确认摘要后，AI 才能继续进入计划或修改执行阶段。

## 哪些操作需要特别确认

以下操作风险较高，AI 必须明确提示你：

- 修改场景。
- 覆盖 Prefab。
- 修改 ProjectSettings。
- 修改 Package manifest。
- 批量移动、删除或重命名资源。
- 生成会影响运行时行为的代码。

## 项目安全边界

AI 不能直接乱改 Unity 资产。涉及场景、Prefab、`.asset`、`.meta`、ProjectSettings 或编辑器状态的修改，必须通过项目规定的 `Unity Editor Adapter` 或已验证命令执行。

如果 AI 只是解释问题、整理需求或写文档，一般不需要 Unity 执行层。
```

- [ ] **Step 2: 验证用户指南可读取**

Run:

```powershell
Get-Content -Encoding UTF8 -LiteralPath "D:\foraiproject\docs\ai\user-guide.md" | Out-Null
```

Expected: 退出码为 `0`，没有编码或路径错误。

- [ ] **Step 3: 提交用户指南**

Run:

```powershell
git add docs/ai/user-guide.md
git commit -m "docs: add ai user guide"
```

Expected: 提交成功，只包含 `docs/ai/user-guide.md`。

## 任务 2：创建分类型提问脚本

**Files:**
- Create: `docs/ai/request-templates.md`

- [ ] **Step 1: 创建 `docs/ai/request-templates.md`**

使用 `apply_patch` 新增文件，内容如下：

````markdown
# AI 需求提问脚本

本文给 AI 和用户共同使用。它不是要求用户自己填完整表格，而是指导 AI 按任务类型主动提问。

## 通用规则

- 先判断任务类型，再进入对应脚本。
- 每轮只问一到三个短问题。
- 优先使用选择题。
- 用户回答“不知道”时，给出安全默认建议。
- 修改前必须输出需求摘要。
- 修改型任务仍必须进入 `Workflow Engine`。

## 通用第一问

如果用户只说了一句模糊需求，先问：

```text
你这次想做的是哪一类？
1. 新增东西
2. 修改已有东西
3. 修复问题
4. 整理资源或文档
5. 只想了解现状
```

## UI 页面新增或修改

适用描述：

- 做一个背包界面。
- 改一下登录弹窗。
- 加一个活动入口。

提问顺序：

1. 这是新界面，还是修改已有界面？
2. 这个界面什么时候打开，给玩家完成什么事情？
3. 页面上需要显示哪些信息？
4. 有哪些按钮或可点击区域？点击后分别发生什么？
5. 有没有参考图、现有页面、Prefab 或素材路径？
6. 是否允许创建新的脚本、Prefab 或 Addressables 条目？
7. 你希望怎么验收这个页面？

用户回答“不知道”时：

- 路径不知道：AI 根据项目结构建议路径，并在摘要中标记为“建议路径，待用户确认”。
- 交互不知道：默认先做静态展示，不实现业务行为。
- 是否允许创建 Prefab 不知道：默认不覆盖已有 Prefab，只提出计划。

需求摘要格式：

```text
任务类型：UI 页面新增或修改
目标：
目标路径或建议路径：
显示内容：
交互行为：
输入素材：
默认处理：
风险点：
验收方式：
```

## Prefab 创建或修改

提问顺序：

1. 你要创建新 Prefab，还是修改已有 Prefab？
2. Prefab 用在什么场景或系统里？
3. 目标路径或现有 Prefab 路径是什么？
4. 需要哪些组件、子物体或引用资源？
5. 是否允许覆盖已有 Prefab？
6. 是否有命名规则或参考对象？
7. 验收时要看到什么？

默认处理：

- 不知道路径时，只建议路径，不直接创建。
- 不知道是否覆盖时，默认禁止覆盖。
- 修改已有 Prefab 时，必须提示风险并请求确认。

## 美术资源导入或整理

提问顺序：

1. 资源类型是什么，例如图标、立绘、音效、材质或模型？
2. 资源现在在哪里，目标放到哪里？
3. 是否需要改名？命名规则是什么？
4. 是否需要加入 Addressables 分组？
5. 是否允许移动或覆盖已有资源？
6. 导入后怎么判断结果正确？

默认处理：

- 默认不删除旧资源。
- 默认不覆盖同名资源。
- 默认不直接改 `.meta`。
- Addressables 分组不明确时，只生成计划并要求确认。

## 数值或配置调整

提问顺序：

1. 要调整哪个系统、角色、道具或功能？
2. 当前数值是多少？目标数值是多少？
3. 数值来源在哪里，例如表格、ScriptableObject、JSON、代码常量？
4. 调整是否影响线上或热更新内容？
5. 验收时看哪个表现？

默认处理：

- 不知道配置位置时，先只读扫描并报告候选位置。
- 不知道目标数值时，不能直接修改。
- 涉及运行时行为时，必须要求验证。

## Bug 复现和修复

提问顺序：

1. 你看到了什么异常现象？
2. 从打开项目到出现问题，需要哪些步骤？
3. 你期望看到什么结果？
4. 实际结果是什么？
5. 这个问题是否稳定复现？
6. 最近是否改过相关 UI、Prefab、配置或脚本？
7. 修复后你希望用什么方式验收？

默认处理：

- 复现步骤不完整时，先帮用户补齐复现描述。
- 不能复现时，先做只读排查，不直接修改。
- 修复运行时行为时，必须补充相关测试或验证命令。

## 只读解释或检查

提问顺序：

1. 你想了解哪个对象、系统或文件？
2. 你希望 AI 用什么方式解释：简单说明、流程图、风险点、修改建议？
3. 是否只读，不做任何修改？

默认处理：

- 默认只读。
- 如果解释过程中发现需要修改，必须重新进入修改型 workflow。
````

- [ ] **Step 2: 验证提问脚本可读取**

Run:

```powershell
Get-Content -Encoding UTF8 -LiteralPath "D:\foraiproject\docs\ai\request-templates.md" | Out-Null
```

Expected: 退出码为 `0`。

- [ ] **Step 3: 提交提问脚本**

Run:

```powershell
git add docs/ai/request-templates.md
git commit -m "docs: add ai request question scripts"
```

Expected: 提交成功，只包含 `docs/ai/request-templates.md`。

## 任务 3：创建引导式验收清单

**Files:**
- Create: `docs/ai/acceptance-checklists.md`

- [ ] **Step 1: 创建 `docs/ai/acceptance-checklists.md`**

使用 `apply_patch` 新增文件，内容如下：

```markdown
# AI 结果验收问答清单

本文帮助策划、美术在 AI 执行后判断结果能不能接受。

## 通用验收问题

AI 完成后，应带用户确认：

1. 本次实际修改了哪些文件或资源？
2. 哪些验证已经运行，结果是什么？
3. 你需要在 Unity 或游戏里检查哪个入口？
4. 你看到的结果是否符合需求摘要？
5. 是否有未验证或需要人工判断的部分？
6. 是否接受本次改动，还是需要继续调整？

## UI 验收

1. 页面能否打开？
2. 文案、图标、数量、按钮是否符合需求摘要？
3. 点击按钮后结果是否符合预期？
4. 不同分辨率下是否有明显错位？
5. 是否有报错或空引用？

## Prefab 验收

1. Prefab 是否在约定路径？
2. 名称是否符合规则？
3. 组件、子物体、引用资源是否完整？
4. 是否覆盖了已有 Prefab？
5. 覆盖是否已经由用户明确确认？

## 美术资源验收

1. 资源是否放在目标路径？
2. 命名是否符合规则？
3. 引用是否没有丢失？
4. 是否加入了正确的 Addressables 分组？
5. 是否没有误删、误移动或误覆盖其他资源？

## 数值或配置验收

1. 目标数值是否已修改为需求摘要中的值？
2. 修改位置是否正确？
3. 游戏表现是否符合预期？
4. 是否有测试或验证命令证明结果？

## Bug 修复验收

1. 原始复现步骤是否还能触发问题？
2. 修复后实际结果是否等于期望结果？
3. 是否运行了相关测试或编译验证？
4. 是否有新的异常或副作用？

## 不能接受的情况

以下情况不能直接接受：

- AI 没有列出实际改动范围。
- AI 没有说明验证结果。
- 修改了高风险对象但没有风险确认。
- 用户无法复现 AI 声称的结果。
- 出现报错、资源丢失、引用丢失或非预期覆盖。
```

- [ ] **Step 2: 验证验收清单可读取**

Run:

```powershell
Get-Content -Encoding UTF8 -LiteralPath "D:\foraiproject\docs\ai\acceptance-checklists.md" | Out-Null
```

Expected: 退出码为 `0`。

- [ ] **Step 3: 提交验收清单**

Run:

```powershell
git add docs/ai/acceptance-checklists.md
git commit -m "docs: add ai acceptance checklists"
```

Expected: 提交成功，只包含 `docs/ai/acceptance-checklists.md`。

## 任务 4：更新 AI 文档入口

**Files:**
- Modify: `docs/ai/project-map.md`
- Modify: `docs/ai/workflows.md`

- [ ] **Step 1: 更新 `docs/ai/project-map.md`**

在 `## 当前重要路径` 后增加：

```markdown
## 面向非工程用户的 AI 入口

- `docs/ai/user-guide.md`：给策划、美术看的 AI 协作说明。
- `docs/ai/request-templates.md`：AI 主动澄清需求时使用的分类型提问脚本。
- `docs/ai/acceptance-checklists.md`：AI 执行完成后带用户验收的问答清单。
```

- [ ] **Step 2: 更新 `docs/ai/workflows.md`**

在 `## 标准修改工作流` 前增加：

```markdown
## 非工程用户需求澄清工作流

适用于策划、美术用自然语言提出的模糊需求。

1. 用户先用一句话描述想法。
2. AI 根据 `docs/ai/request-templates.md` 判断任务类型并逐步提问。
3. 用户可以回答“不知道”；AI 给出安全默认建议，或说明为什么必须确认。
4. AI 汇总需求摘要，包括目标、对象、路径、输入素材、默认处理、风险点和验收方式。
5. 需求澄清和摘要记录在对应的 `question` 或 `auto` workflow 内完成。
6. 用户确认需求摘要后，AI 才能继续进入 `plan`、`change` profile 或修改执行阶段。
7. 修改型任务仍必须经过 `risk review`、必要的人工 gate、`workflow preflight` 和验证。
8. 执行完成后，AI 使用 `docs/ai/acceptance-checklists.md` 带用户验收。

该工作流只降低表达门槛，不降低安全要求。
```

- [ ] **Step 3: 验证入口文档可读取**

Run:

```powershell
Get-Content -Encoding UTF8 -LiteralPath "D:\foraiproject\docs\ai\project-map.md" | Out-Null
Get-Content -Encoding UTF8 -LiteralPath "D:\foraiproject\docs\ai\workflows.md" | Out-Null
```

Expected: 两个命令退出码为 `0`。

- [ ] **Step 4: 提交入口更新**

Run:

```powershell
git add docs/ai/project-map.md docs/ai/workflows.md
git commit -m "docs: link guided ai request workflow"
```

Expected: 提交成功，只包含两个入口文档。

## 任务 5：最终验证

**Files:**
- Read: `docs/ai/user-guide.md`
- Read: `docs/ai/request-templates.md`
- Read: `docs/ai/acceptance-checklists.md`
- Read: `docs/ai/project-map.md`
- Read: `docs/ai/workflows.md`

- [ ] **Step 1: 读取所有新增和更新文档**

Run:

```powershell
Get-Content -Encoding UTF8 -LiteralPath "D:\foraiproject\docs\ai\user-guide.md" | Out-Null
Get-Content -Encoding UTF8 -LiteralPath "D:\foraiproject\docs\ai\request-templates.md" | Out-Null
Get-Content -Encoding UTF8 -LiteralPath "D:\foraiproject\docs\ai\acceptance-checklists.md" | Out-Null
Get-Content -Encoding UTF8 -LiteralPath "D:\foraiproject\docs\ai\project-map.md" | Out-Null
Get-Content -Encoding UTF8 -LiteralPath "D:\foraiproject\docs\ai\workflows.md" | Out-Null
```

Expected: 全部命令退出码为 `0`。

- [ ] **Step 2: 扫描未完成标记**

Run:

```powershell
rg -n "T[B]D|TO[D]O|FIX[M]E|待[定]|占[位]" docs\ai\user-guide.md docs\ai\request-templates.md docs\ai\acceptance-checklists.md docs\ai\project-map.md docs\ai\workflows.md
```

Expected: 退出码为 `1`，无输出，表示没有命中。

- [ ] **Step 3: 检查关键短语**

Run:

```powershell
rg -n "AI 会根据|提问脚本|需求摘要|验收问答|Workflow Engine|risk review|workflow preflight|Unity Editor Adapter" docs\ai\user-guide.md docs\ai\request-templates.md docs\ai\acceptance-checklists.md docs\ai\project-map.md docs\ai\workflows.md
```

Expected: 能看到这些关键短语分布在对应文档中，证明文档覆盖问答式澄清、验收和安全边界。

- [ ] **Step 4: 检查 git 状态**

Run:

```powershell
git status --short
```

Expected: 没有未提交的计划内文件改动。

## 验收标准

- `docs/ai/user-guide.md` 说明用户不用一次说完整，AI 会逐步提问。
- `docs/ai/request-templates.md` 覆盖 UI、Prefab、美术资源、配置、Bug、只读检查六类提问脚本。
- `docs/ai/acceptance-checklists.md` 提供通用和分类型验收问答。
- `docs/ai/project-map.md` 能引导用户找到三个入口文档。
- `docs/ai/workflows.md` 定义非工程用户需求澄清工作流。
- 文档没有未完成标记。
- 没有 Unity 资产、ProjectSettings、package manifest 或运行时代码改动。
