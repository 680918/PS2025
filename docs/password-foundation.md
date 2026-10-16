# 邮箱账号基础：密码保存与校验

本步只完成内部密码能力。网页注册、登录和邮件激活仍未开放，没有新增可设置密码的 HTTP 接口，也不发放登录会话。

## 已实现

- 使用固定版本 `argon2-cffi==25.1.0` 的 Argon2id 高层接口，参数为内存 64 MiB、迭代 3 次、并行度 4。库为每次哈希生成独立的 16 字节随机盐，结果包含参数与盐，数据库不保存明文密码。
- 初始密码长度为 15–128 个字符，支持中文、空格和其他有效 Unicode 字符。空白密码不接受；不要求大小写、数字或特殊字符组合，不裁剪、不截断输入。
- 能区分正确密码与错误密码。未知用户、未设置密码、损坏的哈希、过长输入均不能通过校验；损坏记录不能要求无限内存或迭代次数。
- 同一用户只允许初始化一次，数据库唯一约束防止重复或并发操作覆盖已有密码。更改、找回密码是后续独立流程。

## 数据与旧账户

`SQLiteUserRepository` 在同一 `users.db` 中补建 `user_passwords` 表，以原 `user_id` 关联密码哈希。原 `users` 表和 `User` 模型保持原样；普通用户资料、Coach 上下文和现有 API 响应不增加密码或哈希字段。

初始化是可重复的建表操作，不删除、重建或替换原用户。旧账户默认没有密码，任何密码都不能因此通过校验；不生成共享默认密码。学习旅程、对话和个人文件仍关联原用户编号。

本次开发和测试只使用临时数据库，没有手动修改真实数据目录。以后应用启动时，现有仓库初始化会自动补建密码表。

## 内部接口边界

- `security.passwords.hash_password` / `verify_password`：独立的哈希和验证函数，不操作用户数据。
- `security.auth.initialize_user_password(repository, user_id, password)`：仅供已经验证账户归属的可信内部流程调用，不是公开的旧账户激活或密码重置入口。
- `security.auth.verify_user_password(repository, user_id, password)`：仅表示密码是否匹配，不代表邮箱已验证、已登录或有权访问学习记录。

后续接入真实网页前，仍需完成邮箱归属验证、受保护的登录会话、访问权限、尝试次数限制和常用弱密码筛查。不能仅凭邮箱或用户编号给旧账户设置密码。

## 检查方式

安装项目依赖后运行：

```powershell
python -m pytest tests/test_passwords.py tests/test_password_credentials.py tests/test_sqlite_user_repository.py tests/test_user_service.py tests/test_api_users.py tests/test_web_public_pages.py
```

测试覆盖随机盐、输入边界、正确与错误密码、持久化后重开数据库、账号之间的凭证隔离、禁止覆盖、并发初始化、旧表升级保留身份和学习资料，以及网页仍未开放。

## 技术依据

- [OWASP 密码存储建议](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)
- [OWASP 密码长度与字符支持建议](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
- [argon2-cffi 高层接口说明](https://argon2-cffi.readthedocs.io/en/stable/api.html)
