# Personal Growth AI Coach

长期学习陪伴与个人知识积累工具。CI protected by GitHub Actions.

## 启动网页

使用 Python 3.12。下面以本机的项目目录为例；如果项目放在其他位置，请替换路径。

在 PowerShell 中进入项目目录：

```powershell
Set-Location 'D:\Personal-Growth-Coach'
```

首次使用时安装依赖：

```powershell
python -m pip install -r requirements.txt
```

配置 AI 密钥。如果已经有 `.env`，保留并编辑现有文件。下面的命令仅在文件不存在时复制示例：

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

在 `.env` 中填写自己的 `DEEPSEEK_API_KEY`。模型和其他配置可参考 `.env.example`；密钥保留在本机，不要上传 GitHub。修改配置后需要重新启动。

每次启动网页只需运行：

```powershell
python -m api.run
```

保持这个窗口运行，在浏览器打开 <http://127.0.0.1:8000/>。停止时回到 PowerShell 按 **Ctrl+C**。

未配置密钥也可以打开首页；生成课程、AI 对话等功能需要有效密钥。启动入口仅监听本机地址。

## 当前页面范围

首页已提供「开始使用」和「我已有账户」入口：

- 首页：<http://127.0.0.1:8000/>
- 邮箱登录页：<http://127.0.0.1:8000/web/login>
- 邮箱注册页：<http://127.0.0.1:8000/web/register>

本步仅完成页面与导航。邮箱、密码字段和提交按钮暂时禁用，不创建真实账号、不发送激活邮件，也不保存密码。后续分别接入真实账号校验、邮箱激活与找回流程。第一版不接入手机号或短信服务。

此前只登记姓名和邮箱的后端接口仍保留供现有开发流程使用；它不代表已经完成安全登录，不能据此向公众开放服务。当前启动方式仅供本机开发、查看与验收。

## 常见启动问题

- **提示缺少依赖**：在项目目录重新执行 `python -m pip install -r requirements.txt`。
- **8000 端口被占用**：运行 `python -m api.run --port 8001`，打开 <http://127.0.0.1:8001/>。
- **提示配置格式不正确**：检查 `.env` 中的数值设置，例如 `LLM_TIMEOUT` 应为整数。
- **提示无法初始化数据库**：检查数据目录是否为文件夹、是否有读写权限，以及磁盘空间。
- **网页打不开**：检查启动窗口是否仍在运行、是否显示启动错误，以及浏览器地址中的端口是否一致。

运行 `python -m api.run --help` 可以查看可选参数。

## 数据位置

默认使用项目目录中的 `data` 文件夹保存现有 SQLite 数据库。启动入口不会因命令窗口位置不同而改变默认数据目录，也不会主动清空已有数据库。

需要使用独立的验证数据时，可以指定其他目录：

```powershell
python -m api.run --data-dir .\data\web-smoke --port 8001
```

相对路径以当前命令窗口所在目录为准。切换数据目录会进入独立的数据空间；原目录中的学习记录仍然保留。

## 密码能力进度

已增加密码的安全哈希保存与校验，旧账户没有默认密码，原用户编号和学习资料保持不变。本步只提供内部能力，网页上的注册、登录按钮仍禁用。设计边界与测试方式见 [密码基础说明](docs/password-foundation.md)。

新增密码库已固定在 `requirements.txt` 中；后续安装依赖时一并安装，不需要单独开通云服务，也不会产生短信费用。

## 开发检查

安装开发依赖后运行相关测试：

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest tests/test_api_run.py tests/test_web_home.py tests/test_web_public_pages.py
```
