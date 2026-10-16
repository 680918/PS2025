# 邮箱验证确认页

## 本步效果

邮件链接打开 `/web/verify-email?token=...`，展示知行统一风格的确认页。用户点击「确认验证邮箱」后，以 POST 完成验证。打开、刷新、邮件预览或 GET 预取不会消耗链接。

页面有五种状态：待确认、验证成功、链接不可用、需要重新打开邮件、服务暂时不可用。错误链接统一提示可能过期、使用过或已更新，不透露邮箱或用户编号。成功页明确提示登录功能尚在准备中。

验证成功只更新原有邮箱验证记录，不设置或修改密码、不创建登录会话、不读取学习记录。网页注册、登录和重新发信入口仍未开放，没有接入真实 SMTP，不会自动发邮件。

## 提交与隐私

- 确认表单有短期、带服务端签名的浏览器凭证，绑定当前验证链接；凭证有效 10 分钟，使用 HttpOnly、SameSite=Strict、限定路径的 Cookie。在 HTTPS 下启用 Secure；本机 HTTP 仅供本机开发。
- 明确拒绝跨站提交。没有凭证、凭证被改动、确认页打开太久或服务重启后提交，均需重新从邮件打开。打开多个确认页时，使用最近打开的页面。
- 邮箱链接仍按数据库中的 1 小时有效期判断；浏览器凭证到期不会额外作废尚有效的邮件链接。验证后的链接不可重复使用。
- 验证页禁用缓存、向外发送 Referer、外部资源和嵌入框架。表单字段和请求体有长度、格式与重复字段检查，错误页不回显提交内容。
- `python -m api.run` 关闭 Uvicorn 请求访问日志，避免 URL 中的一次性凭证进入日志；保留启动和错误日志。以后部署反向代理或使用其他启动命令时，需要同样避免记录验证链接的查询串和 POST 内容。
- 浏览器确认凭证使用进程内临时签名密钥，本阶段用于单进程本机运行。生产多进程部署前，需要配置共享且妥善保存的签名密钥，届时再补对应部署测试。

## 验收

```powershell
python -m pytest tests/test_web_email_verification.py tests/test_email_verification.py tests/test_email_verification_inputs.py tests/test_web_public_pages.py tests/test_api_run.py -q -p no:cacheprovider
```

测试使用临时账户和临时数据库，不读取本机真实 `.env`，不调用 SMTP 或 AI。覆盖确认成功、只读预览、过期、重发、邮箱变更、重复确认、跨站与篡改提交、页面过期、服务重启和存储故障。

手动直接打开 `http://127.0.0.1:8000/web/verify-email` 会展示链接不可用页，这是因为没有携带验证凭证。完整确认需由受信任的内部流程生成邮件链接；本步没有增加供公众签发凭证的入口。

参考：[OWASP CSRF 防护](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)、[OWASP 一次性链接与 Referrer 防护](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html)。
