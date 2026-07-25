# Learning Log

（用途：每天增加，不覆盖。这是动态成长记录。）

日期：2026-07-23
Day29

主题：
LLM调用层与Agent最小原型

学习成果：

完成Personal Growth AI Coach最小架构设计。

理解：

main.py负责用户入口。

controller.py负责流程协调。

llm_client.py负责模型通信。

关键认知：

Python+LLM只是大模型应用。

完整Agent需要：

Memory
Tool
Evaluation

形成闭环。

日期：2026-07-22
Day28

主题：
LLM调用层与Agent最小闭环

核心理解：

llm_client负责连接模型，不负责业务逻辑。

system_prompt定义Agent角色和行为规则。

user_message表达用户当前需求。

完成：

理解Python调用DeepSeek API架构。

当前阶段：

从Agent架构设计进入LLM工程实现阶段。

下一步：

实现真实API调用。

日期：2026-07-21
Day26

主题：
LLM调用层设计

核心理解：

llm_client负责连接大模型。
Controller负责流程协调。
LLM负责理解、推理和决策。

完成：

设计Personal Growth AI Coach v0.2运行流程。

新增概念：

Structured Output

下一步：

实现真实API调用。

日期：2026-07-20

Day23

主题：

LLM接入Agent架构

核心理解：

LLM不是Agent本身。

LLM负责理解、推理、决策。

Controller负责流程控制。

llm_client负责连接模型。

实践：

完成Personal Growth AI Coach v0.2架构设计。

当前问题：

需要进入真实API调用阶段。

## 2026-07-15

主题：

Tool Calling与Agent工具设计

## 今日学习内容

理解：

Tool不是知识。

Tool是Agent连接外部世界和执行动作的能力接口。

理解模块区别：

Memory：

保存过去信息。

Tool：

获取外部信息或执行动作。

Planning：

决定下一步行动。

Evaluation：

判断结果。

## 今日输出

完成：

个人成长AI导师Agent工具设计。

设计：

1. 学习记录查询工具

2. 学习反馈保存工具

3. 能力评估工具

## 理解程度

90/100

## 应用程度

75/100

## 当前困难

Tool和Memory边界仍需加强。

尚未完成：

真实API调用。

## 下一步

进入：

Python模拟Tool Calling。
