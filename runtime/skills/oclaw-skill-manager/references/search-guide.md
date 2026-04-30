# Oclaw — Skill 搜索指南

## 市场提供方

由设置 **`AIA_SKILL_MARKET_PROVIDER`** 决定：`clawhub`（默认）或 `cocoloop`（见主 `SKILL.md` 对照表）。Admin 的 `market/search` 与 `market/detail` 会调用当前提供方适配器。

## 主源：ClawHub

当 `AIA_SKILL_MARKET_PROVIDER=clawhub` 时使用。

### Admin HTTP（ClawHub 模式下）

- 搜索：`GET /admin/api/skills/market/search?q=<关键词>&limit=<n>`
- 详情：`GET /admin/api/skills/market/detail?slug=<slug>`

从详情中读取：`slug`、`version`、描述、以及安装所需的 **`archiveUrl`**（ClawHub 下载链）。

## 主源：CocoLoop 商店

当 `AIA_SKILL_MARKET_PROVIDER=cocoloop` 时，同一组 Admin 路由背后走 **`cocoloop_client`**：关键词搜索商店列表，按技能 **`name` 字段** 匹配 slug；详情中的安装 URL 来自列表 **`download_url`**（或按 `asset_name` 拼 zip 直链）。商店前端：[hub.cocoloop.cn](https://hub.cocoloop.cn)。

### 模型侧

若无 Admin 权限，请用户代为搜索/安装，或提供准确 **slug** / **archive_url**。

> 重要：市场搜索不是安装前置条件。  
> 模型安装策略下只允许 `skill_auto_install`。若没有可用市场结果，应向用户索取可安装内容（如技能描述、`SKILL.md` 或源文件）并走 `skill_auto_install`，而不是要求先配置 `AIA_INTERNAL_BASE_URL` 或先启动本地 5173 服务。

## 辅助源：GitHub（可选）

当市场无结果或用户指定开源仓库时：

```
GET https://api.github.com/search/repositories?q=<关键词>+filename:SKILL.md&sort=stars&order=desc
```

需自备 `User-Agent`，注意 API 速率限制。找到仓库后仍需**可安装的归档 URL** 再走 `install-registry`。

## 合并展示建议

向用户展示时标注来源：`[ClawHub]` / `[GitHub]`，并给出 **slug** 或 **full_name**。
