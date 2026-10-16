# 163 验证邮件发送

本文记录独立发信模块和验证邮件模板的阶段；下述“本步”指该阶段。后续已增加 [邮箱验证确认页](email-verification-page.md)。发信仍默认关闭，没有连接真实邮箱，也没有发送真实邮件。网页注册、登录仍未开放；完整账号系统尚未完成。

## 已完成的行为

- 使用普通 `@163.com` 邮箱，连接 `smtp.163.com:465`，全程 TLS，并校验服务器证书。不回退到明文连接。
- 发信凭证使用网易客户端授权码。配置、错误信息不打印授权码、验证链接或收件地址。
- 邮件同时包含纯文本和 HTML：知行品牌、验证按钮、备用链接、北京时间到期时间，以及非本人操作可忽略的说明。模板不包含外部图片或脚本。
- 连接失败、授权失败、超时、收件地址被拒绝等情况返回可识别的错误。一次调用只尝试提交一次，避免自动重试造成重复邮件。
- 发送动作不会验证邮箱、消费验证链接或设置密码。邮件服务器接受邮件也不等于收件箱已经收到；超时、断线可能无法确认投递结果。

## 将来真实测试前的本机配置

目前无需填写配置即可完成本步的模拟测试。准备真实测试时，再按下面步骤操作。

1. 自己登录网易 163 邮箱网页版，进入「设置 → POP3/SMTP/IMAP」，根据页面提示开启 SMTP 服务并生成客户端授权码。页面位置、验证方式以网易当前提示为准。[网易官方授权码帮助](https://help.mail.126.com/faqDetail.do?code=d7a5dc8471cd0c0e8b4b8f4f8e49998b374173cfe9171305fa1ce630d7f67ac286624f309a1a7089)
2. 在本机现有 `.env` 中追加下面的配置，保留已有 AI 密钥等内容。不要用 `.env.example` 覆盖现有 `.env`。

```dotenv
SMTP_ENABLED=true
SMTP_USERNAME=你的完整163邮箱地址
SMTP_AUTH_CODE=你自己生成的客户端授权码
SMTP_TIMEOUT=15
```

3. 不要把授权码、邮箱密码或 `.env` 发到聊天、截图、日志或 GitHub。授权码只在本机填写；取消配置时将 `SMTP_ENABLED` 改回 `false`。
4. 填好配置本身不会发送邮件。本步尚未接入网页，也没有启动自动发信任务。真实测试前还需要确定收件地址和可访问的验证页面，并主动调用发送。

这是小规模内部测试的接入方式，不承诺个人邮箱适合商业批量发送或无限发送；后续上线时再根据实际规模选择事务邮件服务。

## 给开发者的调用边界

模块：`security/verification_mailer.py`，仅使用 Python 标准库，无新增依赖。

- `load_smtp_settings()` 读取已经加载到环境中的配置；不自行读取 `.env`，也不连接网络。默认返回 `None`，明确启用后才校验发信参数。
- `build_verification_email(message, sender)` 生成 MIME 邮件，不发送。输入是上一小步的 `EmailVerificationMessage`。
- `send_verification_email(message, settings)` 向指定收件人提交邮件。返回表示 SMTP 服务器已接受；抛出 `MailConfigurationError` 或带 `code` 的 `MailDeliveryError` 表示配置错误或投递未成功确认。不要把异常的内部属性记录到含凭证的调试日志中。
- 激活链接由可信配置的应用地址生成。生产环境使用 HTTPS；本机 HTTP 链接只供同一台电脑调试，不能直接供外部用户激活。
- 本步没有新增 HTTP 接口、登录会话、公开注册、密码找回或后台任务。

后续接入注册流程时，需要一起处理注册校验、验证码重发的额度限制与滥用防护、失败提示、网页确认激活、登录会话和密码找回，之后才安排完整真实邮件验收。

## 验证方法

```powershell
python -m pytest tests/test_verification_mailer.py tests/test_smtp_settings.py tests/test_email_verification.py tests/test_email_verification_inputs.py -q -p no:cacheprovider
```

测试用替身 SMTP 覆盖加密连接、认证、一次投递、失败处理、邮件正文和配置；不连接真实邮件服务。数据库相关测试只使用临时数据库，检查发送成功和失败都不会提前激活账号。

参考：[Python SMTP 官方文档](https://docs.python.org/3.12/library/smtplib.html)。
