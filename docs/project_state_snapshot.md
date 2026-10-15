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
