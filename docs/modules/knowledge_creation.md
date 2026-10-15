# Knowledge Creation Module

## 1. 模块目标

将用户学习过程中的有效成果转化为可长期复用的知识资产。

核心价值：

学习一次，不只是获得答案，而是沉淀为未来可调用的知识。

---

# 2. 核心流程

---

# 3. 核心领域对象


## LearningEvidence

位置：

learning/evidence.py


职责：

记录一次具体学习事实。


包含：

- session_id
- task
- result
- assessment
- tests_passed
- tests_total


回答：

“发生了什么学习行为？”


---

## LearningProgress

位置：

learning/progress.py


职责：

记录长期成长状态。


包含：

- topic
- learning_count
- understanding_score
- completed_tasks
- practice_count


回答：

“用户成长到了什么程度？”


---

## KnowledgeCandidate

位置：

coach/knowledge/candidate.py


职责：

表示值得沉淀的知识机会。


包含：

- candidate_id
- topic
- candidate_type
- reason
- confidence


回答：

“这个知识是否值得保存？”


---

## KnowledgeArtifact

位置：

coach/knowledge/artifact.py


职责：

最终知识资产。


包含：

- title
- topic
- content
- artifact_type
- source_candidate
- created_at


回答：

“最终保存什么？”


---

# 4. 当前模块组件


## Intent

文件：

coach/knowledge/intent.py


职责：

识别用户是否请求知识创建。


示例：

用户：

“整理成教程”

结果：

knowledge_creation=True


---

## Evidence Builder

文件：

coach/knowledge/evidence_builder.py


职责：

将原始学习数据转换为领域模型。


输入：

学习上下文


输出：

LearningEvidence

LearningProgress


---

## Knowledge Curation Engine

文件：

coach/knowledge/curator.py


职责：

判断学习成果是否达到沉淀标准。


输入：

LearningProgress

LearningEvidence


输出：

KnowledgeCandidate


---

## Generator

文件：

coach/knowledge/generator.py


职责：

Candidate → Artifact


---

## Repository

文件：

coach/knowledge/repository.py


职责：

保存和查询知识资产。


当前支持：

- save
- list_all
- find_by_topic


---

## Workflow

文件：

coach/knowledge/workflow.py


职责：

编排：

Candidate

↓

Artifact

↓

Repository


---

# 5. 当前完成状态


## 已完成

✅ LearningEvidence

✅ LearningProgress

✅ Candidate

✅ Artifact

✅ Artifact Generator

✅ Artifact Repository

✅ Intent Detection

✅ Workflow

✅ Knowledge Runtime Integration


---

# 6. 待完成


## 用户主动创建知识

流程：

用户：

“帮我整理成教程”

↓

Intent

↓

Context

↓

Candidate

↓

Artifact


---

## Agent主动建议沉淀

流程：

学习达到条件

↓

生成Candidate

↓

询问用户

↓

确认后生成Artifact


---

## Knowledge Library Web展示

未来：

首页：

我的知识库

支持：

- 浏览
- 搜索
- 分类
- 调阅


---

# 7. 未来扩展

- Artifact版本管理
- 标签系统
- 向量检索
- 知识评分
- 用户确认状态

# 8. 数据流


用户学习：

LearningEvidence

记录事实


        ↓


LearningProgress

记录成长


        ↓


KnowledgeCandidate

判断是否值得沉淀


        ↓


KnowledgeArtifact

生成知识资产


        ↓


KnowledgeArtifactRepository

保存和查询


## Application Service

coach/knowledge/creation_service.py

职责：

作为用户请求进入知识创建流程的入口。

负责：

User Request
↓
Intent
↓
Workflow
↓
Artifact

✅ Application Service

User Request
 ↓
KnowledgeCreationService
 ↓
Workflow
 ↓
Artifact
 ↓
Repository

Intent                  ✅

Candidate               ✅

Candidate Identity      ✅

Candidate Status        ✅

Confirmation            ✅

Artifact                ✅

Generator               ✅

Repository              ✅

Workflow                ✅

Creation Service        ✅

Intent Detection              ✅

Candidate Creation             ✅

Candidate Identity             ✅

Candidate Lifecycle Status     ✅

Confirmation Flow              ✅

Workflow Guard                 ✅

Artifact Generation            ✅

Artifact Repository            ✅

Creation Service               ✅

领域模型：

✅ LearningEvidence
✅ LearningProgress
✅ KnowledgeCandidate
✅ KnowledgeArtifact
✅ KnowledgeSuggestion


生成能力：

✅ Artifact Generator
✅ Suggestion Builder


流程：

✅ Workflow
✅ Creation Service


存储：

✅ Artifact Repository


生命周期：

✅ Candidate Status
✅ Confirmation Flow


Learning

↓

Candidate

↓

Suggestion

↓

Confirmation

↓

Artifact

↓

Repository

Application Services:

- KnowledgeCreationService
- KnowledgeSuggestionService
- KnowledgeCurationService

Completed:

✅ User request creation
✅ Agent suggestion preparation
✅ Candidate confirmation lifecycle