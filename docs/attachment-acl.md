# Attachment ACL（附件访问控制）

本文档说明 admin chat 附件下载鉴权的访问控制策略、回填流程与 strict 模式上线建议。

## 背景

系统把工具结果/上传文件等二进制内容落盘为 `attachment_id`（内容 hash），前端通过：

- `GET /admin/api/chat/attachments/{attachment_id}`

获取附件 bytes（下载/预览）。

为避免仅凭 `attachment_id` 造成越权读取，需要对下载接口做归属校验。

## 数据结构

- **`attachment_acl`**
  - 用途：记录附件归属关系（哪个租户/用户/会话以何种来源产生/引用了该附件）
  - 主键：`(attachment_id, tenant_id, user_id, session_id, source)`

## 鉴权策略

下载接口会校验：

- `attachment_id` 格式合法（64 位 hex）
- 当前登录用户是否被 ACL 授权访问该附件
- 头像附件通过 `avatar_attachment_id` 放行（不走 ACL）

## strict 模式

环境变量：

- `AIA_ATTACHMENT_ACL_STRICT=1`

行为：

- 下载鉴权只信 `attachment_acl`（以及头像 `avatar_attachment_id`）
- **不会**回退扫描历史 `chat_message.attachments`

适用场景：

- 生产环境附件访问收口
- 已完成历史数据 ACL 回填

## 回填流程（Admin）

为了让历史消息中的附件也能被 strict 模式识别，需要先回填 ACL。

入口（仅 `administrator` 可见/可调用）：

- 管理台 Chat 页面右上角菜单：**回填 ACL**
- 或接口：`POST /admin/api/chat/admin/attachments/acl/backfill?limit_messages=...`

建议流程：

1. 在低峰期执行回填（默认扫描最近 50k 条含 attachments 的消息）
2. 观察返回结果（扫描/插入计数）
3. 开启 `AIA_ATTACHMENT_ACL_STRICT=1`

## 相关配置放一起（ENV）

- `AIA_MAX_ATTACHMENT_BYTES`：控制工具结果 base64 落盘单附件大小上限
- `AIA_ATTACHMENT_ACL_STRICT`：下载鉴权严格只信 `attachment_acl`

## 回滚建议

如 strict 模式误伤历史附件下载（403）：

1. 临时关闭 strict：`AIA_ATTACHMENT_ACL_STRICT=0`
2. 再次执行回填（提高 `limit_messages`）
3. 重新开启 strict

