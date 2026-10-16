# 邮箱验证基础

本步只增加内部邮箱验证能力。网页注册、登录、旧账户激活页面与真实发信仍未开放，没有新增可消费链接的 HTTP 路由。

## 当前行为

1. 可信内部流程为现有用户申请链接。收件地址直接取自数据库当前邮箱，不接受调用者指定其他收件人。
2. 使用 `secrets.token_urlsafe(32)` 生成随机凭证，默认有效 1 小时。数据库只保存 SHA-256 摘要，凭证本身仅进入准备投递的消息对象。
3. 同一账号再次申请需间隔 60 秒。成功生成新链接后，旧链接立即失效；过早重试不影响原链接。
4. 确认时在同一 SQLite 事务中检查凭证、有效时间和当前邮箱，记录验证时间并清除凭证摘要。并发使用也只能有一次成功。
5. 结果与当时实际验证的邮箱绑定。邮箱改变后，旧链接和旧验证状态不能用于新地址。

验证后的状态会在重启后保留，不随原链接到期而消失。同一邮箱已经验证后，不再重复签发验证链接。

## 内部接口

- `issue_email_verification(repository, user_id, activation_url, now=...)`：返回收件人、链接与到期时间组成的 `EmailVerificationMessage`，不实际发信。消息的默认字符串表示隐藏邮箱和完整链接。
- `confirm_email_verification(repository, token, now=...)`：有效时返回被验证的用户编号，否则返回 `None`。它不设置密码、不创建登录会话、不授予学习记录访问权限。
- `repository.is_email_verified(user_id)`：检查账号当前邮箱是否已验证。

`now` 只用于服务器内部时钟与可重复测试，必须包含时区，不能来自用户提交的数据。

`activation_url` 必须来自服务端可信配置，不得直接使用请求 Host 头或用户输入。正式链接使用 HTTPS；仅本地开发允许 localhost、127.0.0.1、::1 的 HTTP 地址。该路由将在后续网页步骤中实现，本步返回的链接不代表已有可访问的激活页面。

未来邮件页面打开链接时应先展示确认，再以受保护的提交完成验证，避免邮箱预览、安全扫描或预取自动消耗凭证。真实投递还需处理地址校验、发送失败与重试、统一提示、请求次数限制，以及日志中凭证和邮箱的脱敏。本步不增加邮件队列或外部服务。

## 数据与旧账户

在原 `users.db` 中补建 `user_email_verifications` 表，不修改 `users`、`user_passwords` 表的原字段，不替换用户编号。旧用户默认未验证，不能因旧记录存在而自动取得“已验证”状态。

验证成功只改变邮箱验证记录，保留已有密码、学习旅程、对话和个人笔记。本次开发测试仅使用临时数据，不手动升级真实数据库；后续启动应用时按原有仓库初始化方式补建新表。

## 本地测试

测试以列表模拟邮件收件箱，不接入真实邮箱，不发送邮件，无邮件发送费用：

```powershell
python -m pytest tests/test_email_verification.py tests/test_email_verification_inputs.py tests/test_password_credentials.py tests/test_web_public_pages.py
```

覆盖正常确认、重启、到期边界、重发与冷却时间、错误凭证、摘要不能冒充凭证、账号隔离、邮箱变更、并发确认与重发、旧数据库兼容和网页仍未开放。

实现参考：[OWASP 邮箱验证建议](https://cheatsheetseries.owasp.org/cheatsheets/Email_Validation_and_Verification_Cheat_Sheet.html)。
