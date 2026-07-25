# Experience Memory

（用途：保存长期有效的方法。这是最容易被忽视，但价值最高的部分。）

## 有效学习方法

### 方法1

理论
↓

案例

↓

输出

↓

反馈

↓

优化

效果：

高。

---

### 方法2

项目驱动学习。

原则：

遇到真实需求，再学习相关技术。

---

## 无效学习方式

大量阅读：

↓

知识增加

↓

无法应用

↓

动力下降

原因：

缺少反馈。

---

## Agent设计原则

Agent设计第一原则：

所有模块必须服务用户目标Goal。

技术不是目的，而是实现目标的手段。

原则2：

先定义目标，再设计功能。

原则3：

Memory让Agent了解用户。

原则4：

Knowledge Base提供领域知识。

原则5：

Tool扩展行动能力。

原则6：

Evaluation形成优化闭环。



## 当前最大杠杆点

持续产生真实项目。

原因：

项目会推动：

学习
↓

应用
↓

反馈

形成增强回路。

## Agent设计原则

- Tool不是能力本身。

- Tool是能力的调用接口。

- Memory负责保存数据。

- Tool负责访问数据。

- Agent通过Tool使用Memory。
  
  

## Agent核心原则

  LLM负责理解、推理、决策。

  Tool负责执行动作。

  Memory负责保存状态。

  Agent通过LLM决定何时调用Tool。



# Tool设计原则

1.
Tool是能力接口，不是业务目标。

2.
Tool提供事实或执行动作，不负责复杂判断。

3.
Tool应该隐藏具体实现方式，提高系统替换能力。

4.
一个Tool尽量只负责一个明确职责。

5.
复杂能力应该拆分成多个Tool，由LLM组合使用。



## Tool Schema设计经验

1. Tool不一定需要参数。
   如果获取当前状态，可以设计为空参数。

2. 参数设计原则：
   只提供完成任务必须的信息，避免增加LLM决策复杂度。

3. Agent能力不在Tool数量，而在于根据目标选择正确Tool组合。
   
   # Agent模块职责
   
   Controller：
   负责协调系统运行流程。
   LLM：
   负责理解、推理、判断、选择行动。
   Planning：
   负责制定行动步骤。
   Tool：
   负责执行外部动作或获取信息。
   Memory：
   负责保存历史状态。
   Skill：
   负责具体解决问题的能力。
   Evaluation：
   负责评价结果并反馈优化。
   问题：
   容易混淆LLM和Controller职责。
   正确理解：
   LLM负责理解、推理、决策。
   Controller负责流程控制、调用工具、管理状态。
   重要认知：
   Prompt不应该绑定具体实现。
   例如：
   不要告诉LLM：
   读取user_profile.md。
   应该告诉：
   获取用户状态。
   具体如何获取由Controller和Memory模块决定。
   原因：
   保持系统可扩展。
   
   

   Agent架构认知：

   Memory不是Tool。

   Memory代表Agent自身状态。

   Tool代表可调用能力接口。

   但是工程实现中，Memory访问可以封装成Tool。

   Controller负责调度。

   LLM负责判断和推理。

   高级Agent通常采用固定流程+LLM动态决策混合模式。

更新日期：2026.7.21

软件设计原则：

模块之间通过接口连接。

不要让Controller直接依赖具体模型。

llm_client负责模型通信。

Controller负责流程协调。

这样系统可以替换模型并长期维护。



Agent工程原则：

不要让业务逻辑进入LLM连接层。

llm_client只负责：

输入Prompt

调用模型

返回结果。

Controller负责：

流程管理和决策执行。



工程原则：

先实现最小可运行系统，再逐步扩展。

不要一开始设计复杂Agent。

MVP优先。



工程原则：

不要让业务流程依赖具体模型。

通过llm_client抽象模型调用。

Controller负责协调。

模块之间通过接口连接。

解耦就像软件世界的万向接头，通过接口层连接不同模块，使模块可以独立变化、替换和扩展。

2026-07-23:

软件架构原则：

接口稳定，实现变化。

Controller不应该依赖具体模型。

通过llm_client抽象模型调用。

这样可以替换DeepSeek、OpenAI等不同LLM。



Agent设计原则：

Memory不是简单存储。

Memory代表Agent长期状态。

Memory数据与Memory访问接口需要分离。

函数命名应该：

动作明确 + 对象明确。

避免使用过于宽泛的动词。
















































































