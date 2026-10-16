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

## 本次新增，待用户验收

注册预览的滚动 60 秒请求额度：同一来源 GET 每分钟 30 次、POST 10 次，整个服务进程分别 240/120 次。超限返回不回显输入的 429 提示及剩余等待时间，拒绝不延长等待。额度在请求体解析与字段校验前判断，GET/POST 独立，内存有界且并发安全；本机启动关闭任意代理头改写来源。无申请保存、无密码哈希计算、无真实发信、无登录会话。

详见 [注册预览请求次数限制](registration-rate-limits.md)、[注册表单防伪提交保护](registration-form-protection.md) 与 [注册表单预览](registration-form-preview.md)。当前网页仍不保存申请，正式注册、登录、欢迎页、找回密码和公开部署仍未完成。下一小步拟补注册浏览器与待验证申请的归属关联；之后连接网页保存、重发与失败恢复并接通 SMTP。旧开发注册入口公开前也须关闭或保护；当前内存限流只适用于本机单进程，不能直接作为公网多进程方案。

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
