# 最新产品开发状态（2026-10-16）

当前产品方向是面向成人自学与个人成长的长期 AI Coach，兼顾聊天、主题学习与个人知识积累。第一版使用邮箱和密码，暂不接入手机号或短信登录。开发按小步骤进行：说明方案、用户同意、实现与测试、用户验收后提交同步。

## 已验收并同步

- 首页、邮箱登录及注册的基础页面与本机启动入口。
- 内部密码哈希与校验、一次性邮箱验证凭证、受保护的网页确认。
- 163 加密发信模块及 `python -m api.mail_test` 独立测试工具。
- 用户已在本机完成真实邮件收信、点击和服务端确认，终端显示测试通过。
- 邮箱阶段保存点为开发分支 `codex/email-entry-pages` 的 `91e5886`，已同步 GitHub；尚未合并到主分支。
- 注册表单的只读填写检查及邮箱验证准备页已验收并同步，保存点为 `b6d6b3d`。字段错误时提示，密码不回填；通过后明确提示邮件尚未发送、账户尚未创建。
- 内部待验证注册申请保存与读取已验收并同步，保存点为 `a873183`。只保存密码安全哈希，默认 1 小时过期；重复和并发申请不能替换尚有效内容或覆盖已有账户。
- 内部注册申请与一次性邮箱凭证绑定、确认后原子开户已验收并同步，保存点为 `12569f9`。1974 项测试通过，网页申请提交尚未接通。
- 注册专用的受保护网页确认页已验收并同步，保存点为 `e56a1b7`。2009 项测试通过，浏览器已检查确认、成功和链接失效页面及手机排版。
- 注册表单 CSRF 与浏览器上下文已验收并同步，保存点为 `768920c`。2041 项全量回归通过，最终提示页调整后 303 项相关回归通过，浏览器已走通异常拒绝与恢复。
- 注册预览请求次数限制已验收并同步，保存点为 `fe7146d`。2058 项全量回归通过，已检验并发、来源防绕过、限流提示和真实等待后的恢复。
- 待验证申请内部浏览器归属已验收并同步，保存点为 `3c10c4b`。2089 项全量回归通过，编号单独不能查询或重发带绑定申请，邮件仍可跨浏览器明确确认。
- 网页保存带归属的待验证申请已验收并同步，保存点为 `c586bbd`。2106 项全量回归通过，等待页显示遮盖邮箱与有效期，重复提交不改写；浏览器已检验桌面和手机页面。本机网页仍不发信、不创建正式账户。
- 内部注册邮件状态和失败重试保护已验收并同步，保存点为 `bb5a39a`。2138 项全量回归通过，发送中、服务器已接收、明确失败与不确定结果持久保存，异常中断不会盲目重发。
- 等待页邮件操作、状态和失败重试已验收并同步，保存点为 `bd5bc1f`。2174 项全量回归通过，浏览器检验桌面、320 像素手机布局，以及实际等待冷却期后的主动重试和模拟确认开户。

## 账户与统一页面阶段已验收并同步

独立的账户完整试用已实现：提供已验证邮箱的密码登录、服务端可撤销的 8 小时会话、本人欢迎页和受防伪保护的退出。2223 项全量回归通过，登录和欢迎模板调整后的页面回归通过，浏览器已检验桌面与 320 像素手机页面。用户现已反馈完成本人 163 邮箱的真实注册、收信确认、登录与退出，按该反馈记录账户流程验收通过；本轮不读取或保存授权码。账户工具仍使用临时数据库，不修改原有学习资料或 `.env`。

用户进一步确认产品交互：聊天、主题学习和围绕书籍资料的讨论应共用一个对话框。已将登录后的三张分离功能卡调整为一个统一对话工作区，侧边提供知识库、资料与书籍标识；知识资产归入知识库。账户与该页面阶段已验收，保存点 `6f2c713` 已同步开发分支到 GitHub。

详见 [统一对话方向](unified-conversation-product.md)、[账户试用](account-trial.md) 与 [等待页邮件操作](registration-web-mail.md)。新账户应用不加载旧的按用户编号访问的开发路由，默认不加载 AI 或 `.env` 配置。`python -m api.run` 仍是旧本机开发入口，不能作为对外账户服务公开部署。

## 统一对话与滚动历史：已验收

根据最新页面反馈，移除账户就绪横条和中间介绍、折叠历史与容量说明，改成独立滚动聊天区。打开和发送后定位最新内容，上滑每批追加 40 轮历史，按账户校验，不调用 AI。学习主题、进度、下一步和资料状态保留在学习栏，必要使用说明收到右侧折叠项。单次输入最多 2000 字，后台不因超过 40 轮清除记录；实际容量受本机存储限制。用户已确认继续下一步，本轮将该调整与持续对话功能一起保存到开发分支；具体保存点以 Git 提交记录为准。

