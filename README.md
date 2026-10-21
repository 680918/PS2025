# 知行 · Personal Growth AI Coach

面向成人自学与个人成长的 AI 学习陪伴工具。一个对话入口，串起聊天、主题学习、书籍阅读和长期知识积累。

当前是**本机个人试用版**。邮箱注册、验证、登录与找回已接通本人 163 邮件试用；尚未公开部署，也未开放任意用户注册。

## 已有账户，日常这样使用

```powershell
Set-Location 'D:\Personal-Growth-Coach'
& 'C:\BCtools\anaconda3\python.exe' -m api.coach_run --ai
```

浏览器打开 [日常登录](http://127.0.0.1:8785/web/login)，使用原邮箱和密码。保持终端运行，停止按 Ctrl+C。已有账户无须重新注册、无须为了登录再次输入邮箱授权码。默认沿用 `data/coach-local`，停止后账户、书籍、对话与教案仍保留；曾使用自定义 `--data-dir` 的用户继续使用原参数。

启动前仅检查本机条件：`python -m api.coach_run --check --ai`。不准备调用 AI 时，去掉 `--ai` 可查阅已有内容。项目需使用已安装 requirements.txt 的同一 Python；上面的路径是本机环境示例。

首次注册或需要找回邮件时使用 `python -m api.coach_run --register --ai`，仅在自己的终端输入本人 163 邮箱及客户端授权码。详细步骤见[日常使用与固定入口](docs/daily-use.md)、[本人真实 AI 试用](docs/real-ai-local-trial.md)。不要覆盖已有 `.env` 或向聊天发送密钥、密码、授权码。

## 模拟与开发体验

`python -m api.coach_run --simulate` 使用 [8784 模拟入口](http://127.0.0.1:8784/web/login) 和独立 `data/coach-simulated`；模拟收信、AI 不调用真实服务。开发助手提供的其他端口是独立预览，不是个人日常空间。每页底部“使用帮助与当前环境”可以核对当前模式和能力开关。

日常默认 8785，模拟默认 8784，`--port` 仍可明确指定；改变端口不改变数据目录。`api.run` 是保留的[旧开发入口](docs/legacy-development-entry.md)，不再作为当前账户产品的日常启动指引。

## 已实现的学习过程

- 统一聊天、当前主题与讨论进度，临时转题后继续学习。
- 书籍上传、粘贴、按书名通用导读、原书分页与连续阅读；扫描页可逐页本地 OCR，核对保存后供引用。
- 书籍选段、学习目录与连续导学，讲解依据和原文核对。
- 教案草稿预览与确认保存、知识库、修订与版本对比、重温、学习手册与资产导出。
- 可确认的学习记忆、账户隔离、AI 请求额度、本机备份恢复。

浏览、上传、手动修订与导出不调用 AI；主动发送和生成内容会使用已启用的模型服务，可能计费。扫描书可直接阅读原图，但未识别的正文不能冒充已经读懂的内容。单本原件当前上限 100 MB、账户合计 300 MB；具体类型与限制以页面提示为准。

## 项目与验收说明

- [当前项目状态](docs/project_state_snapshot.md)
- [日常使用与固定入口](docs/daily-use.md)
- [完整学习流程验收](docs/local-trial-acceptance.md)
- [资料与知识库](docs/materials-and-knowledge.md)
- [原文翻页与 Enter](docs/reader-navigation.md)
- [个人学习资产导出](docs/personal-asset-export.md)
- [开发协作约定](docs/development-workflow.md)

优先把本机完整学习过程做稳，再完善连续导学与真实 AI 质量，之后准备邀请制上线、真实用户试用和收费验证。自动检验通过不代表真实回答质量或公开商用已经验收。
