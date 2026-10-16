# 待验证注册申请的浏览器归属

内部保存与校验现已接上 [网页申请保存](registration-application-saving.md)，成功提交会设置独立的 HttpOnly 归属 Cookie。注册表单会保存待验证申请，但不创建正式账户、不发邮件、不建立登录会话。

## 已完成的行为

- 新申请由服务端生成独立的随机归属凭证。申请、密码哈希和归属摘要在同一个事务中保存，任一保存失败全部回退；不会留下没有归属信息的半份申请。
- 数据库只保存归属凭证的 SHA-256 摘要，并与邮箱链接的摘要使用不同用途前缀。原始凭证只在内部创建结果中交给受信任调用者，不写入数据库、链接、HTML 或日志。
- 查询必须同时提供申请编号和正确凭证，只返回有效申请编号及到期时间，不返回邮箱、名称或密码哈希。未知申请、凭证错误、过期、已完成或被已有账户占用，均无可用结果。
- 对有归属绑定的申请，签发或重发邮箱链接必须在同一数据库事务中检查归属。只提供编号的旧调用会被拒绝；错误凭证不能使原有链接失效，也不能绕过 60 秒重发间隔或延长申请期限。
- 不能凭编号或邮箱把既有申请重新绑定给另一个浏览器。重复或并发申请不能替换原有归属、密码或到期时间。过期后重新申请获得新编号、新凭证。
- 申请默认仍为 1 小时有效；查询不会续期。申请过期清理、被已有账户占用而清理或确认开户成功后，归属记录与邮件凭证一并清除。
- 浏览器归属不证明邮箱属于该用户，也不是登录凭证。开户仍需要有效邮件链接和明确的网页确认；邮件可以在另一台设备或浏览器打开并确认。

## 内部接口

`security/pending_registration.py`：

- `begin_browser_registration(repository, *, email, password, name="", now=None)`：校验填写并创建带归属的申请，返回 `BrowserRegistrationReceipt(request_id, browser_secret, expires_at)`。调用者须先完成 CSRF 和请求次数限制。
- `get_browser_registration(repository, request_id, browser_secret, now=None)`：返回不含邮箱或密码哈希的 `PendingRegistrationReceipt`，不可用时返回 `None`。

`security/email_verification.py`：

- `issue_registration_verification(..., browser_secret=..., now=None)`：对于带归属申请，必须提供正确凭证。返回待发送的邮件对象，不调用 SMTP。申请不可用、凭证不符及冷却时间不足统一抛出 `ValueError`，存储错误不伪装为发送成功。
- `confirm_registration_verification(...)`：继续使用邮件凭证完成原子开户，不要求浏览器归属凭证。

原始 `BrowserRegistrationReceipt` 包含秘密，虽然默认 `repr` 隐藏编号和凭证，也禁止通过 `dataclasses.asdict` 等序列化发给网页或写入日志。最小查询结果不包含原始凭证。普通 `User` 对象和学习资料不增加秘密字段。

旧的 `begin_pending_registration` 仅保留给受信任内部流程与旧测试。`get_pending_registration` 只能读取没有绑定的旧申请，不能用编号读取带绑定申请；旧申请也不能被任意新凭证认领。今后的网页入口必须使用新绑定流程，不能暴露旧内部保存或签发函数。

## 数据与兼容

新增 `registration_browser_bindings` 表，申请编号为主键和外键，关联删除时级联清除，摘要唯一且格式受限。旧表列、用户编号、密码、邮箱验证、学习及对话数据保留。仓库下次初始化时补建表，本次开发不在真实数据库执行迁移。

新建申请与归属保存、归属校验与重发、确认开户与归属清除均采用事务和显式关闭的连接。没有新增服务、调度、队列、付费依赖或设备指纹。

## 接入网页前的边界

归属凭证实际是持有即授权的秘密，不是硬件身份识别。后续只将其作为专用 HttpOnly Cookie 的一部分交给发起申请的浏览器，生产 HTTPS 下加 Secure，并限定路径、SameSite 和不超过申请期限的有效期。查询或重发还需现有 CSRF 与限流保护，不能把归属凭证放进页面隐藏字段或 URL，也不能复用 CSRF 字段充当归属凭证。

若浏览器丢失凭证，不得仅凭邮箱或编号重新认领；恢复方式须另外设计并验证邮箱所有权。本步不提供凭证重置、申请转移或旧申请重新绑定入口。

已保护的网页表单现已连接绑定申请保存与待验证页面，仍不自动发送真实邮件。接下来完成发信状态、重发入口、失败恢复和 SMTP 接入。

## 验收

```powershell
python -m pytest tests/test_registration_browser_binding.py tests/test_pending_registration.py tests/test_registration_verification.py tests/test_web_registration_verification.py -q -p no:cacheprovider
```

临时数据库和测试资料，禁止 SMTP。覆盖秘密只保存摘要、最小查询、编号单独不可用、凭证串用、旧链接保持、重发冷却、重启、过期、并发、逐步故障回退、旧流程兼容、跨浏览器邮件确认，以及正常网页提交仍不保存申请。