用户明确要求统一对话始终保留可见的学习主题、进度、引用资料与快速续学。本步实现按账户保存的统一对话、独立学习记录、转题后继续学习和持续本机入口 `python -m api.coach_run`。进度记录“已讨论什么、下一步什么”，不虚构掌握程度；资料栏显示“未关联资料”，书籍上传、检索和知识库保存尚未接入。

模拟入口隔离真实邮件与 AI；真实 AI 需显式 `--ai` 启用，只有用户发送或续学时调用，可能产生 API 费用。首次真实持续注册需 `--register`，终端隐藏输入本人 163 授权码；默认 `data/coach-local` 和模拟目录已加入 Git 忽略。原临时账户不迁移，旧数据和配置不改写。聊天区每批加载 40 轮，向上滚动继续读取更早记录，不按轮数自动删除；模型接收有长度限制的最近对话及学习摘要；完整长期画像、跨设备同步、资料检索、密码找回和公开部署仍待完成。

最终 2287 项全量回归通过，119 项相关检验通过；自动检验不调用真实 SMTP 或计费 AI。桌面模拟流程已检验主题学习、转题保留与点击续学，手机端提供紧凑学习速览；最终界面调整另做相关回归。真实 AI 的自然交流、摘要质量与转题识别仍需实际体验。实现说明见 [统一对话与续学](coach-dialogue.md)。用户建议按完整功能适当增大粒度；仍先说明方案与效果，本阶段已完成检验与用户验收，后续继续按确认方案、实现检验、验收保存推进。

下一步拟接通“资料与书籍”：按账户持久保存原始资料，围绕所选资料在原对话中交流，并展示真实引用。格式范围、页面效果及实现边界需先与用户确认，尚未实施。

下面保留早期技术状态作为历史背景，不代表当前产品开发步骤。

---

继续 Personal Growth AI Coach 项目。

请读取下面的项目状态，并从当前进度继续，不要重新讲基础。

【项目状态】
 Personal Growth AI Coach 项目状态

## 项目目标

构建一个长期陪伴型 AI Coach Agent。

核心能力：

- Memory
- Planning
- Evaluation
- Context Engineering
- Tool Calling

当前重点：
Context Intelligence Layer。

---

# 当前已完成模块

## 1. Memory Retrieval

已完成：

- memory context selection
- relevance ranking
- retrieval evaluation

包括：

- policy filtering
- ranking
- recall@k
- precision@k
- semantic gap

Controller 已接入：

memory retrieval → ranking → top_k → prompt injection

测试全绿。

---

# 当前开发阶段

Context Engineering。

架构：

Context Sources
    |
    ↓

Context Assembly
    |
    ↓

Context Projection
    |
    ↓

Conflict Detection
    |
    ↓

Conflict Resolution
    |
    ↓

Prompt Context

---

# Context Assembly

文件：

agent/context_assembly.py

已完成：

AssembledContext

包含：

- conversation_context
- learning_continuity
- memory_context

支持：

- source_priority
- source_budget

---

# Context Projection

文件：

agent/context_projection.py

已完成：

Learning Continuity projection：

支持：

current:

- learning.current_topic
- learning.current_understanding
- learning.current_difficulty
- learning.current_next_step

previous:

- learning.previous_topic
- learning.previous_understanding
- learning.previous_difficulty
- learning.previous_next_step

Memory projection：

支持：

- learning.completed_domain
- learning.completed_understanding
- learning.completed_journeys

---

# Context Conflict

文件：

agent/context_conflict.py

当前能力：

## Detection

detect_field_conflict()

detect_projection_conflicts()

## Resolution

ContextConflictResolution

已有：

resolve_context_conflict()

负责：

candidate + source_priority

新增：

resolve_projection_conflict()

负责：

projected_contexts + field_name

并调用 Field Policy。

---

# Context Policy

文件：

agent/context_policy.py

当前支持：

## Learning current

字段：

learning.*

priority:

conversation

> 

learning_continuity

> 

memory

## Completed learning

字段：

learning.completed_

priority:

memory

> 

conversation

## User preference

字段：

user.preference.*

priority:

conversation

> 

memory

测试：

tests/test_context_policy.py

当前：

5 passed

---

# 当前最新任务

正在进行：

Policy Registry 重构。

目标：

从：

if field_name.startswith()

升级为：

FIELD_POLICY_RULES

预计结构：

FIELD_POLICY_RULES = [

(
"learning.completed_",
COMPLETED_LEARNING_POLICY
),

(
"user.preference.",
USER_PREFERENCE_POLICY
),

(
"learning.",
LEARNING_POLICY
),

]

保持行为不变。

验收：

pytest tests/test_context_policy.py

保持：

5 passed

然后：

pytest tests/test_context_conflict.py

保持：

13 passed

---

# 当前开发原则

遵循：

RED → GREEN → REFACTOR

不要提前扩大范围。

当前不要做：

- Runtime Integration
- Controller 修改
- 新增大量 Policy
- Resolver 大重构

下一步：

完成 Policy Registry 重构。
