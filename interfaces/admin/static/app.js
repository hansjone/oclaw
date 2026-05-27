const I18N = {
  zh: {
    "brand.title": "oliver",
    "nav.chat": "对话",
    "nav.models": "模型管理",
    "nav.apiGrants": "API 使用授权",
    "nav.stack": "运行时",
    "nav.users": "用户管理",
    "nav.workspacePaths": "工作区路径",
    "nav.memory": "记忆",
    "nav.audit": "审计与追踪",
    "nav.sessionMonitor": "会话监控",
    "nav.adminAudit": "管理审计",
    "nav.plugins": "插件",
    "nav.skills": "技能",
    "nav.attachments": "附件",
    "nav.profile": "用户信息",
    "notice.noLogin": "v2 已启用登录鉴权：请仅在内网访问",
    "action.refresh": "刷新",
    "title.stack": "运行时",
    "title.users": "用户管理",
    "title.workspacePaths": "工作区路径（按用户）",
    "title.memory": "记忆",
    "title.models": "模型管理",
    "title.apiGrants": "API 使用授权",
    "title.audit": "审计与追踪",
    "title.sessionMonitor": "会话监控",
    "title.adminAudit": "管理审计",
    "title.plugins": "插件",
    "title.skills": "技能",
    "title.attachments": "附件",
    "skills.docsTitle": "oclaw 文档快捷入口：",
    "skills.docsTroubleshooting": "- oclaw/docs/oclaw-skill-troubleshooting.md（安装与运行排障）",
    "skills.docsTraceTaxonomy": "- oclaw/docs/oclaw-trace-taxonomy.md（trace 字段与阶段）",
    "title.profile": "用户信息",
    "attachments.title": "附件",
    "attachments.excelPolicy": "Excel 策略",
    "attachments.excelPolicyHint": "针对 Excel/表格附件的解析与 SQL 查询保护策略。该配置写入 oclaw.json（优先级低于环境变量）。",
    "attachments.maxRowsRead": "最大读取行数",
    "attachments.maxColumns": "最大保留列数",
    "attachments.maxCellChars": "单元格最大字符数",
    "attachments.maxExcelSheets": "Excel 最大 Sheet 数",
    "attachments.largePreviewRows": "大表摘要预览行数",
    "attachments.toolModeEnabled": "启用大表工具模式",
    "attachments.toolModeMinRows": "触发工具模式最小行数",
    "attachments.toolModeMaxBytes": "工具模式最大文件字节数",
    "attachments.sqlTimeoutMs": "SQL 超时（ms）",
    "attachments.imageReplayCapChars": "图片结果回放上限字符数",
    "attachments.videoReplayCapChars": "视频转写结果回放上限字符数",
    "attachments.videoTranscriptChunkSize": "视频转写分块大小",
    "attachments.videoTranscriptChunkOverlap": "视频转写分块重叠",
    "attachments.archiveMaxDepth": "压缩包最大嵌套深度",
    "attachments.archiveMaxFileCount": "压缩包最大文件数",
    "attachments.archiveMaxEntryBytes": "压缩包单文件最大解压字节",
    "attachments.archiveMaxTotalBytes": "压缩包总解压字节上限",
    "attachments.highPreviewWarn": "大表摘要预览行数超过 200，可能显著增加 token 消耗。确认继续？",
    "attachments.invalidNumber": "请输入有效正整数",
    "attachments.sqlTimeoutHint": "硬超时（wall-clock）。范围 100..120000，默认 8000。命中会返回 sql_timeout 结构化错误。",
    "attachments.imageReplayCapHint": "历史轮次中，query_image_attachment 的 OCR/描述结果回放上限。范围 600..30000，默认 4000。",
    "attachments.videoReplayCapHint": "历史轮次中，query_video_attachment 的 transcript 结果回放上限。范围 600..30000，默认 4000。",
    "attachments.videoTranscriptChunkHint": "query_video_attachment(task=transcript) 默认使用该分块参数落库，便于后续 query_text_attachment 检索。",
    "attachments.archivePolicyHint": "archive_processor 的统一预算：支持 zip/tar/tgz/gz，限制嵌套层级、文件数与解压体积。",
    "attachments.loadError": "加载失败",
    "attachments.saved": "已保存",
    "attachments.save": "保存",
    "attachments.resetDefaults": "恢复默认",
    "profile.help": "在此调整显示名称、头像及账号标识；对话页中头像为圆形，助手使用站点 Logo。",
    "profile.displayName": "显示名称",
    "profile.username": "用户名",
    "profile.userId": "用户 ID",
    "profile.tenantId": "团队 ID",
    "profile.role": "角色",
    "profile.createdAt": "注册时间",
    "profile.avatar": "头像",
    "profile.avatarHint": "支持 PNG、JPEG、WebP、GIF，最大 2MB。",
    "profile.chooseImage": "选择图片",
    "profile.removeAvatar": "移除头像",
    "profile.save": "保存设置",
    "profile.saved": "已保存",
    "profile.openChat": "打开对话",
    "profile.loadError": "加载失败",
    "profile.uploadError": "上传失败",
    "profile.chatPrefs": "对话偏好",
    "profile.memoryMode": "记忆模式",
    "profile.memoryModeDefault": "默认（可注入）",
    "profile.memoryModeStoreOnly": "仅记录不注入",
    "profile.memoryCurator": "记忆整理专家",
    "profile.memoryCuratorEnabled": "启用",
    "profile.memoryCuratorDisabled": "停用",
    "table.name": "名称",
    "table.provider": "提供方",
    "stack.title": "服务栈",
    "stack.alerts": "异常告警",
    "stack.mustCleanup": "检测到重复 worker，必须先清理再继续操作。",
    "stack.missingRequired": "关键服务未运行，请先启动栈。",
    "stack.missingServices": "缺失服务：{services}",
    "stack.noAlerts": "未发现异常。",
    "stack.cleanup": "清理异常进程",
    "stack.cleanupDone": "清理完成，已终止异常进程数：{count}",
    "stack.cleanupNone": "未发现可清理的异常进程。",
    "stack.up": "启动栈",
    "stack.down": "停止栈",
    "table.service": "服务",
    "table.pid": "进程号",
    "table.status": "状态",
    "status.running": "运行中",
    "status.stopped": "已停止",
    "tenants.title": "团队",
    "tenants.select": "选择团队",
    "tenants.create": "新建团队",
    "tenants.createPlaceholder": "团队名称（默认 Team）",
    "tenants.users": "用户",
    "tenants.bindings": "渠道绑定",
    "tenants.bindCodes": "绑定码",
    "tenants.createCode": "生成绑定码",
    "tenants.deleteCode": "删除",
    "tenants.codeStatus": "状态",
    "tenants.codeUsed": "已使用",
    "tenants.codeUnused": "未使用",
    "tenants.codeUsedBy": "绑定人",
    "tenants.codeDeleteConfirm": "确认删除该绑定码？",
    "tenants.codeDeleted": "已删除绑定码：{code}",
    "tenants.role": "角色",
    "tenants.codeOptional": "Code（可留空自动生成）",
    "tenants.deleteUnbound": "删除未绑定用户",
    "tenants.deleted": "已删除未绑定用户数：{count}",
    "tenants.deleteUnboundResult": "未绑定用户清理：deleted={deleted}, orphan={orphan}, bound={bound}, total={total}",
    "tenants.saved": "配置已保存",
    "tenants.noTenants": "暂无团队数据。请先通过绑定流程或初始化脚本创建团队。",
    "tenants.noUsers": "该团队暂无用户。",
    "tenants.noBindings": "该团队暂无渠道绑定。",
    "table.id": "ID",
    "table.createdAt": "创建时间",
    "table.userId": "用户ID",
    "table.username": "用户名",
    "table.externalUserId": "外部用户ID",
    "table.channel": "渠道",
    "tenants.userSource": "来源",
    "tenants.sourceWecom": "企业微信",
    "tenants.sourceChannel": "其他渠道",
    "tenants.sourceConsole": "控制台",
    "tenants.chatLogin": "Web 登录",
    "tenants.chatLoginYes": "可（已设密码）",
    "tenants.chatLoginNo": "否",
    "tenants.noSessionTenant": "缺少会话团队信息，请重新登录。",
    "tenants.sessionTenantMissing": "当前登录会话对应的团队不在列表中，请重新登录或联系管理员。",
    "tenants.scopeHint": "「选择团队」决定下方用户/渠道绑定/绑定码所针对的团队。administrator 账号可切换并管理任意团队。上表最后一列标出登录会话最初绑定的团队。",
    "tenants.colScope": "登录标识",
    "tenants.scopeLoginHome": "登录所属",
    "tenants.allTenantsHint": "多团队时：「登录所属」仅作提示；实际操作范围以「选择团队」为准。",
    "tenants.rowActions": "操作",
    "tenants.colTenantName": "团队名",
    "tenants.colTenantId": "团队 ID",
    "tenants.deleteTenant": "删除团队",
    "tenants.deleteTenantConfirm": "确定删除团队「{name}」？将级联删除该团队下用户、绑定与数据，且不可恢复。",
    "tenants.errLastTenant": "至少保留一个团队，无法删除。",
    "tenants.errCannotDeleteCurrentTenant": "不能删除当前登录会话所属团队，请先切换到其他团队再删，或使用其他账号。",
    "tenants.errTenantDeleteMiss": "删除未生效（可能数据库约束失败），请查看服务端日志。",
    "tenants.deleteDisabledLast": "至少需保留一个团队。",
    "tenants.deleteDisabledCurrent": "不能删除当前登录会话所属团队；请先在登录页使用另一团队的 UUID 登录后再删。",
    "audit.title": "审计与追踪",
    "audit.sessionIdPlaceholder": "session_id（可选）",
    "audit.query": "查询",
    "audit.result": "结果",
    "audit.note": "支持表格 + JSON 双视图。",
    "audit.auditTable": "审计表",
    "audit.traceTable": "追踪表",
    "audit.rawJson": "原始 JSON",
    "audit.empty": "暂无数据",
    "audit.columns": "显示列",
    "table.timestamp": "时间",
    "table.specialist": "专家",
    "table.action": "动作",
    "table.statusText": "状态",
    "table.reason": "原因",
    "table.durationMs": "耗时(ms)",
    "table.routeAttachmentIds": "路由附件IDs",
    "table.inputAttachmentIds": "输入附件IDs",
    "table.outputAttachmentIds": "输出附件IDs",
    "table.outputAttachmentUrls": "输出附件URLs",
    "table.noOutputAttachment": "无输出附件",
    "table.eventType": "事件类型",
    "table.traceId": "trace_id",
    "table.spanId": "span_id",
    "table.parentSpanId": "parent_span_id",
    "table.payload": "payload",
    "table.user": "用户",
    "table.sessionsCount": "会话数",
    "table.activeSessions30m": "活跃会话(30m)",
    "table.activeLogins30m": "活跃登录(30m)",
    "table.totalTokensEst": "总 Token(估算)",
    "wecom.title": "企业微信配置",
    "wecom.botId": "Bot ID",
    "wecom.botSecret": "Bot Secret",
    "wecom.autoBind": "首条消息自动绑定",
    "wecom.autoBindTenant": "自动绑定团队",
    "wecom.autoBindRole": "自动绑定角色",
    "wecom.unbind": "解绑 WeCom",
    "wecom.unbindConfirm": "将清空本地 WeCom 配置和全部 WeCom 绑定/会话，确认继续？",
    "wecom.unbindDone": "已解绑 WeCom。identity={ident}，session={sess}",
    "action.save": "保存",
    "plugins.title": "工具插件",
    "workspacePaths.help":
      "为每个用户配置除主工作区（AIA_WORKSPACE_ROOT / 项目根）外可访问的绝对路径，用竖线 | 分隔，例如 D:\\\\|E:\\\\repos\\\\other。与网关环境变量 AIA_WORKSPACE_EXTRA_ROOTS 合并生效。下方「额外根路径」会参与内置工具校验，并在用户聊天时合并进官方 MCP @modelcontextprotocol/server-filesystem 的启动参数（仅该用户）。",
    "workspacePaths.tenant": "团队",
    "workspacePaths.user": "用户",
    "workspacePaths.extraRoots": "额外根路径（| 分隔）",
    "workspacePaths.allowAny": "允许任意路径（高风险）",
    "workspacePaths.allowAnyHint":
      "仅作用于内置工作区工具（read_file / glob 等）的路径校验；不会放开 MCP filesystem，也不会自动把整盘写进 MCP。需要 MCP 列目录的盘符/目录请填在「额外根路径」或环境变量 AIA_WORKSPACE_EXTRA_ROOTS。",
    "workspacePaths.allowHighTools": "允许高风险 Public 工具（全局）",
    "workspacePaths.allowHighToolsHint":
      "开启后将放开 run_command / write_file / edit_file 等高风险 public 工具的模型可见性（等效 AIA_PUBLIC_TOOLS_ALLOW_HIGH=1）。",
    "workspacePaths.load": "加载",
    "workspacePaths.save": "保存",
    "workspacePaths.status": "状态",
    "workspacePaths.fromDb": "已保存到数据库",
    "workspacePaths.selfOnly": "当前账号仅能查看并编辑自己的工作区路径策略（不能代他人配置）。",
    "chat.newSession": "新会话",
    "chat.send": "发送",
    "chat.sessions": "会话",
    "chat.placeholder": "输入消息…",
    "chat.empty": "暂无消息",
    "chat.noSessions": "暂无会话，点击新建开始。",
    "chat.loading": "加载中…",
    "chat.sending": "发送中…",
    "chat.error": "请求失败",
    "table.version": "版本",
    "table.entryPoint": "入口点",
    "table.enabled": "启用",
    "common.notFound": "未找到页面",
    "common.forbidden": "无权访问该页面。",
    "common.error": "错误",
    "theme.label": "界面配色",
    "theme.deepseek": "DeepSeek 默认",
    "theme.github": "GitHub 暗色",
    "theme.nord": "Nord",
    "theme.dracula": "Dracula",
    "theme.forest": "森绿",
    "theme.catppuccin": "Catppuccin Mocha",
    "theme.light": "浅色",
    "lang.switch": "English",
    "memory.title": "记忆治理",
    "memory.hits": "最近命中",
    "memory.items": "记忆条目",
    "memory.config": "向量配置",
    "memory.enabled": "开启向量检索",
    "memory.backend": "后端",
    "memory.topk": "TopK",
    "memory.writerEnabled": "开启自动写入",
    "memory.minConfidence": "最小写入置信度",
    "memory.save": "保存配置",
    "memory.reindex": "重建向量索引",
    "memory.cleanup": "清理低置信记忆",
    "memory.delete": "删除",
    "memory.noData": "暂无记忆数据",
    "memory.filters": "筛选",
    "memory.tenantId": "团队 ID / tenant_id（可选）",
    "memory.userId": "user_id（可选）",
    "memory.applyFilters": "应用筛选",
    "memory.clearFilters": "清空筛选",
    "memory.stats": "统计",
    "memory.hitCount": "命中总数",
    "memory.itemCount": "记忆条目数",
    "memory.avgScore": "平均得分",
    "memory.topSources": "最近来源",
    "memory.wikiCard": "Wiki",
    "memory.wikiStatus": "插件状态",
    "memory.wikiPluginFound": "已安装：{name} v{version}",
    "memory.wikiPluginMissing": "未检测到 memory-wiki 插件",
    "memory.openPlugins": "打开插件页",
    "auth.login": "登录",
    "auth.logout": "退出登录",
    "auth.username": "用户名",
    "auth.consoleUsernameHint": "填写用户名与密码；各菜单仍按账号权限显示。",
    "auth.password": "密码",
    "auth.invalid": "登录失败，请检查凭据",
    "auth.disabled": "账号已被禁用，请联系管理员",
    "users.title": "用户管理",
    "users.search": "搜索用户",
    "users.colUser": "用户",
    "users.createNamePlaceholder": "名称（登录名，唯一）",
    "users.createNameRequired": "请填写名称。",
    "users.deleteConfirm": "确定删除该用户？不可恢复。",
    "users.create": "创建用户",
    "users.update": "更新",
    "users.delete": "删除",
    "users.disable": "禁用",
    "users.enable": "启用",
    "users.passwordOptional": "新密码（可选）",
    "users.wecomAccounts": "企微实例（每用户多个，具名）",
    "users.wecomInstanceName": "实例名",
    "users.wecomBotSecret": "Bot Secret",
    "users.hasBotSecret": "已配Bot密钥",
    "users.clearBotSecret": "清除Bot密钥",
    "users.loadForm": "填入表单",
    "users.noBindingsForUser": "暂无企微绑定或已保存实例；用户在微信侧绑定后会出现行，填齐参数后保存。",
    "users.accountId": "账号ID",
    "users.wecomBotId": "Bot ID",
    "users.botIdRequired": "请先填写 Bot ID",
    "users.accountName": "名称",
    "users.accountActive": "启用",
    "users.accountActions": "账号操作",
    "users.accountSave": "保存账号",
    "users.accountDelete": "删除账号",
    "users.wecomUserLabel": "用户",
    "users.wecomUserEmpty": "请在上表点击一行选中用户",
    "users.accountLoadHint": "选中用户后，表格列出绑定与实例；需编辑时点「填入表单」，再填写 Bot Secret 等并保存（不会自动填入表单）。",
    "users.noTenant": "请先登录并选择团队",
    "users.needUserRead": "需要 admin:user:read 权限以查看与编辑用户列表。",
    "users.colActive": "启用",
    "users.colSetRole": "调整角色",
    "adminAudit.title": "管理操作审计",
    "adminAudit.action": "动作",
    "adminAudit.actor": "操作者",
    "adminAudit.status": "状态",
    "adminAudit.total": "共 {total} 条",
    "adminAudit.jumpPlaceholder": "页码",
    "adminAudit.jump": "跳转",
    "models.sectionActive": "当前模型配置",
    "models.sectionBindings": "智能体与模型绑定",
    "models.sectionNew": "新建模型配置",
    "models.sectionApi": "API 与密钥",
    "models.chatModelSelector": "聊天页模型选择器",
    "models.chatModelSelectorHint": "控制 Chat 页底部的模型下拉是否显示。",
    "models.sectionEval": "Agent Evaluation",
    "models.pickModel": "选用配置",
    "models.agentBindingHelp": "可为不同角色指定模型配置；留空则跟随上方全局选用。",
    "models.bindingsExtraHint": "被定向授权或团队共享的 API 会出现在上方「选用配置」列表中；成员需在此为各角色自行选择要绑定的配置。",
    "models.bindingsScopeHint": "选用与绑定下拉仅含：内置、您自建的配置，以及管理员授权给团队或您个人的配置（与当前账号可见列表一致）。",
    "models.linkApiGrants": "打开 API 使用授权",
    "models.grantsNavHint": "管理谁能看到并选用可分享的模型配置（不含在此页改密钥或端点）。",
    "apiGrants.intro": "选择下方列表中的模型配置（profile），将「使用权」授予整个团队或指定用户。密钥与 Base URL 仍在「模型管理」中配置；成员获得可见性后，在「模型管理」里为各角色绑定 profile。",
    "apiGrants.pickApi": "选择要授权的 API",
    "apiGrants.teamSection": "授权给整个团队",
    "apiGrants.teamHint": "授予后，租户内所有成员在其「选用配置」列表中可见该 API；端点与密钥仍在「模型管理」中维护。",
    "apiGrants.userSection": "授权给指定用户",
    "apiGrants.userHint": "仅该用户在其「选用配置」列表中可见；对方在「模型管理」里自行绑定各角色。",
    "apiGrants.noShareable": "（暂无可分享的模型配置）",
    "apiGrants.forbidden": "仅 administrator 账号且具备团队写权限（或 owner 角色）可管理 API 使用权。",
    "apiGrants.openModels": "前往模型管理",
    "models.useGlobal": "（跟随全局）",
    "models.role.manager": "编排 / Manager",
    "models.role.ops": "网络运维",
    "models.role.generalist": "通用",
    "models.role.image": "图像",
    "models.role.memory": "记忆整理",
    "models.profileName": "配置名称",
    "models.mode": "模式",
    "models.mode.openai": "OpenAI 兼容",
    "models.mode.openai_responses": "OpenAI Responses",
    "models.mode.anthropic": "Anthropic",
    "models.mode.google": "Google (Gemini)",
    "models.mode.ollama": "Ollama",
    "models.mode.rule": "规则（无 LLM）",
    "models.model": "模型名",
    "models.baseUrl": "Base URL",
    "models.baseUrlPlaceholder": "可选，留空用环境默认",
    "models.apiKey": "API Key",
    "models.thinkMode": "Think 模式（仅当前 API）",
    "models.thinkModeHint": "开启后仅对此配置回放完整 reasoning_content（默认关闭）",
    "models.reasoningEffort": "Reasoning 强度",
    "models.reasoningEffortDefault": "默认",
    "models.reasoningEffortLow": "低",
    "models.reasoningEffortMedium": "中",
    "models.reasoningEffortHigh": "高",
    "models.rememberKey": "记住密钥（存库加密）",
    "models.save": "保存",
    "models.delete": "删除此配置",
    "models.deleteConfirm": "确定删除该模型配置？此操作不可撤销。",
    "models.cannotDeleteBuiltin": "无法删除内置 Ollama 配置。",
    "models.createNamePlaceholder": "配置显示名",
    "models.newProfileDefault": "新配置",
    "models.createBtn": "创建",
    "models.builtinLocked": "内置 Ollama 配置：模式固定为 Ollama，可改地址与模型名。",
    "models.warnKeyInDb": "数据库中已有密钥：若输入框为空，保存时不会覆盖（请先填入新密钥或取消勾选「记住密钥」以清空）。",
    "models.openaiKeyHint": "未配置密钥时，将尝试使用环境变量 OPENAI_API_KEY。",
    "models.ollamaHint": "Ollama 本地默认 http://127.0.0.1:11434；一般无需 API Key。",
    "models.evalTotal": "样本数",
    "models.evalSuccess": "成功率",
    "models.evalP95": "P95 延迟",
    "models.evalLogs": "最近评估日志",
    "models.evalToggle": "Agent Evaluation · 点击展开（页内预览最多 100 条）",
    "models.evalLogsPreview": "页内预览",
    "models.evalDownloadCsv": "下载全量 CSV",
    "models.evalDownloadJson": "下载全量 JSON",
    "models.noEvalLogs": "暂无评估记录",
    "models.noProfiles": "暂无模型配置数据。",
    "models.readonly": "只读：当前账号无团队数据写权限（admin:tenant:write）。",
    "models.profileReadonlyHint": "当前配置为管理员授权，仅可选用与对话，不能改名称、端点或密钥。",
    "models.grantsTitle": "授权其他用户使用当前配置",
    "models.grantsHint": "仅 administrator 可管理。被授权用户可在其模型列表中看到并选用此配置（共用密钥）。",
    "models.grantsGrantBtn": "授权",
    "models.grantsRevoke": "撤销",
    "models.grantsEmpty": "尚无定向授权用户。",
    "models.grantsUserHint": "定向授权给单个用户：",
    "models.grantTenantBtn": "全团队可用",
    "models.revokeTenantGrant": "撤销全团队",
    "models.tenantGrantOn": "全团队：已授权",
    "models.tenantGrantOff": "全团队：未授权",
    "models.membersTitle": "各成员可见的模型配置",
    "models.vis.builtin": "内置",
    "models.vis.owned": "我的",
    "models.vis.grantUser": "定向授权",
    "models.vis.grantTenant": "团队共享",
    "models.vis.global": "全局",
    "models.vis.otherUser": "他人配置",
    "models.loadFailed": "加载失败，请展开下方错误信息。",
    "models.dbPath": "当前使用的数据库文件",
    "secrets.migrateTitle": "密钥加密迁移",
    "secrets.migrateHint": "检测到旧版 b64 编码的密钥（弱保护）。建议设置 AIA_ASSISTANT_MASTER_KEY 后一键迁移到更安全的加密格式。",
    "secrets.migrateBtn": "立即迁移",
    "secrets.migrateDone": "迁移完成：settings={s}，profiles={p}",
    "secrets.migrateNoop": "未发现需要迁移的旧密钥。",
    "secrets.migrateNeedKey": "未配置 AIA_ASSISTANT_MASTER_KEY，无法迁移。",
    "secrets.migrateForbidden": "需要 admin:tenant:write 权限。",
    "sessionMonitor.totals": "总览统计",
    "sessionMonitor.totalTokensEst": "总 Token(估算)",
    "sessionMonitor.activeSessions30m": "活跃会话(30m)",
    "sessionMonitor.activeLogins30m": "活跃登录(30m)",
    "sessionMonitor.usersCount": "用户数",
    "sessionMonitor.userStats": "用户统计",
    "sessionMonitor.sessions": "会话明细",
    "sessionMonitor.filterUser": "筛选用户",
    "sessionMonitor.filterSession": "筛选会话",
    "sessionMonitor.selectUserFirst": "请先选择一个用户查看会话。",
    "sessionMonitor.viewAudit": "查看审计",
    "sessionMonitor.viewDetail": "查看详情",
    "sessionMonitor.messages": "消息明细",
    "sessionMonitor.exportMd": "导出 MD",
    "sessionMonitor.exportJson": "导出 JSON",
    "sessionMonitor.pagePrev": "上一页",
    "sessionMonitor.pageNext": "下一页",
    "sessionMonitor.pageInfo": "第 {page} 页 / 共 {totalPages} 页",
    "sessionMonitor.noMessages": "该会话暂无消息。",
    "sessionMonitor.closeDetail": "关闭详情",
    "sessionMonitor.roleFilter": "角色过滤",
    "sessionMonitor.roleAll": "全部",
    "sessionMonitor.roleUser": "用户",
    "sessionMonitor.roleAssistant": "助手",
    "sessionMonitor.roleTool": "工具",
    "sessionMonitor.onlyAdministrator": "仅 administrator 账号可访问该页面。",
  },
  en: {
    "brand.title": "oliver",
    "nav.chat": "Chat",
    "nav.models": "Models",
    "nav.apiGrants": "API access",
    "nav.stack": "Runtime",
    "nav.users": "Users",
    "nav.workspacePaths": "Workspace paths",
    "nav.memory": "Memory",
    "nav.audit": "Audit & Trace",
    "nav.sessionMonitor": "Session Monitor",
    "nav.adminAudit": "Admin Audit",
    "nav.plugins": "Plugins",
    "nav.skills": "Skills",
    "nav.attachments": "Attachments",
    "nav.profile": "User Info",
    "notice.noLogin": "v2 login enabled: internal network only",
    "action.refresh": "Refresh",
    "title.stack": "Runtime",
    "title.users": "Users",
    "title.workspacePaths": "Workspace paths (per user)",
    "title.memory": "Memory",
    "title.models": "Model Management",
    "title.apiGrants": "API access grants",
    "title.audit": "Audit & Trace",
    "title.sessionMonitor": "Session Monitor",
    "title.adminAudit": "Admin Audit",
    "title.plugins": "Plugins",
    "title.skills": "Skills",
    "title.attachments": "Attachments",
    "skills.docsTitle": "oclaw docs quick links:",
    "skills.docsTroubleshooting": "- oclaw/docs/oclaw-skill-troubleshooting.md (install/runtime troubleshooting)",
    "skills.docsTraceTaxonomy": "- oclaw/docs/oclaw-trace-taxonomy.md (trace fields and stages)",
    "title.profile": "User Info",
    "attachments.title": "Attachments",
    "attachments.excelPolicy": "Excel policy",
    "attachments.excelPolicyHint": "Policy for Excel/tabular attachments parsing and SQL query safeguards. Saved into oclaw.json (lower priority than env vars).",
    "attachments.maxRowsRead": "Max rows read",
    "attachments.maxColumns": "Max columns kept",
    "attachments.maxCellChars": "Max chars per cell",
    "attachments.maxExcelSheets": "Max Excel sheets",
    "attachments.largePreviewRows": "Large-table preview rows",
    "attachments.toolModeEnabled": "Enable large-table tool mode",
    "attachments.toolModeMinRows": "Min rows to trigger tool mode",
    "attachments.toolModeMaxBytes": "Max file bytes for tool mode",
    "attachments.sqlTimeoutMs": "SQL timeout (ms)",
    "attachments.imageReplayCapChars": "Image replay cap chars",
    "attachments.videoReplayCapChars": "Video replay cap chars",
    "attachments.videoTranscriptChunkSize": "Video transcript chunk size",
    "attachments.videoTranscriptChunkOverlap": "Video transcript chunk overlap",
    "attachments.archiveMaxDepth": "Archive max depth",
    "attachments.archiveMaxFileCount": "Archive max file count",
    "attachments.archiveMaxEntryBytes": "Archive max entry uncompressed bytes",
    "attachments.archiveMaxTotalBytes": "Archive max total uncompressed bytes",
    "attachments.highPreviewWarn": "Large-table preview rows is above 200, which may significantly increase token usage. Continue?",
    "attachments.invalidNumber": "Please enter valid positive integers",
    "attachments.sqlTimeoutHint": "Hard wall-clock timeout. Range 100..120000, default 8000. Timeout returns structured sql_timeout error.",
    "attachments.imageReplayCapHint": "Replay cap for query_image_attachment OCR/description results in historical context. Range 600..30000, default 4000.",
    "attachments.videoReplayCapHint": "Replay cap for query_video_attachment transcript results in historical context. Range 600..30000, default 4000.",
    "attachments.videoTranscriptChunkHint": "Default chunk parameters used by query_video_attachment(task=transcript) when persisting transcript chunks for query_text_attachment retrieval.",
    "attachments.archivePolicyHint": "Unified archive_processor budget for zip/tar/tgz/gz: limits depth, file count and uncompressed size.",
    "attachments.loadError": "Load failed",
    "attachments.saved": "Saved",
    "attachments.save": "Save",
    "attachments.resetDefaults": "Reset defaults",
    "profile.help": "Adjust display name, avatar, and account identifiers here. In chat, avatars are circular; the assistant uses the site logo.",
    "profile.displayName": "Display name",
    "profile.username": "Username",
    "profile.userId": "User ID",
    "profile.tenantId": "Team ID",
    "profile.role": "Role",
    "profile.createdAt": "Created at",
    "profile.avatar": "Avatar",
    "profile.avatarHint": "PNG, JPEG, WebP, or GIF, up to 2 MB.",
    "profile.chooseImage": "Choose image",
    "profile.removeAvatar": "Remove avatar",
    "profile.save": "Save settings",
    "profile.saved": "Saved",
    "profile.openChat": "Open chat",
    "profile.loadError": "Load failed",
    "profile.uploadError": "Upload failed",
    "profile.chatPrefs": "Chat Preferences",
    "profile.memoryMode": "Memory mode",
    "profile.memoryModeDefault": "Default (inject allowed)",
    "profile.memoryModeStoreOnly": "Store only (no inject)",
    "profile.memoryCurator": "Memory curator specialist",
    "profile.memoryCuratorEnabled": "Enabled",
    "profile.memoryCuratorDisabled": "Disabled",
    "table.name": "name",
    "table.provider": "provider",
    "stack.title": "Stack",
    "stack.alerts": "Alerts",
    "stack.mustCleanup": "Duplicate workers detected. Cleanup is required before continuing.",
    "stack.missingRequired": "Required services are not running. Start the stack first.",
    "stack.missingServices": "Missing services: {services}",
    "stack.noAlerts": "No anomalies detected.",
    "stack.cleanup": "Cleanup orphan workers",
    "stack.cleanupDone": "Cleanup completed. Killed orphan processes: {count}",
    "stack.cleanupNone": "No orphan processes found.",
    "stack.up": "stack up",
    "stack.down": "stack down",
    "table.service": "service",
    "table.pid": "pid",
    "table.status": "status",
    "status.running": "running",
    "status.stopped": "stopped",
    "tenants.title": "Teams",
    "tenants.select": "Select Team",
    "tenants.create": "Create Team",
    "tenants.createPlaceholder": "Team name (default Team)",
    "tenants.users": "Users",
    "tenants.bindings": "Channel Bindings",
    "tenants.bindCodes": "Bind Codes",
    "tenants.createCode": "Create Bind Code",
    "tenants.deleteCode": "Delete",
    "tenants.codeStatus": "Status",
    "tenants.codeUsed": "Used",
    "tenants.codeUnused": "Unused",
    "tenants.codeUsedBy": "Used By",
    "tenants.codeDeleteConfirm": "Delete this bind code?",
    "tenants.codeDeleted": "Bind code deleted: {code}",
    "tenants.role": "Role",
    "tenants.codeOptional": "Code (optional, auto-generated if blank)",
    "tenants.deleteUnbound": "Delete Unbound Users",
    "tenants.deleted": "Deleted unbound users: {count}",
    "tenants.deleteUnboundResult": "Unbound cleanup: deleted={deleted}, orphan={orphan}, bound={bound}, total={total}",
    "tenants.saved": "Configuration saved",
    "tenants.noTenants": "No teams found. Create one via bind flow or bootstrap script first.",
    "tenants.noUsers": "No users under this team.",
    "tenants.noBindings": "No channel bindings under this team.",
    "table.id": "id",
    "table.createdAt": "created_at",
    "table.userId": "user_id",
    "table.username": "username",
    "table.externalUserId": "external_user_id",
    "table.channel": "channel",
    "tenants.userSource": "Source",
    "tenants.sourceWecom": "WeCom",
    "tenants.sourceChannel": "Other channel",
    "tenants.sourceConsole": "Console",
    "tenants.chatLogin": "Web login",
    "tenants.chatLoginYes": "Yes (password set)",
    "tenants.chatLoginNo": "No",
    "tenants.noSessionTenant": "Missing team in session. Please sign in again.",
    "tenants.sessionTenantMissing": "The team for this session is not in the list. Sign in again or contact an admin.",
    "tenants.scopeHint": "The team selector controls which team’s users, bindings, and bind codes are shown below. Accounts named administrator may switch and manage any team. The last column marks the team your login session was issued for.",
    "tenants.colScope": "Session marker",
    "tenants.scopeLoginHome": "Logged-in team",
    "tenants.allTenantsHint": "With multiple teams: “Logged-in team” is informational; the selected team in the dropdown is what you edit.",
    "tenants.rowActions": "Actions",
    "tenants.colTenantName": "Team name",
    "tenants.colTenantId": "Team ID",
    "tenants.deleteTenant": "Delete team",
    "tenants.deleteTenantConfirm": "Delete team “{name}”? All users, bindings, and data under it will be removed. This cannot be undone.",
    "tenants.errLastTenant": "At least one team must remain.",
    "tenants.errCannotDeleteCurrentTenant": "You cannot delete the team of your current session. Switch to another team first or use another account.",
    "tenants.errTenantDeleteMiss": "Delete had no effect (constraints may have blocked it). Check server logs.",
    "tenants.deleteDisabledLast": "At least one team must remain.",
    "tenants.deleteDisabledCurrent": "You cannot delete your current session team; log in with another team UUID on the login page first.",
    "audit.title": "Audit & Trace",
    "audit.sessionIdPlaceholder": "session_id (optional)",
    "audit.query": "Query",
    "audit.result": "Result",
    "audit.note": "Supports dual view: table + raw JSON.",
    "audit.auditTable": "Audit Table",
    "audit.traceTable": "Trace Table",
    "audit.rawJson": "Raw JSON",
    "audit.empty": "No data",
    "audit.columns": "Columns",
    "table.timestamp": "timestamp",
    "table.specialist": "specialist",
    "table.action": "action",
    "table.statusText": "status",
    "table.reason": "reason",
    "table.durationMs": "duration(ms)",
    "table.routeAttachmentIds": "route_attachment_ids",
    "table.inputAttachmentIds": "input_attachment_ids",
    "table.outputAttachmentIds": "output_attachment_ids",
    "table.outputAttachmentUrls": "output_attachment_urls",
    "table.noOutputAttachment": "no_output_attachment",
    "table.eventType": "event_type",
    "table.traceId": "trace_id",
    "table.spanId": "span_id",
    "table.parentSpanId": "parent_span_id",
    "table.payload": "payload",
    "table.user": "user",
    "table.sessionsCount": "sessions",
    "table.activeSessions30m": "active_sessions(30m)",
    "table.activeLogins30m": "active_logins(30m)",
    "table.totalTokensEst": "total_tokens(est)",
    "plugins.title": "Tool Plugins",
    "workspacePaths.help":
      "Per-user extra absolute roots (besides AIA_WORKSPACE_ROOT / project root). Use | as separator, e.g. D:\\\\|E:\\\\repos\\\\other. Merged with gateway env AIA_WORKSPACE_EXTRA_ROOTS. These roots are enforced for built-in workspace tools and, for this user’s chat sessions, appended to the official @modelcontextprotocol/server-filesystem process argv.",
    "workspacePaths.tenant": "Team",
    "workspacePaths.user": "User",
    "workspacePaths.extraRoots": "Extra roots (| separated)",
    "workspacePaths.allowAny": "Allow any path (high risk)",
    "workspacePaths.allowAnyHint":
      "Applies only to built-in workspace tools (read_file / glob, etc.); it does not unlock MCP filesystem or auto-mount whole disks for MCP. List directories you need in “Extra roots” or AIA_WORKSPACE_EXTRA_ROOTS.",
    "workspacePaths.allowHighTools": "Allow high-risk public tools (global)",
    "workspacePaths.allowHighToolsHint":
      "When enabled, high-risk public tools (run_command / write_file / edit_file, etc.) become model-visible (equivalent to AIA_PUBLIC_TOOLS_ALLOW_HIGH=1).",
    "workspacePaths.load": "Load",
    "workspacePaths.save": "Save",
    "workspacePaths.status": "Status",
    "workspacePaths.fromDb": "Saved in database",
    "workspacePaths.selfOnly": "You can only view and edit your own workspace path policy (not other users).",
    "chat.newSession": "New chat",
    "chat.send": "Send",
    "chat.sessions": "Sessions",
    "chat.placeholder": "Message…",
    "chat.empty": "No messages yet",
    "chat.noSessions": "No sessions yet. Create one to start.",
    "chat.loading": "Loading…",
    "chat.sending": "Sending…",
    "chat.error": "Request failed",
    "wecom.title": "WeCom Config",
    "wecom.botId": "Bot ID",
    "wecom.botSecret": "Bot Secret",
    "wecom.autoBind": "Auto bind on first message",
    "wecom.autoBindTenant": "Auto bind team",
    "wecom.autoBindRole": "Auto bind role",
    "wecom.unbind": "Unbind WeCom",
    "wecom.unbindConfirm": "Clear local WeCom config and all WeCom bindings/sessions?",
    "wecom.unbindDone": "WeCom unbound. identities={ident}, sessions={sess}",
    "action.save": "Save",
    "table.version": "version",
    "table.entryPoint": "entry_point",
    "table.enabled": "enabled",
    "common.notFound": "Not found",
    "common.forbidden": "You do not have access to this page.",
    "common.error": "Error",
    "theme.label": "Color theme",
    "theme.deepseek": "DeepSeek (default)",
    "theme.github": "GitHub Dark",
    "theme.nord": "Nord",
    "theme.dracula": "Dracula",
    "theme.forest": "Forest",
    "theme.catppuccin": "Catppuccin Mocha",
    "theme.light": "Light",
    "lang.switch": "中文",
    "memory.title": "Memory Governance",
    "memory.hits": "Recent Hits",
    "memory.items": "Memory Items",
    "memory.config": "Vector Config",
    "memory.enabled": "Enable vector retrieval",
    "memory.backend": "Backend",
    "memory.topk": "TopK",
    "memory.writerEnabled": "Enable auto write",
    "memory.minConfidence": "Min write confidence",
    "memory.save": "Save Config",
    "memory.reindex": "Reindex vectors",
    "memory.cleanup": "Cleanup low-confidence",
    "memory.delete": "Delete",
    "memory.noData": "No memory data",
    "memory.filters": "Filters",
    "memory.tenantId": "team ID / tenant_id (optional)",
    "memory.userId": "user_id (optional)",
    "memory.applyFilters": "Apply Filters",
    "memory.clearFilters": "Clear Filters",
    "memory.stats": "Stats",
    "memory.hitCount": "Hit Count",
    "memory.itemCount": "Memory Items",
    "memory.avgScore": "Average Score",
    "memory.topSources": "Recent Sources",
    "memory.wikiCard": "Wiki",
    "memory.wikiStatus": "Plugin status",
    "memory.wikiPluginFound": "Installed: {name} v{version}",
    "memory.wikiPluginMissing": "memory-wiki plugin not found",
    "memory.openPlugins": "Open plugins page",
    "auth.login": "Login",
    "auth.logout": "Logout",
    "auth.username": "Username",
    "auth.consoleUsernameHint": "Username and password; menus still follow your permissions.",
    "auth.password": "Password",
    "auth.invalid": "Login failed",
    "auth.disabled": "Account is disabled",
    "users.title": "User Management",
    "users.search": "Search users",
    "users.colUser": "User",
    "users.createNamePlaceholder": "Name (login id, unique)",
    "users.createNameRequired": "Enter a name.",
    "users.deleteConfirm": "Delete this user? This cannot be undone.",
    "users.create": "Create User",
    "users.update": "Update",
    "users.delete": "Delete",
    "users.disable": "Disable",
    "users.enable": "Enable",
    "users.passwordOptional": "New password (optional)",
    "users.wecomAccounts": "WeCom instances (named, multiple per user)",
    "users.wecomInstanceName": "Instance name",
    "users.wecomBotSecret": "Bot Secret",
    "users.hasBotSecret": "Bot secret set",
    "users.clearBotSecret": "Clear bot secret",
    "users.loadForm": "Load into form",
    "users.noBindingsForUser": "No WeCom binding or saved instance yet; after the user binds on WeChat, a row appears—fill secrets and save.",
    "users.accountId": "Account ID",
    "users.wecomBotId": "Bot ID",
    "users.botIdRequired": "Bot ID is required",
    "users.accountName": "Name",
    "users.accountActive": "Active",
    "users.accountActions": "Account Actions",
    "users.accountSave": "Save Account",
    "users.accountDelete": "Delete Account",
    "users.wecomUserLabel": "User",
    "users.wecomUserEmpty": "Click a user row in the table above",
    "users.accountLoadHint": "After selecting a user, the table lists bindings and instances. Click “Load into form” to edit, then fill Bot Secret and save (no auto-fill).",
    "users.noTenant": "Sign in first and choose a team scope",
    "users.needUserRead": "admin:user:read is required to view and edit the user list.",
    "users.colActive": "Active",
    "users.colSetRole": "Set role",
    "adminAudit.title": "Admin Operation Audit",
    "adminAudit.action": "Action",
    "adminAudit.actor": "Actor",
    "adminAudit.status": "Status",
    "adminAudit.total": "Total {total}",
    "adminAudit.jumpPlaceholder": "Page",
    "adminAudit.jump": "Go",
    "models.sectionActive": "Active profile",
    "models.sectionBindings": "Agent ↔ profile bindings",
    "models.sectionNew": "New profile",
    "models.sectionApi": "API & secret",
    "models.chatModelSelector": "Chat model selector",
    "models.chatModelSelectorHint": "Control whether the model dropdown is visible on the Chat page.",
    "models.sectionEval": "Agent Evaluation",
    "models.pickModel": "Profile",
    "models.agentBindingHelp": "Optional per-role profile; leave empty to use the global selection above.",
    "models.bindingsExtraHint": "Profiles shared via user or team grants appear in the picker above; each member binds roles here themselves.",
    "models.bindingsScopeHint": "Pickers only include built-in profiles, ones you created, and those granted by an admin (team-wide or to you)—the same set your account can see.",
    "models.linkApiGrants": "Open API access grants",
    "models.grantsNavHint": "Control who can see and select shareable profiles (keys and endpoints are edited on Model Management).",
    "apiGrants.intro": "Pick a profile below, then grant visibility to the whole team or specific users. Keys and URLs are still edited under Model Management; members bind roles there after they can see the profile.",
    "apiGrants.pickApi": "Profile to grant",
    "apiGrants.teamSection": "Grant to entire team",
    "apiGrants.teamHint": "Everyone in the tenant can then see this profile in their picker; endpoints and secrets stay under Model Management.",
    "apiGrants.userSection": "Grant to one user",
    "apiGrants.userHint": "Only that user sees the profile in their picker; they bind roles under Model Management.",
    "apiGrants.noShareable": "(No shareable profiles)",
    "apiGrants.forbidden": "Only the administrator console user with team write permission (or owner role) can manage API access grants.",
    "apiGrants.openModels": "Go to Model Management",
    "models.useGlobal": "(use global)",
    "models.role.manager": "Manager",
    "models.role.ops": "Network ops",
    "models.role.generalist": "Generalist",
    "models.role.image": "Image",
    "models.role.memory": "Memory Curator",
    "models.profileName": "Name",
    "models.mode": "Mode",
    "models.mode.openai": "OpenAI-compatible",
    "models.mode.openai_responses": "OpenAI Responses",
    "models.mode.anthropic": "Anthropic",
    "models.mode.google": "Google (Gemini)",
    "models.mode.ollama": "Ollama",
    "models.mode.rule": "Rule (no LLM)",
    "models.model": "Model",
    "models.baseUrl": "Base URL",
    "models.baseUrlPlaceholder": "Optional",
    "models.apiKey": "API key",
    "models.thinkMode": "Think mode (this API profile only)",
    "models.thinkModeHint": "When on, replay full assistant reasoning_content for this profile only (default off).",
    "models.reasoningEffort": "Reasoning effort",
    "models.reasoningEffortDefault": "Default",
    "models.reasoningEffortLow": "Low",
    "models.reasoningEffortMedium": "Medium",
    "models.reasoningEffortHigh": "High",
    "models.rememberKey": "Remember key (encrypted in DB)",
    "models.save": "Save",
    "models.delete": "Delete profile",
    "models.deleteConfirm": "Delete this profile? This cannot be undone.",
    "models.cannotDeleteBuiltin": "Cannot delete the built-in Ollama profile.",
    "models.createNamePlaceholder": "Display name",
    "models.newProfileDefault": "New profile",
    "models.createBtn": "Create",
    "models.builtinLocked": "Built-in Ollama profile: mode is fixed; you can edit URL/model.",
    "models.warnKeyInDb": "A key exists in DB: empty field won’t overwrite until you enter a new key or uncheck remember.",
    "models.openaiKeyHint": "Without a key, OPENAI_API_KEY from the environment may be used.",
    "models.ollamaHint": "Local Ollama defaults to http://127.0.0.1:11434; API key is usually empty.",
    "models.evalTotal": "Samples",
    "models.evalSuccess": "Success rate",
    "models.evalP95": "P95 latency",
    "models.evalLogs": "Recent eval logs",
    "models.evalToggle": "Agent Evaluation · click to expand (preview up to 100 rows)",
    "models.evalLogsPreview": "Preview",
    "models.evalDownloadCsv": "Download full CSV",
    "models.evalDownloadJson": "Download full JSON",
    "models.noEvalLogs": "No evaluation logs yet",
    "models.noProfiles": "No LLM profiles.",
    "models.readonly": "Read-only: missing admin:tenant:write.",
    "models.profileReadonlyHint": "This profile is shared by an administrator: you may select it for chat but cannot edit name, endpoint, or secret.",
    "models.grantsTitle": "Grant other users access to the selected profile",
    "models.grantsHint": "Only the administrator account can manage grants. Granted users see and can select this profile (shared API key).",
    "models.grantsGrantBtn": "Grant",
    "models.grantsRevoke": "Revoke",
    "models.grantsEmpty": "No per-user grants yet.",
    "models.grantsUserHint": "Grant to one user:",
    "models.grantTenantBtn": "Entire team",
    "models.revokeTenantGrant": "Revoke team",
    "models.tenantGrantOn": "Team: granted",
    "models.tenantGrantOff": "Team: not granted",
    "models.membersTitle": "Model profiles visible to each member",
    "models.vis.builtin": "Built-in",
    "models.vis.owned": "Mine",
    "models.vis.grantUser": "User grant",
    "models.vis.grantTenant": "Team grant",
    "models.vis.global": "Global",
    "models.vis.otherUser": "Other user",
    "models.loadFailed": "Load failed; see error below.",
    "models.dbPath": "SQLite file in use",
    "secrets.migrateTitle": "Secret migration",
    "secrets.migrateHint": "Legacy b64-encoded secrets detected (weak protection). Set AIA_ASSISTANT_MASTER_KEY and migrate to a stronger encrypted format.",
    "secrets.migrateBtn": "Migrate now",
    "secrets.migrateDone": "Migration done: settings={s}, profiles={p}",
    "secrets.migrateNoop": "No legacy secrets found.",
    "secrets.migrateNeedKey": "AIA_ASSISTANT_MASTER_KEY is not set; cannot migrate.",
    "secrets.migrateForbidden": "Requires admin:tenant:write permission.",
    "sessionMonitor.totals": "Overview",
    "sessionMonitor.totalTokensEst": "Total tokens (est)",
    "sessionMonitor.activeSessions30m": "Active sessions (30m)",
    "sessionMonitor.activeLogins30m": "Active logins (30m)",
    "sessionMonitor.usersCount": "Users",
    "sessionMonitor.userStats": "User stats",
    "sessionMonitor.sessions": "Sessions",
    "sessionMonitor.filterUser": "Filter users",
    "sessionMonitor.filterSession": "Filter sessions",
    "sessionMonitor.selectUserFirst": "Select a user to view sessions.",
    "sessionMonitor.viewAudit": "Open audit",
    "sessionMonitor.viewDetail": "View details",
    "sessionMonitor.messages": "Messages",
    "sessionMonitor.exportMd": "Export MD",
    "sessionMonitor.exportJson": "Export JSON",
    "sessionMonitor.pagePrev": "Prev",
    "sessionMonitor.pageNext": "Next",
    "sessionMonitor.pageInfo": "Page {page} / {totalPages}",
    "sessionMonitor.noMessages": "No messages in this session.",
    "sessionMonitor.closeDetail": "Close details",
    "sessionMonitor.roleFilter": "Role filter",
    "sessionMonitor.roleAll": "All",
    "sessionMonitor.roleUser": "User",
    "sessionMonitor.roleAssistant": "Assistant",
    "sessionMonitor.roleTool": "Tool",
    "sessionMonitor.onlyAdministrator": "This page is available to administrator only.",
  },
};

const LANG_KEY = "ops_admin_lang";
const SESSION_MONITOR_ROLE_FILTER_KEY = "ops_session_monitor_role_filter";
let currentLang = (localStorage.getItem(LANG_KEY) || "zh").toLowerCase();
if (!I18N[currentLang]) currentLang = "zh";
const AUTH_TOKEN_KEY = "ops_admin_token";
const AUTH_SESSION_KEY = "ops_admin_session";
const CHAT_MEMORY_MODE_KEY = "ops_chat_memory_mode";
/** 与 localStorage 不同：sessionStorage 按标签页隔离，避免「管理员页 + 普通用户控制台」互相覆盖 token。 */
function authStoreGet(key) {
  try {
    return sessionStorage.getItem(key);
  } catch (_) {
    return null;
  }
}
function authStoreSet(key, value) {
  try {
    sessionStorage.setItem(key, value);
  } catch (_) {}
}
function authStoreRemove(key) {
  try {
    sessionStorage.removeItem(key);
  } catch (_) {}
}
/** 历史版本把 token 放在 localStorage，多标签会串号；启动时清掉以免误读。 */
try {
  localStorage.removeItem(AUTH_TOKEN_KEY);
  localStorage.removeItem(AUTH_SESSION_KEY);
} catch (_) {}
/**
 * /chat 与 /admin 历史上使用不同 key；当用户在同一窗口从 /chat 跳到 /admin 时，
 * 没有 opener 可用，需要从 chat 存储主动迁移一次以复用登录态。
 */
(function seedAdminAuthFromChatStorageIfNeeded() {
  try {
    if (authStoreGet(AUTH_TOKEN_KEY)) return;
    const pairs = [
      [sessionStorage, "ops_chat_token", "ops_chat_session"],
      [localStorage, "ops_chat_token", "ops_chat_session"],
    ];
    for (const [store, kTok, kSess] of pairs) {
      let tok = null;
      let sess = null;
      try {
        tok = store.getItem(kTok);
        sess = store.getItem(kSess);
      } catch (_) {
        continue;
      }
      const t = String(tok || "").trim();
      const s = String(sess || "").trim();
      if (t && s) {
        authStoreSet(AUTH_TOKEN_KEY, t);
        authStoreSet(AUTH_SESSION_KEY, s);
        break;
      }
    }
  } catch (_) {}
})();
/** 从聊天页新开 /admin（审计、设置等）时，复用 opener 同一登录态（chat 或 admin token）。勿对 window.open 使用 noopener，否则读不到 opener。 */
(function seedAdminAuthFromOpenerIfNeeded() {
  try {
    if (authStoreGet(AUTH_TOKEN_KEY)) return;
    const op = window.opener;
    if (!op || op === window) return;
    if (String(location.origin) !== String(op.location.origin)) return;
    const pairs = [
      ["ops_admin_token", "ops_admin_session"],
      ["ops_chat_token", "ops_chat_session"],
    ];
    for (const [kTok, kSess] of pairs) {
      let tok = null;
      let sess = null;
      try {
        tok = op.sessionStorage.getItem(kTok) || op.localStorage.getItem(kTok);
        sess = op.sessionStorage.getItem(kSess) || op.localStorage.getItem(kSess);
      } catch (_) {
        continue;
      }
      const t = String(tok || "").trim();
      const s = String(sess || "").trim();
      if (t && s) {
        authStoreSet(AUTH_TOKEN_KEY, t);
        authStoreSet(AUTH_SESSION_KEY, s);
        break;
      }
    }
  } catch (_) {}
})();
let authSession = null;

function t(key) {
  return (I18N[currentLang] && I18N[currentLang][key]) || (I18N.en && I18N.en[key]) || key;
}

function tf(key, vars = {}) {
  const template = t(key);
  return template.replace(/\{(\w+)\}/g, (_, k) => String(vars[k] ?? ""));
}

/** 合并展示名与登录名（列表/团队页共用） */
function formatUserLabel(u) {
  const un = String(u.username ?? "").trim();
  const dn = String(u.display_name ?? "").trim();
  if (dn && un && dn.toLowerCase() !== un.toLowerCase()) {
    return `${dn} (${un})`;
  }
  return dn || un || "—";
}

function formatAuditActor(r) {
  const un = String(r.actor_username ?? "").trim();
  const dn = String(r.actor_display_name ?? "").trim();
  const id = String(r.actor_user_id ?? "").trim();
  if (dn && un && dn.toLowerCase() !== un.toLowerCase()) {
    return `${dn} (${un})`;
  }
  if (dn || un) return dn || un;
  return id ? id.slice(0, 8) + (id.length > 8 ? "…" : "") : "—";
}

function applyI18nStatic() {
  document.documentElement.lang = currentLang === "zh" ? "zh-CN" : "en";
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    const key = node.getAttribute("data-i18n");
    node.textContent = t(key);
  });
  const langBtn = document.getElementById("btnLang");
  if (langBtn) langBtn.textContent = t("lang.switch");
  const themeSel = document.getElementById("adminThemeSelect");
  if (themeSel && window.OclawAdminTheme) {
    try {
      themeSel.value = OclawAdminTheme.currentAdminTheme();
    } catch (_) {}
  }
}

function toggleLang() {
  currentLang = currentLang === "zh" ? "en" : "zh";
  localStorage.setItem(LANG_KEY, currentLang);
}

function getRoute() {
  const raw = (location.hash || "#/stack").replace(/^#\//, "");
  const [pageRaw, queryRaw] = raw.split("?", 2);
  let page = (pageRaw || "stack").trim();
  if (page === "channels") page = "stack";
  if (page === "tenants") page = "users";
  const params = new URLSearchParams(queryRaw || "");
  return { page, params };
}

/** 当控制台挂在子路径（如 /gw/admin）时，把 /admin/api/... 解析为 /gw/admin/api/... */
function resolveAdminApiUrl(path) {
  const p = String(path || "");
  if (!p.startsWith("/admin/")) return p;
  const pathname = (location.pathname || "").replace(/\/+$/, "") || "/";
  const marker = "/admin";
  const pos = pathname.lastIndexOf(marker);
  if (pos <= 0) return p;
  return pathname.slice(0, pos) + p;
}

function resolveChatUrl() {
  const pathname = (location.pathname || "").replace(/\/+$/, "") || "/";
  const marker = "/admin";
  if (pathname.endsWith(marker)) {
    return `${pathname.slice(0, -marker.length) || ""}/chat`;
  }
  return "/chat";
}

function getStoredAuthToken() {
  return String(authStoreGet(AUTH_TOKEN_KEY) || "").trim();
}

/** 会话在服务端失效或本地缺 token 时清理，并下一帧回到登录（避免在 router 内部 await router 盖住登录页） */
function scheduleReauthAfter401(requestUrl) {
  const u = String(requestUrl || "");
  if (u.includes("/admin/api/auth/login") || u.includes("/admin/api/auth/bootstrap")) return;
  authStoreRemove(AUTH_TOKEN_KEY);
  authStoreRemove(AUTH_SESSION_KEY);
  authSession = null;
  setTimeout(() => {
    router().catch(() => {});
  }, 0);
}

function _haltAfter401() {
  // 401 means "login required". We re-route to login; callers should not show a "request failed" popup.
  // Returning a never-resolving promise avoids bubbling errors into UI code that would flash an alert.
  return new Promise(() => {});
}

async function apiGet(path) {
  const url = resolveAdminApiUrl(path);
  const token = getStoredAuthToken();
  const headers = { "accept": "application/json" };
  if (token) headers["authorization"] = `Bearer ${token}`;
  const res = await fetch(url, { headers });
  if (res.status === 401) {
    scheduleReauthAfter401(url);
    return await _haltAfter401();
  }
  if (!res.ok) throw new Error(`GET ${url} ${res.status}`);
  return await res.json();
}

async function apiPost(path, body) {
  const url = resolveAdminApiUrl(path);
  const token = getStoredAuthToken();
  const headers = { "content-type": "application/json", "accept": "application/json" };
  if (token) headers["authorization"] = `Bearer ${token}`;
  const res = await fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify(body ?? {}),
  });
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch (_) {
    data = null;
  }
  if (res.status === 401) {
    scheduleReauthAfter401(url);
    return await _haltAfter401();
  }
  if (!res.ok) {
    const d = data && typeof data === "object" ? data : {};
    const detail = (d).detail != null ? String((d).detail) : "";
    const errKey = (d).error != null ? String((d).error) : "";
    const msg = detail || errKey || `POST ${url} ${res.status}`;
    throw new Error(msg);
  }
  return data ?? {};
}

/** Skills endpoints often return HTTP 200 with `{ ok: false, result: {...} }` on failure — treat as error for UX. */
function assertSkillMutationOk(r, fallbackMessage) {
  if (!r || r.ok !== false) return;
  const res = r.result && typeof r.result === "object" ? r.result : {};
  const code = res.error_code != null ? String(res.error_code).trim() : "";
  const detail = res.detail != null ? String(res.detail).trim() : "";
  const msg = [code, detail].filter(Boolean).join(": ") || String(fallbackMessage || "skill operation failed");
  throw new Error(msg);
}

async function apiRequest(method, path, body) {
  const url = resolveAdminApiUrl(path);
  const token = getStoredAuthToken();
  const headers = { "accept": "application/json" };
  if (token) headers["authorization"] = `Bearer ${token}`;
  if (body !== undefined && method !== "GET" && method !== "HEAD") {
    headers["content-type"] = "application/json";
  }
  const res = await fetch(url, {
    method,
    headers,
    body: body !== undefined && method !== "GET" && method !== "HEAD" ? JSON.stringify(body ?? {}) : undefined,
  });
  if (res.status === 401) {
    scheduleReauthAfter401(url);
    return await _haltAfter401();
  }
  if (!res.ok) {
    let msg = `${method} ${url} ${res.status}`;
    try {
      const j = await res.json();
      if (j && j.detail !== undefined) {
        msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
      }
    } catch (_) {}
    throw new Error(msg);
  }
  const ct = res.headers.get("content-type") || "";
  if (!ct.includes("application/json")) return {};
  return await res.json();
}

async function apiPostFormData(path, formData) {
  const url = resolveAdminApiUrl(path);
  const token = getStoredAuthToken();
  const headers = {};
  if (token) headers.authorization = `Bearer ${token}`;
  const res = await fetch(url, { method: "POST", headers, body: formData });
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch (_) {
    data = null;
  }
  if (res.status === 401) {
    scheduleReauthAfter401(url);
    return await _haltAfter401();
  }
  if (!res.ok) {
    const d = data && typeof data === "object" ? data : {};
    const detail = d.detail != null ? String(d.detail) : "";
    const errKey = d.error != null ? String(d.error) : "";
    throw new Error(detail || errKey || `POST ${url} ${res.status}`);
  }
  return data ?? {};
}

async function apiDeleteJson(path) {
  const url = resolveAdminApiUrl(path);
  const token = getStoredAuthToken();
  const headers = { accept: "application/json" };
  if (token) headers.authorization = `Bearer ${token}`;
  const res = await fetch(url, { method: "DELETE", headers });
  if (res.status === 401) {
    scheduleReauthAfter401(url);
    return await _haltAfter401();
  }
  if (!res.ok) {
    let msg = `DELETE ${url} ${res.status}`;
    try {
      const j = await res.json();
      if (j && j.detail !== undefined) msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch (_) {}
    throw new Error(msg);
  }
  try {
    return await res.json();
  } catch (_) {
    return {};
  }
}

function _activeCopyCell() {
  return document.querySelector(".cell-copyable.cell-selected");
}

function _selectCopyCell(cell) {
  const prev = _activeCopyCell();
  if (prev && prev !== cell) prev.classList.remove("cell-selected");
  if (cell) cell.classList.add("cell-selected");
}

function _shouldIgnoreCopyShortcut(ev) {
  const t = ev && ev.target ? ev.target : null;
  if (!t || !(t instanceof HTMLElement)) return false;
  const tag = String(t.tagName || "").toLowerCase();
  if (t.isContentEditable) return true;
  return tag === "input" || tag === "textarea" || tag === "select";
}

function _installCellCopyKeyboardShortcut() {
  if (window.__adminCellCopyShortcutInstalled) return;
  window.__adminCellCopyShortcutInstalled = true;
  document.addEventListener("keydown", async (ev) => {
    if (_shouldIgnoreCopyShortcut(ev)) return;
    if (!(ev.ctrlKey || ev.metaKey) || String(ev.key || "").toLowerCase() !== "c") return;
    const active = _activeCopyCell();
    if (!active) return;
    try {
      const txt = String(active.getAttribute("data-copy-text") || active.getAttribute("title") || active.textContent || "");
      if (!txt.trim()) return;
      ev.preventDefault();
      await navigator.clipboard.writeText(txt);
      active.classList.add("cell-copied");
      setTimeout(() => active.classList.remove("cell-copied"), 2600);
    } catch (_) {
      // no-op
    }
  });
}

function attachCellCopyBehavior(cell, getCopyText) {
  if (!cell || cell.dataset.copyBound === "1") return;
  _installCellCopyKeyboardShortcut();
  cell.dataset.copyBound = "1";
  cell.classList.add("cell-copyable");
  cell.addEventListener("click", () => {
    _selectCopyCell(cell);
  });
  cell.addEventListener("dblclick", async () => {
    try {
      const txt = String(typeof getCopyText === "function" ? getCopyText() : (cell.textContent || ""));
      if (!txt) return;
      cell.setAttribute("data-copy-text", txt);
      await navigator.clipboard.writeText(txt);
      cell.classList.add("cell-copied");
      setTimeout(() => cell.classList.remove("cell-copied"), 2600);
    } catch (_) {
      // keep tooltip fallback when clipboard API unavailable
    }
  });
}

function el(tag, attrs = {}, children = []) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === undefined || v === null) continue;
    if (k === "class") e.className = v;
    else if (k === "text") e.textContent = v;
    else if (k.startsWith("on") && typeof v === "function") e.addEventListener(k.slice(2), v);
    else if (k === "disabled" && v === false) {
      e.removeAttribute("disabled");
    } else e.setAttribute(k, v);
  }
  for (const c of children) e.appendChild(c);
  if (String(tag || "").toLowerCase() === "td" && String(e.getAttribute("data-copy-disabled") || "") !== "1") {
    const txt = String(e.textContent || "").trim();
    if (txt) {
      if (!e.getAttribute("title")) e.setAttribute("title", txt);
      attachCellCopyBehavior(e, () => String(e.getAttribute("title") || e.textContent || ""));
    }
  }
  return e;
}

function tdCell(value, maxLen = 120) {
  const full = String(value ?? "");
  const shown = formatSystemLocalDateTime(full);
  const title = shown === full ? full : `${shown}\n${full}`;
  const td = el("td", { text: shortText(shown, maxLen), title });
  td.setAttribute("data-copy-text", shown);
  attachCellCopyBehavior(td, () => shown);
  return td;
}

function enableTableColumnResize(tableEl, columnIndexes = []) {
  if (!tableEl) return;
  const heads = Array.from(tableEl.querySelectorAll("thead th"));
  if (!heads.length) return;
  tableEl.classList.add("table--resizable");
  heads.forEach((th) => th.querySelectorAll(".table-col-resizer").forEach((x) => x.remove()));
  const enabled = new Set(Array.isArray(columnIndexes) ? columnIndexes : []);
  heads.forEach((th, idx) => {
    if (enabled.size && !enabled.has(idx)) return;
    const handle = document.createElement("span");
    handle.className = "table-col-resizer";
    handle.addEventListener("mousedown", (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      const startX = ev.clientX;
      const startW = th.getBoundingClientRect().width;
      document.body.classList.add("col-resize-active");
      const onMove = (mv) => {
        const next = Math.max(72, Math.round(startW + (mv.clientX - startX)));
        th.style.width = `${next}px`;
      };
      const onUp = () => {
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
        document.body.classList.remove("col-resize-active");
      };
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    });
    th.appendChild(handle);
  });
}

function setActive(page) {
  document.querySelectorAll(".nav__item").forEach((a) => {
    a.classList.toggle("nav__item--active", a.dataset.page === page);
  });
  document.getElementById("topTitle").textContent = ({
    stack: t("title.stack"),
    users: t("title.users"),
    memory: t("title.memory"),
    models: t("title.models"),
    "api-grants": t("title.apiGrants"),
    audit: t("title.audit"),
    "session-monitor": t("title.sessionMonitor"),
    "admin-audit": t("title.adminAudit"),
    plugins: t("title.plugins"),
    skills: t("title.skills"),
    attachments: t("title.attachments"),
    "workspace-paths": t("title.workspacePaths"),
    profile: t("title.profile"),
  }[page] || page);
}

function mount(node) {
  const c = document.getElementById("content");
  c.innerHTML = "";
  c.appendChild(node);
}

function renderPageShell(opts = {}, children = []) {
  const title = String(opts.title || "").trim();
  const subtitle = String(opts.subtitle || "").trim();
  const actions = Array.isArray(opts.actions) ? opts.actions.filter(Boolean) : [];
  const sections = Array.isArray(opts.sections) ? opts.sections.filter((x) => x && x.id && x.label) : [];
  const head = [];
  if (title || subtitle || actions.length) {
    const left = [];
    if (title) left.push(el("h1", { class: "page-shell__title", text: title }));
    if (subtitle) left.push(el("div", { class: "page-shell__subtitle muted", text: subtitle }));
    head.push(
      el("div", { class: "page-shell__header" }, [
        el("div", { class: "page-shell__headline" }, left),
        el("div", { class: "page-shell__actions row" }, actions),
      ]),
    );
    if (sections.length > 1) {
      head.push(
        el(
          "div",
          { class: "page-shell__toc", role: "navigation", "aria-label": "page sections" },
          sections.map((s) =>
            el("button", {
              class: "page-shell__tocItem",
              type: "button",
              text: String(s.label),
              onclick: () => {
                const target = document.getElementById(String(s.id));
                if (!target) return;
                target.scrollIntoView({ behavior: "smooth", block: "start" });
              },
            }),
          ),
        ),
      );
    }
  }
  return el("section", { class: "page-shell" }, [...head, ...children.filter(Boolean)]);
}

function renderSectionCard(title, subtitle, bodyNodes = [], opts = {}) {
  const nodes = [el("div", { class: "card__title", text: title })];
  if (subtitle) nodes.push(el("div", { class: "muted", text: subtitle }));
  if (Array.isArray(opts.actions) && opts.actions.length) {
    nodes.push(el("div", { class: "row section-card__actions" }, opts.actions));
  }
  bodyNodes.filter(Boolean).forEach((node) => nodes.push(node));
  const attrs = { class: "card section-card" };
  if (opts.id) attrs.id = String(opts.id);
  return el("div", attrs, nodes);
}

function shortText(v, maxLen = 200) {
  const s = String(v ?? "");
  if (s.length <= maxLen) return s;
  return s.slice(0, Math.max(0, maxLen - 3)) + "...";
}

function formatSystemLocalDateTime(value) {
  const raw = String(value ?? "").trim();
  if (!raw) return "";
  // Keep non-datetime strings unchanged.
  if (!/^\d{4}-\d{2}-\d{2}T/.test(raw)) return raw;
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return raw;
  const locale = currentLang === "zh" ? "zh-CN" : "en-US";
  try {
    return d.toLocaleString(locale, {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
  } catch (_) {
    return raw;
  }
}

function formatIds(v) {
  if (!Array.isArray(v)) return "";
  const vals = v.map((x) => String(x ?? "").trim()).filter(Boolean);
  if (!vals.length) return "";
  if (vals.length > 4) return vals.slice(0, 4).join(", ") + ` (+${vals.length - 4})`;
  return vals.join(", ");
}

function yesNo(v) {
  return v ? "yes" : "no";
}

let runtimePrewarmReminder = "";
function markPrewarmReminder(reason) {
  const why = String(reason || "").trim();
  const base = currentLang === "zh" ? "配置已变更，请立即预热（或重启）" : "Config changed. Please run prewarm now (or restart).";
  runtimePrewarmReminder = why ? `${base} [${why}]` : base;
}

async function renderStack() {
  const [st, anomaliesResp, scanResp, prewarmStatusResp, prewarmPromptsResp, channelSpecResp, weixinDispatchResp, whatsappDispatchResp] = await Promise.all([
    apiGet("/admin/api/stack/status"),
    apiGet("/admin/api/runtime/anomalies"),
    apiGet("/admin/api/runtime/scan-artifacts"),
    apiGet("/admin/api/runtime/prewarm/status"),
    apiGet("/admin/api/runtime/prewarm/prompts?role=manager"),
    apiGet("/admin/api/chat/settings/specialist-flags"),
    apiGet("/admin/api/chat/settings/channel-dispatch/weixin"),
    apiGet("/admin/api/chat/settings/channel-dispatch/whatsapp"),
  ]);
  const requiredServices = ["gateway", "channel:wecom"];
  const runningNames = new Set(
    (Array.isArray(st.items) ? st.items : [])
      .filter((x) => Boolean(x && x.running))
      .map((x) => String(x.name || "")),
  );
  const missingRequired = requiredServices.filter((n) => !runningNames.has(n));
  const items = (st.items || []).flatMap((x) => {
    const name = String((x && x.name) || "");
    const running = Boolean(x && x.running);
    const allPids = Array.isArray(x && x.all_pids) ? x.all_pids.map((v) => String(v || "").trim()).filter(Boolean) : [];
    const primary = String((x && x.pid) || "").trim();
    const pidPorts = (x && x.pid_ports && typeof x.pid_ports === "object") ? x.pid_ports : {};
    const pidRunning = (x && x.pid_running && typeof x.pid_running === "object") ? x.pid_running : {};
    const rows = allPids.length ? allPids : (primary ? [primary] : []);
    return rows.map((pid) => {
      const ports = Array.isArray(pidPorts[pid]) ? pidPorts[pid].map((v) => String(v || "").trim()).filter(Boolean) : [];
      const isPrimary = primary && pid === primary;
      const isRunning = Boolean(pidRunning[pid]);
      return el("tr", {}, [
        el("td", {}, [
          el("div", { text: pid || "-" }),
          isPrimary ? el("div", { class: "muted", text: "primary" }) : el("span"),
        ]),
        el("td", { text: name }),
        el("td", { text: ports.length ? ports.join(", ") : "-" }),
        el("td", {}, [
          el("span", { class: "badge " + (isRunning ? "badge--ok" : "badge--bad"), text: isRunning ? t("status.running") : t("status.stopped") }),
        ]),
      ]);
    });
  });
  const btnUp = el("button", { class: "btn btn--primary", text: t("stack.up"), onclick: async () => {
    await apiPost("/admin/api/stack/up", { channel: "wecom" });
    router();
  }});
  const btnDown = el("button", { class: "btn btn--danger", text: t("stack.down"), onclick: async () => {
    await apiPost("/admin/api/stack/down", {});
    router();
  }});
  const availableDispatchSpecialists = Array.isArray(channelSpecResp && channelSpecResp.available_specialists) && channelSpecResp.available_specialists.length
    ? channelSpecResp.available_specialists.map((x) => String(x || "").trim()).filter(Boolean)
    : ["generalist"];
  const createChannelDispatchCard = (channel, title, initial) => {
    const curMode = String((initial && initial.interaction_mode) || "expert").trim() || "expert";
    const curSpecialist = String((initial && initial.specialist) || "generalist").trim() || "generalist";
    const specialistSel = el("select", { class: "input" }, availableDispatchSpecialists.map((sid) =>
      el("option", { value: sid, text: sid, selected: sid === curSpecialist ? "selected" : undefined }),
    ));
    const status = el("div", { class: "muted", text: `mode=${curMode} specialist=${curSpecialist}` });
    const saveExpertBtn = el("button", {
      class: "btn",
      text: currentLang === "zh" ? "绑定专家" : "Bind specialist",
      onclick: async () => {
        const specialist = String(specialistSel.value || "generalist").trim() || "generalist";
        const resp = await apiPost(`/admin/api/chat/settings/channel-dispatch/${encodeURIComponent(channel)}`, {
          interaction_mode: "expert",
          specialist,
        });
        status.textContent = `mode=${String(resp.interaction_mode || "expert")} specialist=${String(resp.specialist || specialist)}`;
      },
    });
    const saveComprehensiveBtn = el("button", {
      class: "btn btn--primary",
      text: currentLang === "zh" ? "综合" : "Comprehensive",
      onclick: async () => {
        const specialist = String(specialistSel.value || "generalist").trim() || "generalist";
        const resp = await apiPost(`/admin/api/chat/settings/channel-dispatch/${encodeURIComponent(channel)}`, {
          interaction_mode: "comprehensive",
          specialist,
        });
        status.textContent = `mode=${String(resp.interaction_mode || "comprehensive")} specialist=${String(resp.specialist || specialist)}`;
      },
    });
    return el("div", { class: "card" }, [
      el("div", { class: "card__title", text: title }),
      el("div", { class: "row" }, [
        el("label", { text: currentLang === "zh" ? "专家" : "Specialist" }),
        specialistSel,
        saveExpertBtn,
        saveComprehensiveBtn,
      ]),
      status,
      el("div", { class: "muted", text: currentLang === "zh" ? "默认绑定通用专家；综合模式下由全能者分派。" : "Defaults to generalist; comprehensive mode lets manager dispatch." }),
    ]);
  };
  const weixinDispatchCard = createChannelDispatchCard("weixin", "Weixin dispatch", weixinDispatchResp || {});
  const whatsappDispatchCard = createChannelDispatchCard("whatsapp", "WhatsApp dispatch", whatsappDispatchResp || {});
  const cleanupStatus = el("div", { class: "muted", text: "" });
  const btnCleanup = el("button", { class: "btn btn--danger", text: t("stack.cleanup"), onclick: async () => {
    const resp = await apiPost("/admin/api/runtime/cleanup", {});
    const killed = Array.isArray(resp.killed) ? resp.killed : [];
    const total = killed.reduce((acc, x) => acc + ((x && Array.isArray(x.killed_pids)) ? x.killed_pids.length : 0), 0);
    cleanupStatus.textContent = total > 0 ? tf("stack.cleanupDone", { count: total }) : t("stack.cleanupNone");
    router();
  }});
  const alerts = Array.isArray(anomaliesResp.items) ? anomaliesResp.items : [];
  const mustCleanup = Boolean(anomaliesResp.must_cleanup);
  const mergedAlerts = missingRequired.length
    ? []
    : alerts.filter((a) => {
        const typ = String((a && a.type) || "");
        return typ !== "duplicate_process_ambiguous";
      });
  if (missingRequired.length) {
    mergedAlerts.unshift({
      severity: "critical",
      message: tf("stack.missingServices", { services: missingRequired.join(", ") }),
    });
  }
  const alertRows = mergedAlerts.length
    ? mergedAlerts.map((a) => el("li", {
        text: `[${String(a.severity || "info").toUpperCase()}] ${String(a.message || "")}`,
      }))
    : [el("li", { text: t("stack.noAlerts") })];
  const scanItems = Array.isArray(scanResp && scanResp.items) ? scanResp.items : [];
  const scanDir = String((scanResp && scanResp.dir) || "");
  const scanStatus = el("div", { class: "muted", text: "" });
  const keepLatestInput = el("input", { class: "input", type: "number", value: "20", min: "0", max: "500" });
  const maxAgeDaysInput = el("input", { class: "input", type: "number", value: "7", min: "0", max: "3650" });
  const btnCleanScan = el("button", {
    class: "btn btn--danger",
    text: "清理扫描缓存",
    onclick: async () => {
      const resp = await apiPost("/admin/api/runtime/scan-artifacts/cleanup", {});
      scanStatus.textContent = `removed=${Number((resp && resp.removed) || 0)}`;
      router();
    },
  });
  const btnPruneScan = el("button", {
    class: "btn",
    text: "按策略清理",
    onclick: async () => {
      const keepLatest = Number(keepLatestInput.value || 20);
      const maxAgeDays = Number(maxAgeDaysInput.value || 7);
      const resp = await apiPost("/admin/api/runtime/scan-artifacts/prune", {
        keep_latest: Number.isFinite(keepLatest) ? keepLatest : 20,
        max_age_days: Number.isFinite(maxAgeDays) ? maxAgeDays : 7,
      });
      scanStatus.textContent = `removed=${Number((resp && resp.removed) || 0)} keep_latest=${Number((resp && resp.keep_latest) || 0)} max_age_days=${Number((resp && resp.max_age_days) || 0)}`;
      router();
    },
  });
  const scanRows = scanItems.length
    ? scanItems.map((x) => el("tr", {}, [
        tdCell(String(x.name || ""), 26),
        tdCell(String(x.bytes || 0), 12),
        tdCell(String(x.modified_at || ""), 28),
      ]))
    : [el("tr", {}, [el("td", { class: "muted", text: "—", colspan: "3" })])];
  const prewarmInfo = prewarmStatusResp && typeof prewarmStatusResp === "object" ? prewarmStatusResp : {};
  const prewarmLast = prewarmInfo.last && typeof prewarmInfo.last === "object" ? prewarmInfo.last : {};
  const prewarmHistory = Array.isArray(prewarmInfo.history) ? prewarmInfo.history : [];
  const freeze = prewarmInfo.freeze && typeof prewarmInfo.freeze === "object" ? prewarmInfo.freeze : {};
  const prewarmStatus = el("div", { class: "muted", text: "" });
  const btnPrewarm = el("button", {
    class: "btn btn--primary",
    text: currentLang === "zh" ? "立即预热" : "Run prewarm now",
    onclick: async () => {
      prewarmStatus.textContent = currentLang === "zh" ? "[预热] 提交中…" : "[prewarm] submitting…";
      const resp = await apiPost("/admin/api/runtime/prewarm", { mode: "async", reason: "admin_manual" });
      if (!(resp && resp.accepted)) {
        prewarmStatus.textContent = `[prewarm] accepted=${Boolean(resp && resp.accepted)}`;
        return;
      }
      prewarmStatus.textContent =
        currentLang === "zh"
          ? "[预热] 后台执行中，完成后自动刷新本页数据（含提示词）…"
          : "[prewarm] running in background; refreshing this page when finished…";
      runtimePrewarmReminder = "";
      const maxWaitMs = 120000;
      const stepMs = 400;
      let waited = 0;
      while (waited < maxWaitMs) {
        await new Promise((r) => setTimeout(r, stepMs));
        waited += stepMs;
        const st = await apiGet("/admin/api/runtime/prewarm/status");
        if (!(st && st.running)) break;
      }
      await router();
    },
  });
  const prewarmSummary = [
    `running=${Boolean(prewarmInfo.running)}`,
    `last_ok=${Boolean(prewarmLast.ok)}`,
    `elapsed_ms=${Number(prewarmLast.elapsed_ms || 0)}`,
    `freeze_enabled=${Boolean(freeze.enabled)}`,
    `frozen=${Boolean(freeze.frozen)}`,
    `last_warm=${
      Number(freeze.last_warm_ts_ms || 0) > 0
        ? formatSystemLocalDateTime(new Date(Number(freeze.last_warm_ts_ms || 0)).toISOString())
        : "-"
    }`,
  ].join(" | ");
  const historyRows = prewarmHistory.length
    ? prewarmHistory.slice(0, 20).map((x) =>
        el("tr", {}, [
          tdCell(formatSystemLocalDateTime(new Date(Number(x.finished_at_ms || 0)).toISOString()), 24),
          tdCell(String(x.reason || "-"), 20),
          tdCell(String(Boolean(x.ok)), 8),
          tdCell(String(Number(x.elapsed_ms || 0)), 10),
          tdCell(String(x.error || "-"), 38),
        ]))
    : [el("tr", {}, [el("td", { class: "muted", text: "—", colspan: "5" })])];
  const promptsSectionBody = el("div");
  const promptsRoleSelect = el("select", { class: "input" }, [
    el("option", { value: "manager", text: "manager (default)" }),
    el("option", { value: "", text: currentLang === "zh" ? "全部角色" : "all roles" }),
  ]);
  const renderPromptCards = (resp) => {
    const promptsObj = resp && typeof resp === "object" ? resp : {};
    const promptsMap = promptsObj.prompts && typeof promptsObj.prompts === "object" ? promptsObj.prompts : {};
    const promptRoleCards = Object.keys(promptsMap)
    .sort((a, b) => String(a).localeCompare(String(b)))
    .map((rid) => {
      const item = promptsMap[rid] && typeof promptsMap[rid] === "object" ? promptsMap[rid] : {};
      const finalSystem = String(item.system_prompt || "");
      return el("div", { class: "card", style: "margin-top:10px;" }, [
        el("div", { class: "card__title", text: `role: ${rid}` }),
        el("div", {}, [
          el("div", { class: "muted", text: "system_prompt" }),
          el("textarea", {
            class: "input",
            rows: "12",
            readonly: "readonly",
            text: finalSystem,
            style: "width:100%;box-sizing:border-box;",
          }),
        ]),
      ]);
      });
    promptsSectionBody.innerHTML = "";
    if (promptRoleCards.length) {
      promptRoleCards.forEach((n) => promptsSectionBody.appendChild(n));
    } else {
      promptsSectionBody.appendChild(el("div", { class: "muted", text: "-" }));
    }
  };
  const btnReloadPrompts = el("button", {
    class: "btn",
    text: currentLang === "zh" ? "刷新提示词" : "Reload prompts",
    onclick: async () => {
      const role = String(promptsRoleSelect.value || "").trim();
      const q = role ? `?role=${encodeURIComponent(role)}` : "";
      const resp = await apiGet(`/admin/api/runtime/prewarm/prompts${q}`);
      renderPromptCards(resp);
    },
  });
  promptsRoleSelect.addEventListener("change", async () => {
    const role = String(promptsRoleSelect.value || "").trim();
    const q = role ? `?role=${encodeURIComponent(role)}` : "";
    const resp = await apiGet(`/admin/api/runtime/prewarm/prompts${q}`);
    renderPromptCards(resp);
  });
  renderPromptCards(prewarmPromptsResp);
  return el("div", {}, [
    el("div", { class: "card" }, [
      el("div", { class: "card__title", text: t("stack.alerts") }),
      (mustCleanup || missingRequired.length)
        ? el("div", {
            class: "alert alert--critical",
            text: missingRequired.length ? t("stack.missingRequired") : t("stack.mustCleanup"),
          })
        : el("div", { class: "muted", text: t("stack.noAlerts") }),
      el("ul", { class: "alert-list" }, alertRows),
      missingRequired.length ? el("div", { class: "muted", text: t("stack.missingRequired") }) : el("div", { class: "row" }, [btnCleanup]),
      cleanupStatus,
    ]),
    el("div", { class: "card" }, [
      el("div", { class: "card__title", text: t("stack.title") }),
      el("div", { class: "row" }, [btnUp, btnDown]),
      el("div", { style: "height:10px" }),
      el("table", { class: "table" }, [
        el("thead", {}, [el("tr", {}, [el("th", { text: t("table.pid") }), el("th", { text: t("table.service") }), el("th", { text: "端口" }), el("th", { text: t("table.status") })])]),
        el("tbody", {}, items),
      ]),
    ]),
    weixinDispatchCard,
    whatsappDispatchCard,
    el("div", { class: "card" }, [
      el("div", { class: "card__title", text: currentLang === "zh" ? "提示词/工具预热" : "Prompt/Tool Prewarm" }),
      el("div", { class: "muted", text: prewarmSummary }),
      runtimePrewarmReminder ? el("div", { class: "alert alert--warning", text: runtimePrewarmReminder }) : el("span"),
      el(
        "div",
        {
          class: "muted",
          text:
            currentLang === "zh"
              ? "任何 skill/tool/角色/提示词变更后，请立即预热；复杂变更可直接重启。综合模式下：全能者会产出 dispatch.instruction_text，并只把该指令传给专家执行。系统每10分钟自动异步预热一次。"
              : "After any skill/tool/role/prompt change, run prewarm immediately; restart for complex changes. In comprehensive mode, manager produces dispatch.instruction_text and only this instruction is sent to specialists. System also auto-prewarms every 10 minutes.",
        },
      ),
      el("div", { class: "row" }, [btnPrewarm]),
      prewarmStatus,
    ]),
    el("div", { class: "card" }, [
      el("div", { class: "card__title", text: currentLang === "zh" ? "预热历史（最近20次）" : "Prewarm History (latest 20)" }),
      el("table", { class: "table" }, [
        el("thead", {}, [el("tr", {}, [
          el("th", { text: "finished_at" }),
          el("th", { text: "reason" }),
          el("th", { text: "ok" }),
          el("th", { text: "elapsed_ms" }),
          el("th", { text: "error" }),
        ])]),
        el("tbody", {}, historyRows),
      ]),
    ]),
    el("div", { class: "card" }, [
      el("div", { class: "card__title", text: currentLang === "zh" ? "预热后提示词（按专家）" : "Prewarmed Prompts by Role" }),
      el("div", { class: "muted", text: currentLang === "zh" ? "展示 manager + 各专家预热后的提示词内容。" : "Shows prewarmed prompt content for manager and specialists." }),
      el("div", { class: "row" }, [
        el("label", { text: currentLang === "zh" ? "角色筛选" : "Role filter" }),
        promptsRoleSelect,
        btnReloadPrompts,
      ]),
      promptsSectionBody,
    ]),
    el("div", { class: "card" }, [
      el("div", { class: "card__title", text: "扫描缓存文件" }),
      el("div", { class: "muted", text: scanDir || "-" }),
      el("div", { class: "muted", text: "仅清理 history_entries_*.json 与 state_scan_*.json" }),
      el("div", { class: "row" }, [
        el("label", { text: "keep_latest" }),
        keepLatestInput,
        el("label", { text: "max_age_days" }),
        maxAgeDaysInput,
        btnPruneScan,
        btnCleanScan,
      ]),
      scanStatus,
      el("table", { class: "table" }, [
        el("thead", {}, [el("tr", {}, [el("th", { text: "name" }), el("th", { text: "bytes" }), el("th", { text: "modified_at" })])]),
        el("tbody", {}, scanRows),
      ]),
    ]),
  ]);
}

async function renderUserManagement() {
  const sessionTid = String((authSession && authSession.tenant_id) || "").trim();
  if (!sessionTid) {
    return el("div", {}, [
      el("div", { class: "card" }, [
        el("div", { class: "card__title", text: t("users.title") }),
        el("div", { class: "muted", text: t("tenants.noSessionTenant") }),
      ]),
    ]);
  }

  let allTenants = [];
  try {
    const allTenantsResp = await apiGet("/admin/api/tenants");
    allTenants = allTenantsResp.tenants || [];
  } catch (err) {
    if (!hasPermission("admin:user:read")) {
      return el("div", { class: "card" }, [
        el("div", { class: "card__title", text: t("common.error") }),
        el("div", { class: "pre", text: String(err) }),
      ]);
    }
    allTenants = [{ id: sessionTid, name: "", created_at: "" }];
  }

  if (!allTenants.length) {
    return el("div", {}, [
      el("div", { class: "card" }, [
        el("div", { class: "card__title", text: t("users.title") }),
        el("div", { class: "muted", text: t("tenants.noTenants") }),
      ]),
    ]);
  }

  const status = el("div", { class: "muted", text: "" });

  const tenantRows = allTenants.map((x) => {
    const tid = String(x.id || "");
    const isLoginHome = tid === sessionTid;
    const tname = String(x.name || "").trim() || tid.slice(0, 8);
    const canDelete = allTenants.length > 1 && tid !== sessionTid;
    const btnDel = el("button", {
      type: "button",
      class: "btn btn--danger",
      text: t("tenants.deleteTenant"),
      disabled: canDelete ? undefined : "disabled",
      title: canDelete
        ? undefined
        : allTenants.length <= 1
          ? t("tenants.deleteDisabledLast")
          : t("tenants.deleteDisabledCurrent"),
      onclick: async (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (!canDelete) return;
        if (!window.confirm(tf("tenants.deleteTenantConfirm", { name: tname }))) return;
        status.textContent = "";
        try {
          const resp = await apiPost("/admin/api/tenants/delete", { tenant_id: tid });
          if (!resp.ok) {
            const err = String(resp.error || "error");
            status.textContent =
              err === "last_tenant_cannot_delete"
                ? t("tenants.errLastTenant")
                : err === "cannot_delete_current_tenant"
                  ? t("tenants.errCannotDeleteCurrentTenant")
                  : err;
            return;
          }
          if (!Number(resp.deleted || 0)) {
            status.textContent = t("tenants.errTenantDeleteMiss");
            return;
          }
          await router();
        } catch (err) {
          status.textContent = String(err && err.message ? err.message : err);
        }
      },
    });
    return el("tr", {}, [
      el("td", { text: String(x.name || "") }),
      el("td", { text: formatSystemLocalDateTime(String(x.created_at || "")) }),
      el("td", {
        class: isLoginHome ? "" : "muted",
        text: isLoginHome ? t("tenants.scopeLoginHome") : "—",
      }),
      el("td", {}, [btnDel]),
    ]);
  });

  const selector = el("select", { class: "input" });
  for (const item of allTenants) {
    const optLabel = String(item.name || "").trim() || String(item.id || "").slice(0, 8);
    selector.appendChild(el("option", { value: String(item.id || ""), text: optLabel }));
  }
  const preferredIdx = allTenants.findIndex((x) => String(x.id || "") === sessionTid);
  selector.selectedIndex = preferredIdx >= 0 ? preferredIdx : 0;

  const bindingsBody = el("tbody");
  const codesBody = el("tbody");

  const searchInput = el("input", { class: "input", placeholder: t("users.search") });
  const userStatus = el("div", { class: "muted", text: "" });
  const userBody = el("tbody");
  const accountStatus = el("div", { class: "muted", text: "" });
  const selectedUserField = el("input", {
    class: "input input--readonly",
    readonly: "readonly",
    placeholder: t("users.wecomUserEmpty"),
  });
  const accountBody = el("tbody");
  const accountChannelInput = el("select", { class: "input" }, [
    el("option", { value: "wecom", text: "wecom" }),
    el("option", { value: "weixin", text: "weixin" }),
    el("option", { value: "whatsapp", text: "whatsapp" }),
  ]);
  const accountIdInput = el("input", { class: "input", placeholder: t("users.wecomBotId") });
  const accountNameInput = el("input", { class: "input", placeholder: t("users.wecomInstanceName") });
  const botSecretInput = el("input", { class: "input", type: "password", placeholder: t("users.wecomBotSecret") });
  const botSecretField = el("div", { class: "row--wecom-form__field" }, [el("div", { class: "muted", text: t("users.wecomBotSecret") }), botSecretInput]);
  const clearBotChk = el("input", { type: "checkbox" });
  const clearBotField = el("label", { class: "kv row--wecom-form__chk" }, [clearBotChk, document.createTextNode(" " + t("users.clearBotSecret"))]);
  const accountActiveInput = el("input", { type: "checkbox" });
  const accountSpecialistInput = el("select", { class: "input" }, [el("option", { value: "generalist", text: "generalist" })]);
  accountActiveInput.checked = true;
  let selectedUserId = "";
  let selectedUsername = "";
  let selectedDisplayName = "";
  let availableAccountSpecialists = ["generalist"];

  const refreshSelectedUserField = () => {
    if (!selectedUserId) {
      selectedUserField.value = "";
      return;
    }
    const who = formatUserLabel({ username: selectedUsername, display_name: selectedDisplayName });
    selectedUserField.value = who;
  };

  const clearWecomForm = () => {
    accountIdInput.value = "";
    accountNameInput.value = "";
    botSecretInput.value = "";
    clearBotChk.checked = false;
    accountActiveInput.checked = true;
    accountSpecialistInput.value = "generalist";
  };
  const currentAccountChannel = () => String(accountChannelInput.value || "wecom").trim().toLowerCase() || "wecom";
  const refreshAccountFormByChannel = () => {
    const isWecom = currentAccountChannel() === "wecom";
    botSecretField.style.display = isWecom ? "" : "none";
    clearBotField.style.display = isWecom ? "" : "none";
  };
  const setAccountSpecialistOptions = (specialists) => {
    const opts = Array.isArray(specialists) && specialists.length
      ? specialists.map((x) => String(x || "").trim()).filter(Boolean)
      : ["generalist"];
    const uniq = Array.from(new Set(["generalist", ...opts]));
    availableAccountSpecialists = uniq;
    const old = String(accountSpecialistInput.value || "generalist").trim() || "generalist";
    accountSpecialistInput.innerHTML = "";
    uniq.forEach((sid) => {
      accountSpecialistInput.appendChild(el("option", { value: sid, text: sid, selected: sid === old ? "selected" : undefined }));
    });
    if (!uniq.includes(old)) accountSpecialistInput.value = "generalist";
  };

  const newUserName = el("input", { class: "input", placeholder: t("users.createNamePlaceholder") });
  const newUserRole = el("select", { class: "input" }, [
    el("option", { value: "member", text: "member" }),
    el("option", { value: "admin", text: "admin" }),
    el("option", { value: "guest", text: "guest" }),
    el("option", { value: "owner", text: "owner" }),
  ]);
  const newUserPassword = el("input", { class: "input", type: "password", placeholder: t("auth.password") });

  const getTenantId = () => String(selector.value || "");

  const mergeWecomBindingAndInstances = (bindings, items) => {
    const byAid = new Map();
    for (const it of items) {
      const aid = String(it.account_id || "").trim();
      if (aid) byAid.set(aid, it);
    }
    const seen = new Set();
    const out = [];
    for (const b of bindings) {
      const aid = String(b.account_id || "").trim();
      if (!aid || seen.has(aid)) continue;
      seen.add(aid);
      out.push({ binding: b, instance: byAid.get(aid) || null });
    }
    for (const it of items) {
      const aid = String(it.account_id || "").trim();
      if (!aid || seen.has(aid)) continue;
      out.push({ binding: null, instance: it });
    }
    return out;
  };

  const prefillFromMerged = (m) => {
    const inst = m.instance;
    const bind = m.binding;
    const aid = inst ? String(inst.account_id || "").trim() : String(bind?.account_id || "").trim();
    accountIdInput.value = aid;
    const nameFromInst = inst ? String(inst.name || "").trim() : "";
    const nameFromBind = bind ? String(bind.account_name || "").trim() : "";
    accountNameInput.value = nameFromInst || nameFromBind;
    if (inst) {
      accountActiveInput.checked = !!inst.is_active;
    } else {
      accountActiveInput.checked = true;
    }
    const mode = String(((inst && inst.config) || {}).interaction_mode || "expert").trim().toLowerCase();
    const specialist = String(((inst && inst.config) || {}).specialist || "generalist").trim().toLowerCase() || "generalist";
    accountSpecialistInput.value = availableAccountSpecialists.includes(specialist) ? specialist : "generalist";
    if (mode === "comprehensive") {
      accountStatus.textContent = currentLang === "zh" ? "当前账号模式：综合" : "Current account mode: comprehensive";
    }
    botSecretInput.value = "";
    clearBotChk.checked = false;
  };

  const loadAccounts = async () => {
    accountBody.innerHTML = "";
    clearWecomForm();
    const tenantId = getTenantId();
    if (!selectedUserId) {
      accountStatus.textContent = "";
      accountBody.appendChild(el("tr", {}, [el("td", { text: t("audit.empty"), colspan: "10" })]));
      return;
    }
    const ch = currentAccountChannel();
    const bindUrl = `/admin/api/bindings?tenant_id=${encodeURIComponent(tenantId)}&channel=${encodeURIComponent(ch)}&user_id=${encodeURIComponent(selectedUserId)}`;
    const accUrl = `/admin/api/user-channel-accounts?tenant_id=${encodeURIComponent(tenantId)}&user_id=${encodeURIComponent(selectedUserId)}&channel=${encodeURIComponent(ch)}&include_inactive=1`;
    const [bindResp, accResp] = await Promise.all([ch === "wecom" ? apiGet(bindUrl) : Promise.resolve({ bindings: [] }), apiGet(accUrl)]);
    const bindings = Array.isArray(bindResp && bindResp.bindings) ? bindResp.bindings : [];
    const items = Array.isArray(accResp.items) ? accResp.items : [];
    const merged = ch === "wecom" ? mergeWecomBindingAndInstances(bindings, items) : items.map((it) => ({ binding: null, instance: it }));
    accountStatus.textContent = "";
    if (!merged.length) {
      accountBody.appendChild(el("tr", {}, [el("td", { text: t("users.noBindingsForUser"), colspan: "10" })]));
      return;
    }
    merged.forEach((m) => {
      const inst = m.instance;
      const bind = m.binding;
      const accountId = inst ? String(inst.account_id || "") : String(bind?.account_id || "");
      const displayName = (inst && String(inst.name || "").trim()) || (bind && String(bind.account_name || "").trim()) || "";
      const extUid = bind ? String(bind.external_user_id || "") : "";
      const ts = (inst && String(inst.updated_at || "").trim()) || (bind && String(bind.created_at || "").trim()) || "";
      const cfg = (inst && inst.config && typeof inst.config === "object") ? inst.config : {};
      const modeText = String(cfg.interaction_mode || "expert");
      const specialistText = String(cfg.specialist || "generalist");
      const btnFill = el("button", {
        class: "btn",
        text: t("users.loadForm"),
        onclick: (e) => {
          e.stopPropagation();
          prefillFromMerged(m);
        },
      });
      const deleteCell = el("td", {});
      if (inst) {
        const btnBindExpert = el("button", {
          class: "btn",
          text: currentLang === "zh" ? "绑定专家" : "Bind specialist",
          onclick: async (e) => {
            e.stopPropagation();
            const specialist = String(accountSpecialistInput.value || "generalist").trim() || "generalist";
            await apiPost("/admin/api/user-channel-accounts/upsert", {
              tenant_id: tenantId,
              user_id: selectedUserId,
              channel: ch,
              account_id: accountId,
              name: displayName,
              is_active: !!inst.is_active,
              config: { interaction_mode: "expert", specialist },
            });
            await loadAccounts();
          },
        });
        const btnComprehensive = el("button", {
          class: "btn btn--primary",
          text: currentLang === "zh" ? "综合" : "Comprehensive",
          onclick: async (e) => {
            e.stopPropagation();
            const specialist = String(accountSpecialistInput.value || "generalist").trim() || "generalist";
            await apiPost("/admin/api/user-channel-accounts/upsert", {
              tenant_id: tenantId,
              user_id: selectedUserId,
              channel: ch,
              account_id: accountId,
              name: displayName,
              is_active: !!inst.is_active,
              config: { interaction_mode: "comprehensive", specialist },
            });
            await loadAccounts();
          },
        });
        const btnDeleteAccount = el("button", { class: "btn btn--danger", text: t("users.accountDelete"), onclick: async (e) => {
          e.stopPropagation();
          await apiPost("/admin/api/user-channel-accounts/delete", {
            tenant_id: tenantId,
            user_id: selectedUserId,
            channel: ch,
            account_id: accountId,
          });
          await loadAccounts();
        }});
        deleteCell.appendChild(btnBindExpert);
        deleteCell.appendChild(btnComprehensive);
        deleteCell.appendChild(btnDeleteAccount);
      } else {
        deleteCell.appendChild(document.createTextNode("—"));
      }
      accountBody.appendChild(el("tr", {}, [
        tdCell(accountId, 22),
        tdCell(displayName, 16),
        tdCell(extUid || "—", 18),
        tdCell(inst ? (ch === "wecom" ? (inst.has_bot_secret ? "Y" : "-") : "-") : "—", 4),
        tdCell(inst ? (inst.is_active ? "1" : "0") : "—", 4),
        tdCell(modeText || "expert", 8),
        tdCell(specialistText || "generalist", 10),
        tdCell(ts, 20),
        el("td", {}, [btnFill]),
        deleteCell,
      ]));
    });
  };

  const btnSaveAccount = el("button", { class: "btn", text: t("users.accountSave"), onclick: async () => {
    if (!selectedUserId) {
      accountStatus.textContent = "select user first";
      return;
    }
    const aid = accountIdInput.value.trim();
    if (!aid) {
      accountStatus.textContent = t("users.botIdRequired");
      return;
    }
    const tenantId = getTenantId();
    const ch = currentAccountChannel();
    const specialist = String(accountSpecialistInput.value || "generalist").trim() || "generalist";
    const resp = await apiPost("/admin/api/user-channel-accounts/upsert", {
      tenant_id: tenantId,
      user_id: selectedUserId,
      channel: ch,
      account_id: aid,
      name: accountNameInput.value.trim(),
      wecom_mode: ch === "wecom" ? "bot_api" : undefined,
      bot_secret: botSecretInput.value.trim(),
      clear_bot_secret: !!clearBotChk.checked,
      is_active: !!accountActiveInput.checked,
      config: {
        interaction_mode: "expert",
        specialist,
      },
    });
    accountStatus.textContent = resp.ok ? "ok" : String(resp.error || "error");
    if (resp.ok) {
      botSecretInput.value = "";
      clearBotChk.checked = false;
      await loadAccounts();
      await loadList();
    }
  }});
  accountChannelInput.addEventListener("change", async () => {
    clearWecomForm();
    refreshAccountFormByChannel();
    await loadAccounts();
  });

  const loadList = async () => {
    if (!hasPermission("admin:user:read")) {
      userBody.innerHTML = "";
      userBody.appendChild(el("tr", {}, [el("td", { text: t("users.needUserRead"), colspan: "7" })]));
      return;
    }
    const tenantId = getTenantId();
    const tMeta = allTenants.find((r) => String(r.id || "") === tenantId) || {};
    const sessionTenantName = String(tMeta.name || "").trim();
    const q = encodeURIComponent(searchInput.value.trim());
    const resp = await apiGet(`/admin/api/users?tenant_id=${encodeURIComponent(tenantId)}&include_inactive=1&q=${q}&limit=300`);
    const users = Array.isArray(resp.users) ? resp.users : [];
    userBody.innerHTML = "";
    if (!users.length) {
      userBody.appendChild(el("tr", {}, [el("td", { text: t("audit.empty"), colspan: "7" })]));
      return;
    }
    users.forEach((u) => {
      const newRole = el("select", { class: "input" }, [
        el("option", { value: "member", text: "member" }),
        el("option", { value: "admin", text: "admin" }),
        el("option", { value: "guest", text: "guest" }),
        el("option", { value: "owner", text: "owner" }),
      ]);
      newRole.value = String(u.role || "member");
      const pwd = el("input", { class: "input", type: "password", placeholder: t("users.passwordOptional") });
      const btnToggle = el("button", { class: "btn", text: u.is_active ? t("users.disable") : t("users.enable"), onclick: async () => {
        await apiPost("/admin/api/users/update", {
          tenant_id: tenantId,
          user_id: u.id,
          is_active: !u.is_active,
        });
        await loadList();
      }});
      const btnUpdate = el("button", { class: "btn", text: t("users.update"), onclick: async () => {
        await apiPost("/admin/api/users/update", {
          tenant_id: tenantId,
          user_id: u.id,
          role: newRole.value,
          password: pwd.value.trim() || undefined,
        });
        await loadList();
      }});
      const btnDelete = el("button", { class: "btn btn--danger", text: t("users.delete"), onclick: async (e) => {
        e.stopPropagation();
        if (!window.confirm(t("users.deleteConfirm"))) return;
        await apiPost("/admin/api/users/delete", { tenant_id: tenantId, user_id: u.id });
        await loadList();
      }});
      const actionWrap = el("div", { class: "table__cell-actions" }, [btnToggle, btnUpdate, btnDelete]);
      const tr = el("tr", {}, [
        tdCell(sessionTenantName || "—", 14),
        tdCell(formatUserLabel(u), 28),
        tdCell(u.role || "", 10),
        tdCell(u.is_active ? "1" : "0", 4),
        el("td", { class: "table__cell--form" }, [newRole]),
        el("td", { class: "table__cell--form" }, [pwd]),
        el("td", { class: "table__cell--actions" }, [actionWrap]),
      ]);
      tr.style.cursor = "pointer";
      tr.addEventListener("click", async (e) => {
        if (e.target && e.target.closest && e.target.closest("button,select,input")) return;
        selectedUserId = String(u.id || "");
        selectedUsername = String(u.username || "");
        selectedDisplayName = String(u.display_name || "");
        refreshSelectedUserField();
        await loadAccounts();
      });
      userBody.appendChild(tr);
    });
  };

  const btnCreateUser = el("button", { class: "btn btn--primary", text: t("users.create"), onclick: async () => {
    if (!hasPermission("admin:user:write")) {
      userStatus.textContent = "forbidden";
      return;
    }
    try {
      const raw = newUserName.value.trim();
      if (!raw) {
        userStatus.textContent = t("users.createNameRequired");
        return;
      }
      const resp = await apiPost("/admin/api/users/create", {
        tenant_id: getTenantId(),
        username: raw,
        display_name: raw,
        role: newUserRole.value,
        password: newUserPassword.value.trim(),
      });
      userStatus.textContent = resp.ok ? "ok" : String(resp.error || "error");
      if (resp.ok) {
        newUserName.value = "";
        newUserPassword.value = "";
        await loadList();
        await loadBindingsAndCodes();
      }
    } catch (e) {
      userStatus.textContent = String(e && e.message ? e.message : e);
    }
  }});

  const btnSearchUsers = el("button", { class: "btn", text: t("audit.query"), onclick: loadList });

  const createName = el("input", { class: "input", placeholder: t("tenants.createPlaceholder") });
  const btnCreateTenant = el("button", { class: "btn", text: t("tenants.create"), onclick: async () => {
    if (!hasPermission("admin:tenant:write")) {
      status.textContent = "forbidden";
      return;
    }
    await apiPost("/admin/api/tenants/create", { name: createName.value.trim() || "Team" });
    await router();
  }});

  const roleInput = el("select", { class: "input" }, [
    el("option", { value: "member", text: "member" }),
    el("option", { value: "admin", text: "admin" }),
    el("option", { value: "guest", text: "guest" }),
  ]);
  const codeInput = el("input", { class: "input", placeholder: t("tenants.codeOptional") });
  const btnCreateCode = el("button", { class: "btn", text: t("tenants.createCode"), onclick: async () => {
    const tid = String(selector.value || "");
    await apiPost("/admin/api/bind-codes/create", {
      tenant_id: tid,
      role: roleInput.value || "member",
      code: codeInput.value.trim(),
    });
    codeInput.value = "";
    await loadBindingsAndCodes();
  }});
  const btnDeleteUnbound = el("button", { class: "btn btn--danger", text: t("tenants.deleteUnbound"), onclick: async () => {
    const tid = String(selector.value || "");
    const resp = await apiPost("/admin/api/users/delete-unbound", { tenant_id: tid, channel: "wecom" });
    status.textContent = tf("tenants.deleteUnboundResult", {
      deleted: Number(resp.deleted || 0),
      orphan: Number(resp.orphan_users || 0),
      bound: Number(resp.bound_users || 0),
      total: Number(resp.users_total || 0),
    });
    await loadBindingsAndCodes();
    await loadList();
  }});

  const loadBindingsAndCodes = async () => {
    const tid = String(selector.value || "");
    const [bindingsResp, codesResp] = await Promise.all([
      apiGet("/admin/api/bindings?tenant_id=" + encodeURIComponent(tid) + "&channel=wecom"),
      apiGet("/admin/api/bind-codes?tenant_id=" + encodeURIComponent(tid)),
    ]);
    const bindings = bindingsResp.bindings || [];
    const codes = codesResp.codes || [];

    const bindingTenantLabel = (tenantId) => {
      const id = String(tenantId || "");
      const meta = allTenants.find((x) => String(x.id || "") === id);
      const name = String(meta && meta.name ? meta.name : "").trim();
      return name || id.slice(0, 8) || "—";
    };
    const bindingUserLabel = (b) =>
      formatUserLabel({
        username: String(b.username != null && b.username !== "" ? b.username : b.user_id || ""),
        display_name: String(b.display_name || ""),
      });

    bindingsBody.innerHTML = "";
    if (!bindings.length) {
      bindingsBody.appendChild(el("tr", {}, [el("td", { text: t("tenants.noBindings"), colspan: "6" })]));
    } else {
      bindings.forEach((b) => {
        bindingsBody.appendChild(el("tr", {}, [
          el("td", { text: bindingTenantLabel(b.tenant_id) }),
          el("td", { text: bindingUserLabel(b) }),
          el("td", { text: String(b.channel || "") }),
          el("td", { text: String(b.account_id || "") }),
          el("td", { text: String(b.account_name || "") }),
          el("td", { text: String(b.external_user_id || "") }),
        ]));
      });
    }

    codesBody.innerHTML = "";
    if (!codes.length) {
      codesBody.appendChild(el("tr", {}, [el("td", { text: "-", colspan: "6" })]));
    } else {
      codes.forEach((c) => {
        const codeText = String(c.code || "");
        const isUsed = Boolean(c.used_at);
        const btnDeleteCode = el("button", { class: "btn btn--danger", text: t("tenants.deleteCode"), onclick: async () => {
          if (!window.confirm(t("tenants.codeDeleteConfirm"))) return;
          await apiPost("/admin/api/bind-codes/delete", { tenant_id: tid, code: codeText });
          status.textContent = tf("tenants.codeDeleted", { code: codeText });
          await loadBindingsAndCodes();
        }});
        codesBody.appendChild(el("tr", {}, [
          el("td", { text: codeText }),
          el("td", { text: String(c.role || "") }),
          el("td", { text: isUsed ? t("tenants.codeUsed") : t("tenants.codeUnused") }),
          el("td", { text: String(c.used_by_external_user_id || "") }),
          el("td", { text: formatSystemLocalDateTime(String(c.created_at || "")) }),
          el("td", {}, [btnDeleteCode]),
        ]));
      });
    }
  };
  selector.addEventListener("change", () => {
    selectedUserId = "";
    selectedUsername = "";
    selectedDisplayName = "";
    refreshSelectedUserField();
    Promise.all([loadBindingsAndCodes(), loadList(), loadAccounts()]).catch((err) => {
      mount(el("div", { class: "card" }, [el("div", { class: "card__title", text: t("common.error") }), el("div", { class: "pre", text: String(err) })]));
    });
  });
  await loadBindingsAndCodes();
  try {
    const sf = await apiGet("/admin/api/chat/settings/specialist-flags");
    setAccountSpecialistOptions(sf.available_specialists || ["generalist"]);
  } catch (_) {
    setAccountSpecialistOptions(["generalist"]);
  }
  await loadList();
  refreshSelectedUserField();
  refreshAccountFormByChannel();
  await loadAccounts();

  const tenantsListHint = allTenants.length > 1
    ? el("div", { class: "muted", style: "margin-top:8px", text: t("tenants.allTenantsHint") })
    : el("div", {});

  return el("div", {}, [
    el("div", { class: "card" }, [
      el("div", { class: "card__title", text: t("tenants.title") }),
      el("div", { class: "row" }, [createName, btnCreateTenant]),
      el("div", { class: "row" }, [el("label", { text: t("tenants.select") }), selector]),
      el("div", { class: "muted", style: "margin-top:6px", text: t("tenants.scopeHint") }),
      el("table", { class: "table" }, [
        el("thead", {}, [el("tr", {}, [
          el("th", { text: t("tenants.colTenantName") }),
          el("th", { text: t("table.createdAt") }),
          el("th", { text: t("tenants.colScope") }),
          el("th", { text: t("tenants.rowActions") }),
        ])]),
        el("tbody", {}, tenantRows),
      ]),
      status,
      tenantsListHint,
    ]),
    el("div", { class: "card" }, [
      el("div", { class: "card__title", text: t("users.title") }),
      el("div", { class: "row" }, [searchInput, btnSearchUsers]),
      el("div", { class: "row" }, [newUserName, newUserRole, newUserPassword, btnCreateUser]),
      userStatus,
      el("div", { class: "table-wrap" }, [el("table", { class: "table table--compact table--users-mgmt" }, [
        el("thead", {}, [el("tr", {}, [
          el("th", { text: t("tenants.colTenantName") }),
          el("th", { text: t("users.colUser") }),
          el("th", { text: t("tenants.role") }),
          el("th", { text: t("users.colActive") }),
          el("th", { text: t("users.colSetRole") }),
          el("th", { text: t("users.passwordOptional") }),
          el("th", { text: t("tenants.rowActions") }),
        ])]),
        userBody,
      ])]),
    ]),
    el("div", { class: "card" }, [
      el("div", { class: "card__title", text: t("users.wecomAccounts") }),
      el("div", {}, [el("div", { class: "muted", text: t("users.wecomUserLabel") }), selectedUserField]),
      el("div", { class: "muted", style: "margin-bottom:8px", text: t("users.accountLoadHint") }),
      el("div", { class: "row row--wecom-form" }, [
        el("div", { class: "row--wecom-form__field" }, [el("div", { class: "muted", text: "channel" }), accountChannelInput]),
        el("div", { class: "row--wecom-form__field" }, [el("div", { class: "muted", text: t("users.wecomBotId") }), accountIdInput]),
        el("div", { class: "row--wecom-form__field" }, [el("div", { class: "muted", text: t("users.wecomInstanceName") }), accountNameInput]),
        el("div", { class: "row--wecom-form__field" }, [el("div", { class: "muted", text: currentLang === "zh" ? "专家" : "Specialist" }), accountSpecialistInput]),
        botSecretField,
        el("label", { class: "kv row--wecom-form__chk" }, [accountActiveInput, document.createTextNode(" " + t("users.accountActive"))]),
        clearBotField,
        btnSaveAccount,
      ]),
      accountStatus,
      el("div", { class: "table-wrap" }, [el("table", { class: "table table--compact" }, [
        el("thead", {}, [el("tr", {}, [
          el("th", { text: t("users.wecomBotId") }),
          el("th", { text: t("users.wecomInstanceName") }),
          el("th", { text: t("table.externalUserId") }),
          el("th", { text: t("users.hasBotSecret") }),
          el("th", { text: t("users.accountActive") }),
          el("th", { text: currentLang === "zh" ? "模式" : "Mode" }),
          el("th", { text: t("table.specialist") }),
          el("th", { text: t("table.timestamp") }),
          el("th", { text: t("users.loadForm") }),
          el("th", { text: t("users.accountActions") }),
        ])]),
        accountBody,
      ])]),
    ]),
    el("div", { class: "card" }, [
      el("div", { class: "card__title", text: t("tenants.bindings") }),
      el("table", { class: "table" }, [
        el("thead", {}, [el("tr", {}, [
          el("th", { text: t("tenants.title") }),
          el("th", { text: t("tenants.users") }),
          el("th", { text: t("table.channel") }),
          el("th", { text: "account_id" }),
          el("th", { text: "account_name" }),
          el("th", { text: t("table.externalUserId") }),
        ])]),
        bindingsBody,
      ]),
    ]),
    el("div", { class: "card" }, [
      el("div", { class: "card__title", text: t("tenants.bindCodes") }),
      el("div", { class: "row" }, [
        el("label", { text: t("tenants.role") }),
        roleInput,
        codeInput,
        btnCreateCode,
        btnDeleteUnbound,
      ]),
      el("table", { class: "table" }, [
        el("thead", {}, [el("tr", {}, [
          el("th", { text: "code" }),
          el("th", { text: t("tenants.role") }),
          el("th", { text: t("tenants.codeStatus") }),
          el("th", { text: t("tenants.codeUsedBy") }),
          el("th", { text: t("table.createdAt") }),
          el("th", { text: t("tenants.deleteCode") }),
        ])]),
        codesBody,
      ]),
    ]),
  ]);
}

function hasPermission(permission) {
  const role = String((authSession && authSession.role) || "");
  const perms = new Set(Array.isArray(authSession && authSession.permissions) ? authSession.permissions : []);
  if (role === "owner") return true;
  return perms.has(permission);
}

/** 与 models_api._can_manage_llm_grants 一致：仅控制台 administrator 用户可管理授权 */
function canManageApiGrants() {
  const un = String((authSession && authSession.username) || "").trim().toLowerCase();
  if (un !== "administrator") return false;
  const role = String((authSession && authSession.role) || "").trim();
  if (role === "owner") return true;
  return hasPermission("admin:tenant:write");
}

function isAdministratorUsername() {
  return String((authSession && authSession.username) || "").trim().toLowerCase() === "administrator";
}

/** 与 models_api._profile_shareable_for_admin_grant 一致 */
function profileShareableForGrant(p, sessionUserId) {
  if (!p || p.is_builtin) return false;
  const own = String(p.owner_user_id || "").trim();
  if (!own) return true;
  return own === String(sessionUserId || "").trim();
}

async function renderAudit(initialSessionId = "") {
  const input = el("input", { class: "input", placeholder: t("audit.sessionIdPlaceholder") });
  const resultWrap = el("div");
  let selectedTraceId = "";
  const onlyFailures = el("input", { type: "checkbox" });
  const formatTracePayload = (row) => {
    const et = String((row && row.event_type) || "");
    const p = (row && typeof row.payload === "object" && row.payload) ? row.payload : {};
    if (et === "tool_wire_filter") {
      const before = Number(p.tools_before || 0);
      const after = Number(p.tools_after || 0);
      const hidden = Number(p.hidden_total || 0);
      const hiddenMcp = Number(p.hidden_mcp_total || 0);
      const preview = Array.isArray(p.hidden_mcp_preview) ? p.hidden_mcp_preview.slice(0, 8).join(", ") : "";
      const head = `wire_filter before=${before} after=${after} hidden=${hidden} hidden_mcp=${hiddenMcp}`;
      return preview ? `${head} | mcp: ${preview}` : head;
    }
    if (et === "llm_first_token") {
      const ms = Number(p.first_token_ms || 0);
      return `ttft_ms=${ms}`;
    }
    if (et === "memory_retrieval_finished") {
      return `memory short=${Number(p.short_term_count || 0)} semantic=${Number(p.semantic_hit_count || 0)} enabled=${Boolean(p.enabled)}`;
    }
    if (et === "router_decision") {
      return `route mode=${String(p.mode || "")} reason=${String(p.reason || "")}`;
    }
    if (et === "run_started") {
      return `run_started run_id=${String(p.run_id || "")} max_attempts=${Number(p.max_attempts || 0)}`;
    }
    if (et === "attempt_started") {
      return `attempt_started run_id=${String(p.run_id || "")} no=${Number(p.attempt_no || 0)}`;
    }
    if (et === "attempt_finished") {
      return `attempt_finished run_id=${String(p.run_id || "")} no=${Number(p.attempt_no || 0)} status=${String(p.status || "")}`;
    }
    if (et === "run_retry") {
      return `run_retry run_id=${String(p.run_id || "")} next_attempt=${Number(p.next_attempt_no || 0)}`;
    }
    if (et === "run_compact") {
      return `run_compact run_id=${String(p.run_id || "")} count=${Number(p.compact_count || 0)}`;
    }
    if (et === "run_finished") {
      return `run_finished run_id=${String(p.run_id || "")} status=${String(p.status || "")} attempts=${Number(p.attempts || 0)}`;
    }
    if (et === "task_enqueued" || et === "task_claimed" || et === "task_finished" || et === "task_failed") {
      return `${et} task_id=${String(p.task_id || "")} ok=${p.ok === undefined ? "-" : Boolean(p.ok)}`;
    }
    if (et === "turn_stage" && String(p.stage || "") === "finish") {
      const ttft = p.first_token_ms;
      const elapsed = Number(p.turn_elapsed_ms || 0);
      const tools = Number(p.tool_trace_count || 0);
      return `finish ttft_ms=${ttft === null || ttft === undefined ? "-" : Number(ttft)} elapsed_ms=${elapsed} tools=${tools}`;
    }
    return JSON.stringify(p || {});
  };
  const auditColumnDefs = [
    { key: "timestamp", label: t("table.timestamp"), getter: (r) => r.timestamp || "", maxLen: 24 },
    { key: "specialist", label: t("table.specialist"), getter: (r) => r.specialist || "", maxLen: 24 },
    { key: "action", label: t("table.action"), getter: (r) => r.action || "", maxLen: 24 },
    { key: "status", label: t("table.statusText"), getter: (r) => r.status || "", maxLen: 16 },
    { key: "reason", label: t("table.reason"), getter: (r) => r.reason || "", maxLen: 40 },
    { key: "duration", label: t("table.durationMs"), getter: (r) => String(r.duration_ms || ""), maxLen: 20 },
    {
      key: "noOutput",
      label: t("table.noOutputAttachment"),
      getter: (r) => yesNo(((r.payload && typeof r.payload === "object") ? r.payload.no_output_attachment : false)),
      maxLen: 8,
    },
    {
      key: "attachments",
      label: "attachments",
      getter: (r) => {
        const payload = (r && typeof r.payload === "object" && r.payload) ? r.payload : {};
        const routeIds = formatIds(payload.attachment_ids);
        const inIds = formatIds(payload.input_attachment_ids);
        const outIds = formatIds(payload.output_attachment_ids);
        const outUrls = formatIds(payload.output_attachment_urls);
        return [routeIds ? `route:${routeIds}` : "", inIds ? `in:${inIds}` : "", outIds ? `out:${outIds}` : "", outUrls ? `url:${outUrls}` : ""]
          .filter(Boolean)
          .join(" | ") || "-";
      },
      maxLen: 120,
    },
    {
      key: "payload",
      label: t("table.payload"),
      getter: (r) => JSON.stringify(r.payload || {}),
      maxLen: 120,
    },
  ];
  const traceColumnDefs = [
    { key: "timestamp", label: t("table.timestamp"), getter: (r) => r.timestamp || "", maxLen: 24 },
    { key: "eventType", label: t("table.eventType"), getter: (r) => r.event_type || "", maxLen: 28 },
    { key: "traceId", label: t("table.traceId"), getter: (r) => r.trace_id || "", maxLen: 20 },
    { key: "spanId", label: t("table.spanId"), getter: (r) => r.span_id || "", maxLen: 20 },
    { key: "parentSpanId", label: t("table.parentSpanId"), getter: (r) => r.parent_span_id || "", maxLen: 20 },
    {
      key: "errorCode",
      label: "error_code",
      getter: (r) => String((r.payload && r.payload.error_code) || ""),
      maxLen: 32,
    },
    { key: "payload", label: t("table.payload"), getter: (r) => formatTracePayload(r), maxLen: 120 },
  ];
  const auditVisible = new Set(auditColumnDefs.map((x) => x.key));
  const traceVisible = new Set(traceColumnDefs.map((x) => x.key));

  const buildColumnToggleRow = (defs, visibleSet) => {
    const wrap = el("div", { class: "row" });
    defs.forEach((d) => {
      const cb = el("input", { type: "checkbox" });
      cb.checked = visibleSet.has(d.key);
      cb.addEventListener("change", () => {
        if (cb.checked) visibleSet.add(d.key);
        else visibleSet.delete(d.key);
      });
      wrap.appendChild(el("label", { class: "kv" }, [cb, document.createTextNode(" " + d.label)]));
    });
    return wrap;
  };

  const auditColsToggle = buildColumnToggleRow(auditColumnDefs, auditVisible);
  const traceColsToggle = buildColumnToggleRow(traceColumnDefs, traceVisible);
  const runQuery = async () => {
    const sid = input.value.trim();
    const a = await apiGet("/admin/api/audit" + (sid ? ("?session_id=" + encodeURIComponent(sid)) : ""));
    const tr = await apiGet("/admin/api/trace" + (sid ? ("?session_id=" + encodeURIComponent(sid)) : ""));
    const tasks = await apiGet("/admin/api/oclaw/tasks?" + (sid ? ("session_id=" + encodeURIComponent(sid) + "&") : "") + "limit=120");
    const runs = await apiGet("/admin/api/oclaw/runs?" + (sid ? ("session_id=" + encodeURIComponent(sid) + "&") : "") + "limit=80&include_attempts=1");
    const health = await apiGet(
      "/admin/api/audit/session-health?" + (sid ? ("session_id=" + encodeURIComponent(sid) + "&limit=20") : "limit=40"),
    );
    const auditRows = Array.isArray(a.audit) ? a.audit : [];
    const traceRows = Array.isArray(tr.trace) ? tr.trace : [];
    const traceIds = Array.from(new Set(traceRows.map((r) => String(r.trace_id || "")).filter(Boolean)));
    if (selectedTraceId && !traceIds.includes(selectedTraceId)) selectedTraceId = "";
    const filteredByTrace = selectedTraceId ? traceRows.filter((r) => String(r.trace_id || "") === selectedTraceId) : traceRows;
    const filteredTraceRows = onlyFailures.checked
      ? filteredByTrace.filter((r) => {
          const p = (r && typeof r.payload === "object") ? r.payload : {};
          return p.ok === false || String(p.error_code || "").trim() !== "";
        })
      : filteredByTrace;
    const auditBody = el("tbody");
    const visibleAuditCols = auditColumnDefs.filter((c) => auditVisible.has(c.key));
    if (!auditRows.length) {
      auditBody.appendChild(el("tr", {}, [el("td", { text: t("audit.empty"), colspan: String(Math.max(1, visibleAuditCols.length)) })]));
    } else {
      auditRows.forEach((r) => {
        const row = el("tr");
        visibleAuditCols.forEach((c) => row.appendChild(tdCell(c.getter(r), c.maxLen || 120)));
        auditBody.appendChild(row);
      });
    }
    const traceBody = el("tbody");
    const visibleTraceCols = traceColumnDefs.filter((c) => traceVisible.has(c.key));
    if (!filteredTraceRows.length) {
      traceBody.appendChild(el("tr", {}, [el("td", { text: t("audit.empty"), colspan: String(Math.max(1, visibleTraceCols.length)) })]));
    } else {
      filteredTraceRows.forEach((r) => {
        const row = el("tr");
        visibleTraceCols.forEach((c) => row.appendChild(tdCell(c.getter(r), c.maxLen || 120)));
        traceBody.appendChild(row);
      });
    }
    const pre = el("div", { class: "pre", text: JSON.stringify({ audit: a, trace: tr, health }, null, 2) });
    resultWrap.innerHTML = "";
    const healthItems = Array.isArray(health.items) ? health.items : [];
    const healthRows = healthItems.map((x) => el("tr", {}, [
      tdCell(String(x.session_id || ""), 26),
      tdCell(String(x.title || ""), 26),
      tdCell(String(x.assistant_count || 0), 8),
      tdCell(String(x.tool_count || 0), 8),
      tdCell(String(x.mcp_tool_count || 0), 8),
      tdCell(String(x.last_tool_at || "-"), 20),
      tdCell(String(x.status || ""), 20),
    ]));
    resultWrap.appendChild(el("div", { class: "card" }, [
      el("div", { class: "card__title", text: "Session Tool Health" }),
      el("div", { class: "muted", text: `warn=${Number(health.warn_count || 0)} (assistant replied but no tool uses)` }),
      el("div", { class: "table-wrap" }, [el("table", { class: "table table--compact" }, [
        el("thead", {}, [el("tr", {}, [
          el("th", { text: "session_id" }),
          el("th", { text: "title" }),
          el("th", { text: "assistant_msgs" }),
          el("th", { text: "tool_uses" }),
          el("th", { text: "mcp_calls" }),
          el("th", { text: "last_tool_at" }),
          el("th", { text: "status" }),
        ])]),
        el("tbody", {}, healthRows.length ? healthRows : [el("tr", {}, [el("td", { text: "-", colspan: "7" })])]),
      ])]),
    ]));
    const taskRows = Array.isArray(tasks.tasks) ? tasks.tasks : [];
    const queued = Number((tasks.counts || {}).queued || 0);
    const claimed = Number((tasks.counts || {}).claimed || 0);
    const done = Number((tasks.counts || {}).done || 0);
    const failed = Number((tasks.counts || {}).failed || 0);
    resultWrap.appendChild(el("div", { class: "card" }, [
      el("div", { class: "card__title", text: "oclaw Tasks" }),
      el("div", { class: "muted", text: `queued=${queued} claimed=${claimed} done=${done} failed=${failed}` }),
      el("div", { class: "table-wrap" }, [el("table", { class: "table table--compact" }, [
        el("thead", {}, [el("tr", {}, [
          el("th", { text: "task_id" }),
          el("th", { text: "status" }),
          el("th", { text: "attempt_count" }),
          el("th", { text: "session_id" }),
          el("th", { text: "updated_at" }),
          el("th", { text: "last_error" }),
        ])]),
        el(
          "tbody",
          {},
          taskRows.length
            ? taskRows.slice(0, 80).map((x) => el("tr", {}, [
                tdCell(String(x.id || ""), 24),
                tdCell(String(x.status || ""), 10),
                tdCell(String(x.attempt_count || 0), 10),
                tdCell(String(x.session_id || ""), 20),
                tdCell(String(x.updated_at || ""), 22),
                tdCell(String(x.last_error || ""), 40),
              ]))
            : [el("tr", {}, [el("td", { text: "-", colspan: "6" })])],
        ),
      ])]),
    ]));
    const runRows = Array.isArray(runs.runs) ? runs.runs : [];
    const runRunning = Number((runs.counts || {}).running || 0);
    const runSuccess = Number((runs.counts || {}).success || 0);
    const runFailed = Number((runs.counts || {}).failed || 0);
    const rp = (runs && typeof runs.retry_policy === "object" && runs.retry_policy) ? runs.retry_policy : {};
    const effRetryCodes = Array.isArray(rp.effective_retryable_error_codes) ? rp.effective_retryable_error_codes.join(", ") : "";
    resultWrap.appendChild(el("div", { class: "card" }, [
      el("div", { class: "card__title", text: "oclaw Runs" }),
      el("div", { class: "muted", text: `running=${runRunning} success=${runSuccess} failed=${runFailed}` }),
      el("div", { class: "muted", text: effRetryCodes ? `retryable_error_codes=${effRetryCodes}` : "" }),
      el("div", { class: "table-wrap" }, [el("table", { class: "table table--compact" }, [
        el("thead", {}, [el("tr", {}, [
          el("th", { text: "run_id" }),
          el("th", { text: "status" }),
          el("th", { text: "session_id" }),
          el("th", { text: "attempts" }),
          el("th", { text: "updated_at" }),
        ])]),
        el(
          "tbody",
          {},
          runRows.length
            ? runRows.slice(0, 60).map((x) => {
                const attempts = Array.isArray(x.attempts) ? x.attempts : [];
                const attemptSummary = attempts.length
                  ? attempts.map((a) => `${Number(a.attempt_no || 0)}:${String(a.status || "")}`).join(" | ")
                  : "-";
                return el("tr", {}, [
                  tdCell(String(x.run_id || ""), 24),
                  tdCell(String(x.status || ""), 10),
                  tdCell(String(x.session_id || ""), 20),
                  tdCell(attemptSummary, 60),
                  tdCell(String(x.updated_at || ""), 22),
                ]);
              })
            : [el("tr", {}, [el("td", { text: "-", colspan: "5" })])],
        ),
      ])]),
    ]));

    const deliveryRows = auditRows
      .filter((r) => r && typeof r === "object" && r.action === "specialist_step")
      .map((r) => {
        const payload = (r && typeof r.payload === "object" && r.payload) ? r.payload : {};
        const d = (payload && typeof payload.specialist_delivery === "object" && payload.specialist_delivery)
          ? payload.specialist_delivery
          : null;
        if (!d) return null;
        const traces = Array.isArray(d.tool_traces) ? d.tool_traces : [];
        const toolsText = traces.length
          ? traces
              .map((x) => `${String(x.name || "")}(ok=${Boolean(x.ok)}, ${Number(x.latency_ms || 0)}ms)`)
              .join(" | ")
          : "-";
        return {
          timestamp: String(r.timestamp || ""),
          specialist: String(r.specialist || d.specialist || ""),
          stepId: String(d.step_id || payload.step_id || ""),
          answer: String(d.answer_text || ""),
          tools: toolsText,
          notes: String(d.notes || ""),
        };
      })
      .filter(Boolean);
    resultWrap.appendChild(el("div", { class: "card" }, [
      el("div", { class: "card__title", text: "Specialist Delivery Timeline" }),
      el("div", { class: "muted", text: "专家侧工具执行与交付摘要（specialist -> core）" }),
      el("div", { class: "table-wrap" }, [el("table", { class: "table table--compact" }, [
        el("thead", {}, [el("tr", {}, [
          el("th", { text: "timestamp" }),
          el("th", { text: "specialist" }),
          el("th", { text: "step_id" }),
          el("th", { text: "answer_for_user" }),
          el("th", { text: "tools_executed_inside_specialist" }),
          el("th", { text: "notes" }),
        ])]),
        el(
          "tbody",
          {},
          deliveryRows.length
            ? deliveryRows.map((x) =>
                el("tr", {}, [
                  tdCell(x.timestamp, 24),
                  tdCell(x.specialist, 14),
                  tdCell(x.stepId, 20),
                  tdCell(x.answer, 120),
                  tdCell(x.tools, 120),
                  tdCell(x.notes, 24),
                ]),
              )
            : [el("tr", {}, [el("td", { text: "-", colspan: "6" })])],
        ),
      ])]),
    ]));

    // Turn summary (group by trace_id) for quick navigation.
    if (traceIds.length) {
      const sel = el("select", { class: "input" });
      sel.appendChild(el("option", { value: "", text: `trace_id (${traceIds.length})` }));
      traceIds.forEach((tid) => sel.appendChild(el("option", { value: tid, text: tid })));
      sel.value = selectedTraceId;
      const summary = el("div", { class: "muted", text: "" });
      const failSummary = el("div", { class: "muted", text: "" });
      const recomputeSummary = () => {
        const rows = filteredTraceRows;
        const counts = {};
        rows.forEach((r) => {
          const et = String(r.event_type || "");
          counts[et] = (counts[et] || 0) + 1;
        });
        const get = (k) => Number(counts[k] || 0);
        summary.textContent = [
          `route_decided=${get("route_decided")}`,
          `plan_created=${get("plan_created")}`,
          `tool_wire_filter=${get("tool_wire_filter")}`,
          `llm_first_token=${get("llm_first_token")}`,
          `llm_called=${get("llm_called")}`,
          `llm_result=${get("llm_result")}`,
          `tool_use_called=${get("tool_called")}`,
          `tool_result=${get("tool_result")}`,
        ].join(" | ");
        const agg = {};
        rows.forEach((r) => {
          const p = (r && typeof r.payload === "object") ? r.payload : {};
          const ec = String(p.error_code || "").trim();
          if (!ec) return;
          agg[ec] = (agg[ec] || 0) + 1;
        });
        const parts = Object.entries(agg).sort((a, b) => b[1] - a[1]).slice(0, 8).map(([k, v]) => `${k}:${v}`);
        failSummary.textContent = parts.length ? `Failure summary: ${parts.join(" | ")}` : "Failure summary: -";
      };
      sel.addEventListener("change", () => {
        selectedTraceId = String(sel.value || "");
        runQuery();
      });
      recomputeSummary();
      resultWrap.appendChild(el("div", { class: "card" }, [
        el("div", { class: "card__title", text: "Turn summary" }),
        el("div", { class: "row" }, [sel, el("label", { class: "kv" }, [onlyFailures, document.createTextNode(" only failures")])]),
        summary,
        failSummary,
      ]));
    }
    resultWrap.appendChild(el("div", { class: "card" }, [
      el("div", { class: "card__title", text: t("audit.auditTable") }),
      el("div", { class: "muted", text: t("audit.columns") }),
      auditColsToggle,
      el("div", { class: "table-wrap" }, [el("table", { class: "table table--compact" }, [
        el("thead", {}, [el("tr", {}, auditColumnDefs.filter((c) => auditVisible.has(c.key)).map((c) => el("th", { text: c.label })))]),
        auditBody,
      ])]),
    ]));
    resultWrap.appendChild(el("div", { class: "card" }, [
      el("div", { class: "card__title", text: t("audit.traceTable") }),
      el("div", { class: "muted", text: t("audit.columns") }),
      traceColsToggle,
      el("div", { class: "table-wrap" }, [el("table", { class: "table table--compact" }, [
        el("thead", {}, [el("tr", {}, traceColumnDefs.filter((c) => traceVisible.has(c.key)).map((c) => el("th", { text: c.label })))]),
        traceBody,
      ])]),
    ]));
    const details = el("details", { class: "details" }, [
      el("summary", { text: t("audit.rawJson") }),
      pre,
    ]);
    resultWrap.appendChild(el("div", { class: "card" }, [details]));
  };
  const btn = el("button", { class: "btn btn--primary", text: t("audit.query"), onclick: async () => {
    await runQuery();
  }});
  onlyFailures.addEventListener("change", runQuery);
  auditColsToggle.addEventListener("change", runQuery);
  traceColsToggle.addEventListener("change", runQuery);
  const card = el("div", { class: "card" }, [
    el("div", { class: "card__title", text: t("audit.title") }),
    el("div", { class: "row" }, [input, btn]),
    el("div", { class: "muted", text: t("audit.note") }),
  ]);
  if (initialSessionId) {
    input.value = initialSessionId;
    await runQuery();
  }
  return el("div", {}, [card, resultWrap]);
}

async function renderMemory() {
  const route = getRoute();
  const tenantQ = route.params.get("tenant_id") || "";
  const userQ = route.params.get("user_id") || "";
  const buildQS = (limit = 50) => {
    const p = new URLSearchParams();
    p.set("limit", String(limit));
    if (tenantInput.value.trim()) p.set("tenant_id", tenantInput.value.trim());
    if (userInput.value.trim()) p.set("user_id", userInput.value.trim());
    return p.toString();
  };

  const tenantInput = el("input", { class: "input", placeholder: t("memory.tenantId"), value: tenantQ });
  const userInput = el("input", { class: "input", placeholder: t("memory.userId"), value: userQ });
  const status = el("div", { class: "muted", text: "" });
  const statsWrap = el("div", { class: "muted", text: "" });
  const hitsWrap = el("div");
  const itemsWrap = el("div");
  const wikiStatus = el("div", { class: "muted", text: "" });
  const memoryModeSelect = el("select", { class: "input", style: "max-width:320px;" });
  memoryModeSelect.appendChild(el("option", { value: "default", text: t("profile.memoryModeDefault") }));
  memoryModeSelect.appendChild(el("option", { value: "store_only", text: t("profile.memoryModeStoreOnly") }));
  const memoryCuratorSelect = el("select", { class: "input", style: "max-width:220px;" });
  memoryCuratorSelect.appendChild(el("option", { value: "1", text: t("profile.memoryCuratorEnabled") }));
  memoryCuratorSelect.appendChild(el("option", { value: "0", text: t("profile.memoryCuratorDisabled") }));

  const normalizeMemoryMode = (raw) => {
    const mm = String(raw || "").trim().toLowerCase();
    return mm === "store_only" ? "store_only" : "default";
  };

  const enabled = el("input", { type: "checkbox" });
  const backend = el("select", { class: "input" }, [
    el("option", { value: "sqlite", text: "sqlite" }),
    el("option", { value: "chroma", text: "chroma" }),
    el("option", { value: "qdrant", text: "qdrant" }),
  ]);
  const topk = el("input", { class: "input", type: "number", value: "5", min: "1", max: "20" });
  const writerEnabled = el("input", { type: "checkbox" });
  const ragMode = el("select", { class: "input" }, [
    el("option", { value: "keyword", text: "keyword" }),
    el("option", { value: "vector", text: "vector" }),
  ]);
  const embeddingMode = el("select", { class: "input" }, [
    el("option", { value: "", text: "openai(default/fallback)" }),
    el("option", { value: "openai", text: "openai" }),
    el("option", { value: "hash", text: "hash/offline" }),
  ]);
  const episodicTtlDays = el("input", { class: "input", type: "number", value: "90", min: "1", max: "3650" });
  const minConf = el("input", {
    class: "input",
    type: "number",
    value: "0.75",
    min: "0",
    max: "1",
    step: "0.05",
  });
  const btnSave = el("button", { class: "btn btn--primary", text: t("memory.save"), onclick: async () => {
    const saved = await apiPost("/admin/api/memory/config", {
      enabled: enabled.checked,
      backend: backend.value,
      top_k: Number(topk.value || 5),
      writer_enabled: writerEnabled.checked,
      write_min_confidence: Number(minConf.value || 0.75),
      rag_mode: String(ragMode.value || "keyword"),
      rag_embedding_mode: String(embeddingMode.value || ""),
      memory_episodic_ttl_days: Number(episodicTtlDays.value || 90),
    });
    localStorage.setItem(CHAT_MEMORY_MODE_KEY, normalizeMemoryMode(memoryModeSelect.value));
    await apiPost("/admin/api/chat/settings/specialist-flags", {
      flags: {
        generalist: true,
        memory: String(memoryCuratorSelect.value || "1") !== "0",
      },
    });
    status.textContent = JSON.stringify(saved.config || {});
  }});
  const btnReindex = el("button", { class: "btn", text: t("memory.reindex"), onclick: async () => {
    const resp = await apiPost("/admin/api/memory/reindex", {});
    status.textContent = `reindexed=${Number(resp.reindexed || 0)}`;
  }});
  const btnCleanup = el("button", { class: "btn btn--danger", text: t("memory.cleanup"), onclick: async () => {
    const resp = await apiPost("/admin/api/memory/cleanup-low-confidence", { max_confidence: 0.35 });
    status.textContent = `deleted=${Number(resp.deleted || 0)}`;
    router();
  }});

  const loadData = async () => {
    const qs = buildQS(50);
    const [cfgResp, hitsResp, itemsResp, statsResp] = await Promise.all([
      apiGet("/admin/api/memory/config"),
      apiGet("/admin/api/memory/hits?" + qs),
      apiGet("/admin/api/memory/items?" + qs),
      apiGet("/admin/api/memory/stats?" + qs),
    ]);
    const cfg = cfgResp.config || {};
    enabled.checked = !!cfg.enabled;
    backend.value = String(cfg.backend || "sqlite");
    topk.value = String(cfg.top_k || 5);
    writerEnabled.checked = !!cfg.writer_enabled;
    minConf.value = String(cfg.write_min_confidence ?? 0.75);
    ragMode.value = String(cfg.rag_mode || "keyword");
    embeddingMode.value = String(cfg.rag_embedding_mode || "");
    episodicTtlDays.value = String(cfg.memory_episodic_ttl_days || 90);
    memoryModeSelect.value = normalizeMemoryMode(localStorage.getItem(CHAT_MEMORY_MODE_KEY));
    try {
      const sf = await apiGet("/admin/api/chat/settings/specialist-flags");
      const flags = sf && sf.flags && typeof sf.flags === "object" ? sf.flags : {};
      memoryCuratorSelect.value = flags.memory === false ? "0" : "1";
    } catch (_) {
      memoryCuratorSelect.value = "1";
    }
    const hits = Array.isArray(hitsResp.hits) ? hitsResp.hits : [];
    const items = Array.isArray(itemsResp.items) ? itemsResp.items : [];
    const stats = (statsResp && statsResp.stats) || {};
    const srcText = Array.isArray(stats.top_sources) ? stats.top_sources.map((x) => `${x.source}:${x.count}`).join(", ") : "";
    statsWrap.textContent = `${t("memory.hitCount")}: ${Number(stats.hit_count || 0)} | ${t("memory.itemCount")}: ${Number(stats.item_count || 0)} | ${t("memory.avgScore")}: ${Number(stats.avg_score || 0).toFixed(3)} | ${t("memory.topSources")}: ${srcText || "-"}`;

    const hitBody = el("tbody");
    if (!hits.length) {
      hitBody.appendChild(el("tr", {}, [el("td", { text: t("memory.noData"), colspan: "6" })]));
    } else {
      hits.forEach((h) => {
        hitBody.appendChild(el("tr", {}, [
          tdCell(h.timestamp || "", 24),
          tdCell(h.tenant_id || "", 18),
          tdCell(h.user_id || "", 18),
          tdCell(h.query_text || "", 40),
          tdCell(h.memory_id || "", 18),
          tdCell(String(h.score || ""), 10),
        ]));
      });
    }
    hitsWrap.innerHTML = "";
    hitsWrap.appendChild(el("div", { class: "table-wrap" }, [el("table", { class: "table table--compact" }, [
      el("thead", {}, [el("tr", {}, [
        el("th", { text: t("table.timestamp") }),
        el("th", { text: "tenant_id" }),
        el("th", { text: "user_id" }),
        el("th", { text: "query" }),
        el("th", { text: "memory_id" }),
        el("th", { text: "score" }),
      ])]),
      hitBody,
    ])]));

    const itemBody = el("tbody");
    if (!items.length) {
      itemBody.appendChild(el("tr", {}, [el("td", { text: t("memory.noData"), colspan: "8" })]));
    } else {
      items.forEach((it) => {
        const btnDelete = el("button", { class: "btn btn--danger", text: t("memory.delete"), onclick: async () => {
          await apiPost("/admin/api/memory/delete", { memory_id: it.memory_id });
          await loadData();
        }});
        itemBody.appendChild(el("tr", {}, [
          tdCell(it.memory_id || "", 18),
          tdCell(it.tenant_id || "", 18),
          tdCell(it.user_id || "", 18),
          tdCell(it.memory_type || "", 14),
          tdCell(String(it.confidence ?? ""), 8),
          tdCell(it.content || "", 80),
          tdCell(it.updated_at || "", 24),
          el("td", {}, [btnDelete]),
        ]));
      });
    }
    itemsWrap.innerHTML = "";
    itemsWrap.appendChild(el("div", { class: "table-wrap" }, [el("table", { class: "table table--compact" }, [
      el("thead", {}, [el("tr", {}, [
        el("th", { text: "memory_id" }),
        el("th", { text: "tenant_id" }),
        el("th", { text: "user_id" }),
        el("th", { text: "type" }),
        el("th", { text: "confidence" }),
        el("th", { text: "content" }),
        el("th", { text: t("table.timestamp") }),
        el("th", { text: t("memory.delete") }),
      ])]),
      itemBody,
    ])]));

    try {
      const pluginsResp = await apiGet("/admin/api/plugins");
      const rows = Array.isArray(pluginsResp.plugins) ? pluginsResp.plugins : [];
      const wikiPlugin = rows.find((x) => String((x && x.plugin_name) || "").toLowerCase() === "memory-wiki");
      if (wikiPlugin) {
        wikiStatus.textContent = t("memory.wikiPluginFound", {
          name: String(wikiPlugin.plugin_name || "memory-wiki"),
          version: String(wikiPlugin.plugin_version || "-"),
        });
      } else {
        wikiStatus.textContent = t("memory.wikiPluginMissing");
      }
    } catch (_) {
      wikiStatus.textContent = t("memory.wikiPluginMissing");
    }
  };

  const btnApplyFilters = el("button", { class: "btn", text: t("memory.applyFilters"), onclick: async () => {
    const p = new URLSearchParams();
    if (tenantInput.value.trim()) p.set("tenant_id", tenantInput.value.trim());
    if (userInput.value.trim()) p.set("user_id", userInput.value.trim());
    location.hash = "#/memory" + (p.toString() ? ("?" + p.toString()) : "");
    await loadData();
  }});
  const btnClearFilters = el("button", { class: "btn", text: t("memory.clearFilters"), onclick: async () => {
    tenantInput.value = "";
    userInput.value = "";
    location.hash = "#/memory";
    await loadData();
  }});
  await loadData();

  return el("div", {}, [
    el("div", { class: "card" }, [
      el("div", { class: "card__title", text: t("memory.config") }),
      el("div", { class: "row" }, [el("label", { text: t("memory.enabled") }), enabled]),
      el("div", { class: "row" }, [el("label", { text: t("memory.backend") }), backend]),
      el("div", { class: "row" }, [el("label", { text: t("memory.topk") }), topk]),
      el("div", { class: "row" }, [el("label", { text: t("memory.writerEnabled") }), writerEnabled]),
      el("div", { class: "row" }, [el("label", { text: "RAG mode" }), ragMode]),
      el("div", { class: "row" }, [el("label", { text: "Embedding mode" }), embeddingMode]),
      el("div", { class: "row" }, [el("label", { text: "Episodic TTL days" }), episodicTtlDays]),
      el("div", { class: "row" }, [el("label", { text: t("memory.minConfidence") }), minConf]),
      el("div", { class: "row" }, [btnSave, btnReindex, btnCleanup]),
      status,
    ]),
    el("div", { class: "card" }, [
      el("div", { class: "card__title", text: t("memory.wikiCard") }),
      el("div", { class: "row" }, [el("label", { text: t("profile.memoryMode") }), memoryModeSelect]),
      el("div", { class: "row" }, [el("label", { text: t("profile.memoryCurator") }), memoryCuratorSelect]),
      el("div", { class: "row" }, [el("label", { text: t("memory.wikiStatus") }), wikiStatus]),
      el("div", { class: "row" }, [
        el("button", {
          class: "btn",
          text: t("memory.openPlugins"),
          onclick: () => {
            location.hash = "#/plugins";
          },
        }),
      ]),
    ]),
    el("div", { class: "card" }, [
      el("div", { class: "card__title", text: t("memory.filters") }),
      el("div", { class: "row" }, [tenantInput, userInput, btnApplyFilters, btnClearFilters]),
      statsWrap,
    ]),
    el("div", { class: "card" }, [
      el("div", { class: "card__title", text: t("memory.hits") }),
      hitsWrap,
    ]),
    el("div", { class: "card" }, [
      el("div", { class: "card__title", text: t("memory.items") }),
      itemsWrap,
    ]),
  ]);
}

async function renderApiGrants() {
  const status = el("div", { class: "muted", text: "" });
  const profileSel = el("select", { class: "input" });
  const grantListEl = el("div", {});
  const grantUserSel = el("select", { class: "input" });
  const grantMsg = el("div", { class: "muted", text: "" });
  const grantBtn = el("button", { class: "btn btn--primary", text: t("models.grantsGrantBtn") });
  const tenantGrantStatus = el("span", { class: "muted", text: "" });

  let state = null;

  const VIS_KEYS = {
    builtin: "models.vis.builtin",
    owned: "models.vis.owned",
    grant_user: "models.vis.grantUser",
    grant_tenant: "models.vis.grantTenant",
    global: "models.vis.global",
    other_user: "models.vis.otherUser",
  };

  function visibilityTag(vr) {
    const k = VIS_KEYS[String(vr || "")];
    return k ? t(k) : "";
  }

  async function paintGrants() {
    grantMsg.textContent = "";
    const pid = String(profileSel.value || "").trim();
    if (!pid) {
      grantListEl.innerHTML = "";
      tenantGrantStatus.textContent = "";
      return;
    }
    try {
      const tg = await apiGet("/admin/api/models/grants/tenant?profile_id=" + encodeURIComponent(pid));
      tenantGrantStatus.textContent = tg.granted ? t("models.tenantGrantOn") : t("models.tenantGrantOff");
      const g = await apiGet("/admin/api/models/grants?profile_id=" + encodeURIComponent(pid));
      const rows = Array.isArray(g.grants) ? g.grants : [];
      grantListEl.innerHTML = "";
      if (!rows.length) {
        grantListEl.appendChild(el("div", { class: "muted", text: t("models.grantsEmpty") }));
        return;
      }
      rows.forEach((r) => {
        const disp = String(r.display_name || r.username || r.user_id || "").trim();
        const rev = el("button", { class: "btn", text: t("models.grantsRevoke"), onclick: async () => {
          try {
            await apiRequest(
              "DELETE",
              "/admin/api/models/grants?profile_id=" + encodeURIComponent(pid) + "&user_id=" + encodeURIComponent(String(r.user_id || "")),
              undefined,
            );
            await paintGrants();
          } catch (e) {
            grantMsg.textContent = String(e.message || e);
          }
        } });
        grantListEl.appendChild(el("div", { class: "row" }, [
          el("span", { text: disp || r.user_id }),
          rev,
        ]));
      });
    } catch (e) {
      grantMsg.textContent = String(e.message || e);
    }
  }

  const btnTenantGrant = el("button", {
    class: "btn btn--primary",
    text: t("models.grantTenantBtn"),
    onclick: async () => {
      const pid = String(profileSel.value || "").trim();
      if (!pid) return;
      try {
        await apiPost("/admin/api/models/grants/tenant", { profile_id: pid });
        await paintGrants();
      } catch (e) {
        grantMsg.textContent = String(e.message || e);
      }
    },
  });
  const btnTenantRevoke = el("button", {
    class: "btn",
    text: t("models.revokeTenantGrant"),
    onclick: async () => {
      const pid = String(profileSel.value || "").trim();
      if (!pid) return;
      try {
        await apiRequest(
          "DELETE",
          "/admin/api/models/grants/tenant?profile_id=" + encodeURIComponent(pid),
          undefined,
        );
        await paintGrants();
      } catch (e) {
        grantMsg.textContent = String(e.message || e);
      }
    },
  });
  const grantTenantRow = el("div", { class: "row", style: "flex-wrap:wrap;gap:8px;align-items:center;" }, [
    btnTenantGrant,
    btnTenantRevoke,
    tenantGrantStatus,
  ]);

  const membersBody = el("div", {});
  let membersLoaded = false;
  const membersDetails = el("details", { class: "details" });
  membersDetails.appendChild(el("summary", { text: t("models.membersTitle") }));
  membersDetails.appendChild(membersBody);
  const membersWrap = el("div", { class: "card" }, [membersDetails]);

  membersDetails.addEventListener("toggle", async () => {
    if (!membersDetails.open || membersLoaded) return;
    try {
      const r = await apiGet("/admin/api/models/members");
      membersLoaded = true;
      membersBody.innerHTML = "";
      const list = Array.isArray(r.members) ? r.members : [];
      if (!list.length) {
        membersBody.appendChild(el("div", { class: "muted", text: "—" }));
        return;
      }
      list.forEach((m) => {
        const names = (m.profiles || []).map((p) => {
          const nm = String(p.name || p.id || "").trim();
          const vr = p.visibility_reason ? ` (${visibilityTag(p.visibility_reason)})` : "";
          return nm + vr;
        });
        membersBody.appendChild(el("div", { class: "card", style: "margin-bottom:10px" }, [
          el("div", { class: "card__title", text: formatUserLabel(m) }),
          el("div", { class: "muted", text: names.filter(Boolean).length ? names.join("；") : "—" }),
        ]));
      });
    } catch (e) {
      membersLoaded = false;
      membersBody.appendChild(el("div", { class: "muted", text: String(e.message || e) }));
    }
  });

  async function ensureGrantUsers() {
    grantUserSel.innerHTML = "";
    const tid = String((authSession && authSession.tenant_id) || "").trim();
    if (!tid) return;
    try {
      const u = await apiGet("/admin/api/users?tenant_id=" + encodeURIComponent(tid) + "&limit=500");
      grantUserSel.appendChild(el("option", { value: "", text: "—" }));
      (u.users || []).forEach((x) => {
        const uid = String(x.id || "").trim();
        if (!uid) return;
        grantUserSel.appendChild(el("option", { value: uid, text: formatUserLabel(x) || uid }));
      });
    } catch (e) {
      grantMsg.textContent = String(e.message || e);
    }
  }

  function fillProfileSelect() {
    profileSel.innerHTML = "";
    const uid = String((authSession && authSession.user_id) || "").trim();
    const all = (state && Array.isArray(state.profiles)) ? state.profiles : [];
    const list = all.filter((p) => profileShareableForGrant(p, uid));
    if (!list.length) {
      profileSel.appendChild(el("option", { value: "", text: t("apiGrants.noShareable") }));
      profileSel.disabled = true;
      return;
    }
    profileSel.disabled = false;
    list.forEach((p) => {
      const own = String(p.owner_user_id || "").trim();
      const tag = own ? t("models.vis.owned") : t("models.vis.global");
      const name = String(p.name || p.id || "").trim();
      profileSel.appendChild(el("option", { value: String(p.id), text: `${name} (${tag})` }));
    });
  }

  profileSel.addEventListener("change", async () => {
    await paintGrants();
  });

  grantBtn.addEventListener("click", async () => {
    const pid = String(profileSel.value || "").trim();
    const uid = String(grantUserSel.value || "").trim();
    if (!pid || !uid) return;
    try {
      await apiPost("/admin/api/models/grants", { profile_id: pid, user_id: uid });
      await paintGrants();
    } catch (e) {
      grantMsg.textContent = String(e.message || e);
    }
  });

  async function refresh() {
    try {
      const data = await apiGet("/admin/api/models");
      state = data;
      status.textContent = "";
      if (!data || data.can_manage_llm_grants !== true) return;
      fillProfileSelect();
      await ensureGrantUsers();
      await paintGrants();
    } catch (e) {
      state = null;
      status.textContent = String(e.message || e);
    }
  }

  await refresh();

  const forbiddenCard = el("div", { class: "card" }, [
    el("div", { class: "card__title", text: t("title.apiGrants") }),
    el("div", { class: "muted", text: t("apiGrants.forbidden") }),
    el("div", { class: "row" }, [
      el("a", { href: "#/models", text: t("apiGrants.openModels") }),
    ]),
  ]);

  if (!state || state.can_manage_llm_grants !== true) {
    const bits = [forbiddenCard];
    if (status.textContent) bits.push(el("div", { class: "card" }, [el("pre", { class: "pre", text: status.textContent })]));
    return el("div", {}, bits);
  }

  const introCard = el("div", { class: "card" }, [
    el("div", { class: "card__title", text: t("title.apiGrants") }),
    el("div", { class: "muted", text: t("apiGrants.intro") }),
    status,
  ]);
  const pickCard = el("div", { class: "card" }, [
    el("div", { class: "card__title", text: t("apiGrants.pickApi") }),
    el("div", { class: "row" }, [profileSel]),
  ]);
  const teamCard = el("div", { class: "card" }, [
    el("div", { class: "card__title", text: t("apiGrants.teamSection") }),
    el("div", { class: "muted", text: t("apiGrants.teamHint") }),
    grantTenantRow,
  ]);
  const userCard = el("div", { class: "card" }, [
    el("div", { class: "card__title", text: t("apiGrants.userSection") }),
    el("div", { class: "muted", text: t("apiGrants.userHint") }),
    el("div", { class: "row" }, [grantUserSel, grantBtn]),
    grantListEl,
    grantMsg,
  ]);

  return el("div", {}, [introCard, pickCard, teamCard, userCard, membersWrap]);
}

async function renderModels() {
  const canPickActive = hasPermission("admin:read");
  const canConfigureBindings = canPickActive;
  const canConfigureChatUi = hasPermission("admin:tenant:write");
  const status = el("div", { class: "muted", text: "" });
  const isAdminPool = String((authSession && authSession.username) || "").trim().toLowerCase() === "administrator";
  // 与后端 _require_models_mutate 对齐：administrator 写全局池需 tenant:write；普通用户写自己的配置只需 admin:read
  const canMutateProfiles = isAdminPool ? hasPermission("admin:tenant:write") : canPickActive;
  const readonlyHint = el("div", {
    class: "muted",
    text: isAdminPool && !canMutateProfiles ? t("models.readonly") : "",
  });
  const activeSelect = el("select", { class: "input", disabled: !canPickActive });
  const chatModelSelectorVisibleCb = el("input", { type: "checkbox", disabled: !canConfigureChatUi });
  const bindingWrap = el("div", {});
  const opsAiSpecialistSelect = el("select", { class: "input", disabled: !canConfigureBindings });
  const opsAiProfileSelect = el("select", { class: "input", disabled: !canConfigureBindings });
  const modelsGrantsLinkRow = el("div", { class: "muted", style: "display:none" });
  const newName = el("input", { class: "input", placeholder: t("models.createNamePlaceholder") });
  const newMode = el("select", { class: "input", disabled: !canMutateProfiles }, [
    el("option", { value: "openai", text: t("models.mode.openai") }),
    el("option", { value: "anthropic", text: t("models.mode.anthropic") }),
    el("option", { value: "google", text: t("models.mode.google") }),
    el("option", { value: "ollama", text: t("models.mode.ollama") }),
    el("option", { value: "rule", text: t("models.mode.rule") }),
  ]);
  const profName = el("input", { class: "input" });
  const modeSel = el("select", { class: "input" });
  const modelInp = el("input", { class: "input" });
  const baseInp = el("input", { class: "input", placeholder: t("models.baseUrlPlaceholder") });
  const thinkingModeCb = el("input", { type: "checkbox" });
  const reasoningEffortSel = el("select", { class: "input", style: "max-width:180px" }, [
    el("option", { value: "", text: t("models.reasoningEffortDefault") }),
    el("option", { value: "low", text: t("models.reasoningEffortLow") }),
    el("option", { value: "medium", text: t("models.reasoningEffortMedium") }),
    el("option", { value: "high", text: t("models.reasoningEffortHigh") }),
  ]);
  const keyInp = el("input", { class: "input", type: "password", autocomplete: "off" });
  const rememberCb = el("input", { type: "checkbox" });
  const readonlyProfileHint = el("div", { class: "muted", text: "" });
  const builtinCap = el("div", { class: "muted", text: "" });
  const warnKey = el("div", { class: "muted", text: "" });
  const openaiHint = el("div", { class: "muted", text: "" });
  const ollamaHint = el("div", { class: "muted", text: "" });
  const evalMetrics = el("div", { class: "row" });
  const evalTableWrap = el("div");
  const evalDetails = el("details", { class: "details" });
  const evalSummary = el("summary", { text: t("models.evalToggle") });
  const evalInner = el("div", {});
  const expertsStatus = el("div", { class: "muted", text: "" });
  const expertsSelect = el("select", { class: "input" });
  const expertNewId = el("input", { class: "input", placeholder: "new expert id, e.g. qa" });
  const expertNewNameEn = el("input", { class: "input", placeholder: "English name (required)" });
  const expertNewNameZh = el("input", { class: "input", placeholder: "中文名（可选）" });
  const expertRoleSel = el("select", { class: "input" }, [
    el("option", { value: "expert", text: "expert" }),
    el("option", { value: "system", text: "system" }),
  ]);
  const expertNameEn = el("input", { class: "input", placeholder: "English name (required)" });
  const expertNameZh = el("input", { class: "input", placeholder: "中文名（可选）" });
  const expertSoul = el("textarea", { class: "input", rows: "5", placeholder: "SOUL.md (optional)" });
  const expertRoleSystem = el("textarea", { class: "input", rows: "5", placeholder: "ROLE_SYSTEM.md (optional)" });

  async function downloadEvalExport(format) {
    const fmt = format === "json" ? "json" : "csv";
    const url = resolveAdminApiUrl(`/admin/api/models/eval/export?format=${encodeURIComponent(fmt)}`);
    const token = getStoredAuthToken();
    const res = await fetch(url, {
      headers: {
        accept: fmt === "json" ? "application/json" : "text/csv",
        ...(token ? { authorization: `Bearer ${token}` } : {}),
      },
    });
    if (!res.ok) throw new Error(`export ${res.status}`);
    const blob = await res.blob();
    const a = document.createElement("a");
    const name = fmt === "json" ? "agent_eval_logs.json" : "agent_eval_logs.csv";
    a.href = URL.createObjectURL(blob);
    a.download = name;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  const btnEvalCsv = el("button", {
    class: "btn",
    text: t("models.evalDownloadCsv"),
    onclick: async () => {
      try {
        await downloadEvalExport("csv");
      } catch (e) {
        status.textContent = String(e.message || e);
      }
    },
  });
  const btnEvalJson = el("button", {
    class: "btn",
    text: t("models.evalDownloadJson"),
    onclick: async () => {
      try {
        await downloadEvalExport("json");
      } catch (e) {
        status.textContent = String(e.message || e);
      }
    },
  });
  const evalActionRow = el("div", { class: "row" }, [
    el("span", { class: "muted", text: t("models.evalLogsPreview") }),
    btnEvalCsv,
    btnEvalJson,
  ]);
  evalInner.appendChild(evalMetrics);
  evalInner.appendChild(evalActionRow);
  evalInner.appendChild(evalTableWrap);
  evalDetails.appendChild(evalSummary);
  evalDetails.appendChild(evalInner);

  let state = null;
  let evalPack = null;
  let secretsStatus = null;
  let expertsState = { items: [] };

  const secretsStatusMsg = el("div", { class: "muted", text: "" });
  const secretsMigrateBtn = el("button", { class: "btn", text: t("secrets.migrateBtn") });
  const secretsCard = el("div", { class: "card", style: "display:none" }, [
    el("div", { class: "card__title", text: t("secrets.migrateTitle") }),
    el("div", { class: "muted", text: t("secrets.migrateHint") }),
    el("div", { class: "row" }, [secretsMigrateBtn]),
    secretsStatusMsg,
  ]);

  function fmtSecretsDone(s, p) {
    return t("secrets.migrateDone").replace("{s}", String(s)).replace("{p}", String(p));
  }

  function paintSecretsCard() {
    secretsStatusMsg.textContent = "";
    if (!secretsStatus || secretsStatus.ok !== true) {
      secretsCard.style.display = "none";
      return;
    }
    const n1 = intOr0(secretsStatus.legacy_b64_app_settings);
    const n2 = intOr0(secretsStatus.legacy_b64_llm_profiles);
    const total = n1 + n2;
    const canMigrate = hasPermission("admin:tenant:write");
    if (total <= 0) {
      secretsCard.style.display = "none";
      return;
    }
    secretsCard.style.display = "";
    if (!canMigrate) {
      secretsMigrateBtn.disabled = true;
      secretsStatusMsg.textContent = t("secrets.migrateForbidden");
      return;
    }
    if (!secretsStatus.has_master_key) {
      secretsMigrateBtn.disabled = true;
      secretsStatusMsg.textContent = t("secrets.migrateNeedKey");
      return;
    }
    secretsMigrateBtn.disabled = false;
    secretsStatusMsg.textContent = `legacy: settings=${n1}, profiles=${n2}`;
  }

  const VIS_KEYS = {
    builtin: "models.vis.builtin",
    owned: "models.vis.owned",
    grant_user: "models.vis.grantUser",
    grant_tenant: "models.vis.grantTenant",
    global: "models.vis.global",
    other_user: "models.vis.otherUser",
  };

  function visibilityTag(vr) {
    const k = VIS_KEYS[String(vr || "")];
    return k ? t(k) : "";
  }

  function labelFor(pid) {
    const profiles = (state && state.profiles) || [];
    const p = profiles.find((x) => String(x.id) === String(pid));
    const base = (p && String(p.name || "").trim()) || pid;
    const vr = p && p.visibility_reason;
    if (!vr) return base;
    const tag = visibilityTag(vr);
    return tag ? `${base} (${tag})` : base;
  }

  function fillModeSelect(sel, modes, current) {
    sel.innerHTML = "";
    modes.forEach((m) => {
      const label =
        m === "openai"
          ? t("models.mode.openai")
          : m === "openai_responses"
            ? t("models.mode.openai_responses")
            : m === "anthropic"
              ? t("models.mode.anthropic")
              : m === "google"
                ? t("models.mode.google")
                : m === "ollama"
                  ? t("models.mode.ollama")
                  : t("models.mode.rule");
      sel.appendChild(el("option", {
        value: m,
        text: label,
      }));
    });
    if (modes.includes(current)) sel.value = current;
    else sel.value = modes[0];
  }

  async function refresh() {
    try {
      const data = await apiGet("/admin/api/models");
      state = data;
      status.textContent = "";
      paint();
      try {
        secretsStatus = await apiGet("/admin/api/secrets/status");
      } catch (_) {
        secretsStatus = null;
      }
      paintSecretsCard();
      try {
        evalPack = await apiGet("/admin/api/models/eval?limit_logs=100");
        paintEval();
      } catch (ee) {
        evalPack = { ok: false, summary: {}, logs: [] };
        paintEval();
        status.textContent = [status.textContent, `${t("models.sectionEval")}: ${String(ee.message || ee)}`].filter(Boolean).join(" | ");
      }
      try {
        expertsState = await apiGet("/admin/api/experts");
      } catch (_) {
        expertsState = { ok: false, items: [] };
      }
      paintExperts();
    } catch (e) {
      state = null;
      evalPack = null;
      secretsStatus = null;
      expertsState = { ok: false, items: [] };
      status.textContent = String(e.message || e);
    }
  }

  function currentExpertItem() {
    const items = Array.isArray(expertsState && expertsState.items) ? expertsState.items : [];
    const id = String(expertsSelect.value || "");
    return items.find((x) => String(x.id || "") === id) || null;
  }

  function fillExpertFields(item) {
    const files = (item && item.files && typeof item.files === "object") ? item.files : {};
    expertNameEn.value = String((item && item.display_name_en) || "");
    expertNameZh.value = String((item && item.display_name_zh) || "");
    expertRoleSel.value = String((item && item.role) || "expert");
    expertSoul.value = String(files["SOUL.md"] || "");
    expertRoleSystem.value = String(files["ROLE_SYSTEM.md"] || "");
    const isSystem = !!(item && (item.builtin || String(item.role || "") === "system"));
    expertRoleSel.disabled = isSystem;
    btnExpertDelete.disabled = isSystem;
  }

  function paintExperts() {
    const items = Array.isArray(expertsState && expertsState.items) ? expertsState.items : [];
    const prev = String(expertsSelect.value || "");
    expertsSelect.innerHTML = "";
    items.forEach((x) => {
      const id = String(x.id || "");
      if (!id) return;
      const isSystem = !!(x && (x.builtin || String(x.role || "") === "system"));
      const tail = isSystem ? " (system)" : "";
      const name = String(x.display_name_en || "").trim() || id;
      expertsSelect.appendChild(el("option", { value: id, text: `${name} [${id}]${tail}` }));
    });
    if (items.some((x) => String(x.id || "") === prev)) expertsSelect.value = prev;
    else if (items.length) expertsSelect.value = String(items[0].id || "");
    fillExpertFields(currentExpertItem());
  }

  secretsMigrateBtn.addEventListener("click", async () => {
    if (!hasPermission("admin:tenant:write")) {
      secretsStatusMsg.textContent = t("secrets.migrateForbidden");
      return;
    }
    secretsMigrateBtn.disabled = true;
    secretsStatusMsg.textContent = "";
    try {
      const res = await apiPost("/admin/api/secrets/migrate", {});
      if (res && res.ok) {
        const s = intOr0(res.migrated_app_settings);
        const p = intOr0(res.migrated_llm_profiles);
        secretsStatusMsg.textContent = (s + p) > 0 ? fmtSecretsDone(s, p) : t("secrets.migrateNoop");
      } else {
        secretsStatusMsg.textContent = String((res && (res.error || res.detail)) || "migrate_failed");
      }
      try {
        secretsStatus = await apiGet("/admin/api/secrets/status");
      } catch (_) {
        secretsStatus = null;
      }
      paintSecretsCard();
    } catch (e) {
      secretsStatusMsg.textContent = String(e.message || e);
      paintSecretsCard();
    } finally {
      secretsMigrateBtn.disabled = false;
    }
  });

  function paintBindings() {
    bindingWrap.innerHTML = "";
    if (!state || !state.bindings) return;
    const profiles = state.profiles || [];
    const profileIds = profiles.map((p) => String(p.id));
    const roleIds = Array.isArray(state.role_ids) ? state.role_ids : [];
    roleIds.forEach((rid) => {
      const sel = el("select", { class: "input", disabled: !canConfigureBindings });
      sel.appendChild(el("option", { value: "", text: t("models.useGlobal") }));
      profiles.forEach((p) => {
        sel.appendChild(el("option", { value: String(p.id), text: labelFor(p.id) }));
      });
      const v = String(state.bindings[rid] || "").trim();
      sel.value = profileIds.includes(v) ? v : "";
      sel.addEventListener("change", async () => {
        if (!canConfigureBindings) return;
        const next = Object.assign({}, state.bindings);
        next[rid] = String(sel.value || "");
        try {
          await apiPost("/admin/api/models/bindings", { bindings: next });
          await refresh();
        } catch (e) {
          status.textContent = String(e.message || e);
        }
      });
      bindingWrap.appendChild(el("div", { class: "row" }, [
        el("label", { text: t("models.role." + rid) + " " }),
        sel,
      ]));
    });
  }

  function paintOpsAiBindings() {
    if (!state || !state.ops_ai_bindings) return;
    const profiles = state.profiles || [];
    const profileIds = profiles.map((p) => String(p.id));
    const roleIds = (Array.isArray(state.role_ids) ? state.role_ids : []).filter((rid) => String(rid || "") !== "manager");

    const curSpecialist = String(opsAiSpecialistSelect.value || "").trim();
    opsAiSpecialistSelect.innerHTML = "";
    roleIds.forEach((rid) => {
      opsAiSpecialistSelect.appendChild(el("option", { value: String(rid), text: t("models.role." + rid) }));
    });
    if (roleIds.includes(curSpecialist)) opsAiSpecialistSelect.value = curSpecialist;
    else if (roleIds.length) opsAiSpecialistSelect.value = roleIds[0];

    const rid = String(opsAiSpecialistSelect.value || "").trim();
    opsAiProfileSelect.innerHTML = "";
    profiles.forEach((p) => {
      opsAiProfileSelect.appendChild(el("option", { value: String(p.id), text: labelFor(p.id) }));
    });
    const v = String((state.ops_ai_bindings && state.ops_ai_bindings[rid]) || "").trim();
    opsAiProfileSelect.value = profileIds.includes(v) ? v : "";
  }

  function paintEval() {
    evalMetrics.innerHTML = "";
    evalTableWrap.innerHTML = "";
    const summary = (evalPack && evalPack.summary) || {};
    const total = intOr0(summary.total);
    const sr = Number(summary.success_rate || 0);
    const p95 = intOr0(summary.p95_latency_ms);
    evalMetrics.appendChild(el("span", { text: `${t("models.evalTotal")}: ${total}  ` }));
    evalMetrics.appendChild(el("span", { text: `${t("models.evalSuccess")}: ${(sr * 100).toFixed(1)}%  ` }));
    evalMetrics.appendChild(el("span", { text: `${t("models.evalP95")}: ${p95} ms` }));
    const logs = Array.isArray(evalPack && evalPack.logs) ? evalPack.logs : [];
    if (!logs.length) {
      evalTableWrap.appendChild(el("div", { class: "muted", text: t("models.noEvalLogs") }));
      return;
    }
    const tbody = el("tbody");
    logs.forEach((r) => {
      tbody.appendChild(el("tr", {}, [
        tdCell(r.timestamp || "", 24),
        tdCell(r.session_id || "", 20),
        tdCell(r.specialist || "", 12),
        tdCell(r.task_kind || "", 14),
        tdCell(r.success ? "1" : "0", 4),
        tdCell(String(r.latency_ms ?? ""), 8),
        tdCell(String(r.notes || ""), 60),
      ]));
    });
    evalTableWrap.appendChild(el("div", { class: "table-wrap" }, [el("table", { class: "table table--compact" }, [
      el("thead", {}, [el("tr", {}, [
        el("th", { text: t("table.timestamp") }),
        el("th", { text: "session_id" }),
        el("th", { text: t("table.specialist") }),
        el("th", { text: "task_kind" }),
        el("th", { text: t("table.status") }),
        el("th", { text: t("table.durationMs") }),
        el("th", { text: "notes" }),
      ])]),
      tbody,
    ])]));
  }

  function intOr0(x) {
    const n = parseInt(String(x), 10);
    return Number.isFinite(n) ? n : 0;
  }

  function paint() {
    if (!state) return;
    if (state.ok !== true) {
      status.textContent = status.textContent || t("models.loadFailed");
      return;
    }
    const profiles = Array.isArray(state.profiles) ? state.profiles : [];
    const builtin = String(state.builtin_ollama_profile_id || "");
    activeSelect.innerHTML = "";
    profiles.forEach((p) => {
      activeSelect.appendChild(el("option", { value: String(p.id), text: labelFor(p.id) }));
    });
    const aid = String(state.active_llm_profile_id || "");
    if (profiles.some((p) => String(p.id) === aid)) activeSelect.value = aid;
    activeSelect.disabled = !canPickActive;
    chatModelSelectorVisibleCb.disabled = !canConfigureChatUi;
    chatModelSelectorVisibleCb.checked = state.chat_model_selector_visible !== false;
    opsAiSpecialistSelect.disabled = !canConfigureBindings;
    opsAiProfileSelect.disabled = !canConfigureBindings;

    paintBindings();
    paintOpsAiBindings();

    const selProf = profiles.find((p) => String(p.id) === aid) || profiles[0] || {};
    const pid = String(selProf.id || "");
    const rowMutable = selProf.mutable !== false;
    const canEditFields = canMutateProfiles && rowMutable;
    readonlyProfileHint.textContent = rowMutable ? "" : t("models.profileReadonlyHint");
    const isBuiltin = pid === builtin;
    profName.value = String(selProf.name || "");
    const rawMode = String(selProf.mode || "openai").toLowerCase();
    const baseAllowedModes = ["openai", "anthropic", "google", "ollama", "rule"];
    const allowedModes = rawMode === "openai_responses" ? ["openai_responses", ...baseAllowedModes] : baseAllowedModes;
    const modeVal = allowedModes.includes(rawMode) ? rawMode : "openai";
    if (isBuiltin) {
      fillModeSelect(modeSel, ["ollama"], "ollama");
      modeSel.disabled = true;
      builtinCap.textContent = t("models.builtinLocked");
    } else {
      modeSel.disabled = !canEditFields;
      builtinCap.textContent = "";
      fillModeSelect(modeSel, allowedModes, modeVal);
    }
    modelInp.value = String(selProf.model || "");
    baseInp.value = String(selProf.base_url || "");
    thinkingModeCb.checked = !!selProf.thinking_mode_enabled;
    reasoningEffortSel.value = String(selProf.reasoning_effort || "");
    keyInp.value = String(state.profile_secret || "");
    rememberCb.checked = !!selProf.has_key;

    profName.disabled = !canEditFields;
    modelInp.disabled = !canEditFields;
    baseInp.disabled = !canEditFields;
    thinkingModeCb.disabled = !canEditFields;
    reasoningEffortSel.disabled = !canEditFields;
    keyInp.disabled = !canEditFields;
    rememberCb.disabled = !canEditFields;

    const m = isBuiltin ? "ollama" : modeVal;
    warnKey.textContent = "";
    openaiHint.textContent = "";
    ollamaHint.textContent = "";
    if (m === "openai" || m === "openai_responses") {
      ollamaHint.textContent = "";
      if (state.has_openai_api_key_env) openaiHint.textContent = t("models.openaiKeyHint");
      if (selProf.has_key && !String(keyInp.value || "").trim()) {
        warnKey.textContent = t("models.warnKeyInDb");
      }
    } else if (m === "google") {
      openaiHint.textContent = "";
      ollamaHint.textContent = "";
    } else if (m === "ollama") {
      ollamaHint.textContent = t("models.ollamaHint");
    }

    btnDelete.disabled = !canMutateProfiles || !rowMutable || pid === builtin;

    modelsGrantsLinkRow.innerHTML = "";
    if (state.can_manage_llm_grants) {
      modelsGrantsLinkRow.style.display = "";
      modelsGrantsLinkRow.appendChild(el("span", { text: `${t("models.grantsNavHint")} ` }));
      modelsGrantsLinkRow.appendChild(el("a", { href: "#/api-grants", text: t("models.linkApiGrants") }));
    } else {
      modelsGrantsLinkRow.style.display = "none";
    }

    paintEval();
  }

  activeSelect.addEventListener("change", async () => {
    if (!canPickActive) return;
    try {
      await apiPost("/admin/api/models/active", { profile_id: activeSelect.value });
      await refresh();
    } catch (e) {
      status.textContent = String(e.message || e);
    }
  });
  chatModelSelectorVisibleCb.addEventListener("change", async () => {
    if (!canConfigureChatUi) return;
    try {
      await apiPost("/admin/api/models/chat-ui", {
        chat_model_selector_visible: !!chatModelSelectorVisibleCb.checked,
      });
      await refresh();
    } catch (e) {
      status.textContent = String(e.message || e);
    }
  });
  opsAiSpecialistSelect.addEventListener("change", async () => {
    paintOpsAiBindings();
  });
  opsAiProfileSelect.addEventListener("change", async () => {
    if (!canConfigureBindings) return;
    try {
      const rid = String(opsAiSpecialistSelect.value || "").trim();
      const next = Object.assign({}, (state && state.ops_ai_bindings) || {});
      next[rid] = String(opsAiProfileSelect.value || "");
      await apiPost("/admin/api/models/ops-ai/bindings", { bindings: next });
      await refresh();
    } catch (e) {
      status.textContent = String(e.message || e);
    }
  });

  const btnCreate = el("button", { class: "btn btn--primary", text: t("models.createBtn"), onclick: async () => {
    if (!canMutateProfiles) return;
    try {
      await apiPost("/admin/api/models/profiles", {
        name: newName.value.trim() || t("models.newProfileDefault"),
        mode: newMode.value,
      });
      newName.value = "";
      await refresh();
    } catch (e) {
      status.textContent = String(e.message || e);
    }
  }});

  const btnSave = el("button", { class: "btn btn--primary", text: t("models.save"), onclick: async () => {
    if (!canMutateProfiles) return;
    const sel = (state.profiles || []).find((p) => String(p.id) === String(state.active_llm_profile_id || ""));
    if (sel && sel.mutable === false) return;
    const pid = String(state.active_llm_profile_id || "");
    const builtin = String(state.builtin_ollama_profile_id || "");
    try {
      let modeSave = modeSel.value;
      if (pid === builtin) modeSave = "ollama";
      await apiRequest("PATCH", "/admin/api/models/profiles/" + encodeURIComponent(pid), {
        name: profName.value.trim() || t("models.newProfileDefault"),
        mode: modeSave,
        model: modelInp.value.trim(),
        base_url: baseInp.value.trim(),
        thinking_mode_enabled: !!thinkingModeCb.checked,
        reasoning_effort: String(reasoningEffortSel.value || ""),
      });
      await apiRequest("POST", "/admin/api/models/profiles/" + encodeURIComponent(pid) + "/secret", {
        remember: rememberCb.checked,
        secret: keyInp.value,
      });
      await refresh();
    } catch (e) {
      status.textContent = String(e.message || e);
    }
  }});

  const btnDelete = el("button", { class: "btn btn--danger", text: t("models.delete"), onclick: async () => {
    if (!canMutateProfiles) return;
    const pid = String(state.active_llm_profile_id || "");
    const builtin = String(state.builtin_ollama_profile_id || "");
    if (pid === builtin) {
      status.textContent = t("models.cannotDeleteBuiltin");
      return;
    }
    if (!globalThis.confirm(t("models.deleteConfirm"))) return;
    try {
      await apiRequest("DELETE", "/admin/api/models/profiles/" + encodeURIComponent(pid), {});
      await refresh();
    } catch (e) {
      status.textContent = String(e.message || e);
    }
  }});

  const btnExpertCreate = el("button", {
    class: "btn btn--primary",
    text: "Create expert",
    onclick: async () => {
      if (!hasPermission("admin:tenant:write")) return;
      const eid = String(expertNewId.value || "").trim();
      if (!eid) {
        expertsStatus.textContent = "expert id required";
        return;
      }
      if (!String(expertNewNameEn.value || "").trim()) {
        expertsStatus.textContent = "English name is required";
        return;
      }
      if (!String(expertSoul.value || "").trim() && !String(expertRoleSystem.value || "").trim()) {
        expertsStatus.textContent = "SOUL.md or ROLE_SYSTEM.md is required";
        return;
      }
      try {
        const res = await apiPost("/admin/api/experts", {
          id: eid,
          display_name_en: String(expertNewNameEn.value || "").trim(),
          display_name_zh: String(expertNewNameZh.value || "").trim(),
          role: "expert",
          files: {
            "SOUL.md": expertSoul.value,
            "ROLE_SYSTEM.md": expertRoleSystem.value,
          },
        });
        if (!res || res.ok !== true) throw new Error(String((res && res.error) || "create_failed"));
        expertNewId.value = "";
        expertNewNameEn.value = "";
        expertNewNameZh.value = "";
        expertsStatus.textContent = "expert created";
        markPrewarmReminder("expert_created");
        await refresh();
        expertsSelect.value = String(res.created || "");
        fillExpertFields(currentExpertItem());
      } catch (e) {
        expertsStatus.textContent = String((e && e.message) || e);
      }
    },
  });

  const btnExpertSave = el("button", {
    class: "btn btn--primary",
    text: "Save expert files",
    onclick: async () => {
      if (!hasPermission("admin:tenant:write")) return;
      const item = currentExpertItem();
      if (!item) return;
      if (!String(expertNameEn.value || "").trim()) {
        expertsStatus.textContent = "English name is required";
        return;
      }
      if (!String(expertSoul.value || "").trim() && !String(expertRoleSystem.value || "").trim()) {
        expertsStatus.textContent = "SOUL.md or ROLE_SYSTEM.md is required";
        return;
      }
      try {
        const eid = String(item.id || "");
        const res = await apiRequest("PATCH", "/admin/api/experts/" + encodeURIComponent(eid), {
          display_name_en: String(expertNameEn.value || "").trim(),
          display_name_zh: String(expertNameZh.value || "").trim(),
          role: String(expertRoleSel.value || "expert"),
          files: {
            "SOUL.md": expertSoul.value,
            "ROLE_SYSTEM.md": expertRoleSystem.value,
          },
        });
        if (!res || res.ok !== true) throw new Error(String((res && res.error) || "update_failed"));
        expertsStatus.textContent = "expert saved";
        markPrewarmReminder("expert_updated");
        await refresh();
        expertsSelect.value = eid;
        fillExpertFields(currentExpertItem());
      } catch (e) {
        expertsStatus.textContent = String((e && e.message) || e);
      }
    },
  });

  const btnExpertDelete = el("button", {
    class: "btn btn--danger",
    text: "Delete expert",
    onclick: async () => {
      if (!hasPermission("admin:tenant:write")) return;
      const item = currentExpertItem();
      if (!item) return;
      if (item.builtin || String(item.role || "") === "system") {
        expertsStatus.textContent = "system expert cannot be deleted";
        return;
      }
      const eid = String(item.id || "");
      if (!globalThis.confirm(`Delete expert ${eid}?`)) return;
      try {
        const res = await apiRequest("DELETE", "/admin/api/experts/" + encodeURIComponent(eid), {});
        if (!res || res.ok !== true) throw new Error(String((res && res.error) || "delete_failed"));
        expertsStatus.textContent = "expert deleted";
        markPrewarmReminder("expert_deleted");
        await refresh();
      } catch (e) {
        expertsStatus.textContent = String((e && e.message) || e);
      }
    },
  });

  expertsSelect.addEventListener("change", () => {
    fillExpertFields(currentExpertItem());
  });

  await refresh();

  if (!state) {
    return el("div", {}, [
      el("div", { class: "card" }, [
        el("div", { class: "card__title", text: t("title.models") }),
        el("div", { class: "muted", text: t("models.loadFailed") }),
        el("pre", { class: "pre", text: status.textContent || "" }),
      ]),
    ]);
  }

  if (state.ok === true && Array.isArray(state.profiles) && state.profiles.length === 0) {
    const noProfBody = [
      el("div", { class: "card__title", text: t("title.models") }),
      el("div", { class: "muted", text: t("models.noProfiles") }),
    ];
    if (state.db_path) {
      noProfBody.push(el("div", { class: "muted", text: `${t("models.dbPath")}: ${state.db_path}` }));
    }
    noProfBody.push(status);
    return el("div", {}, [el("div", { class: "card" }, noProfBody)]);
  }

  if (state.ok !== true) {
    return el("div", {}, [
      el("div", { class: "card" }, [
        el("div", { class: "card__title", text: t("title.models") }),
        el("div", { class: "muted", text: t("models.loadFailed") }),
        el("pre", { class: "pre", text: JSON.stringify(state, null, 2) }),
        status,
      ]),
    ]);
  }

  const topBits = [readonlyHint, status, modelsGrantsLinkRow];
  if (state.db_path) {
    topBits.push(el("div", { class: "muted", text: `${t("models.dbPath")}: ${state.db_path}` }));
  }
  // Show secret migration helper when legacy secrets exist.
  topBits.push(secretsCard);

  return renderPageShell({
    title: t("title.models"),
    subtitle: "模型切换、绑定与评估配置",
    sections: [
      { id: "models-overview", label: "概览" },
      { id: "models-bindings", label: "绑定" },
      { id: "models-ops-ai", label: "内部API" },
      { id: "models-api", label: "API配置" },
      { id: "models-experts", label: "Experts" },
      { id: "models-eval", label: "评估" },
    ],
  }, [
    ...topBits,
    el("div", { class: "page-grid page-grid--two" }, [
      renderSectionCard(t("models.sectionActive"), "", [
        el("div", { class: "row" }, [el("label", { text: t("models.pickModel") }), activeSelect]),
        el("div", { class: "row" }, [el("label", { text: t("models.chatModelSelector") }), chatModelSelectorVisibleCb]),
        el("div", { class: "muted", text: t("models.chatModelSelectorHint") }),
      ], { id: "models-overview" }),
      renderSectionCard(t("models.sectionNew"), "", [
        el("div", { class: "row" }, [el("label", { text: t("models.profileName") }), newName]),
        el("div", { class: "row" }, [el("label", { text: t("models.mode") }), newMode]),
        el("div", { class: "row" }, [btnCreate]),
      ]),
    ]),
    renderSectionCard(t("models.sectionBindings"), t("models.agentBindingHelp"), [
      el("div", { class: "muted", text: t("models.bindingsExtraHint") }),
      el("div", { class: "muted", text: t("models.bindingsScopeHint") }),
      bindingWrap,
    ], { id: "models-bindings" }),
    renderSectionCard("内部 API模型配置", "仅用于 v1 / 专家模式：选择专家并绑定 API 配置。", [
      el("div", { class: "row" }, [el("label", { text: "专家" }), opsAiSpecialistSelect]),
      el("div", { class: "row" }, [el("label", { text: "API配置" }), opsAiProfileSelect]),
    ], { id: "models-ops-ai" }),
    renderSectionCard(t("models.sectionApi"), "", [
      builtinCap,
      readonlyProfileHint,
      el("div", { class: "row" }, [el("label", { text: t("models.profileName") }), profName]),
      el("div", { class: "row" }, [el("label", { text: t("models.mode") }), modeSel]),
      el("div", { class: "row" }, [el("label", { text: t("models.model") }), modelInp]),
      el("div", { class: "row" }, [el("label", { text: t("models.baseUrl") }), baseInp]),
      el("div", { class: "row" }, [el("label", { text: t("models.thinkMode") }), thinkingModeCb]),
      el("div", { class: "muted", text: t("models.thinkModeHint") }),
      el("div", { class: "row" }, [el("label", { text: t("models.reasoningEffort") }), reasoningEffortSel]),
      warnKey,
      openaiHint,
      ollamaHint,
      el("div", { class: "row" }, [el("label", { text: t("models.apiKey") }), keyInp]),
      el("div", { class: "row" }, [el("label", { text: t("models.rememberKey") }), rememberCb]),
      el("div", { class: "row" }, [btnSave]),
      el("div", { class: "row" }, [btnDelete]),
    ], { id: "models-api" }),
    renderSectionCard("Experts", "Runtime registry and workspace prompt files are split into two sections below.", [
      el("div", { class: "card", style: "margin:8px 0;padding:10px;" }, [
        el("div", { class: "card__title", text: "Runtime Expert Registry" }),
        el("div", { class: "row" }, [el("label", { text: "Existing" }), expertsSelect]),
        el("div", { class: "row" }, [btnExpertDelete]),
        el("div", { class: "row" }, [el("label", { text: "Create ID" }), expertNewId]),
        el("div", { class: "row" }, [el("label", { text: "Create Name(en)" }), expertNewNameEn]),
        el("div", { class: "row" }, [el("label", { text: "Create Name(zh)" }), expertNewNameZh]),
        el("div", { class: "row" }, [btnExpertCreate]),
        el("div", { class: "row" }, [el("label", { text: "Name(en)" }), expertNameEn]),
        el("div", { class: "row" }, [el("label", { text: "Name(zh)" }), expertNameZh]),
        el("div", { class: "row" }, [el("label", { text: "Role" }), expertRoleSel]),
      ]),
      el("div", { class: "card", style: "margin:8px 0;padding:10px;" }, [
        el("div", { class: "card__title", text: "Workspace Prompt Files" }),
        el("div", { class: "muted", text: "SOUL.md or ROLE_SYSTEM.md is required." }),
        el("div", { class: "row" }, [el("label", { text: "SOUL.md" }), expertSoul]),
        el("div", { class: "row" }, [el("label", { text: "ROLE_SYSTEM.md" }), expertRoleSystem]),
        el("div", { class: "row" }, [btnExpertSave]),
      ]),
      expertsStatus,
    ], { id: "models-experts" }),
    el("div", { class: "card section-card", id: "models-eval" }, [evalDetails]),
  ]);
}

const PLUGINS_PAGE_SIZE = 15;

function pluginsFold(summaryText, innerNodes) {
  const det = el("details", { class: "details plugins-fold" });
  det.appendChild(el("summary", { text: summaryText }));
  const inner = el("div", { class: "plugins-fold__inner" });
  innerNodes.forEach((n) => inner.appendChild(n));
  det.appendChild(inner);
  return det;
}

/** totalHolder.value = row count; pageRef.value = 1-based page */
function pluginsPagerBar(totalHolder, pageRef, onRepaint) {
  const wrap = el("div", {
    class: "row plugins-pager",
    style: "gap:8px;align-items:center;margin-top:6px;flex-wrap:wrap;",
  });
  const lab = el("span", { class: "muted", text: "" });
  const maxP = () => Math.max(1, Math.ceil(Math.max(0, totalHolder.value) / PLUGINS_PAGE_SIZE));
  const prevBtn = el("button", { class: "btn btn--small", text: "上一页" });
  const nextBtn = el("button", { class: "btn btn--small", text: "下一页" });
  const sync = () => {
    const total = totalHolder.value;
    let cur = pageRef.value;
    const mp = maxP();
    if (cur > mp) {
      cur = mp;
      pageRef.value = cur;
    }
    if (cur < 1) {
      cur = 1;
      pageRef.value = 1;
    }
    const start = total === 0 ? 0 : (cur - 1) * PLUGINS_PAGE_SIZE + 1;
    const end = Math.min(cur * PLUGINS_PAGE_SIZE, total);
    lab.textContent = total ? `第 ${start}–${end} / 共 ${total} 条` : "无数据";
    prevBtn.disabled = cur <= 1 || total === 0;
    nextBtn.disabled = cur >= mp || total === 0;
  };
  prevBtn.addEventListener("click", () => {
    if (pageRef.value > 1) {
      pageRef.value--;
      onRepaint();
      sync();
    }
  });
  nextBtn.addEventListener("click", () => {
    if (pageRef.value < maxP()) {
      pageRef.value++;
      onRepaint();
      sync();
    }
  });
  wrap.appendChild(prevBtn);
  wrap.appendChild(lab);
  wrap.appendChild(nextBtn);
  sync();
  return { wrap, sync };
}

/** 与后端 `load_tool_policies_dict` 一致：0；1–9998；≥9999 → 9999 */
function normalizeWirePolicyLevel(raw) {
  const s = String(raw ?? "").trim();
  if (s === "") return 0;
  const n = Number(s);
  if (!Number.isFinite(n)) return 0;
  if (n >= 9999) return 9999;
  if (n <= 0) return 0;
  return Math.min(Math.trunc(n), 9998);
}

async function renderPlugins() {
  const p = await apiGet("/admin/api/plugins");
  let toolPolicy = {
    disable_tool_confirm: false,
    enforced_retry_mode: "first_round_only",
    tool_loop_state_machine: true,
    tool_signature_budget: 2,
    turn_max_tool_workers: 8,
    turn_max_tool_rounds: 30,
    turn_max_context_messages: 80,
    turn_runner_impl: "oclaw",
    manager_decision_mode: "",
    sse_queue_maxsize: 2000,
    tool_log_max_chars: 200000,
    enable_mcp_tools: true,
    enable_plugin_tools: false,
    enable_run_command: true,
    tool_context_truncate_enabled: true,
    chat_show_ttft_debug: false,
    tool_llm_message_max_chars: 0,
    mcp_filesystem_extra_roots: "",
    mcp_env_allowlist: "",
    oclaw_retryable_error_codes: "",
    oclaw_retry_codes_strict_mode: false,
    wecom_longconn_workers: 2,
    wecom_longconn_inbound_queue_maxsize: 200,
  };
  let mcp = { servers: [] };
  let mcpFailures = { items: [] };
  let marketTrending = { items: [] };
  let depStatus = { items: [] };
  let mcpBinding = { available_specialists: ["generalist"], servers: [], mapping: {} };
  let mcpUsage = { summary: [], calls: [] };
  let mcpUpdateState = { byServer: {} };
  let mcpActionMenuEl = null;
  const closeMcpActionMenu = () => {
    if (mcpActionMenuEl && mcpActionMenuEl.parentNode) {
      mcpActionMenuEl.parentNode.removeChild(mcpActionMenuEl);
    }
    mcpActionMenuEl = null;
  };
  try {
    mcp = await apiGet("/admin/api/mcp/servers");
  } catch (_) {}
  try {
    mcpFailures = await apiGet("/admin/api/mcp/failures?limit=20");
  } catch (_) {}
  try {
    marketTrending = await apiGet("/admin/api/mcp/market/trending?per_source_limit=4");
  } catch (_) {}
  try {
    depStatus = await apiGet("/admin/api/mcp/dependencies");
  } catch (_) {}
  try {
    mcpBinding = await apiGet("/admin/api/mcp/binding");
  } catch (_) {}
  try {
    toolPolicy = await apiGet("/admin/api/tool-policy");
  } catch (_) {}
  try {
    mcpUsage = await apiGet("/admin/api/mcp/usage?limit=500");
  } catch (_) {}
  const pluginCatalog = Array.isArray(p.plugins) ? p.plugins : [];
  const pluginPageRef = { value: 1 };
  const pluginTotalHolder = { value: pluginCatalog.length };
  const pluginTbody = el("tbody");
  const buildPluginRow = (x) =>
    el("tr", {}, [
      el("td", { text: String(x.plugin_name || "") }),
      el("td", { text: String(x.plugin_version || "") }),
      el("td", { text: String(x.entry_point || "") }),
      el("td", { text: String(x.enabled ? 1 : 0) }),
    ]);
  const repaintPlugins = () => {
    pluginTbody.innerHTML = "";
    const start = (pluginPageRef.value - 1) * PLUGINS_PAGE_SIZE;
    pluginCatalog.slice(start, start + PLUGINS_PAGE_SIZE).forEach((x) => {
      pluginTbody.appendChild(buildPluginRow(x));
    });
  };
  repaintPlugins();
  const pluginPager = pluginsPagerBar(pluginTotalHolder, pluginPageRef, repaintPlugins);
  const sourceType = el("select", { class: "input" }, [
    el("option", { value: "github", text: "github" }),
    el("option", { value: "npm", text: "npm" }),
    el("option", { value: "pypi", text: "pypi" }),
  ]);
  const sourceRef = el("input", { class: "input", placeholder: "source_ref (repo url / package)" });
  const version = el("input", { class: "input", placeholder: "version(optional)" });
  const entryCmd = el("input", { class: "input", placeholder: "entry_command (required for runtime)" });
  const entryArgs = el("input", { class: "input", placeholder: "entry_args (space separated)" });
  const marketQ = el("input", { class: "input", placeholder: "search MCP market (github/npm/pypi)" });
  const marketBtn = el("button", { class: "btn", text: "Search" });
  const marketRefreshBtn = el("button", { class: "btn", text: "Refresh Trending" });
  const checkAllBtn = el("button", {
    class: "btn",
    text: "Check Installed",
    onclick: async () => {
      const r = await apiPost("/admin/api/mcp/check-all", { enabled_only: true });
      const items = Array.isArray(r.items) ? r.items : [];
      const parts = items.map((x) => {
        const sid = String(x.server_id || "-");
        if (x.ok) return `${sid}:ok(${Number(x.tools_synced || 0)})`;
        return `${sid}:err(${String(x.error_code || "unknown")})`;
      });
      installStatus.textContent = `[check-all] ok=${Number(r.ok_count || 0)} err=${Number(r.error_count || 0)} ${parts.join(" | ")}`;
      router();
    },
  });
  const checkUpdatesBtn = el("button", {
    class: "btn",
    text: "Check Updates",
    onclick: async () => {
      const r = await apiPost("/admin/api/mcp/check-updates", { enabled_only: true });
      const items = Array.isArray(r.items) ? r.items : [];
      const next = {};
      items.forEach((x) => {
        const sid = String(x.server_id || "").trim();
        if (!sid) return;
        next[sid] = x;
      });
      mcpUpdateState.byServer = next;
      const updates = items.filter((x) => !!x.has_update).map((x) => String(x.server_id || "-"));
      installStatus.textContent =
        `[check-updates] total=${Number(r.total || 0)} updates=${Number(r.update_count || 0)} ` +
        (updates.length ? `(${updates.join(", ")})` : "(none)");
      repaintMcpInstalled();
    },
  });
  const updateOutdatedBtn = el("button", {
    class: "btn",
    text: "Update Outdated Only",
    onclick: async () => {
      const byServer = mcpUpdateState.byServer && typeof mcpUpdateState.byServer === "object" ? mcpUpdateState.byServer : {};
      const outdated = Object.keys(byServer).filter((sid) => !!(byServer[sid] && byServer[sid].has_update));
      if (!outdated.length) {
        installStatus.textContent = "[update-outdated] no outdated MCPs. Click Check Updates first.";
        return;
      }
      const results = [];
      for (const sid of outdated) {
        const r = await apiPost("/admin/api/mcp/update", {
          server_id: sid,
          update_to_latest: true,
          sync_tools: true,
        });
        results.push({ server_id: sid, ok: !!r.ok, raw: r });
      }
      const okCount = results.filter((x) => x.ok).length;
      installStatus.textContent =
        `[update-outdated] total=${results.length} ok=${okCount} err=${results.length - okCount} ` +
        results.map((x) => `${x.server_id}:${x.ok ? "ok" : "err"}`).join(" | ");
      markPrewarmReminder("mcp_updated");
      router();
    },
  });
  const e2eCheckBtn = el("button", {
    class: "btn",
    text: "E2E Check",
    onclick: async () => {
      const r = await apiPost("/admin/api/mcp/e2e-check", {});
      const items = Array.isArray(r.items) ? r.items : [];
      const parts = items.map((x) => {
        const sid = String(x.server_id || "-");
        return `${sid}:${x.ok ? "ok" : ("err(" + String(x.error || "unknown") + ")")}`;
      });
      installStatus.textContent = `[e2e] ok=${Number(r.ok_count || 0)} err=${Number(r.error_count || 0)} session=${String(r.session_id || "-")} ${parts.join(" | ")}`;
      router();
    },
  });
  const updateAllBtn = el("button", {
    class: "btn",
    text: "Update Installed",
    onclick: async () => {
      const r = await apiPost("/admin/api/mcp/update", {
        enabled_only: true,
        update_to_latest: true,
        sync_tools: true,
      });
      const items = Array.isArray(r.items) ? r.items : [];
      const parts = items.map((x) => {
        const sid = String(x.server_id || "-");
        if (x.ok) return `${sid}:ok(sync=${Number(x.tools_synced || 0)})`;
        return `${sid}:err(${String(x.error_code || "unknown")})`;
      });
      installStatus.textContent =
        `[update-all] total=${Number(r.total || 0)} ok=${Number(r.ok_count || 0)} err=${Number(r.error_count || 0)} ${parts.join(" | ")}`;
      markPrewarmReminder("mcp_updated");
      router();
    },
  });
  const repairWeakIncludeDisabledCb = el("input", { type: "checkbox" });
  repairWeakIncludeDisabledCb.checked = false;
  const repairWeakBtn = el("button", {
    class: "btn",
    text: "Repair weak",
    title:
      "MCPs with health≠ok or zero cached tools: run health + sync. By default only enabled rows; tick “Include disabled” to repair disabled installs too.",
    onclick: async () => {
      const enabledOnly = !repairWeakIncludeDisabledCb.checked;
      const r = await apiPost("/admin/api/mcp/repair-weak", { enabled_only: enabledOnly });
      const items = Array.isArray(r.items) ? r.items : [];
      const parts = items.map((x) => {
        const sid = String(x.server_id || "-");
        if (x.ok) return `${sid}:ok(${Number(x.tools_synced || 0)})`;
        return `${sid}:err(${String(x.error_code || "unknown")})`;
      });
      const scope = enabledOnly ? "enabled_only" : "include_disabled";
      installStatus.textContent =
        `[repair-weak:${scope}] selected=${Number(r.selected || 0)} skip_ok=${Number(r.skipped_healthy || 0)} ` +
        `ok=${Number(r.ok_count || 0)} err=${Number(r.error_count || 0)} ${parts.join(" | ")}`;
      router();
    },
  });
  const repairWeakScopeLabel = el("label", { class: "row", style: "align-items:center;gap:6px;" }, [
    repairWeakIncludeDisabledCb,
    el("span", { class: "muted", text: "Include disabled" }),
  ]);
  const marketWrap = el("div");
  const marketTableMount = el("div");
  const marketPagerMount = el("div");
  marketWrap.appendChild(marketTableMount);
  marketWrap.appendChild(marketPagerMount);
  let marketSearchItems = [];
  const marketSearchPageRef = { value: 1 };
  const marketSearchTotalHolder = { value: 0 };
  const trendingWrap = el("div");
  const trendingTableMount = el("div");
  const trendingPagerMount = el("div");
  trendingWrap.appendChild(trendingTableMount);
  trendingWrap.appendChild(trendingPagerMount);
  let trendingItemsCache = [];
  const trendingPageRef = { value: 1 };
  const trendingTotalHolder = { value: 0 };
  const depWrap = el("div");
  const depTableMount = el("div");
  const depPagerMount = el("div");
  depWrap.appendChild(depTableMount);
  depWrap.appendChild(depPagerMount);
  const depItemsList = Array.isArray(depStatus.items) ? depStatus.items : [];
  const depPageRef = { value: 1 };
  const depTotalHolder = { value: depItemsList.length };
  const bindingStatus = el("div", { class: "muted", text: "" });
  const installStatus = el("div", { class: "muted", text: "" });
  const preflightFixWrap = el("div");
  const toolPolicyStatus = el("div", { class: "muted", text: "" });
  const legacyToolPolicyNote = el("div", {
    class: "muted",
    text: "Legacy tool-policy switches (confirm/retry/state-machine/signature budget) are disconnected under oclaw.",
  });
  const turnMaxWorkersInput = el("input", {
    class: "input",
    type: "number",
    min: "1",
    max: "32",
    value: String(Number(toolPolicy.turn_max_tool_workers || 8)),
    style: "max-width:120px",
  });
  const turnMaxRoundsInput = el("input", {
    class: "input",
    type: "number",
    min: "1",
    max: "100",
    value: String(Number(toolPolicy.turn_max_tool_rounds || 30)),
    style: "max-width:120px",
  });
  const turnMaxCtxInput = el("input", {
    class: "input",
    type: "number",
    min: "10",
    max: "400",
    value: String(Number(toolPolicy.turn_max_context_messages || 80)),
    style: "max-width:120px",
  });
  const turnRunnerImplNote = el("div", {
    class: "muted",
    text: "Turn runner: oclaw (legacy runners disconnected)",
  });
  const managerDecisionModeNote = el("div", {
    class: "muted",
    text: "Manager decision mode: (legacy disconnected)",
  });
  const sseQueueMaxsizeInput = el("input", {
    class: "input",
    type: "number",
    min: "200",
    max: "50000",
    value: String(Number(toolPolicy.sse_queue_maxsize || 2000)),
    style: "max-width:140px",
  });
  const toolLogMaxCharsInput = el("input", {
    class: "input",
    type: "number",
    min: "20000",
    max: "2000000",
    value: String(Number(toolPolicy.tool_log_max_chars || 200000)),
    style: "max-width:140px",
  });
  const enableMcpToolsCb = el("input", { type: "checkbox" });
  enableMcpToolsCb.checked = !!toolPolicy.enable_mcp_tools;
  const enablePluginToolsCb = el("input", { type: "checkbox" });
  enablePluginToolsCb.checked = !!toolPolicy.enable_plugin_tools;
  const enableRunCommandCb = el("input", { type: "checkbox" });
  enableRunCommandCb.checked = !!toolPolicy.enable_run_command;
  const toolContextTruncateCb = el("input", { type: "checkbox" });
  toolContextTruncateCb.checked = !!toolPolicy.tool_context_truncate_enabled;
  const chatShowTtftDebugCb = el("input", { type: "checkbox" });
  chatShowTtftDebugCb.checked = !!toolPolicy.chat_show_ttft_debug;
  const toolLlmMessageMaxCharsInput = el("input", {
    class: "input",
    type: "number",
    min: "0",
    max: "500000",
    value: String(Number(toolPolicy.tool_llm_message_max_chars ?? 0)),
    style: "max-width:140px",
  });
  const mcpFilesystemExtraRootsInput = el("input", {
    class: "input",
    value: String(toolPolicy.mcp_filesystem_extra_roots || ""),
    placeholder: "D:\\work|D:\\docs",
  });
  const mcpEnvAllowlistInput = el("input", {
    class: "input",
    value: String(toolPolicy.mcp_env_allowlist || ""),
    placeholder: "BRAVE_API_KEY,GOOGLE_OAUTH_CREDENTIALS,...",
  });
  const oclawRetryableErrorCodesInput = el("input", {
    class: "input",
    value: String(toolPolicy.oclaw_retryable_error_codes || ""),
    placeholder: "provider_timeout,provider_rate_limited,...",
  });
  const oclawRetryCodesStrictModeCb = el("input", { type: "checkbox" });
  oclawRetryCodesStrictModeCb.checked = !!toolPolicy.oclaw_retry_codes_strict_mode;
  const wecomLongconnWorkersInput = el("input", {
    class: "input",
    type: "number",
    min: "1",
    max: "8",
    value: String(Number(toolPolicy.wecom_longconn_workers || 2)),
    style: "max-width:120px",
  });
  const wecomLongconnInboundQueueInput = el("input", {
    class: "input",
    type: "number",
    min: "20",
    max: "5000",
    value: String(Number(toolPolicy.wecom_longconn_inbound_queue_maxsize || 200)),
    style: "max-width:140px",
  });
  const saveToolPolicyBtn = el("button", {
    class: "btn",
    text: "Save Tool Policy",
    onclick: async () => {
      const r = await apiPost("/admin/api/tool-policy", {
        turn_max_tool_workers: Number(turnMaxWorkersInput.value || 8),
        turn_max_tool_rounds: Number(turnMaxRoundsInput.value || 30),
        turn_max_context_messages: Number(turnMaxCtxInput.value || 80),
        // manager_decision_mode is legacy-only; no longer submitted.
        sse_queue_maxsize: Number(sseQueueMaxsizeInput.value || 2000),
        tool_log_max_chars: Number(toolLogMaxCharsInput.value || 200000),
        enable_mcp_tools: !!enableMcpToolsCb.checked,
        enable_plugin_tools: !!enablePluginToolsCb.checked,
        enable_run_command: !!enableRunCommandCb.checked,
        tool_context_truncate_enabled: !!toolContextTruncateCb.checked,
        chat_show_ttft_debug: !!chatShowTtftDebugCb.checked,
        tool_llm_message_max_chars: Number(toolLlmMessageMaxCharsInput.value || 0),
        mcp_filesystem_extra_roots: String(mcpFilesystemExtraRootsInput.value || ""),
        mcp_env_allowlist: String(mcpEnvAllowlistInput.value || ""),
        oclaw_retryable_error_codes: String(oclawRetryableErrorCodesInput.value || ""),
        oclaw_retry_codes_strict_mode: !!oclawRetryCodesStrictModeCb.checked,
        wecom_longconn_workers: Number(wecomLongconnWorkersInput.value || 2),
        wecom_longconn_inbound_queue_maxsize: Number(wecomLongconnInboundQueueInput.value || 200),
      });
      const unknownRetry = Array.isArray(r.unknown_retryable_error_codes) ? r.unknown_retryable_error_codes : [];
      if (unknownRetry.length) {
        toolPolicyStatus.textContent = `[tool-policy] saved with warnings: unknown_retryable_error_codes=${unknownRetry.join(", ")} | ` + JSON.stringify(r);
      } else {
        toolPolicyStatus.textContent = `[tool-policy] ` + JSON.stringify(r);
      }
      toolPolicyStatus.textContent += " | restart gateway/desktop to apply run_command toggle";
    },
  });
  const availableSpecialists = Array.isArray(mcpBinding.available_specialists) && mcpBinding.available_specialists.length
    ? mcpBinding.available_specialists.map((x) => String(x))
    : ["generalist"];
  const bindingServers = Array.isArray(mcpBinding.servers)
    ? mcpBinding.servers.filter((x) => x && String(x.server_id || "").trim())
    : [];
  let bindingDraft = mcpBinding.mapping && typeof mcpBinding.mapping === "object" ? { ...mcpBinding.mapping } : {};
  const allSpecialistIds = () => {
    const s = new Set(availableSpecialists.map((x) => String(x)));
    Object.keys(bindingDraft).forEach((k) => s.add(String(k)));
    return Array.from(s).sort();
  };
  const specialistsBoundToServer = (sid) => {
    const out = [];
    allSpecialistIds().forEach((sp) => {
      const arr = Array.isArray(bindingDraft[sp]) ? bindingDraft[sp].map((x) => String(x)) : [];
      if (arr.includes(String(sid))) out.push(sp);
    });
    return out;
  };
  let repaintExpertBindingDashboard = () => {};
  const specialistSelect = el("select", { class: "input" }, availableSpecialists.map((sp) =>
    el("option", { value: sp, text: sp }),
  ));
  const bindingListWrap = el("div");
  const bindingListRowsMount = el("div");
  const bindingListPagerMount = el("div");
  bindingListWrap.appendChild(bindingListRowsMount);
  bindingListWrap.appendChild(bindingListPagerMount);
  const bindingListPageRef = { value: 1 };
  const bindingListTotalHolder = { value: 0 };
  const bindingReverseWrap = el("div");
  const bindingReverseTableMount = el("div");
  const bindingReversePagerMount = el("div");
  bindingReverseWrap.appendChild(bindingReverseTableMount);
  bindingReverseWrap.appendChild(bindingReversePagerMount);
  const bindingReversePageRef = { value: 1 };
  const bindingReverseTotalHolder = { value: 0 };
  const flashInstalledRow = (sid) => {
    const row = document.getElementById(`mcp-installed-${sid}`);
    if (!row) {
      bindingStatus.textContent = `[binding] installed row not found: ${sid}`;
      return;
    }
    row.scrollIntoView({ behavior: "smooth", block: "center" });
    const oldBg = row.style.backgroundColor;
    row.style.backgroundColor = "rgba(255, 215, 0, 0.22)";
    setTimeout(() => {
      row.style.backgroundColor = oldBg || "";
    }, 1800);
  };
  const renderBindingReverse = () => {
    bindingReverseTotalHolder.value = bindingServers.length;
    const start = (bindingReversePageRef.value - 1) * PLUGINS_PAGE_SIZE;
    const slice = bindingServers.slice(start, start + PLUGINS_PAGE_SIZE);
    const rows = slice.map((srv) => {
      const sid = String(srv.server_id || "");
      const specialists = allSpecialistIds().filter((sp) => {
        const mapped = Array.isArray(bindingDraft[sp]) ? bindingDraft[sp].map((x) => String(x)) : [];
        return mapped.includes(sid);
      });
      const locateBtn = el("button", {
        class: "btn btn--small",
        text: "Locate",
        onclick: () => flashInstalledRow(sid),
      });
      return el("tr", {}, [
        tdCell(sid, 38),
        tdCell(specialists.length ? specialists.join(", ") : "-", 62),
        el("td", {}, [locateBtn]),
      ]);
    });
    bindingReverseTableMount.innerHTML = "";
    bindingReverseTableMount.appendChild(
      el("div", { class: "table-wrap" }, [
        el("table", { class: "table table--compact" }, [
          el("thead", {}, [el("tr", {}, [el("th", { text: "server_id" }), el("th", { text: "bound specialists" }), el("th", { text: "action" })])]),
          el("tbody", {}, rows.length ? rows : [el("tr", {}, [el("td", { text: "-", colspan: "3" })])]),
        ]),
      ]),
    );
    bindingReversePagerMount.innerHTML = "";
    const brBar = pluginsPagerBar(bindingReverseTotalHolder, bindingReversePageRef, renderBindingReverse);
    bindingReversePagerMount.appendChild(brBar.wrap);
    repaintExpertBindingDashboard();
  };
  const renderBindingList = () => {
    const current = String(specialistSelect.value || "");
    const existing = Array.isArray(bindingDraft[current]) ? bindingDraft[current].map((x) => String(x)) : [];
    const selected = new Set(existing);
    bindingListTotalHolder.value = bindingServers.length;
    const start = (bindingListPageRef.value - 1) * PLUGINS_PAGE_SIZE;
    const slice = bindingServers.slice(start, start + PLUGINS_PAGE_SIZE);
    bindingListRowsMount.innerHTML = "";
    if (!bindingServers.length) {
      bindingListRowsMount.appendChild(el("div", { class: "muted", text: "No MCP servers installed yet." }));
      bindingListPagerMount.innerHTML = "";
      const blBar0 = pluginsPagerBar(bindingListTotalHolder, bindingListPageRef, renderBindingList);
      bindingListPagerMount.appendChild(blBar0.wrap);
      repaintExpertBindingDashboard();
      return;
    }
    slice.forEach((srv) => {
      const sid = String(srv.server_id || "");
      const cb = el("input", { type: "checkbox" });
      cb.checked = selected.has(sid);
      cb.addEventListener("change", () => {
        const prev = new Set(Array.isArray(bindingDraft[current]) ? bindingDraft[current].map((x) => String(x)) : []);
        if (cb.checked) prev.add(sid);
        else prev.delete(sid);
        bindingDraft[current] = Array.from(prev);
        renderBindingReverse();
      });
      const label = `${sid}${srv.enabled ? "" : " (disabled)"}`;
      bindingListRowsMount.appendChild(el("label", { class: "row" }, [cb, el("span", { text: label })]));
    });
    bindingListPagerMount.innerHTML = "";
    const blBar = pluginsPagerBar(bindingListTotalHolder, bindingListPageRef, renderBindingList);
    bindingListPagerMount.appendChild(blBar.wrap);
    repaintExpertBindingDashboard();
  };
  specialistSelect.addEventListener("change", () => {
    bindingListPageRef.value = 1;
    bindingReversePageRef.value = 1;
    renderBindingList();
    renderBindingReverse();
  });
  const selectAllBindingBtn = el("button", {
    class: "btn",
    text: "Select All",
    onclick: () => {
      const current = String(specialistSelect.value || "");
      bindingDraft[current] = bindingServers.map((x) => String(x.server_id || "")).filter((x) => x);
      renderBindingList();
      renderBindingReverse();
    },
  });
  const clearBindingBtn = el("button", {
    class: "btn",
    text: "Clear",
    onclick: () => {
      const current = String(specialistSelect.value || "");
      bindingDraft[current] = [];
      renderBindingList();
      renderBindingReverse();
    },
  });
  const saveBindingBtn = el("button", {
    class: "btn",
    text: "Save Binding",
    onclick: async () => {
      const r = await apiPost("/admin/api/mcp/binding", { mapping: bindingDraft });
      bindingStatus.textContent = `[binding] ` + JSON.stringify(r);
      markPrewarmReminder("mcp_binding_changed");
      router();
    },
  });
  renderBindingList();
  renderBindingReverse();
  const jsonInstallInput = el("textarea", {
    class: "input",
    placeholder:
      "Paste install JSON: one object, array of objects, { servers:[...] }, { payload:{...} }, or Cursor-style { mcpServers:{...} }",
    rows: "6",
  });
  const cliInstallInput = el("input", {
    class: "input",
    placeholder: "CLI one-liner, e.g. npx -y mcp-fetch-server | pip install mcp-server-time | pip install git+https://... && python -m <module>",
  });
  const _parseCliInstall = (raw) => {
    const s = String(raw || "").trim();
    if (!s) return { ok: false, error: "empty_command" };
    // Support "A && B" one-liners (we only parse safe shapes; never shell-eval).
    const segs = s.split(/\s*&&\s*/).map((x) => String(x || "").trim()).filter(Boolean);
    const s0 = String(segs[0] || "").trim();
    const s1 = String(segs[1] || "").trim();
    // normalize spaces for simple token parse (no shell eval).
    const parts = s0.split(/\s+/).filter(Boolean);
    const low0 = String(parts[0] || "").toLowerCase();
    const low1 = String(parts[1] || "").toLowerCase();
    const idxPkg = (arr) => arr.findIndex((x) => !String(x || "").startsWith("-"));
    if (low0 === "npx" || (low0 === "npm" && low1 === "exec")) {
      // npx -y <pkg>
      const rest = low0 === "npx" ? parts.slice(1) : parts.slice(2);
      const i = idxPkg(rest);
      const pkg = i >= 0 ? String(rest[i] || "").trim() : "";
      if (!pkg) return { ok: false, error: "npx_package_missing" };
      const tail = i >= 0 ? rest.slice(i + 1).map((x) => String(x || "").trim()).filter(Boolean) : [];
      return {
        ok: true,
        payload: {
          source_type: "npm",
          source_ref: pkg,
          server_id: pkg,
          entry_command: "npx",
          // Keep package tail args (e.g. "run <token>") for MCP CLIs that require subcommands/auth.
          entry_args: ["-y", pkg, ...tail],
        },
      };
    }
    if (low0 === "npm" && low1 === "install") {
      // npm install [-g] <pkg>
      const rest = parts.slice(2);
      const i = idxPkg(rest);
      const pkg = i >= 0 ? String(rest[i] || "").trim() : "";
      if (!pkg) return { ok: false, error: "npm_package_missing" };
      return {
        ok: true,
        payload: {
          source_type: "npm",
          source_ref: pkg,
          server_id: pkg,
          entry_command: "npx",
          entry_args: ["-y", pkg],
        },
      };
    }
    if ((low0 === "pip" && low1 === "install") || (low0 === "python" && low1 === "-m" && String(parts[2] || "").toLowerCase() === "pip")) {
      const rest = low0 === "pip" ? parts.slice(2) : parts.slice(4);
      const i = idxPkg(rest);
      const pkg = i >= 0 ? String(rest[i] || "").trim() : "";
      if (!pkg) return { ok: false, error: "pypi_package_missing" };
      // If pip install uses git+... URL, require explicit entry module via "&& python -m <module>".
      if (pkg.toLowerCase().startsWith("git+")) {
        const p1 = s1.split(/\s+/).filter(Boolean);
        const p10 = String(p1[0] || "").toLowerCase();
        const p11 = String(p1[1] || "").toLowerCase();
        const mod = (p10 === "python" && p11 === "-m") ? String(p1[2] || "").trim() : "";
        if (!mod) return { ok: false, error: "git_pip_requires_python_m" };
        const repoName = pkg.replace(/^git\+/i, "").split(/[?#]/)[0].split("/").filter(Boolean).pop() || "mcp-server";
        const sid = String(repoName).replace(/\.git$/i, "");
        return {
          ok: true,
          payload: {
            source_type: "pypi",
            source_ref: pkg,
            server_id: sid,
            entry_command: "python",
            entry_args: ["-m", mod],
          },
        };
      }
      return {
        ok: true,
        payload: {
          source_type: "pypi",
          source_ref: pkg,
          server_id: pkg,
          entry_command: "python",
          entry_args: ["-m", pkg.replace(/-/g, "_")],
        },
      };
    }
    return { ok: false, error: "unsupported_cli_command" };
  };
  const installBtn = el("button", {
    class: "btn btn--primary",
    text: "Install MCP",
    onclick: async () => {
      const payload = {
        source_type: sourceType.value,
        source_ref: sourceRef.value.trim(),
        version: version.value.trim(),
        entry_command: entryCmd.value.trim(),
        entry_args: entryArgs.value.trim() ? entryArgs.value.trim().split(/\s+/) : [],
      };
      const pre = await apiPost("/admin/api/mcp/preflight", payload);
      if (!pre.ok) {
        installStatus.textContent = `[preflight] ${String(pre.error_code || "")} ${String(pre.error || "")}`.trim();
        const fixes = Array.isArray(pre.fix_suggestions) ? pre.fix_suggestions : [];
        preflightFixWrap.innerHTML = "";
        if (fixes.length) {
          const rows = fixes.map((f) => {
            const cmd = String((f && f.command) || "");
            const copyBtn = el("button", {
              class: "btn",
              text: "Copy",
              onclick: async () => {
                try {
                  await navigator.clipboard.writeText(cmd);
                  installStatus.textContent = `[copied] ${cmd}`;
                } catch (_) {
                  installStatus.textContent = `[copy_failed] ${cmd}`;
                }
              },
            });
            return el("tr", {}, [
              tdCell(String((f && f.title) || ""), 24),
              tdCell(cmd, 72),
              el("td", {}, [copyBtn]),
            ]);
          });
          preflightFixWrap.appendChild(el("div", { class: "table-wrap" }, [el("table", { class: "table table--compact" }, [
            el("thead", {}, [el("tr", {}, [el("th", { text: "fix" }), el("th", { text: "command/url" }), el("th", { text: "action" })])]),
            el("tbody", {}, rows),
          ])]));
        }
        return;
      }
      preflightFixWrap.innerHTML = "";
      const warns = Array.isArray(pre.warnings) ? pre.warnings : [];
      if (warns.length) {
        installStatus.textContent = `[preflight warnings] ${warns.join(", ")}`;
      }
      const res = await apiPost("/admin/api/mcp/install", payload);
      installStatus.textContent = JSON.stringify(res);
      markPrewarmReminder("mcp_installed");
      router();
    },
  });
  const jsonInstallBtn = el("button", {
    class: "btn",
    text: "Install from JSON",
    onclick: async () => {
      preflightFixWrap.innerHTML = "";
      const raw = String(jsonInstallInput.value || "").trim();
      if (!raw) {
        installStatus.textContent = "[json] empty payload";
        return;
      }
      let parsed;
      try {
        parsed = JSON.parse(raw);
      } catch (err) {
        installStatus.textContent = `[json] invalid JSON: ${String((err && err.message) || err || "parse_failed")}`;
        return;
      }
      let list;
      let detectedMcpServersShape = false;
      if (Array.isArray(parsed)) {
        list = parsed;
      } else if (parsed && typeof parsed === "object" && Array.isArray(parsed.servers)) {
        list = parsed.servers;
      } else if (parsed && typeof parsed === "object" && parsed.mcpServers && typeof parsed.mcpServers === "object") {
        detectedMcpServersShape = true;
        installStatus.textContent =
          "[json] detected mcpServers shape; streamableHttp/sse entries will be installed via mcp-remote bridge";
        const envVarRe = /\$\{([A-Za-z_][A-Za-z0-9_]*)\}/g;
        list = Object.entries(parsed.mcpServers).map(([rawKey, rawServer]) => {
          const key = String(rawKey || "").trim();
          const s = rawServer && typeof rawServer === "object" ? rawServer : {};
          const transport = String(s.type || "").trim().toLowerCase();
          const baseUrl = String(s.baseUrl || s.url || "").trim();
          const headers = s.headers && typeof s.headers === "object" ? s.headers : {};

          // Build env schema from ${ENV_VAR} placeholders in headers.
          const envSchema = {};
          Object.entries(headers).forEach(([hk, hv]) => {
            const v = String(hv || "");
            let m;
            while ((m = envVarRe.exec(v)) !== null) {
              const envName = String(m[1] || "").trim();
              if (!envName) continue;
              envSchema[envName] = {
                required: true,
                description: `Auto-detected from header ${String(hk || "").trim()}`,
              };
            }
          });

          // Convert remote MCP (streamable HTTP / SSE) to stdio bridge via mcp-remote.
          // Equivalent runtime command: npx -y mcp-remote <baseUrl> --header "K: V" ...
          //
          // Note: mcp-remote uses transport strategy "http-first" and may fall back to "sse-only"
          // automatically, so both shapes can share the same bridge command.
          if (
            transport === "streamablehttp" ||
            transport === "streamable_http" ||
            transport === "streamable-http" ||
            transport === "sse"
          ) {
            const entryArgs = ["-y", "mcp-remote"];
            if (baseUrl) entryArgs.push(baseUrl);
            Object.entries(headers).forEach(([hk, hv]) => {
              const hn = String(hk || "").trim();
              const hvs = String(hv || "").trim();
              if (!hn || !hvs) return;
              entryArgs.push("--header", `${hn}: ${hvs}`);
            });
            return {
              source_type: "npm",
              source_ref: "mcp-remote",
              server_id: key || String(s.name || "mcp-remote").trim() || "mcp-remote",
              entry_command: "npx",
              entry_args: entryArgs,
              env_schema: envSchema,
              required_permissions: Array.isArray(s.required_permissions) ? s.required_permissions.map((x) => String(x)) : [],
              risk_level: String(s.risk_level || "high"),
              enabled: Object.prototype.hasOwnProperty.call(s, "isActive") ? !!s.isActive : true,
              timeout_s: Number(s.timeout_s || 30),
              dry_run: false,
            };
          }

          // Best-effort passthrough for stdio-like definitions.
          const cmd = String(s.command || s.entry_command || "").trim();
          const cmdArgs = Array.isArray(s.args) ? s.args.map((x) => String(x)) : [];
          return {
            source_type: String(s.source_type || "npm").trim() || "npm",
            source_ref: String(s.source_ref || "mcp-remote").trim() || "mcp-remote",
            server_id: key || String(s.name || s.server_id || "mcp-server").trim() || "mcp-server",
            entry_command: cmd,
            entry_args: cmdArgs,
            env_schema: Object.keys(envSchema).length ? envSchema : (s.env_schema && typeof s.env_schema === "object" ? s.env_schema : {}),
            required_permissions: Array.isArray(s.required_permissions) ? s.required_permissions.map((x) => String(x)) : [],
            risk_level: String(s.risk_level || "high"),
            enabled: Object.prototype.hasOwnProperty.call(s, "isActive") ? !!s.isActive : true,
            timeout_s: Number(s.timeout_s || 30),
            dry_run: false,
          };
        });
      } else if (parsed && typeof parsed === "object" && parsed.payload && typeof parsed.payload === "object") {
        list = [parsed.payload];
      } else {
        list = [parsed];
      }
      const results = [];
      for (const item of list) {
        if (!item || typeof item !== "object") {
          results.push({ ok: false, error: "item_not_object" });
          continue;
        }
        const payload = {
          source_type: String(item.source_type || "").trim(),
          source_ref: String(item.source_ref || "").trim(),
          server_id: String(item.server_id || "").trim(),
          version: String(item.version || "").trim(),
          entry_command: String(item.entry_command || "").trim(),
          entry_args: Array.isArray(item.entry_args) ? item.entry_args.map((x) => String(x)) : [],
          env_schema: item.env_schema && typeof item.env_schema === "object" ? item.env_schema : {},
          required_permissions: Array.isArray(item.required_permissions)
            ? item.required_permissions.map((x) => String(x))
            : [],
          risk_level: String(item.risk_level || "high"),
          enabled: Object.prototype.hasOwnProperty.call(item, "enabled") ? !!item.enabled : true,
          timeout_s: Number(item.timeout_s || 30),
          dry_run: !!item.dry_run,
        };
        const pre = await apiPost("/admin/api/mcp/preflight", payload);
        if (!pre.ok) {
          results.push({
            ok: false,
            server_id: payload.server_id || payload.source_ref || "-",
            phase: "preflight",
            error_code: pre.error_code || "",
            error: pre.error || "preflight_failed",
          });
          continue;
        }
        const res = await apiPost("/admin/api/mcp/install", payload);
        results.push({
          ok: !!res.ok,
          server_id: res.server_id || payload.server_id || payload.source_ref || "-",
          phase: "install",
          error_code: res.error_code || "",
          error: res.error || "",
        });
      }
      installStatus.textContent = JSON.stringify(results);
      if (detectedMcpServersShape) {
        installStatus.textContent =
          "[json] mcpServers import finished (using mcp-remote bridge where needed)\n" + installStatus.textContent;
      }
      markPrewarmReminder("mcp_batch_installed");
      router();
    },
  });
  const cliInstallModal = el("div", { class: "session-monitor-modal", style: "display:none;" });
  const cliInstallModalTitle = el("div", { class: "card__title", text: "MCP CLI install" });
  const cliInstallModalBody = el("pre", { class: "pre", text: "" });
  const closeCliInstallModal = () => {
    cliInstallModal.style.display = "none";
  };
  const openCliInstallModal = (title, text) => {
    cliInstallModalTitle.textContent = String(title || "MCP CLI install");
    cliInstallModalBody.textContent = String(text || "");
    cliInstallModal.style.display = "flex";
  };
  const setCliInstallModal = (title, text) => {
    if (title) cliInstallModalTitle.textContent = String(title);
    if (text != null) cliInstallModalBody.textContent = String(text);
  };
  cliInstallModal.addEventListener("click", (e) => {
    if (e.target === cliInstallModal) closeCliInstallModal();
  });
  cliInstallModal.appendChild(
    el("div", { class: "card session-monitor-modal__card", style: "width:min(720px,96vw);" }, [
      cliInstallModalTitle,
      cliInstallModalBody,
      el("div", { class: "row", style: "justify-content:flex-end;margin-top:10px;" }, [
        el("button", { class: "btn", text: "Close", onclick: closeCliInstallModal }),
      ]),
    ]),
  );
  const cliInstallBtn = el("button", {
    class: "btn",
    text: "Install from CLI",
    onclick: async () => {
      preflightFixWrap.innerHTML = "";
      openCliInstallModal("MCP CLI install", "Parsing command...");
      const parsed = _parseCliInstall(cliInstallInput.value);
      if (!parsed.ok) {
        installStatus.textContent = `[cli] ${String(parsed.error || "parse_failed")}`;
        setCliInstallModal("MCP CLI install failed", installStatus.textContent);
        return;
      }
      const payload = {
        source_type: String(parsed.payload.source_type || "").trim(),
        source_ref: String(parsed.payload.source_ref || "").trim(),
        server_id: String(parsed.payload.server_id || "").trim(),
        entry_command: String(parsed.payload.entry_command || "").trim(),
        entry_args: Array.isArray(parsed.payload.entry_args) ? parsed.payload.entry_args.map((x) => String(x)) : [],
        version: "",
      };
      setCliInstallModal("MCP CLI install", "Running preflight...");
      const pre = await apiPost("/admin/api/mcp/preflight", payload);
      if (!pre.ok) {
        installStatus.textContent = `[cli/preflight] ${String(pre.error_code || "")} ${String(pre.error || "")}`.trim();
        setCliInstallModal("MCP CLI preflight failed", installStatus.textContent);
        return;
      }
      setCliInstallModal("MCP CLI install", "Installing...");
      const res = await apiPost("/admin/api/mcp/install", payload);
      installStatus.textContent = `[cli] ` + JSON.stringify(res);
      if (res && res.ok) {
        setCliInstallModal("MCP CLI install success", installStatus.textContent);
        markPrewarmReminder("mcp_installed");
        router();
      } else {
        setCliInstallModal("MCP CLI install failed", installStatus.textContent);
      }
    },
  });
  const mcpServerList = Array.isArray(mcp.servers) ? mcp.servers : [];
  const expertBindingDashTbody = el("tbody");
  repaintExpertBindingDashboard = () => {
    expertBindingDashTbody.innerHTML = "";
    const ids = allSpecialistIds();
    if (!ids.length) {
      expertBindingDashTbody.appendChild(el("tr", {}, [el("td", { class: "muted", text: "—", colspan: "3" })]));
      return;
    }
    ids.forEach((sp) => {
      const sids = new Set((bindingDraft[sp] || []).map(String).filter(Boolean));
      let toolCnt = 0;
      mcpServerList.forEach((row) => {
        const rsid = String(row.server_id || "");
        if (!sids.has(rsid)) return;
        const tools = Array.isArray(row.tools) ? row.tools : [];
        toolCnt += tools.length;
      });
      expertBindingDashTbody.appendChild(el("tr", {}, [
        tdCell(sp, 28),
        tdCell(String(sids.size), 10),
        tdCell(String(toolCnt), 12),
      ]));
    });
  };
  repaintExpertBindingDashboard();
  const mcpInstalledPageRef = { value: 1 };
  const mcpInstalledTotalHolder = { value: mcpServerList.length };
  const mcpInstalledTbody = el("tbody");
  const buildMcpInstalledRow = (x) => {
    const sid = String(x.server_id || "");
    const toggleBtn = el("button", {
      class: "btn",
      text: x.enabled ? "Disable" : "Enable",
      onclick: async () => {
        closeMcpActionMenu();
        await apiPost("/admin/api/mcp/toggle", { server_id: sid, enabled: !x.enabled });
        markPrewarmReminder("mcp_toggled");
        router();
      },
    });
    const healthBtn = el("button", {
      class: "btn",
      text: "Health",
      onclick: async () => {
        closeMcpActionMenu();
        const r = await apiPost("/admin/api/mcp/healthcheck", { server_id: sid });
        installStatus.textContent = `[health:${sid}] ` + JSON.stringify(r);
        router();
      },
    });
    const syncBtn = el("button", {
      class: "btn",
      text: "Sync Tools",
      onclick: async () => {
        closeMcpActionMenu();
        const r = await apiPost("/admin/api/mcp/tools/sync", { server_id: sid });
        installStatus.textContent = `[sync:${sid}] ` + JSON.stringify(r);
        router();
      },
    });
    const reinstallBtn = el("button", {
      class: "chat-sess-menu-item",
      text: "Reinstall",
      onclick: async () => {
        closeMcpActionMenu();
        const r = await apiPost("/admin/api/mcp/reinstall", { server_id: sid });
        installStatus.textContent = `[reinstall:${sid}] ` + JSON.stringify(r);
        markPrewarmReminder("mcp_reinstalled");
        router();
      },
    });
    const updateBtn = el("button", {
      class: "chat-sess-menu-item",
      text: "Update",
      onclick: async () => {
        closeMcpActionMenu();
        const r = await apiPost("/admin/api/mcp/update", {
          server_id: sid,
          update_to_latest: true,
          sync_tools: true,
        });
        installStatus.textContent = `[update:${sid}] ` + JSON.stringify(r);
        markPrewarmReminder("mcp_updated");
        router();
      },
    });
    const uninstallBtn = el("button", {
      class: "chat-sess-menu-item",
      text: "Uninstall",
      onclick: async () => {
        closeMcpActionMenu();
        if (!window.confirm(`Uninstall ${sid} and remove from MCP registry?`)) return;
        const r = await apiPost("/admin/api/mcp/uninstall", { server_id: sid, remove_record: true });
        installStatus.textContent = `[uninstall:${sid}] ` + JSON.stringify(r);
        markPrewarmReminder("mcp_uninstalled");
        router();
      },
    });
    const deleteBtn = el("button", {
      class: "chat-sess-menu-item",
      text: "Delete",
      onclick: async () => {
        closeMcpActionMenu();
        if (!window.confirm(`Delete ${sid} from MCP registry only?`)) return;
        const r = await apiPost("/admin/api/mcp/delete", { server_id: sid });
        installStatus.textContent = `[delete:${sid}] ` + JSON.stringify(r);
        markPrewarmReminder("mcp_deleted");
        router();
      },
    });
    toggleBtn.className = "chat-sess-menu-item";
    healthBtn.className = "chat-sess-menu-item";
    syncBtn.className = "chat-sess-menu-item";
    const actionMenuBtn = el("button", {
      class: "chat-sess-more",
      text: "⋯",
      title: "MCP actions",
      onclick: (ev) => {
        ev.stopPropagation();
        closeMcpActionMenu();
        const menu = el("div", { class: "chat-sess-menu-pop", style: "position:fixed;z-index:250;" }, [
          toggleBtn,
          healthBtn,
          syncBtn,
          updateBtn,
          reinstallBtn,
          uninstallBtn,
          deleteBtn,
        ]);
        const rect = ev.currentTarget.getBoundingClientRect();
        document.body.appendChild(menu);
        const mrect = menu.getBoundingClientRect();
        const pad = 8;
        let left = rect.left - 120;
        let top = rect.bottom + 4;
        if (top + mrect.height > window.innerHeight - pad) {
          top = rect.top - 4 - mrect.height;
        }
        left = Math.max(pad, Math.min(left, window.innerWidth - pad - mrect.width));
        top = Math.max(pad, Math.min(top, window.innerHeight - pad - mrect.height));
        menu.style.left = `${left}px`;
        menu.style.top = `${top}px`;
        mcpActionMenuEl = menu;
        const close = (e) => {
          if (!menu.contains(e.target)) {
            closeMcpActionMenu();
            document.removeEventListener("click", close);
          }
        };
        setTimeout(() => document.addEventListener("click", close), 0);
      },
    });
    const tools = Array.isArray(x.tools) ? x.tools.map((t) => String(t.tool_name || "")).join(", ") : "";
    const upd = (mcpUpdateState.byServer && mcpUpdateState.byServer[sid]) || null;
    const updText = upd
      ? (upd.check_error
        ? `err:${String(upd.check_error || "").slice(0, 80)}`
        : (upd.has_update
          ? `update ${String(upd.current_version || "-")} -> ${String(upd.latest_version || "-")}`
          : "up-to-date"))
      : "-";
    const healthObj = x.health && typeof x.health === "object" ? x.health : {};
    const healthStatus = String(healthObj.status || "-");
    const healthDetail = healthObj.detail && typeof healthObj.detail === "object" ? healthObj.detail : {};
    const healthErrCode = String(healthDetail.error_code || "");
    const healthErrMsg = String(healthDetail.error || "");
    const healthText = healthErrCode ? `${healthStatus}:${healthErrCode}` : healthStatus;
    const healthTitle = healthErrCode || healthErrMsg
      ? `${healthErrCode || "error"} ${healthErrMsg}`.trim()
      : (healthDetail.synced_tools != null ? `synced_tools=${Number(healthDetail.synced_tools || 0)}` : healthStatus);
    return el("tr", { id: `mcp-installed-${sid}` }, [
      tdCell(sid, 28),
      tdCell(String(x.source_type || ""), 10),
      tdCell(String(x.source_ref || ""), 42),
      tdCell(String(x.version || ""), 16),
      tdCell(String(x.entry_command || ""), 24),
      tdCell(tools || "-", 48),
      tdCell(updText, 28),
      tdCell(String(x.enabled ? 1 : 0), 8),
      el("td", { text: healthText, title: healthTitle }),
      el("td", { class: "table__cell-actions" }, [actionMenuBtn]),
    ]);
  };
  const repaintMcpInstalled = () => {
    mcpInstalledTbody.innerHTML = "";
    const start = (mcpInstalledPageRef.value - 1) * PLUGINS_PAGE_SIZE;
    mcpServerList.slice(start, start + PLUGINS_PAGE_SIZE).forEach((x) => {
      mcpInstalledTbody.appendChild(buildMcpInstalledRow(x));
    });
  };
  repaintMcpInstalled();
  const mcpInstalledPager = pluginsPagerBar(mcpInstalledTotalHolder, mcpInstalledPageRef, repaintMcpInstalled);
  const renderMarket = async () => {
    const q = marketQ.value.trim();
    if (!q) {
      marketTableMount.innerHTML = "";
      marketPagerMount.innerHTML = "";
      marketSearchItems = [];
      marketSearchTotalHolder.value = 0;
      return;
    }
    const resp = await apiGet("/admin/api/mcp/market/search?q=" + encodeURIComponent(q) + "&per_source_limit=60");
    marketSearchItems = Array.isArray(resp.items) ? resp.items : [];
    marketSearchTotalHolder.value = marketSearchItems.length;
    marketSearchPageRef.value = 1;
    const paintMarket = () => {
      const start = (marketSearchPageRef.value - 1) * PLUGINS_PAGE_SIZE;
      const pageItems = marketSearchItems.slice(start, start + PLUGINS_PAGE_SIZE);
      const bodyRows = pageItems.map((it) => {
        const useBtn = el("button", {
          class: "btn",
          text: "Use",
          onclick: () => {
            sourceType.value = String(it.source_type || "github");
            sourceRef.value = String(it.source_ref || "");
            version.value = String(it.version || "");
            const tpl = (it && typeof it.install_template === "object") ? it.install_template : {};
            entryCmd.value = String(tpl.entry_command || entryCmd.value || "");
            const args = Array.isArray(tpl.entry_args) ? tpl.entry_args.map((x) => String(x)).join(" ") : "";
            if (args) entryArgs.value = args;
          },
        });
        return el("tr", {}, [
          tdCell(String(it.source_type || ""), 10),
          tdCell(String(it.name || ""), 24),
          tdCell(String(it.description || ""), 60),
          tdCell(String(it.source_ref || ""), 40),
          tdCell(String(it.version || ""), 12),
          el("td", {}, [useBtn]),
        ]);
      });
      marketTableMount.innerHTML = "";
      marketTableMount.appendChild(el("div", { class: "table-wrap" }, [el("table", { class: "table table--compact" }, [
        el("thead", {}, [el("tr", {}, [
          el("th", { text: "source" }),
          el("th", { text: "name" }),
          el("th", { text: "description" }),
          el("th", { text: "ref" }),
          el("th", { text: "version" }),
          el("th", { text: "action" }),
        ])]),
        el("tbody", {}, bodyRows.length ? bodyRows : [el("tr", {}, [el("td", { text: "-", colspan: "6" })])]),
      ])]));
    };
    paintMarket();
    marketPagerMount.innerHTML = "";
    const mkBar = pluginsPagerBar(marketSearchTotalHolder, marketSearchPageRef, paintMarket);
    marketPagerMount.appendChild(mkBar.wrap);
  };
  marketBtn.addEventListener("click", renderMarket);
  const renderTrending = async () => {
    trendingItemsCache = Array.isArray(marketTrending.items) ? marketTrending.items : [];
    trendingTotalHolder.value = trendingItemsCache.length;
    trendingPageRef.value = 1;
    const paintTrending = () => {
      const start = (trendingPageRef.value - 1) * PLUGINS_PAGE_SIZE;
      const pageItems = trendingItemsCache.slice(start, start + PLUGINS_PAGE_SIZE);
      const row = pageItems.map((x) => {
        const useBtn = el("button", {
          class: "btn",
          text: "Use",
          onclick: () => {
            sourceType.value = String(x.source_type || "github");
            sourceRef.value = String(x.source_ref || "");
            version.value = String(x.version || "");
            const tpl = (x && typeof x.install_template === "object") ? x.install_template : {};
            entryCmd.value = String(tpl.entry_command || entryCmd.value || "");
            const args = Array.isArray(tpl.entry_args) ? tpl.entry_args.map((k) => String(k)).join(" ") : "";
            if (args) entryArgs.value = args;
          },
        });
        return el("tr", {}, [
          tdCell(String(x.source_type || ""), 10),
          tdCell(String(x.name || ""), 26),
          tdCell(String(x.description || ""), 70),
          tdCell(String(x.stars || 0), 8),
          el("td", {}, [useBtn]),
        ]);
      });
      trendingTableMount.innerHTML = "";
      trendingTableMount.appendChild(el("div", { class: "table-wrap" }, [el("table", { class: "table table--compact" }, [
        el("thead", {}, [el("tr", {}, [el("th", { text: "source" }), el("th", { text: "name" }), el("th", { text: "description" }), el("th", { text: "stars" }), el("th", { text: "action" })])]),
        el("tbody", {}, row.length ? row : [el("tr", {}, [el("td", { text: "-", colspan: "5" })])]),
      ])]));
    };
    paintTrending();
    trendingPagerMount.innerHTML = "";
    const trBar = pluginsPagerBar(trendingTotalHolder, trendingPageRef, paintTrending);
    trendingPagerMount.appendChild(trBar.wrap);
  };
  const renderDeps = () => {
    depTotalHolder.value = depItemsList.length;
    const paintDeps = () => {
      const start = (depPageRef.value - 1) * PLUGINS_PAGE_SIZE;
      const slice = depItemsList.slice(start, start + PLUGINS_PAGE_SIZE);
      const rows = slice.map((x) =>
        el("tr", {}, [
          tdCell(String(x.name || ""), 12),
          tdCell(String(x.ok ? "ok" : "missing"), 12),
          tdCell(String(x.version || ""), 28),
          tdCell(String(x.path || ""), 50),
        ]),
      );
      depTableMount.innerHTML = "";
      depTableMount.appendChild(el("div", { class: "table-wrap" }, [el("table", { class: "table table--compact" }, [
        el("thead", {}, [el("tr", {}, [el("th", { text: "dep" }), el("th", { text: "status" }), el("th", { text: "version" }), el("th", { text: "path" })])]),
        el("tbody", {}, rows.length ? rows : [el("tr", {}, [el("td", { text: "-", colspan: "4" })])]),
      ])]));
    };
    paintDeps();
    depPagerMount.innerHTML = "";
    const depBar = pluginsPagerBar(depTotalHolder, depPageRef, paintDeps);
    depPagerMount.appendChild(depBar.wrap);
  };
  marketRefreshBtn.addEventListener("click", async () => {
    marketTrending = await apiGet("/admin/api/mcp/market/trending?per_source_limit=4&refresh=1");
    await renderTrending();
  });
  renderTrending();
  renderDeps();
  const failureText = Array.isArray(mcpFailures.items)
    ? mcpFailures.items.map((x) => `${x.server_id}/${x.error_code || "-"}:${x.count}`).join(" | ")
    : "";
  const usageSummaryList = Array.isArray(mcpUsage.summary) ? mcpUsage.summary : [];
  const usageCallsList = Array.isArray(mcpUsage.calls) ? mcpUsage.calls : [];
  const usageSummaryPageRef = { value: 1 };
  const usageSummaryTotalHolder = { value: usageSummaryList.length };
  const usageSummaryTbody = el("tbody");
  const usageCallsPageRef = { value: 1 };
  const usageCallsTotalHolder = { value: usageCallsList.length };
  const usageCallsTbody = el("tbody");
  const buildUsageSummaryRow = (x) =>
    el("tr", {}, [
      tdCell(String(x.server_id || ""), 24),
      tdCell(String(x.mcp_tool_name || x.tool_name || ""), 30),
      tdCell(String(x.specialist || "-"), 16),
      tdCell(String(x.count || 0), 10),
      tdCell(String(x.last_ts || ""), 24),
    ]);
  const buildUsageCallRow = (x) =>
    el("tr", {}, [
      tdCell(String(x.timestamp || ""), 22),
      tdCell(String(x.server_id || ""), 18),
      tdCell(String(x.mcp_tool_name || x.tool_name || ""), 22),
      tdCell(String(x.specialist || "-"), 14),
      tdCell(String(x.session_id || ""), 22),
      tdCell(String(x.duration_ms || 0), 10),
    ]);
  const repaintUsageSummary = () => {
    usageSummaryTbody.innerHTML = "";
    const start = (usageSummaryPageRef.value - 1) * PLUGINS_PAGE_SIZE;
    usageSummaryList.slice(start, start + PLUGINS_PAGE_SIZE).forEach((x) => {
      usageSummaryTbody.appendChild(buildUsageSummaryRow(x));
    });
  };
  const repaintUsageCalls = () => {
    usageCallsTbody.innerHTML = "";
    const start = (usageCallsPageRef.value - 1) * PLUGINS_PAGE_SIZE;
    usageCallsList.slice(start, start + PLUGINS_PAGE_SIZE).forEach((x) => {
      usageCallsTbody.appendChild(buildUsageCallRow(x));
    });
  };
  repaintUsageSummary();
  repaintUsageCalls();
  const usageSummaryPager = pluginsPagerBar(usageSummaryTotalHolder, usageSummaryPageRef, repaintUsageSummary);
  const usageCallsPager = pluginsPagerBar(usageCallsTotalHolder, usageCallsPageRef, repaintUsageCalls);
  let toolWire = { tools: [], config: {}, policies: {}, penalty_state: {}, role: "" };
  try {
    toolWire = await apiGet("/admin/api/mcp/tool-wire");
  } catch (_) {}
  const twc = toolWire.config || {};
  const wireTools = Array.isArray(toolWire.tools) ? toolWire.tools : [];
  const wireRoleMode = String(toolWire.role_mode || "restricted");
  const wireRoleSelect = el("select", { class: "input" }, [
    el("option", { value: "", text: "global（默认）" }),
    el("option", { value: "manager", text: "manager（全能者）" }),
    ...availableSpecialists
      .filter((x) => String(x) !== "manager")
      .map((sp) => el("option", { value: String(sp), text: String(sp) })),
  ]);
  wireRoleSelect.value = String(toolWire.role || "");
  const wireCfgStatus = el("div", { class: "muted", text: "" });
  const wirePolStatus = el("div", { class: "muted", text: "" });
  const wireRoleModeSelect = el("select", { class: "input" }, [
    el("option", { value: "restricted", text: "受限（启用惩罚机制）" }),
    el("option", { value: "unrestricted", text: "不受限（惩罚无效）" }),
    el("option", { value: "forbidden", text: "禁止（MCP 全禁）" }),
  ]);
  wireRoleModeSelect.value = wireRoleMode;
  const saveWireRoleModeBtn = el("button", {
    class: "btn",
    text: "保存 role 模式",
    onclick: async () => {
      const role = String(wireRoleSelect.value || "").trim();
      if (!role) {
        wireCfgStatus.textContent = "[role-mode] 请选择具体 role（非 global）";
        return;
      }
      const r = await apiPost("/admin/api/mcp/tool-wire/role-mode", {
        role,
        mode: String(wireRoleModeSelect.value || "restricted"),
      });
      wireCfgStatus.textContent = `[role-mode] ` + JSON.stringify(r);
      markPrewarmReminder("tool_wire_role_mode_changed");
      router();
    },
  });
  const applyWireRoleSelectorState = () => {
    const isGlobal = !String(wireRoleSelect.value || "").trim();
    saveWireRoleModeBtn.disabled = isGlobal;
    wireRoleModeSelect.disabled = isGlobal;
    if (isGlobal) {
      wireCfgStatus.textContent = "[role-mode] global 不支持 role 模式设置，请选择具体 role。";
    }
  };
  const inpWirePolicy = el("select", { class: "input" }, [
    el("option", { value: "inherit", text: "inherit（随 URL；DashScope 默认开）" }),
    el("option", { value: "always", text: "always（不按 URL，始终启用分层）" }),
    el("option", { value: "never", text: "never（关分层；9999 仍过滤）" }),
  ]);
  inpWirePolicy.value = String(twc.wire_policy || "inherit");
  const inpTopN = el("input", { class: "input", type: "number", min: "3", max: "80", value: String(twc.top_n_full ?? 20) });
  const inpStaleH = el("input", { class: "input", type: "number", step: "0.25", value: String(twc.stale_hours ?? 3) });
  const inpPenMin = el("input", { class: "input", type: "number", value: String(twc.penalty_minutes ?? 30) });
  const inpMedS = el("input", { class: "input", type: "number", value: String(twc.medium_rank_start ?? 21) });
  const inpMedE = el("input", { class: "input", type: "number", value: String(twc.medium_rank_end ?? 50) });
  const inpMedDesc = el("input", { class: "input", type: "number", value: String(twc.medium_desc_chars ?? 520) });
  const inpMinCap = el("input", { class: "input", type: "number", value: String(twc.minimal_desc_cap ?? 80) });
  const inpPenaltyEnabled = el("input", { type: "checkbox" });
  inpPenaltyEnabled.checked = !Boolean(twc.penalty_disable);
  const saveWireCfgBtn = el("button", {
    class: "btn",
    text: "保存全局参数",
    onclick: async () => {
      const r = await apiPost("/admin/api/mcp/tool-wire/config", {
        wire_policy: inpWirePolicy.value,
        top_n_full: Number(inpTopN.value),
        stale_hours: Number(inpStaleH.value),
        penalty_minutes: Number(inpPenMin.value),
        medium_rank_start: Number(inpMedS.value),
        medium_rank_end: Number(inpMedE.value),
        medium_desc_chars: Number(inpMedDesc.value),
        minimal_desc_cap: Number(inpMinCap.value),
        penalty_disable: !Boolean(inpPenaltyEnabled.checked),
      });
      wireCfgStatus.textContent = JSON.stringify(r);
      markPrewarmReminder("tool_wire_config_changed");
      router();
    },
  });
  const resetPenaltyStateBtn = el("button", {
    class: "btn",
    text: "重置惩罚状态",
    onclick: async () => {
      if (!window.confirm("确认重置当前 MCP 工具惩罚状态？该操作会立即清空 penalty state。")) return;
      const qs = wireRoleSelect.value ? ("?role=" + encodeURIComponent(wireRoleSelect.value)) : "";
      const r = await apiPost("/admin/api/mcp/tool-wire/penalty/reset" + qs, {});
      wireCfgStatus.textContent = JSON.stringify(r);
      markPrewarmReminder("tool_wire_penalty_reset");
      router();
    },
  });
  const draftPolicies = {};
  wireTools.forEach((t) => {
    if (t.policy_in_db) draftPolicies[t.wire_name] = normalizeWirePolicyLevel(t.policy_level);
    else draftPolicies[t.wire_name] = null;
  });
  const wireToolBody = el("tbody");
  const wireToolsPageRef = { value: 1 };
  const wireToolsTotalHolder = { value: wireTools.length };
  const wireCheckedSet = new Set();
  const wireSubMatch = (a, pat) => {
    const p = String(pat || "").trim();
    if (!p) return true;
    return String(a ?? "").toLowerCase().includes(p.toLowerCase());
  };
  const wireFOnlyChecked = el("input", { type: "checkbox", title: "仅显示已勾选行" });
  const wireFServer = el("input", { class: "input", placeholder: "含", style: "width:100%;min-width:64px;box-sizing:border-box;" });
  const wireFTool = el("input", { class: "input", placeholder: "含", style: "width:100%;min-width:64px;box-sizing:border-box;" });
  const wireFWire = el("input", { class: "input", placeholder: "含", style: "width:100%;min-width:64px;box-sizing:border-box;" });
  const wireFExpert = el("input", { class: "input", placeholder: "专家含", style: "width:100%;min-width:64px;box-sizing:border-box;" });
  const wireFCountMin = el("input", { class: "input", type: "number", placeholder: "≥", style: "width:100%;box-sizing:border-box;" });
  const wireFCountMax = el("input", { class: "input", type: "number", placeholder: "≤", style: "width:100%;box-sizing:border-box;" });
  const wireFLastTs = el("input", { class: "input", placeholder: "含", style: "width:100%;min-width:64px;box-sizing:border-box;" });
  const wireFPenalty = el("input", { class: "input", placeholder: "含", style: "width:100%;min-width:64px;box-sizing:border-box;" });
  const wireFLevelMin = el("input", { class: "input", type: "number", placeholder: "等级≥", style: "width:100%;box-sizing:border-box;" });
  const wireFLevelMax = el("input", { class: "input", type: "number", placeholder: "等级≤", style: "width:100%;box-sizing:border-box;" });
  const wireFilterCountLabel = el("span", { class: "muted", text: "" });
  const wireRoleModeHint = el("div", { class: "muted", text: "" });
  const wireRowMatchesFilters = (t) => {
    if (wireFOnlyChecked.checked && !wireCheckedSet.has(t.wire_name)) return false;
    if (!wireSubMatch(t.server_id, wireFServer.value)) return false;
    if (!wireSubMatch(t.mcp_tool_name, wireFTool.value)) return false;
    if (!wireSubMatch(t.wire_name, wireFWire.value)) return false;
    const ex = specialistsBoundToServer(t.server_id).join(", ");
    if (!wireSubMatch(ex, wireFExpert.value)) return false;
    const cnt = Number(t.count || 0);
    if (String(wireFCountMin.value).trim() && cnt < Number(wireFCountMin.value)) return false;
    if (String(wireFCountMax.value).trim() && cnt > Number(wireFCountMax.value)) return false;
    const ph = (t.penalty && t.penalty.unblock_hint) || "";
    if (!wireSubMatch(ph, wireFPenalty.value)) return false;
    if (!wireSubMatch(t.last_ts || "", wireFLastTs.value)) return false;
    const lvRaw = draftPolicies[t.wire_name];
    const lvNum = lvRaw === null || lvRaw === undefined ? null : Number(lvRaw);
    const minS = String(wireFLevelMin.value).trim();
    if (minS) {
      const m = Number(minS);
      if (Number.isFinite(m)) {
        if (lvNum === null || lvNum === undefined) {
          if (m > 0) return false;
        } else if (lvNum < m) return false;
      }
    }
    const maxS = String(wireFLevelMax.value).trim();
    if (maxS && lvNum !== null && lvNum !== undefined) {
      const m = Number(maxS);
      if (Number.isFinite(m) && lvNum > m) return false;
    }
    return true;
  };
  const roleModeBadge = (modeRaw) => {
    const mode = String(modeRaw || "restricted");
    if (mode === "unrestricted") {
      return el("span", { class: "badge badge--ok", text: "unrestricted" });
    }
    if (mode === "forbidden") {
      return el("span", { class: "badge badge--bad", text: "forbidden" });
    }
    return el("span", { class: "badge badge--mode-restricted", text: "restricted" });
  };
  const getWireToolsFiltered = () => wireTools.filter((x) => wireRowMatchesFilters(x));
  const paintWireToolRows = () => {
    wireToolBody.innerHTML = "";
    if (!wireTools.length) {
      wireToolBody.appendChild(el("tr", {}, [el("td", { text: "暂无已缓存工具（对各 MCP 点 Sync Tools）", colspan: "9" })]));
      return;
    }
    const list = getWireToolsFiltered();
    if (!list.length) {
      wireToolBody.appendChild(el("tr", {}, [el("td", { text: "无匹配行（请调整筛选）", colspan: "9" })]));
      return;
    }
    const start = (wireToolsPageRef.value - 1) * PLUGINS_PAGE_SIZE;
    list.slice(start, start + PLUGINS_PAGE_SIZE).forEach((t) => {
      const rowCb = el("input", { type: "checkbox" });
      rowCb.checked = wireCheckedSet.has(t.wire_name);
      rowCb.addEventListener("change", () => {
        if (rowCb.checked) wireCheckedSet.add(t.wire_name);
        else wireCheckedSet.delete(t.wire_name);
      });
      const lv0 = draftPolicies[t.wire_name];
      const lvlSel = el(
        "select",
        {
          class: "input",
          title: "按 role：默认（继承全局惩罚）/ 不惩罚 / 永禁",
          style: "width:140px;max-width:100%;",
          "data-wire-level": "1",
        },
        [
          el("option", { value: "", text: "默认（继承）" }),
          el("option", { value: "0", text: "不惩罚（0）" }),
          el("option", { value: "9999", text: "永禁（9999）" }),
        ],
      );
      lvlSel.value = lv0 === null || lv0 === undefined ? "" : String(normalizeWirePolicyLevel(lv0));
      const syncLevelFromSelect = () => {
        const v = String(lvlSel.value || "").trim();
        if (!v) {
          draftPolicies[t.wire_name] = null;
          lvlSel.value = "";
          return;
        }
        const n = normalizeWirePolicyLevel(v);
        draftPolicies[t.wire_name] = n;
        lvlSel.value = String(n);
      };
      lvlSel.addEventListener("change", syncLevelFromSelect);
      const ph = (t.penalty && t.penalty.unblock_hint) || "-";
      const exCell = specialistsBoundToServer(t.server_id).join(", ") || "—";
      wireToolBody.appendChild(
        el(
          "tr",
          { "data-wire-name": t.wire_name },
          [
            el("td", {}, [rowCb]),
            tdCell(t.server_id, 20),
            tdCell(t.mcp_tool_name, 22),
            tdCell(t.wire_name, 32),
            tdCell(exCell, 20),
            tdCell(String(t.count || 0), 8),
            tdCell(String(t.last_ts || "-"), 22),
            el("td", {}, [roleModeBadge(wireRoleModeSelect.value || "restricted")]),
            el("td", {
              text: ph,
              title: ph,
              style: "max-width:240px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;",
            }),
            el("td", {}, [lvlSel]),
          ],
        ),
      );
    });
  };
  const applyWireRoleModeUiState = () => {
    const mode = String(wireRoleModeSelect.value || "restricted");
    const disabled = mode !== "restricted";
    if (mode === "unrestricted") {
      wireRoleModeHint.textContent = "当前 role 为不受限：单工具惩罚策略不生效。";
    } else if (mode === "forbidden") {
      wireRoleModeHint.textContent = "当前 role 为禁止：MCP 全禁，单工具惩罚策略不生效。";
    } else {
      wireRoleModeHint.textContent = "";
    }
    const staticControls = [
      wireFOnlyChecked,
      wireFServer,
      wireFTool,
      wireFWire,
      wireFExpert,
      wireFCountMin,
      wireFCountMax,
      wireFLastTs,
      wireFPenalty,
      wireFLevelMin,
      wireFLevelMax,
      clearWireFiltersBtn,
      bulkLvlInput,
      applyBulkWireBtn,
      saveWirePolBtn,
    ];
    staticControls.forEach((node) => {
      if (node) node.disabled = disabled;
    });
    Array.from(wireToolBody.querySelectorAll("input,select,button")).forEach((el0) => {
      el0.disabled = disabled;
    });
  };
  const wireToolsPager = pluginsPagerBar(wireToolsTotalHolder, wireToolsPageRef, paintWireToolRows);
  const refreshWireToolsFiltered = () => {
    const list = getWireToolsFiltered();
    wireToolsTotalHolder.value = list.length;
    wireFilterCountLabel.textContent = `筛选 ${list.length} / 共 ${wireTools.length} 条`;
    const maxPage = Math.max(1, Math.ceil(list.length / PLUGINS_PAGE_SIZE) || 1);
    if (wireToolsPageRef.value > maxPage) wireToolsPageRef.value = maxPage;
    if (wireToolsPageRef.value < 1) wireToolsPageRef.value = 1;
    paintWireToolRows();
    wireToolsPager.sync();
    applyWireRoleModeUiState();
  };
  const onWireFilterChange = () => {
    wireToolsPageRef.value = 1;
    refreshWireToolsFiltered();
  };
  [
    wireFServer,
    wireFTool,
    wireFWire,
    wireFExpert,
    wireFCountMin,
    wireFCountMax,
    wireFLastTs,
    wireFPenalty,
    wireFLevelMin,
    wireFLevelMax,
  ].forEach((inp) => inp.addEventListener("input", onWireFilterChange));
  wireFOnlyChecked.addEventListener("change", onWireFilterChange);
  wireRoleModeSelect.addEventListener("change", applyWireRoleModeUiState);
  wireRoleSelect.addEventListener("change", applyWireRoleSelectorState);
  const bulkLvlInput = el(
    "select",
    { class: "input", title: "批量写入", style: "width:140px;" },
    [
      el("option", { value: "0", text: "不惩罚（0）" }),
      el("option", { value: "9999", text: "永禁（9999）" }),
      el("option", { value: "", text: "清空（继承）" }),
    ],
  );
  bulkLvlInput.value = "0";
  const clearWireFiltersBtn = el("button", {
    class: "btn",
    text: "清除筛选",
    onclick: () => {
      wireFServer.value = "";
      wireFTool.value = "";
      wireFWire.value = "";
      wireFExpert.value = "";
      wireFCountMin.value = "";
      wireFCountMax.value = "";
      wireFLastTs.value = "";
      wireFPenalty.value = "";
      wireFLevelMin.value = "";
      wireFLevelMax.value = "";
      wireFOnlyChecked.checked = false;
      onWireFilterChange();
    },
  });
  const applyBulkWireBtn = el("button", {
    class: "btn",
    text: "批量应用到选中",
    onclick: async () => {
      const bulkRaw = String(bulkLvlInput.value ?? "").trim();
      const lv = bulkRaw === "" ? null : normalizeWirePolicyLevel(bulkRaw);
      const selectedWireNames = [];
      Array.from(wireToolBody.querySelectorAll("tr")).forEach((tr) => {
        const cb = tr.querySelector("input[type=checkbox]");
        if (!cb || !cb.checked) return;
        const wn = tr.getAttribute("data-wire-name");
        const sel = tr.querySelector("[data-wire-level]");
        if (wn && sel) {
          selectedWireNames.push(String(wn));
          draftPolicies[wn] = lv;
          sel.value = lv === null ? "" : String(lv);
        }
      });
      if (selectedWireNames.length) {
        try {
          if (lv === null) {
            await apiPost("/admin/api/mcp/tool-wire/policies", {
              role: String(wireRoleSelect.value || ""),
              policies: {},
              clears: selectedWireNames,
            });
          } else {
            await apiPost("/admin/api/mcp/tool-wire/policies/batch", {
              role: String(wireRoleSelect.value || ""),
              level: Number(lv),
              wire_names: selectedWireNames,
            });
          }
          markPrewarmReminder("tool_wire_policies_batch_changed");
        } catch (err) {
          wirePolStatus.textContent = `[批量] 后端批量写入失败: ${String((err && err.message) || err)}`;
          return;
        }
      }
      wirePolStatus.textContent = "[批量] 已写入后端并更新本地视图";
    },
  });
  const saveWirePolBtn = el("button", {
    class: "btn btn--primary",
    text: "保存工具策略",
    onclick: async () => {
      Array.from(wireToolBody.querySelectorAll("tr")).forEach((tr) => {
        const wn = tr.getAttribute("data-wire-name");
        const sel = tr.querySelector("[data-wire-level]");
        if (wn && sel) {
          const raw = String(sel.value ?? "").trim();
          draftPolicies[wn] = raw === "" ? null : normalizeWirePolicyLevel(raw);
        }
      });
      const pol = {};
      const clears = [];
      wireTools.forEach((t) => {
        const wn = t.wire_name;
        const v = draftPolicies[wn];
        if (v === null || v === undefined) clears.push(wn);
        else pol[wn] = v;
      });
      const r = await apiPost("/admin/api/mcp/tool-wire/policies", {
        role: String(wireRoleSelect.value || ""),
        policies: pol,
        clears,
      });
      wirePolStatus.textContent = JSON.stringify(r);
      markPrewarmReminder("tool_wire_policies_changed");
      router();
    },
  });
  refreshWireToolsFiltered();
  applyWireRoleSelectorState();
  applyWireRoleModeUiState();
  const foldToolPolicy = pluginsFold(`【1】工具策略与已注册插件（${pluginCatalog.length}）`, [
    el("div", { class: "muted", text: "Tool policy（确认 / 重试）与 Python 工具插件表" }),
    legacyToolPolicyNote,
    el("div", { class: "row" }, [
      el("label", { text: "Turn max tool workers (1-32)" }),
      turnMaxWorkersInput,
    ]),
    el("div", { class: "row" }, [
      el("label", { text: "Turn max tool rounds (1-100)" }),
      turnMaxRoundsInput,
    ]),
    el("div", { class: "row" }, [
      el("label", { text: "Turn max context messages (10-400)" }),
      turnMaxCtxInput,
    ]),
    el("div", { class: "row" }, [
      el("label", { text: "Turn runner implementation" }),
      turnRunnerImplNote,
    ]),
    el("div", { class: "row" }, [
      el("label", { text: "Manager decision mode" }),
      managerDecisionModeNote,
    ]),
    el("div", { class: "row" }, [
      el("label", { text: "SSE queue maxsize (200-50000)" }),
      sseQueueMaxsizeInput,
    ]),
    el("div", { class: "row" }, [
      el("label", { text: "Tool log max chars (20000-2000000)" }),
      toolLogMaxCharsInput,
    ]),
    el("div", { class: "row" }, [el("label", { class: "kv" }, [enableMcpToolsCb, document.createTextNode(" Enable MCP tools")])]),
    el("div", { class: "row" }, [el("label", { class: "kv" }, [enablePluginToolsCb, document.createTextNode(" Enable plugin tools")])]),
    el("div", { class: "row" }, [el("label", { class: "kv" }, [enableRunCommandCb, document.createTextNode(" Enable run_command (high-risk)")])]),
    el("div", { class: "row" }, [el("label", { class: "kv" }, [toolContextTruncateCb, document.createTextNode(" Compress tool result in agent context (50 chars + hint)")])]),
    el("div", { class: "row" }, [el("label", { class: "kv" }, [chatShowTtftDebugCb, document.createTextNode(" Show TTFT debug timings in chat status")])]),
    el("div", { class: "row" }, [
      el("label", { text: "Tool message max chars to LLM (0=unlimited, 4096-500000 recommended)" }),
      toolLlmMessageMaxCharsInput,
    ]),
    el("div", { class: "muted", text: "Set 0 to disable truncation. If some gateways return 400 for oversized tool messages, set back to 24000." }),
    el("div", { class: "row" }, [
      el("label", { text: "MCP filesystem extra roots (| separated)" }),
      mcpFilesystemExtraRootsInput,
    ]),
    el("div", { class: "row" }, [
      el("label", { text: "MCP env allowlist (comma separated)" }),
      mcpEnvAllowlistInput,
    ]),
    el("div", { class: "row" }, [
      el("label", { text: "oclaw retryable error codes (comma separated)" }),
      oclawRetryableErrorCodesInput,
    ]),
    el("div", { class: "row" }, [el("label", { class: "kv" }, [oclawRetryCodesStrictModeCb, document.createTextNode(" Strict mode: reject unknown retry codes")])]),
    el("div", { class: "row" }, [
      el("label", { text: "WeCom longconn workers (1-8)" }),
      wecomLongconnWorkersInput,
    ]),
    el("div", { class: "row" }, [
      el("label", { text: "WeCom inbound queue maxsize (20-5000)" }),
      wecomLongconnInboundQueueInput,
    ]),
    el("div", { class: "row" }, [saveToolPolicyBtn]),
    toolPolicyStatus,
    el("div", { class: "table-wrap" }, [
      el("table", { class: "table" }, [
        el("thead", {}, [el("tr", {}, [el("th", { text: t("table.name") }), el("th", { text: t("table.version") }), el("th", { text: t("table.entryPoint") }), el("th", { text: t("table.enabled") })])]),
        pluginTbody,
      ]),
    ]),
    pluginPager.wrap,
  ]);
  const foldMcpMarket = pluginsFold("【2】MCP 市场 / 依赖 / Trending / 检索结果", [
    el("div", { class: "muted", text: failureText ? `Failure summary: ${failureText}` : "Failure summary: -" }),
    el("div", { class: "muted", text: "本地依赖检查" }),
    depWrap,
    el("div", { class: "row" }, [marketQ, marketBtn, marketRefreshBtn]),
    el("div", { class: "muted", text: "Trending" }),
    trendingWrap,
    el("div", { class: "muted", text: "Market search" }),
    marketWrap,
  ]);
  const foldMcpInstall = pluginsFold("【3】MCP 安装（表单 / JSON / 运维）", [
    el("div", { class: "row" }, [sourceType, sourceRef, version]),
    el("div", { class: "row" }, [entryCmd, entryArgs, installBtn]),
    el("div", { class: "muted", text: "CLI direct install (paste one command)" }),
    el("div", { class: "row" }, [cliInstallInput, cliInstallBtn]),
    el("div", { class: "muted", text: "常用命令行安装示例（可先本机验证，再填上方表单）" }),
    el("pre", {
      class: "pre",
      text:
`# npm 包（本地安装）
npm install mcp-fetch-server

# 直接运行（推荐）
npx -y mcp-fetch-server

# 全局安装后运行
npm install -g mcp-fetch-server
mcp-fetch-server

# Python 包示例
pip install mcp-server-time
python -m mcp_server_time

# Python（Git URL / VCS）示例：必须显式指定 entry module
pip install git+https://github.com/philschmid/code-sandbox-mcp.git && python -m code_sandbox_mcp`,
    }),
    el("div", { class: "muted", text: "JSON install (single object or array)" }),
    jsonInstallInput,
    el("div", { class: "row" }, [jsonInstallBtn]),
    el("div", { class: "row", style: "flex-wrap:wrap;align-items:center;gap:8px;" }, [
      checkUpdatesBtn,
      updateOutdatedBtn,
      checkAllBtn,
      e2eCheckBtn,
      updateAllBtn,
      repairWeakBtn,
      repairWeakScopeLabel,
    ]),
    installStatus,
    preflightFixWrap,
  ]);
  const mcpExportJsonBtn = el("button", {
    class: "btn",
    text: "Export JSON (download)",
    title: "Download uninstall/reinstallable snapshot (same shape as “Install from JSON”)",
    onclick: async () => {
      let r;
      try {
        r = await apiGet("/admin/api/mcp/export");
      } catch (err) {
        installStatus.textContent = "[export] " + String((err && err.message) || err);
        return;
      }
      if (!r || r.ok !== true || !r.document) {
        installStatus.textContent = "[export] failed: " + JSON.stringify(r);
        return;
      }
      const text = JSON.stringify(r.document, null, 2) + "\n";
      const blob = new Blob([text], { type: "application/json" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "mcp_registry_migrated.json";
      a.click();
      URL.revokeObjectURL(a.href);
      installStatus.textContent =
        "[export] downloaded mcp_registry_migrated.json" + (r.local_path ? " ; on server: " + r.local_path : "");
    },
  });
  const foldMcpInstalled = pluginsFold(`【4】已安装 MCP 服务（${mcpServerList.length}）`, [
    el("div", { class: "row", style: "align-items:center;flex-wrap:wrap;gap:10px;margin-bottom:8px;" }, [
      mcpExportJsonBtn,
      el("div", {
        class: "muted",
        text: "新安装/重装/卸载(删记录)成功后自动写入: src/_local/mcp_registry_migrated.json，便于换机迁移。",
      }),
    ]),
    el("div", { class: "table-wrap" }, [
      el("table", { class: "table table--compact" }, [
        el("thead", {}, [el("tr", {}, [
          el("th", { text: "server_id" }),
          el("th", { text: "source" }),
          el("th", { text: "ref" }),
          el("th", { text: "version" }),
          el("th", { text: "entry" }),
          el("th", { text: "tools" }),
          el("th", { text: "update" }),
          el("th", { text: "enabled" }),
          el("th", { text: "health" }),
          el("th", { text: "actions" }),
        ])]),
        mcpInstalledTbody,
      ]),
    ]),
    mcpInstalledPager.wrap,
  ]);
  const foldMcpUsage = pluginsFold(
    `【5】MCP 用量（summary ${usageSummaryList.length} / calls ${usageCallsList.length}）`,
    [
      el("div", { class: "muted", text: "MCP Usage Summary" }),
      el("div", { class: "table-wrap" }, [
        el("table", { class: "table table--compact" }, [
          el("thead", {}, [el("tr", {}, [
            el("th", { text: "server_id" }),
            el("th", { text: "tool_name" }),
            el("th", { text: "specialist" }),
            el("th", { text: "count" }),
            el("th", { text: "last_called_at" }),
          ])]),
          usageSummaryTbody,
        ]),
      ]),
      usageSummaryPager.wrap,
      el("div", { class: "muted", text: "Recent MCP Calls", style: "margin-top:10px;" }),
      el("div", { class: "table-wrap" }, [
        el("table", { class: "table table--compact" }, [
          el("thead", {}, [el("tr", {}, [
            el("th", { text: "timestamp" }),
            el("th", { text: "server_id" }),
            el("th", { text: "tool_name" }),
            el("th", { text: "specialist" }),
            el("th", { text: "session_id" }),
            el("th", { text: "duration_ms" }),
          ])]),
          usageCallsTbody,
        ]),
      ]),
      usageCallsPager.wrap,
    ],
  );
  const foldWireGlobal = pluginsFold("【6】线侧策略 — 全局参数", [
    el("div", {
      class: "muted",
      text: "按 mcp__server__tool；wire_policy=always 不依赖 base_url。",
    }),
    el("div", { class: "row", style: "flex-wrap:wrap;gap:8px;align-items:center;" }, [
      el("label", { text: "wire_policy" }),
      inpWirePolicy,
      el("label", { text: "Top N 全量" }),
      inpTopN,
      el("label", { text: "全局闲置(h)" }),
      inpStaleH,
      el("label", { text: "罚时长(min)" }),
      inpPenMin,
    ]),
    el("div", { class: "row", style: "flex-wrap:wrap;gap:8px;align-items:center;" }, [
      el("label", { text: "medium rank" }),
      inpMedS,
      inpMedE,
      el("label", { text: "medium 描述上限" }),
      inpMedDesc,
      el("label", { text: "minimal 描述" }),
      inpMinCap,
      el("label", {}, [inpPenaltyEnabled, el("span", { text: "启用惩罚机制", style: "margin-left:6px;" })]),
    ]),
    el("div", { class: "row" }, [
      el("label", { text: "role" }),
      wireRoleSelect,
      wireRoleModeSelect,
      saveWireRoleModeBtn,
      saveWireCfgBtn,
      resetPenaltyStateBtn,
      wireCfgStatus,
    ]),
  ]);
  const wireLevelHint = el("div", {
    class: "muted",
    style: "font-size:12px;line-height:1.45;margin-bottom:6px;",
    text:
      "留空=未配置（运行时走全局闲置惩罚与线侧分层/压缩）。0=该 role 下此工具不参与闲置惩罚。任意整数 1–9998：闲置与罚均为 N×10 分钟；≥9999 视为 9999 永久不上送。新安装 MCP 在 Sync Tools 后出现新行，默认留空即自动走全局，直至你在本页保存。",
  });
  const foldWireTools = pluginsFold(`【7】线侧策略 — 已安装工具（${wireTools.length}）`, [
    wireLevelHint,
    wireRoleModeHint,
    el("div", { class: "row", style: "flex-wrap:wrap;gap:8px;align-items:center;" }, [
      wireFilterCountLabel,
      clearWireFiltersBtn,
      el("span", { class: "muted", text: "批量等级" }),
      bulkLvlInput,
      applyBulkWireBtn,
      saveWirePolBtn,
      wirePolStatus,
    ]),
    el("div", { class: "table-wrap" }, [
      el("table", { class: "table table--compact" }, [
        el("thead", {}, [
          el("tr", {}, [
            el("th", { text: "选" }),
            el("th", { text: "server" }),
            el("th", { text: "tool" }),
            el("th", { text: "wire_name" }),
            el("th", { text: "专家（绑定推导）" }),
            el("th", { text: "count" }),
            el("th", { text: "last_ts" }),
            el("th", { text: "effective_mode" }),
            el("th", { text: "惩罚/解封" }),
            el("th", { text: "策略" }),
          ]),
          el("tr", {}, [
            el("th", {}, [wireFOnlyChecked]),
            el("th", {}, [wireFServer]),
            el("th", {}, [wireFTool]),
            el("th", {}, [wireFWire]),
            el("th", {}, [wireFExpert]),
            el("th", {}, [
              el("div", { style: "display:flex;flex-direction:column;gap:4px;" }, [wireFCountMin, wireFCountMax]),
            ]),
            el("th", {}, [wireFLastTs]),
            el("th", { text: "-" }),
            el("th", {}, [wireFPenalty]),
            el("th", {}, [
              el("div", { style: "display:flex;flex-direction:column;gap:4px;" }, [wireFLevelMin, wireFLevelMax]),
            ]),
          ]),
        ]),
        wireToolBody,
      ]),
    ]),
    wireToolsPager.wrap,
  ]);
  wireRoleSelect.addEventListener("change", async () => {
    try {
      const qs = wireRoleSelect.value ? ("?role=" + encodeURIComponent(wireRoleSelect.value)) : "";
      toolWire = await apiGet("/admin/api/mcp/tool-wire" + qs);
      wireCfgStatus.textContent = `[role] switched to ${String(toolWire.role || "global")}`;
      wireRoleModeSelect.value = String(toolWire.role_mode || "restricted");
      // reload current page to rebuild wireTools + drafts cleanly
      router();
    } catch (err) {
      wireCfgStatus.textContent = `[role] load failed: ${String((err && err.message) || err)}`;
    }
  });
  const foldExpertBindingDash = pluginsFold("【8】专家 MCP 绑定看板（自动）", [
    el("div", {
      class: "muted",
      text: "按当前绑定草稿与已安装 MCP 的 tools 列表汇总；专家列表来自 SPECIALISTS 与绑定 mapping 键，随扩展自动增减。",
    }),
    el("div", { class: "table-wrap" }, [
      el("table", { class: "table table--compact" }, [
        el("thead", {}, [el("tr", {}, [
          el("th", { text: "专家" }),
          el("th", { text: "绑定 MCP 数" }),
          el("th", { text: "tools 数（各 server 累加）" }),
        ])]),
        expertBindingDashTbody,
      ]),
    ]),
  ]);
  const foldMcpBinding = pluginsFold("【9】MCP 专家绑定（编辑）", [
    el("div", { class: "muted", text: "Bind MCP servers to specialists (many-to-many)." }),
    el("div", { class: "row" }, [el("label", { text: "Specialist" }), specialistSelect, selectAllBindingBtn, clearBindingBtn, saveBindingBtn]),
    bindingListWrap,
    el("div", { class: "muted", text: "Reverse view: server -> specialists" }),
    bindingReverseWrap,
    bindingStatus,
  ]);
  return renderPageShell({
    title: t("plugins.title"),
    subtitle: "按功能分区展示，默认折叠；表格支持分页（每页 " + PLUGINS_PAGE_SIZE + " 条）。",
    sections: [
      { id: "plugins-tool-policy", label: "策略" },
      { id: "plugins-market", label: "市场" },
      { id: "plugins-install", label: "安装" },
      { id: "plugins-instances", label: "实例" },
      { id: "plugins-binding", label: "专家绑定" },
    ],
  }, [
    el("div", { class: "page-grid page-grid--single" }, [
      el("div", { id: "plugins-tool-policy" }, [foldToolPolicy]),
      el("div", { id: "plugins-market" }, [foldMcpMarket]),
      el("div", { id: "plugins-install" }, [foldMcpInstall]),
      el("div", { id: "plugins-instances" }, [foldMcpInstalled]),
      foldMcpUsage,
      foldWireGlobal,
      foldWireTools,
      foldExpertBindingDash,
      el("div", { id: "plugins-binding" }, [foldMcpBinding]),
    ]),
    cliInstallModal,
  ]);
}

async function renderAdminAudit() {
  const action = el("input", { class: "input", placeholder: t("adminAudit.action") });
  const actor = el("input", { class: "input", placeholder: t("adminAudit.actor") });
  const status = el("input", { class: "input", placeholder: t("adminAudit.status") });
  const tbody = el("tbody");
  const pager = el("div", { class: "row", style: "gap:8px;align-items:center;flex-wrap:wrap;margin-top:8px;" });
  const pageInfo = el("span", { class: "muted", text: tf("sessionMonitor.pageInfo", { page: 1, totalPages: 1 }) });
  const totalInfo = el("span", { class: "muted", text: tf("adminAudit.total", { total: 0 }) });
  const pageInput = el("input", {
    class: "input",
    type: "number",
    min: "1",
    step: "1",
    placeholder: t("adminAudit.jumpPlaceholder"),
    style: "width:90px;",
  });
  let page = 1;
  const pageSize = 50;
  let total = 0;
  const totalPages = () => Math.max(1, Math.ceil((Number(total) || 0) / pageSize));
  const setPager = () => {
    const tp = totalPages();
    pageInfo.textContent = tf("sessionMonitor.pageInfo", { page, totalPages: tp });
    totalInfo.textContent = tf("adminAudit.total", { total });
    pageInput.value = String(page);
    btnPrev.disabled = page <= 1;
    btnNext.disabled = page >= tp;
  };
  const load = async () => {
    const p = new URLSearchParams();
    p.set("limit", String(pageSize));
    p.set("offset", String((Math.max(1, page) - 1) * pageSize));
    if (action.value.trim()) p.set("action", action.value.trim());
    if (actor.value.trim()) p.set("actor_user_id", actor.value.trim());
    if (status.value.trim()) p.set("status", status.value.trim());
    const resp = await apiGet("/admin/api/admin-audit?" + p.toString());
    total = Math.max(0, Number(resp.total || 0) || 0);
    const rows = Array.isArray(resp.items) ? resp.items : [];
    tbody.innerHTML = "";
    if (!rows.length) {
      tbody.appendChild(el("tr", {}, [el("td", { text: t("audit.empty"), colspan: "8" })]));
      setPager();
      return;
    }
    rows.forEach((r) => {
      tbody.appendChild(el("tr", {}, [
        tdCell(r.timestamp || "", 24),
        tdCell(formatAuditActor(r), 28),
        tdCell(r.action || "", 20),
        tdCell(r.target_type || "", 16),
        tdCell(r.target_id || "", 24),
        tdCell(r.status || "", 12),
        tdCell(r.actor_tenant_id || "", 24),
        tdCell(JSON.stringify(r.detail || {}), 120),
      ]));
    });
    setPager();
  };
  const btn = el("button", {
    class: "btn btn--primary",
    text: t("audit.query"),
    onclick: async () => {
      page = 1;
      await load();
    },
  });
  const btnPrev = el("button", {
    class: "btn btn--small",
    text: t("sessionMonitor.pagePrev"),
    disabled: true,
    onclick: async () => {
      if (page <= 1) return;
      page -= 1;
      await load();
    },
  });
  const btnNext = el("button", {
    class: "btn btn--small",
    text: t("sessionMonitor.pageNext"),
    disabled: true,
    onclick: async () => {
      const tp = totalPages();
      if (page >= tp) return;
      page += 1;
      await load();
    },
  });
  const btnJump = el("button", {
    class: "btn btn--small",
    text: t("adminAudit.jump"),
    onclick: async () => {
      const tp = totalPages();
      let target = parseInt(String(pageInput.value || "").trim(), 10);
      if (!Number.isFinite(target)) target = page;
      target = Math.max(1, Math.min(tp, target));
      if (target === page) {
        setPager();
        return;
      }
      page = target;
      await load();
    },
  });
  pageInput.addEventListener("keydown", async (ev) => {
    if (ev.key !== "Enter") return;
    ev.preventDefault();
    btnJump.click();
  });
  pager.appendChild(btnPrev);
  pager.appendChild(btnNext);
  pager.appendChild(pageInfo);
  pager.appendChild(totalInfo);
  pager.appendChild(pageInput);
  pager.appendChild(btnJump);
  await load();
  return el("div", {}, [
    el("div", { class: "card" }, [
      el("div", { class: "card__title", text: t("adminAudit.title") }),
      el("div", { class: "row" }, [action, actor, status, btn]),
      pager,
      el("div", { class: "table-wrap" }, [el("table", { class: "table table--compact" }, [
        el("thead", {}, [el("tr", {}, [
          el("th", { text: t("table.timestamp") }),
          el("th", { text: t("adminAudit.actor") }),
          el("th", { text: t("adminAudit.action") }),
          el("th", { text: "target_type" }),
          el("th", { text: "target_id" }),
          el("th", { text: t("adminAudit.status") }),
          el("th", { text: "tenant_id" }),
          el("th", { text: t("table.payload") }),
        ])]),
        tbody,
      ])]),
    ]),
  ]);
}

async function renderSessionMonitor() {
  const userQ = el("input", { class: "input", placeholder: t("sessionMonitor.filterUser") });
  const sessQ = el("input", { class: "input", placeholder: t("sessionMonitor.filterSession") });
  const activeOnlyChk = el("input", { type: "checkbox" });
  const selectedHint = el("div", { class: "muted", text: t("sessionMonitor.selectUserFirst") });
  const userBody = el("tbody");
  const sessBody = el("tbody");
  const sessionPagerTop = el("div", { class: "row" });
  const sessionPagerBottom = el("div", { class: "row" });
  const detailBody = el("tbody");
  const detailStatus = el("div", { class: "muted", text: t("sessionMonitor.noMessages") });
  const detailPager = el("div", { class: "row" });
  const detailRoleFilter = el("select", { class: "input" });
  const detailModal = el("div", { class: "session-monitor-modal", style: "display:none;" });
  const detailModalCard = el("div", { class: "session-monitor-modal__card" });
  const totalsWrap = el("div", { class: "row" });
  let selectedUserId = "";
  let selectedSessionId = "";
  let sessionLimit = 20;
  let sessionOffset = 0;
  let sessionTotal = 0;
  let detailMessages = [];
  let detailPage = 1;
  const detailPageSize = 20;
  let sessionMenuEl = null;

  const rebuildDetailRoleFilter = () => {
    const saved = String(localStorage.getItem(SESSION_MONITOR_ROLE_FILTER_KEY) || "").trim();
    const prev = String(detailRoleFilter.value || saved || "all");
    detailRoleFilter.innerHTML = "";
    detailRoleFilter.appendChild(el("option", { value: "all", text: t("sessionMonitor.roleAll") }));
    detailRoleFilter.appendChild(el("option", { value: "user", text: t("sessionMonitor.roleUser") }));
    detailRoleFilter.appendChild(el("option", { value: "assistant", text: t("sessionMonitor.roleAssistant") }));
    detailRoleFilter.appendChild(el("option", { value: "tool", text: t("sessionMonitor.roleTool") }));
    detailRoleFilter.value = ["all", "user", "assistant", "tool"].includes(prev) ? prev : "all";
  };

  const buildPageInfo = (page, totalPages) => tf("sessionMonitor.pageInfo", { page, totalPages });

  const downloadSessionExport = async (sessionId, format) => {
    const q = format === "json" ? "format=json" : "format=md";
    const path = `/admin/api/chat/sessions/${encodeURIComponent(sessionId)}/export?${q}`;
    const url = resolveAdminApiUrl(path);
    const tok = getStoredAuthToken();
    const res = await fetch(url, {
      headers: tok ? { authorization: `Bearer ${tok}` } : {},
    });
    if (!res.ok) throw new Error(`export_failed_${res.status}`);
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `chat-${String(sessionId || "").slice(0, 8)}.${format === "json" ? "json" : "md"}`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const closeSessionMenu = () => {
    if (sessionMenuEl && sessionMenuEl.parentNode) {
      sessionMenuEl.remove();
    }
    sessionMenuEl = null;
  };

  const closeDetailModal = () => {
    detailModal.style.display = "none";
  };

  const renderTotals = (totals) => {
    totalsWrap.innerHTML = "";
    const cards = [
      { key: "total_tokens_est", label: t("sessionMonitor.totalTokensEst") },
      { key: "active_sessions_30m", label: t("sessionMonitor.activeSessions30m") },
      { key: "active_logins_30m", label: t("sessionMonitor.activeLogins30m") },
      { key: "users_count", label: t("sessionMonitor.usersCount") },
    ];
    cards.forEach((c) => {
      totalsWrap.appendChild(
        el("div", { class: "kv", text: `${c.label}: ${String((totals && totals[c.key]) ?? 0)}` }),
      );
    });
  };

  const renderDetailPager = () => {
    detailPager.innerHTML = "";
    const role = String(detailRoleFilter.value || "all");
    const filtered = Array.isArray(detailMessages)
      ? detailMessages.filter((m) => {
          if (role === "all") return true;
          const r = String(m.role || "").toLowerCase();
          return role === "tool" ? r === "tool" || r === "function" : r === role;
        })
      : [];
    const total = filtered.length;
    const totalPages = Math.max(1, Math.ceil(total / detailPageSize));
    const info = el("span", { class: "muted", text: buildPageInfo(detailPage, totalPages) });
    const btnPrev = el("button", {
      class: "btn btn--small",
      text: t("sessionMonitor.pagePrev"),
      disabled: detailPage <= 1,
      onclick: () => {
        if (detailPage <= 1) return;
        detailPage -= 1;
        renderDetailMessages();
      },
    });
    const btnNext = el("button", {
      class: "btn btn--small",
      text: t("sessionMonitor.pageNext"),
      disabled: detailPage >= totalPages,
      onclick: () => {
        if (detailPage >= totalPages) return;
        detailPage += 1;
        renderDetailMessages();
      },
    });
    detailPager.appendChild(btnPrev);
    detailPager.appendChild(btnNext);
    detailPager.appendChild(info);
  };

  const renderDetailMessages = () => {
    detailBody.innerHTML = "";
    if (!selectedSessionId) {
      detailStatus.textContent = t("sessionMonitor.selectUserFirst");
      detailPager.innerHTML = "";
      return;
    }
    const role = String(detailRoleFilter.value || "all");
    const all = Array.isArray(detailMessages) ? detailMessages : [];
    const filtered = all.filter((m) => {
      if (role === "all") return true;
      const r = String(m.role || "").toLowerCase();
      return role === "tool" ? r === "tool" || r === "function" : r === role;
    });
    if (!filtered.length) {
      detailStatus.textContent = t("sessionMonitor.noMessages");
      detailPager.innerHTML = "";
      return;
    }
    const totalPages = Math.max(1, Math.ceil(filtered.length / detailPageSize));
    if (detailPage > totalPages) detailPage = totalPages;
    const start = (detailPage - 1) * detailPageSize;
    const rows = filtered.slice(start, start + detailPageSize);
    detailStatus.textContent = `session_id: ${selectedSessionId} | ${filtered.length}/${all.length}`;
    rows.forEach((m) => {
      detailBody.appendChild(
        el("tr", {}, [
          tdCell(m.id || "", 8),
          tdCell(m.role || "", 10),
          tdCell(m.content || "", 120),
          tdCell(m.timestamp || "", 24),
        ]),
      );
    });
    renderDetailPager();
  };

  const loadSessionDetail = async (sessionId, opts = {}) => {
    const openModal = Boolean(opts && opts.openModal);
    selectedSessionId = String(sessionId || "");
    detailPage = 1;
    detailBody.innerHTML = "";
    detailStatus.textContent = `${t("chat.loading")}...`;
    detailPager.innerHTML = "";
    if (!selectedSessionId) {
      detailStatus.textContent = t("sessionMonitor.noMessages");
      if (openModal) detailModal.style.display = "flex";
      return;
    }
    try {
      const resp = await apiGet(`/admin/api/chat/sessions/${encodeURIComponent(selectedSessionId)}/messages`);
      detailMessages = Array.isArray(resp.messages) ? resp.messages : [];
      renderDetailMessages();
    } catch (err) {
      detailMessages = [];
      detailBody.innerHTML = "";
      detailPager.innerHTML = "";
      detailStatus.textContent = `${t("chat.error")}: ${String(err && err.message ? err.message : err)}`;
    }
    if (openModal) detailModal.style.display = "flex";
  };

  const renderSessionPager = () => {
    const totalPages = Math.max(1, Math.ceil(Math.max(0, sessionTotal) / sessionLimit));
    const current = Math.floor(sessionOffset / sessionLimit) + 1;
    const row = el("div", { class: "row" }, [
      el("button", {
        class: "btn btn--small",
        text: t("sessionMonitor.pagePrev"),
        disabled: sessionOffset <= 0,
        onclick: async () => {
          if (sessionOffset <= 0) return;
          sessionOffset = Math.max(0, sessionOffset - sessionLimit);
          await loadSessions();
        },
      }),
      el("button", {
        class: "btn btn--small",
        text: t("sessionMonitor.pageNext"),
        disabled: sessionOffset + sessionLimit >= sessionTotal,
        onclick: async () => {
          if (sessionOffset + sessionLimit >= sessionTotal) return;
          sessionOffset += sessionLimit;
          await loadSessions();
        },
      }),
      el("span", { class: "muted", text: buildPageInfo(current, totalPages) }),
    ]);
    return row;
  };

  const updateSessionPagers = () => {
    sessionPagerTop.innerHTML = "";
    sessionPagerBottom.innerHTML = "";
    sessionPagerTop.appendChild(renderSessionPager());
    sessionPagerBottom.appendChild(renderSessionPager());
  };
  detailRoleFilter.addEventListener("change", () => {
    try {
      localStorage.setItem(SESSION_MONITOR_ROLE_FILTER_KEY, String(detailRoleFilter.value || "all"));
    } catch (_) {}
    detailPage = 1;
    renderDetailMessages();
  });

  const loadSessions = async () => {
    sessBody.innerHTML = "";
    if (!selectedUserId) {
      sessBody.appendChild(el("tr", {}, [el("td", { text: t("sessionMonitor.selectUserFirst"), colspan: "8" })]));
      selectedHint.textContent = t("sessionMonitor.selectUserFirst");
      sessionTotal = 0;
      updateSessionPagers();
      return;
    }
    const sp = new URLSearchParams();
    sp.set("user_id", selectedUserId);
    sp.set("limit", String(sessionLimit));
    sp.set("offset", String(sessionOffset));
    if (sessQ.value.trim()) sp.set("q", sessQ.value.trim());
    if (activeOnlyChk.checked) sp.set("active_only", "1");
    const resp = await apiGet("/admin/api/chat/admin/sessions?" + sp.toString());
    const rows = Array.isArray(resp.sessions) ? resp.sessions : [];
    sessionTotal = Number(resp.total || 0);
    selectedHint.textContent = `${t("table.userId")}: ${selectedUserId}`;
    if (!rows.length) {
      sessBody.appendChild(el("tr", {}, [el("td", { text: t("audit.empty"), colspan: "8" })]));
      if (selectedSessionId && !rows.some((x) => String(x.session_id || "") === selectedSessionId)) {
        selectedSessionId = "";
        detailMessages = [];
        renderDetailMessages();
      }
      updateSessionPagers();
      return;
    }
    rows.forEach((r) => {
      const sid = String(r.session_id || "");
      const btnMore = el("button", {
        class: "chat-sess-more" + (sid === selectedSessionId ? " chat-sess-more--active" : ""),
        text: "⋯",
        title: t("chat.sessionMenu"),
        onclick: (ev) => {
          ev.stopPropagation();
          closeSessionMenu();
          const menu = el("div", { class: "chat-sess-menu-pop", style: "position:fixed;z-index:250;" }, [
            el("button", {
              class: "chat-sess-menu-item",
              text: t("sessionMonitor.viewDetail"),
              onclick: async () => {
                closeSessionMenu();
                await loadSessionDetail(sid, { openModal: true });
              },
            }),
            el("button", {
              class: "chat-sess-menu-item",
              text: t("sessionMonitor.viewAudit"),
              onclick: () => {
                closeSessionMenu();
                location.hash = `#/audit?session_id=${encodeURIComponent(sid)}`;
              },
            }),
            el("button", {
              class: "chat-sess-menu-item",
              text: t("sessionMonitor.exportMd"),
              onclick: async () => {
                closeSessionMenu();
                await downloadSessionExport(sid, "md");
              },
            }),
            el("button", {
              class: "chat-sess-menu-item",
              text: t("sessionMonitor.exportJson"),
              onclick: async () => {
                closeSessionMenu();
                await downloadSessionExport(sid, "json");
              },
            }),
          ]);
          const rect = ev.currentTarget.getBoundingClientRect();
          document.body.appendChild(menu);
          // Clamp into viewport; flip above if near bottom.
          const mrect = menu.getBoundingClientRect();
          const pad = 8;
          let left = rect.left - 120;
          let top = rect.bottom + 4;
          if (top + mrect.height > window.innerHeight - pad) {
            top = rect.top - 4 - mrect.height;
          }
          left = Math.max(pad, Math.min(left, window.innerWidth - pad - mrect.width));
          top = Math.max(pad, Math.min(top, window.innerHeight - pad - mrect.height));
          menu.style.left = `${left}px`;
          menu.style.top = `${top}px`;
          sessionMenuEl = menu;
          const close = (e) => {
            if (!menu.contains(e.target)) {
              closeSessionMenu();
              document.removeEventListener("click", close);
            }
          };
          setTimeout(() => document.addEventListener("click", close), 0);
        },
      });
      sessBody.appendChild(
        el(
          "tr",
          {
            "data-session-id": sid,
            class: sid === selectedSessionId ? "session-monitor-row--active" : "",
            onclick: async () => {
              selectedSessionId = sid;
              closeSessionMenu();
              const sessionRows = Array.from(sessBody.querySelectorAll("tr[data-session-id]"));
              sessionRows.forEach((tr) => {
                const curr = String(tr.getAttribute("data-session-id") || "");
                tr.classList.toggle("session-monitor-row--active", curr === selectedSessionId);
              });
            },
          },
          [
          tdCell(sid, 24),
          tdCell(r.title || "", 30),
          tdCell(r.username || "", 16),
          tdCell(r.message_count || "", 10),
          tdCell(r.last_message_at || "", 24),
          tdCell(r.is_active_30m ? "yes" : "no", 8),
          el("td", { class: "table__cell-actions" }, [btnMore]),
          ],
        ),
      );
    });
    updateSessionPagers();
  };

  const loadUsers = async () => {
    const p = new URLSearchParams();
    p.set("limit", "200");
    if (userQ.value.trim()) p.set("q", userQ.value.trim());
    const resp = await apiGet("/admin/api/chat/admin/user-stats?" + p.toString());
    renderTotals(resp.totals || {});
    const rows = Array.isArray(resp.users) ? resp.users : [];
    userBody.innerHTML = "";
    if (!rows.length) {
      userBody.appendChild(el("tr", {}, [el("td", { text: t("audit.empty"), colspan: "9" })]));
      selectedUserId = "";
      selectedSessionId = "";
      detailMessages = [];
      await loadSessions();
      return;
    }
    if (!selectedUserId || !rows.some((x) => String(x.user_id || "") === selectedUserId)) {
      selectedUserId = String(rows[0].user_id || "");
    }
    rows.forEach((r) => {
      const uid = String(r.user_id || "");
      const pickBtn = el("button", {
        class: "btn btn--small",
        "data-user-pick": "1",
        "data-user-id": uid,
        text: uid === selectedUserId ? "●" : "○",
        onclick: async () => {
          selectedUserId = uid;
          sessionOffset = 0;
          selectedSessionId = "";
          detailMessages = [];
          const pickBtns = Array.from(userBody.querySelectorAll("button[data-user-pick='1']"));
          pickBtns.forEach((btnEl) => {
            const id = String(btnEl.getAttribute("data-user-id") || "");
            btnEl.textContent = id === selectedUserId ? "●" : "○";
          });
          await loadSessions();
        },
      });
      userBody.appendChild(
        el("tr", {}, [
          el("td", {}, [pickBtn]),
          tdCell(r.username || "", 16),
          tdCell(r.display_name || "", 16),
          tdCell(r.role || "", 10),
          tdCell(r.sessions_count || "", 10),
          tdCell(r.active_sessions_30m || "", 10),
          tdCell(r.active_login_30m || "", 10),
          tdCell(r.total_tokens_est || "", 14),
          tdCell(r.last_message_at || "", 24),
        ]),
      );
    });
    await loadSessions();
  };

  const btnQueryUsers = el("button", { class: "btn btn--primary", text: t("audit.query"), onclick: loadUsers });
  const btnQuerySessions = el("button", {
    class: "btn",
    text: t("audit.query"),
    onclick: async () => {
      sessionOffset = 0;
      selectedSessionId = "";
      detailMessages = [];
      await loadSessions();
    },
  });
  const activeOnlyLabel = el("label", { class: "row" }, [
    activeOnlyChk,
    el("span", { class: "muted", text: t("sessionMonitor.activeSessions30m") }),
  ]);

  await loadUsers();
  rebuildDetailRoleFilter();
  const btnCloseDetail = el("button", {
    class: "btn btn--small",
    text: t("sessionMonitor.closeDetail"),
    onclick: () => {
      selectedSessionId = "";
      detailMessages = [];
      detailBody.innerHTML = "";
      detailStatus.textContent = t("sessionMonitor.noMessages");
      detailPager.innerHTML = "";
      closeDetailModal();
      loadSessions().catch(() => {});
    },
  });
  const detailTable = el("table", { class: "table table--compact session-monitor-detail-table" }, [
    el("thead", {}, [
      el("tr", {}, [
        el("th", { text: "id" }),
        el("th", { text: "role" }),
        el("th", { text: "content" }),
        el("th", { text: t("table.timestamp") }),
      ]),
    ]),
    detailBody,
  ]);
  detailModalCard.appendChild(
    el("div", { class: "card" }, [
      el("div", { class: "card__title", text: t("sessionMonitor.messages") }),
      el("div", { class: "row" }, [
        el("span", { class: "muted", text: t("sessionMonitor.roleFilter") }),
        detailRoleFilter,
        btnCloseDetail,
      ]),
      detailStatus,
      detailPager,
      el("div", { class: "table-wrap" }, [
        detailTable,
      ]),
    ]),
  );
  enableTableColumnResize(detailTable, [2, 3]);
  detailModal.appendChild(detailModalCard);
  detailModal.addEventListener("click", (ev) => {
    if (ev.target === detailModal) closeDetailModal();
  });
  return renderPageShell({
    title: t("title.sessionMonitor"),
    subtitle: "按用户、会话与消息详情进行巡检与导出",
    sections: [
      { id: "sm-totals", label: "总览" },
      { id: "sm-users", label: "用户" },
      { id: "sm-sessions", label: "会话" },
    ],
  }, [
    renderSectionCard(t("sessionMonitor.totals"), "", [totalsWrap], { id: "sm-totals" }),
    renderSectionCard(t("sessionMonitor.userStats"), "", [
      el("div", { class: "row" }, [userQ, btnQueryUsers]),
      el("div", { class: "table-wrap" }, [
        el("table", { class: "table table--compact" }, [
          el("thead", {}, [
            el("tr", {}, [
              el("th", { text: "#" }),
              el("th", { text: t("table.username") }),
              el("th", { text: t("table.name") }),
              el("th", { text: t("tenants.role") }),
              el("th", { text: t("table.sessionsCount") }),
              el("th", { text: t("table.activeSessions30m") }),
              el("th", { text: t("table.activeLogins30m") }),
              el("th", { text: t("table.totalTokensEst") }),
              el("th", { text: t("table.timestamp") }),
            ]),
          ]),
          userBody,
        ]),
      ]),
    ], { id: "sm-users" }),
    renderSectionCard(t("sessionMonitor.sessions"), "", [
      el("div", { class: "row" }, [sessQ, activeOnlyLabel, btnQuerySessions]),
      selectedHint,
      sessionPagerTop,
      el("div", { class: "table-wrap" }, [
        el("table", { class: "table table--compact session-monitor-session-table" }, [
          el("thead", {}, [
            el("tr", {}, [
              el("th", { text: "session_id" }),
              el("th", { text: t("table.name") }),
              el("th", { text: t("table.username") }),
              el("th", { text: "msg_count" }),
              el("th", { text: t("table.timestamp") }),
              el("th", { text: t("table.activeSessions30m") }),
              el("th", { text: t("table.action") }),
            ]),
          ]),
          sessBody,
        ]),
      ]),
      sessionPagerBottom,
    ], { id: "sm-sessions" }),
    detailModal,
  ]);
}

async function renderWorkspacePaths() {
  const sessionTid = String((authSession && authSession.tenant_id) || "").trim();
  const sessionUid = String((authSession && authSession.user_id) || "").trim();
  const canUserRead = hasPermission("admin:user:read");
  const canWsRead = hasPermission("admin:workspace_paths:read");
  const canWsWrite = hasPermission("admin:workspace_paths:write");
  const selfService = !canUserRead && canWsRead;
  if (!sessionTid || (!canUserRead && !canWsRead)) {
    return el("div", { class: "card" }, [
      el("div", { class: "card__title", text: t("title.workspacePaths") }),
      el("div", { class: "muted", text: t("common.forbidden") }),
    ]);
  }
  if (selfService && !sessionUid) {
    return el("div", { class: "card" }, [
      el("div", { class: "card__title", text: t("title.workspacePaths") }),
      el("div", { class: "muted", text: t("tenants.noSessionTenant") }),
    ]);
  }
  let allTenants = [];
  try {
    const allTenantsResp = await apiGet("/admin/api/tenants");
    allTenants = allTenantsResp.tenants || [];
  } catch (_) {
    allTenants = [{ id: sessionTid, name: "", created_at: "" }];
  }
  if (!allTenants.length) {
    return el("div", { class: "card" }, [
      el("div", { class: "card__title", text: t("title.workspacePaths") }),
      el("div", { class: "muted", text: t("tenants.noTenants") }),
    ]);
  }
  const tenantSel = el("select", { class: "input" });
  for (const item of allTenants) {
    const optLabel = String(item.name || "").trim() || String(item.id || "").slice(0, 8);
    tenantSel.appendChild(el("option", { value: String(item.id || ""), text: optLabel }));
  }
  const preferredIdx = allTenants.findIndex((x) => String(x.id || "") === sessionTid);
  tenantSel.selectedIndex = preferredIdx >= 0 ? preferredIdx : 0;
  if (selfService) {
    tenantSel.disabled = true;
    tenantSel.title = t("workspacePaths.selfOnly");
  }
  const userSel = el("select", { class: "input" });
  const selfUserLabel = el("div", {
    class: "muted",
    text: formatUserLabel({
      username: authSession && authSession.username,
      display_name: authSession && authSession.display_name,
    }) + (sessionUid ? ` · ${sessionUid.slice(0, 8)}…` : ""),
  });
  if (selfService) {
    userSel.style.display = "none";
  }
  const extraInput = el("textarea", {
    class: "input",
    rows: "4",
    placeholder: "D:\\\\|E:\\\\|D:\\\\repos\\\\other",
    style: "min-height:88px;font-family:monospace;",
  });
  const allowAnyCb = el("input", { type: "checkbox" });
  const allowHighToolsCb = el("input", { type: "checkbox" });
  const status = el("div", { class: "muted", text: "" });
  const canWrite = hasPermission("admin:user:write") || canWsWrite;
  const canTogglePublicHigh = hasPermission("admin:user:write");
  if (!canTogglePublicHigh) {
    allowHighToolsCb.disabled = true;
  }

  const getEffectiveTid = () => (selfService ? sessionTid : String(tenantSel.value || ""));
  const getEffectiveUid = () => (selfService ? sessionUid : String(userSel.value || ""));

  const loadUsers = async () => {
    if (selfService) return;
    const tid = String(tenantSel.value || "");
    userSel.innerHTML = "";
    if (!tid) return;
    const resp = await apiGet(
      "/admin/api/users?tenant_id=" +
        encodeURIComponent(tid) +
        "&include_inactive=1&q=&limit=500",
    );
    const users = Array.isArray(resp.users) ? resp.users : [];
    for (const u of users) {
      const id = String(u.id || "");
      if (!id) continue;
      const label = formatUserLabel(u);
      userSel.appendChild(el("option", { value: id, text: label }));
    }
    if (userSel.options.length) userSel.selectedIndex = 0;
  };

  const loadPolicy = async () => {
    const tid = getEffectiveTid();
    const uid = getEffectiveUid();
    if (!tid || !uid) {
      status.textContent = "";
      return;
    }
    status.textContent = "…";
    try {
      const r = await apiGet(
        "/admin/api/users/workspace-path-policy?tenant_id=" +
          encodeURIComponent(tid) +
          "&user_id=" +
          encodeURIComponent(uid),
      );
      if (!r.ok) {
        status.textContent = String(r.error || "error");
        return;
      }
      const pol = r.policy || {};
      extraInput.value = String(pol.extra_roots || "");
      allowAnyCb.checked = !!pol.allow_any_path;
      allowHighToolsCb.checked = !!r.public_tools_allow_high;
      status.textContent = (r.from_db ? t("workspacePaths.fromDb") + " · " : "") + JSON.stringify(pol);
    } catch (e) {
      status.textContent = String(e && e.message ? e.message : e);
    }
  };

  tenantSel.addEventListener("change", async () => {
    await loadUsers();
    await loadPolicy();
  });
  userSel.addEventListener("change", () => {
    loadPolicy();
  });

  await loadUsers();
  await loadPolicy();

  const loadBtn = el("button", {
    class: "btn",
    text: t("workspacePaths.load"),
    onclick: () => loadPolicy(),
  });
  const saveBtn = el("button", {
    class: "btn btn--primary",
    text: t("workspacePaths.save"),
    disabled: canWrite ? undefined : "disabled",
    onclick: async () => {
      if (!canWrite) return;
      const tid = getEffectiveTid();
      const uid = getEffectiveUid();
      if (!tid || !uid) return;
      status.textContent = "…";
      try {
        const payload = {
          tenant_id: tid,
          user_id: uid,
          extra_roots: extraInput.value,
          allow_any_path: !!allowAnyCb.checked,
        };
        if (canTogglePublicHigh) {
          payload.public_tools_allow_high = !!allowHighToolsCb.checked;
        }
        const r = await apiPost("/admin/api/users/workspace-path-policy", payload);
        if (!r.ok) {
          status.textContent = String(r.error || "error");
          return;
        }
        await loadPolicy();
      } catch (e) {
        status.textContent = String(e && e.message ? e.message : e);
      }
    },
  });

  const userRowChildren = selfService ? [selfUserLabel] : [userSel];
  const cardParts = [
    el("div", { class: "card__title", text: t("title.workspacePaths") }),
    el("div", { class: "muted", text: t("workspacePaths.help") }),
  ];
  if (selfService) {
    cardParts.push(el("div", { class: "muted", style: "margin-top:6px;", text: t("workspacePaths.selfOnly") }));
  }
  cardParts.push(
    el("div", { style: "height:10px" }),
    el("div", { class: "row" }, [
      el("label", { text: t("workspacePaths.tenant") }),
      tenantSel,
    ]),
    el("div", { class: "row" }, [
      el("label", { text: t("workspacePaths.user") }),
      ...userRowChildren,
    ]),
    el("div", { class: "row" }, [el("label", { text: t("workspacePaths.extraRoots") })]),
    extraInput,
    el("label", { class: "row", style: "align-items:center;gap:8px;margin-top:8px;" }, [
      allowAnyCb,
      el("span", { text: t("workspacePaths.allowAny") }),
    ]),
    el("div", { class: "muted", style: "margin-top:6px;line-height:1.45;", text: t("workspacePaths.allowAnyHint") }),
    el("label", { class: "row", style: "align-items:center;gap:8px;margin-top:10px;" }, [
      allowHighToolsCb,
      el("span", { text: t("workspacePaths.allowHighTools") }),
    ]),
    el("div", { class: "muted", style: "margin-top:6px;line-height:1.45;", text: t("workspacePaths.allowHighToolsHint") }),
    el("div", { class: "row", style: "margin-top:10px;gap:8px;" }, [loadBtn, saveBtn]),
    el("div", { class: "muted", style: "margin-top:8px;" }, [el("span", { text: t("workspacePaths.status") + ": " }), status]),
  );
  return el("div", { class: "card" }, cardParts);
}

async function renderAttachments() {
  const status = el("div", { class: "muted", text: "" });
  const hint = el("div", { class: "muted", style: "line-height:1.45;", text: t("attachments.excelPolicyHint") });
  const loadBtn = el("button", { class: "btn", type: "button", text: t("action.refresh") });
  const saveBtn = el("button", { class: "btn btn--primary", type: "button", text: t("attachments.save") });
  const resetBtn = el("button", { class: "btn", type: "button", text: t("attachments.resetDefaults") });

  const rowInput = el("input", { class: "input", type: "number", min: "1", step: "1" });
  const colInput = el("input", { class: "input", type: "number", min: "1", step: "1" });
  const cellInput = el("input", { class: "input", type: "number", min: "1", step: "1" });
  const maxSheetsInput = el("input", { class: "input", type: "number", min: "1", step: "1" });
  const largePreviewRowsInput = el("input", { class: "input", type: "number", min: "1", step: "1" });
  const toolEnabledInput = el("input", { type: "checkbox" });
  const toolMinRowsInput = el("input", { class: "input", type: "number", min: "1", step: "1" });
  const toolMaxBytesInput = el("input", { class: "input", type: "number", min: "1", step: "1" });
  const sqlTimeoutInput = el("input", { class: "input", type: "number", min: "100", max: "120000", step: "1" });
  const imageReplayCapInput = el("input", { class: "input", type: "number", min: "600", max: "30000", step: "1" });
  const videoReplayCapInput = el("input", { class: "input", type: "number", min: "600", max: "30000", step: "1" });
  const videoTranscriptChunkSizeInput = el("input", { class: "input", type: "number", min: "1", max: "8000", step: "1" });
  const videoTranscriptChunkOverlapInput = el("input", { class: "input", type: "number", min: "1", max: "4000", step: "1" });
  const archiveMaxDepthInput = el("input", { class: "input", type: "number", min: "1", max: "10", step: "1" });
  const archiveMaxFileCountInput = el("input", { class: "input", type: "number", min: "1", max: "20000", step: "1" });
  const archiveMaxEntryBytesInput = el("input", { class: "input", type: "number", min: "1", step: "1" });
  const archiveMaxTotalBytesInput = el("input", { class: "input", type: "number", min: "1", step: "1" });

  const clampTimeout = (raw, fallback = 8000) => {
    const n = parseInt(String(raw ?? "").trim(), 10);
    if (!Number.isFinite(n)) return fallback;
    return Math.max(100, Math.min(120000, n));
  };

  const parsePositiveInt = (v) => {
    const n = parseInt(String(v ?? "").trim(), 10);
    if (!Number.isFinite(n) || n < 1) return null;
    return n;
  };

  const readUiLimits = () => {
    const rows = parsePositiveInt(rowInput.value);
    const cols = parsePositiveInt(colInput.value);
    const chars = parsePositiveInt(cellInput.value);
    const maxSheets = parsePositiveInt(maxSheetsInput.value);
    const previewRows = parsePositiveInt(largePreviewRowsInput.value);
    const minRows = parsePositiveInt(toolMinRowsInput.value);
    const maxBytes = parsePositiveInt(toolMaxBytesInput.value);
    const sqlTimeoutMs = parsePositiveInt(sqlTimeoutInput.value);
    const imageReplayCapChars = parsePositiveInt(imageReplayCapInput.value);
    const videoReplayCapChars = parsePositiveInt(videoReplayCapInput.value);
    const videoTranscriptChunkSize = parsePositiveInt(videoTranscriptChunkSizeInput.value);
    const videoTranscriptChunkOverlap = parsePositiveInt(videoTranscriptChunkOverlapInput.value);
    const archiveMaxDepth = parsePositiveInt(archiveMaxDepthInput.value);
    const archiveMaxFileCount = parsePositiveInt(archiveMaxFileCountInput.value);
    const archiveMaxEntryBytes = parsePositiveInt(archiveMaxEntryBytesInput.value);
    const archiveMaxTotalBytes = parsePositiveInt(archiveMaxTotalBytesInput.value);
    if (
      rows === null ||
      cols === null ||
      chars === null ||
      maxSheets === null ||
      previewRows === null ||
      minRows === null ||
      maxBytes === null ||
      sqlTimeoutMs === null ||
      imageReplayCapChars === null ||
      videoReplayCapChars === null ||
      videoTranscriptChunkSize === null ||
      videoTranscriptChunkOverlap === null ||
      archiveMaxDepth === null ||
      archiveMaxFileCount === null ||
      archiveMaxEntryBytes === null ||
      archiveMaxTotalBytes === null
    ) {
      throw new Error(t("attachments.invalidNumber"));
    }
    if (previewRows > 200 && !window.confirm(t("attachments.highPreviewWarn"))) {
      throw new Error("cancelled");
    }
    return {
      max_rows_read: rows,
      max_columns: cols,
      max_cell_chars: chars,
      max_excel_sheets: maxSheets,
      large_table_preview_rows: previewRows,
      tool_mode_enabled: !!toolEnabledInput.checked,
      tool_mode_min_rows: minRows,
      tool_mode_max_bytes: maxBytes,
      sql_timeout_ms: clampTimeout(sqlTimeoutMs, 8000),
      image_result_replay_cap_chars: Math.max(600, Math.min(30000, imageReplayCapChars)),
      video_result_replay_cap_chars: Math.max(600, Math.min(30000, videoReplayCapChars)),
      video_transcript_chunk_size: Math.max(1, Math.min(8000, videoTranscriptChunkSize)),
      video_transcript_chunk_overlap: Math.max(1, Math.min(4000, videoTranscriptChunkOverlap)),
      archive_max_depth: Math.max(1, Math.min(10, archiveMaxDepth)),
      archive_max_file_count: Math.max(1, Math.min(20000, archiveMaxFileCount)),
      archive_max_entry_bytes: Math.max(1, archiveMaxEntryBytes),
      archive_max_total_uncompressed_bytes: Math.max(1, archiveMaxTotalBytes),
    };
  };

  const applyUiLimits = (limits) => {
    const l = limits && typeof limits === "object" ? limits : {};
    rowInput.value = String(l.max_rows_read || 5000);
    colInput.value = String(l.max_columns || 200);
    cellInput.value = String(l.max_cell_chars || 500);
    maxSheetsInput.value = String(l.max_excel_sheets || 50);
    largePreviewRowsInput.value = String(l.large_table_preview_rows || 20);
    toolEnabledInput.checked = !!l.tool_mode_enabled;
    toolMinRowsInput.value = String(l.tool_mode_min_rows || 5000);
    toolMaxBytesInput.value = String(l.tool_mode_max_bytes || 31457280);
    sqlTimeoutInput.value = String(clampTimeout(l.sql_timeout_ms, 8000));
    imageReplayCapInput.value = String(Math.max(600, Math.min(30000, parsePositiveInt(l.image_result_replay_cap_chars) || 4000)));
    videoReplayCapInput.value = String(Math.max(600, Math.min(30000, parsePositiveInt(l.video_result_replay_cap_chars) || 4000)));
    videoTranscriptChunkSizeInput.value = String(Math.max(1, Math.min(8000, parsePositiveInt(l.video_transcript_chunk_size) || 1600)));
    videoTranscriptChunkOverlapInput.value = String(Math.max(1, Math.min(4000, parsePositiveInt(l.video_transcript_chunk_overlap) || 200)));
    archiveMaxDepthInput.value = String(Math.max(1, Math.min(10, parsePositiveInt(l.archive_max_depth) || 2)));
    archiveMaxFileCountInput.value = String(Math.max(1, Math.min(20000, parsePositiveInt(l.archive_max_file_count) || 200)));
    archiveMaxEntryBytesInput.value = String(Math.max(1, parsePositiveInt(l.archive_max_entry_bytes) || 10485760));
    archiveMaxTotalBytesInput.value = String(Math.max(1, parsePositiveInt(l.archive_max_total_uncompressed_bytes) || 52428800));
  };

  const load = async () => {
    status.textContent = t("chat.loading");
    try {
      const r = await apiGet("/admin/api/chat/settings/attachment-limits");
      const limits = r && typeof r.limits === "object" ? r.limits : {};
      applyUiLimits(limits);
      status.textContent = "";
    } catch (_) {
      status.textContent = t("attachments.loadError");
    }
  };

  const save = async () => {
    status.textContent = t("chat.sending");
    try {
      const next = readUiLimits();
      await apiPost("/admin/api/chat/settings/attachment-limits", { limits: next });
      status.textContent = t("attachments.saved");
      setTimeout(() => {
        if (status.textContent === t("attachments.saved")) status.textContent = "";
      }, 1500);
    } catch (e) {
      if (String(e && e.message ? e.message : e) === "cancelled") {
        status.textContent = "";
        return;
      }
      status.textContent = `${t("common.error")}: ${String(e)}`;
    }
  };

  const reset = async () => {
    status.textContent = t("chat.sending");
    try {
      const resp = await apiPost("/admin/api/chat/settings/attachment-limits", { limits: null });
      const limits = resp && typeof resp.limits === "object" ? resp.limits : {};
      applyUiLimits(limits);
      status.textContent = t("attachments.saved");
      setTimeout(() => {
        if (status.textContent === t("attachments.saved")) status.textContent = "";
      }, 1500);
    } catch (e) {
      status.textContent = `${t("common.error")}: ${String(e)}`;
    }
  };

  loadBtn.addEventListener("click", load);
  saveBtn.addEventListener("click", save);
  resetBtn.addEventListener("click", reset);
  await load();

  const inputRow = (labelText, inputEl) =>
    el("div", { style: "display:grid;gap:6px;margin-top:8px;" }, [
      el("div", { class: "muted", text: labelText }),
      inputEl,
    ]);

  return renderPageShell({
    title: t("attachments.title"),
    subtitle: "附件处理阈值、预算与回放策略配置",
    actions: [loadBtn, resetBtn, saveBtn],
    sections: [
      { id: "attach-overview", label: "说明" },
      { id: "attach-table", label: "表格" },
      { id: "attach-media", label: "图像/视频" },
      { id: "attach-archive", label: "压缩包" },
    ],
  }, [
    renderSectionCard("策略说明", t("attachments.excelPolicy"), [hint], { id: "attach-overview" }),
    el("div", { class: "page-grid page-grid--two" }, [
      renderSectionCard("表格与工具模式", "", [
        inputRow(t("attachments.maxRowsRead"), rowInput),
        inputRow(t("attachments.maxColumns"), colInput),
        inputRow(t("attachments.maxCellChars"), cellInput),
        inputRow(t("attachments.maxExcelSheets"), maxSheetsInput),
        inputRow(t("attachments.largePreviewRows"), largePreviewRowsInput),
        el("label", { class: "muted", style: "display:flex;gap:8px;align-items:center;margin-top:10px;cursor:pointer;" }, [
          toolEnabledInput,
          el("span", { text: t("attachments.toolModeEnabled") }),
        ]),
        inputRow(t("attachments.toolModeMinRows"), toolMinRowsInput),
        inputRow(t("attachments.toolModeMaxBytes"), toolMaxBytesInput),
        inputRow(t("attachments.sqlTimeoutMs"), sqlTimeoutInput),
        el("div", { class: "muted", style: "margin-top:6px;line-height:1.45;", text: t("attachments.sqlTimeoutHint") }),
      ], { id: "attach-table" }),
      renderSectionCard("图像与视频策略", "", [
        inputRow(t("attachments.imageReplayCapChars"), imageReplayCapInput),
        el("div", { class: "muted", style: "margin-top:6px;line-height:1.45;", text: t("attachments.imageReplayCapHint") }),
        inputRow(t("attachments.videoReplayCapChars"), videoReplayCapInput),
        el("div", { class: "muted", style: "margin-top:6px;line-height:1.45;", text: t("attachments.videoReplayCapHint") }),
        inputRow(t("attachments.videoTranscriptChunkSize"), videoTranscriptChunkSizeInput),
        inputRow(t("attachments.videoTranscriptChunkOverlap"), videoTranscriptChunkOverlapInput),
        el("div", { class: "muted", style: "margin-top:6px;line-height:1.45;", text: t("attachments.videoTranscriptChunkHint") }),
      ], { id: "attach-media" }),
    ]),
    renderSectionCard("压缩包预算策略", "", [
      inputRow(t("attachments.archiveMaxDepth"), archiveMaxDepthInput),
      inputRow(t("attachments.archiveMaxFileCount"), archiveMaxFileCountInput),
      inputRow(t("attachments.archiveMaxEntryBytes"), archiveMaxEntryBytesInput),
      inputRow(t("attachments.archiveMaxTotalBytes"), archiveMaxTotalBytesInput),
      el("div", { class: "muted", style: "margin-top:6px;line-height:1.45;", text: t("attachments.archivePolicyHint") }),
      el("div", { style: "height:8px" }),
      status,
    ], { id: "attach-archive" }),
  ]);
}

async function renderProfile() {
  const status = el("div", { class: "muted", text: "" });
  const dnInput = el("input", { class: "input", type: "text", maxlength: "120" });
  const metaUser = el("div", { class: "muted pre", text: "" });
  const metaIds = el("div", { class: "muted pre", text: "" });
  const avatarPreview = el("img", {
    class: "profile-avatar-preview",
    alt: "",
    style:
      "display:none;width:48px;height:48px;border-radius:999px;object-fit:contain;border:2px solid rgba(255,255,255,0.12);background:rgba(255,255,255,0.08);padding:5px;box-sizing:border-box;",
  });
  const avatarRow = el("div", { class: "row", style: "align-items:center;gap:16px;flex-wrap:wrap;" }, [
    el("div", {}, [avatarPreview]),
    el("div", { style: "min-width:200px;flex:1;" }, [
      el("div", { class: "muted", style: "margin-bottom:6px;", text: t("profile.avatar") }),
      el("div", { class: "muted", style: "margin-bottom:8px;font-size:12px;line-height:1.4;", text: t("profile.avatarHint") }),
    ]),
  ]);
  const fileInput = el("input", { type: "file", accept: "image/png,image/jpeg,image/jpg,image/webp,image/gif", style: "display:none" });
  const chooseBtn = el("button", { class: "btn", type: "button", text: t("profile.chooseImage") });
  const removeBtn = el("button", { class: "btn", type: "button", text: t("profile.removeAvatar") });
  const saveBtn = el("button", { class: "btn btn--primary", type: "button", text: t("profile.save") });
  const chatBtn = el("button", { class: "btn", type: "button", text: t("profile.openChat") });

  function showBuiltinDefaultAvatar() {
    try {
      const prev = avatarPreview.dataset.blobUrl;
      if (prev) URL.revokeObjectURL(prev);
    } catch (_) {}
    delete avatarPreview.dataset.blobUrl;
    avatarPreview.src = resolveAdminApiUrl("/admin/assets/default-user-avatar.svg");
    avatarPreview.style.objectFit = "contain";
    avatarPreview.style.padding = "5px";
    avatarPreview.style.background = "rgba(255,255,255,0.08)";
    avatarPreview.style.display = "block";
  }

  /** <img> cannot send Authorization; load avatar via fetch + blob */
  async function refreshAvatarBlob(p) {
    const aid = p && String(p.avatar_attachment_id || "").trim();
    if (!aid) {
      showBuiltinDefaultAvatar();
      return;
    }
    try {
      const tok = getStoredAuthToken();
      const u = resolveAdminApiUrl(`/admin/api/chat/attachments/${encodeURIComponent(aid)}`);
      const res = await fetch(u, { headers: tok ? { authorization: `Bearer ${tok}` } : {} });
      if (!res.ok) throw new Error("avatar fetch");
      const blob = await res.blob();
      try {
        const prev = avatarPreview.dataset.blobUrl;
        if (prev) URL.revokeObjectURL(prev);
      } catch (_) {}
      const url = URL.createObjectURL(blob);
      avatarPreview.dataset.blobUrl = url;
      avatarPreview.src = url;
      avatarPreview.style.objectFit = "cover";
      avatarPreview.style.padding = "0";
      avatarPreview.style.background = "transparent";
      avatarPreview.style.display = "block";
    } catch (_) {
      showBuiltinDefaultAvatar();
    }
  }

  async function load() {
    status.textContent = t("chat.loading");
    try {
      const r = await apiGet("/admin/api/chat/profile");
      if (!r || !r.ok || !r.profile) throw new Error("profile");
      const p = r.profile;
      dnInput.value = String(p.display_name || "");
      metaUser.textContent = `${t("profile.username")}: ${String(p.username || "—")}\n${t("profile.role")}: ${String(p.role || "—")}`;
      metaIds.textContent = `${t("profile.userId")}: ${String(p.id || "—")}\n${t("profile.tenantId")}: ${String(p.tenant_id || "—")}\n${t("profile.createdAt")}: ${String(p.created_at || "—")}`;
      await refreshAvatarBlob(p);
      status.textContent = "";
    } catch (e) {
      status.textContent = `${t("profile.loadError")}: ${String(e && e.message ? e.message : e)}`;
    }
  }

  chooseBtn.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", async () => {
    const f = fileInput.files && fileInput.files[0];
    fileInput.value = "";
    if (!f) return;
    status.textContent = t("chat.sending");
    try {
      const fd = new FormData();
      fd.append("file", f, f.name || "avatar.png");
      const r = await apiPostFormData("/admin/api/chat/profile/avatar", fd);
      if (!r || !r.ok) throw new Error("upload");
      status.textContent = t("profile.saved");
      await load();
    } catch (e) {
      status.textContent = `${t("profile.uploadError")}: ${String(e && e.message ? e.message : e)}`;
    }
  });
  removeBtn.addEventListener("click", async () => {
    status.textContent = t("chat.sending");
    try {
      await apiDeleteJson("/admin/api/chat/profile/avatar");
      status.textContent = t("profile.saved");
      await load();
    } catch (e) {
      status.textContent = String(e && e.message ? e.message : e);
    }
  });
  saveBtn.addEventListener("click", async () => {
    status.textContent = t("chat.sending");
    try {
      await apiRequest("PATCH", "/admin/api/chat/profile", { display_name: dnInput.value.trim() });
      status.textContent = t("profile.saved");
      await load();
      try {
        const sess = JSON.parse(authStoreGet(AUTH_SESSION_KEY) || "{}");
        if (sess && typeof sess === "object") {
          sess.display_name = dnInput.value.trim();
          authStoreSet(AUTH_SESSION_KEY, JSON.stringify(sess));
          authSession = sess;
        }
      } catch (_) {}
    } catch (e) {
      status.textContent = String(e && e.message ? e.message : e);
    }
  });
  chatBtn.addEventListener("click", () => {
    window.location.assign(resolveChatUrl());
  });

  await load();

  const profileCard = el("div", { class: "card" }, [
    el("div", { class: "card__title", text: t("title.profile") }),
    el("div", { class: "muted", style: "margin-bottom:10px;line-height:1.45;", text: t("profile.help") }),
    el("div", { class: "row" }, [el("label", { text: t("profile.displayName") }), dnInput]),
    el("div", { style: "height:8px" }),
    avatarRow,
    el("div", { class: "row", style: "margin-top:10px;gap:8px;flex-wrap:wrap;" }, [fileInput, chooseBtn, removeBtn]),
    el("div", { class: "row", style: "margin-top:12px;gap:8px;flex-wrap:wrap;" }, [saveBtn, chatBtn]),
    el("div", { style: "height:8px" }),
    el("div", { style: "margin-top:14px" }, [metaUser]),
    el("div", { style: "margin-top:6px" }, [metaIds]),
    el("div", { class: "muted", style: "margin-top:10px;" }, [status]),
  ]);
  return el("div", {}, [profileCard]);
}

async function renderSkills() {
  const SKILL_AUDIT_RETRYABLE_ONLY_KEY = "ops_admin_skill_audit_retryable_only";
  const status = el("div", { class: "muted", text: "" });
  const rowsState = { items: [] };
  const auditState = { items: [] };
  const nameInp = el("input", { class: "input", placeholder: "skill name" });
  const descInp = el("input", { class: "input", placeholder: "description" });
  const bodyInp = el("textarea", { class: "input", rows: "4", placeholder: "SKILL.md body markdown" });
  const regInp = el("input", { class: "input", placeholder: "registry archive URL (zip/tar)" });
  const localDirInp = el("input", { class: "input", placeholder: "local skill dir (contains SKILL.md)" });
  const marketStatus = el("div", { class: "muted", text: "" });
  const skillModeStatus = el("div", { class: "muted", text: "" });
  const skillPromptModeCb = el("input", { type: "checkbox" });
  const skillToolcallModeCb = el("input", { type: "checkbox" });
  const skillMarketProviderSelect = el("select", { class: "input", style: "min-width:160px;" }, [
    el("option", { value: "clawhub", text: "clawhub (ClawHub)" }),
    el("option", { value: "cocoloop", text: "cocoloop (CocoLoop)" }),
  ]);
  const marketQ = el("input", { class: "input", placeholder: "search skills (keyword)" });
  const marketLimitInp = el("input", { class: "input", placeholder: "limit", value: "40", style: "max-width:120px;" });
  const marketTbody = el("tbody");
  const marketDetailPre = el("pre", { class: "muted pre", text: "" });
  let marketItems = [];

  const loadSkillMode = async () => {
    try {
      const r = await apiGet("/admin/api/skills/mode");
      skillPromptModeCb.checked = !!r.prompt_in_system;
      skillToolcallModeCb.checked = !!r.toolcall_enabled;
      const mp = String(r.market_provider || "clawhub").trim().toLowerCase();
      skillMarketProviderSelect.value = mp === "cocoloop" ? "cocoloop" : "clawhub";
      skillModeStatus.textContent = "";
    } catch (e) {
      skillModeStatus.textContent = `mode: ${String(e && e.message ? e.message : e)}`;
    }
  };
  const saveSkillMode = async () => {
    skillModeStatus.textContent = `${t("chat.loading")}...`;
    try {
      const r = await apiPost("/admin/api/skills/mode", {
        prompt_in_system: !!skillPromptModeCb.checked,
        toolcall_enabled: !!skillToolcallModeCb.checked,
        market_provider: String(skillMarketProviderSelect.value || "clawhub").trim(),
      });
      skillPromptModeCb.checked = !!r.prompt_in_system;
      skillToolcallModeCb.checked = !!r.toolcall_enabled;
      const mp = String(r.market_provider || "clawhub").trim().toLowerCase();
      skillMarketProviderSelect.value = mp === "cocoloop" ? "cocoloop" : "clawhub";
      skillModeStatus.textContent = `saved: prompt=${String(!!r.prompt_in_system)} toolcall=${String(!!r.toolcall_enabled)} market=${String(skillMarketProviderSelect.value)}`;
    } catch (e) {
      skillModeStatus.textContent = `mode: ${String(e && e.message ? e.message : e)}`;
    }
  };

  const loadMarket = async (q) => {
    const qq = String(q || "").trim();
    const lim = Math.max(1, Math.min(200, parseInt(String(marketLimitInp.value || "40"), 10) || 40));
    marketStatus.textContent = `${t("chat.loading")}...`;
    try {
      const resp = await apiGet(`/admin/api/skills/market/search?q=${encodeURIComponent(qq)}&limit=${encodeURIComponent(String(lim))}`);
      marketItems = Array.isArray(resp.items) ? resp.items : [];
      marketStatus.textContent = `results: ${marketItems.length}`;
      repaintMarket();
    } catch (e) {
      marketItems = [];
      marketStatus.textContent = `${t("common.error")}: ${String(e && e.message ? e.message : e)}`;
      repaintMarket();
    }
  };

  const loadMarketDetail = async (slug) => {
    const s = String(slug || "").trim();
    if (!s) return;
    marketDetailPre.textContent = `${t("chat.loading")}...`;
    try {
      const resp = await apiGet(`/admin/api/skills/market/detail?slug=${encodeURIComponent(s)}`);
      marketDetailPre.textContent = JSON.stringify(resp.detail || {}, null, 2);
    } catch (e) {
      marketDetailPre.textContent = `${t("common.error")}: ${String(e && e.message ? e.message : e)}`;
    }
  };

  const installFromMarket = async (slug, version) => {
    const s = String(slug || "").trim();
    if (!s) return;
    marketStatus.textContent = `installing: ${s}...`;
    openSkillInstallModal(`Installing ${s}...`);
    try {
      const r = await apiPost("/admin/api/skills/market/install", { slug: s, version: version ? String(version) : undefined, overwrite: false });
      assertSkillMutationOk(r, "Market install failed");
      status.textContent = `install-market success: ${JSON.stringify(r.result || {})}`;
      marketStatus.textContent = `installed: ${s}`;
      await refreshSkillsState();
      finishSkillInstallModal(true, `${s} installed successfully.`);
    } catch (e) {
      status.textContent = String(e && e.message ? e.message : e);
      marketStatus.textContent = `install failed: ${s}`;
      finishSkillInstallModal(false, `Install failed: ${String(e && e.message ? e.message : e)}`);
    }
  };

  const repaintMarket = () => {
    marketTbody.innerHTML = "";
    (marketItems || []).forEach((x) => {
      const slug = String(x.slug || "");
      const ver = String(x.version || "");
      const btnDetail = el("button", { class: "btn btn--small", text: "Detail", onclick: async () => await loadMarketDetail(slug) });
      marketTbody.appendChild(
        el("tr", {}, [
          el("td", { text: slug }),
          el("td", { text: String(x.name || "") }),
          el("td", { text: ver }),
          el("td", { text: shortText(String(x.description || ""), 80) }),
          el("td", {}, [btnDetail]),
        ]),
      );
    });
  };

  const btnMarketSearch = el("button", { class: "btn", text: "Search", onclick: async () => await loadMarket(marketQ.value) });
  const btnMarketLatest = el("button", { class: "btn", text: "Latest", onclick: async () => await loadMarket("") });
  const marketBox = el("details", { style: "margin:10px 0 14px 0;" }, [
    el("summary", { text: "Skill market (ClawHub / CocoLoop)", style: "cursor:pointer;user-select:none;" }),
    el("div", { style: "height:8px" }),
    el("div", { class: "row", style: "gap:8px;flex-wrap:wrap;margin-bottom:8px;" }, [marketQ, marketLimitInp, btnMarketSearch, btnMarketLatest]),
    marketStatus,
    el("div", { style: "height:8px" }),
    el("div", { class: "table-wrap" }, [
      el("table", { class: "table table--compact" }, [
        el("thead", {}, [el("tr", {}, [el("th", { text: "slug" }), el("th", { text: "name" }), el("th", { text: "version" }), el("th", { text: "description" }), el("th", { text: "action" })])]),
        marketTbody,
      ]),
    ]),
    el("div", { style: "height:8px" }),
    el("div", { class: "muted", text: "Detail" }),
    marketDetailPre,
  ]);

  const skillBindingState = { roles: [], names: [], mapping: {}, enabled: false, managerInherit: true };
  const skillBindingStatus = el("div", { class: "muted", text: "" });
  const skillBindingPersistHint = el("div", {
    class: "muted",
    style: "margin:6px 0;line-height:1.5;",
    text: "Checkboxes and per-role skill lists are not saved until you click Save skill role binding.",
  });
  const skillBindingEnvHint = el("div", {
    class: "muted",
    style: "margin:6px 0;line-height:1.5;display:none;",
  });
  const skillEffectiveState = { items: [] };
  const skillBindingEnabledCb = el("input", { type: "checkbox" });
  const skillBindingManagerInheritCb = el("input", { type: "checkbox" });
  const skillRoleSelect = el("select", { class: "input" }, []);
  const skillBindingListWrap = el("div");
  const skillBindingDashTbody = el("tbody");
  const skillEffectiveTbody = el("tbody");
  const renderSkillBindingDashboard = () => {
    skillBindingDashTbody.innerHTML = "";
    const roles = Array.isArray(skillBindingState.roles) ? skillBindingState.roles : [];
    const mapping = skillBindingState.mapping && typeof skillBindingState.mapping === "object" ? skillBindingState.mapping : {};
    const managerBound = new Set(Array.isArray(mapping.manager) ? mapping.manager.map((x) => String(x)) : []);
    const inheritManager = !!skillBindingState.managerInherit;
    roles.forEach((role) => {
      const direct = new Set(Array.isArray(mapping[role]) ? mapping[role].map((x) => String(x)) : []);
      const effective = new Set([...(role === "manager" || !inheritManager ? [] : Array.from(managerBound)), ...Array.from(direct)]);
      skillBindingDashTbody.appendChild(
        el("tr", {}, [
          el("td", { text: role }),
          el("td", { text: String(direct.size) }),
          el("td", { text: String(effective.size) }),
        ]),
      );
    });
    if (!roles.length) {
      skillBindingDashTbody.appendChild(el("tr", {}, [el("td", { text: "-", colspan: "3" })]));
    }
  };
  const renderSkillEffectiveDashboard = () => {
    skillEffectiveTbody.innerHTML = "";
    const rows = Array.isArray(skillEffectiveState.items) ? skillEffectiveState.items : [];
    rows.forEach((x) => {
      const names = Array.isArray(x.names_preview) ? x.names_preview.map((v) => String(v || "").trim()).filter(Boolean) : [];
      const docsOnlyNames = Array.isArray(x.docs_only_names_preview)
        ? x.docs_only_names_preview.map((v) => String(v || "").trim()).filter(Boolean)
        : [];
      const previewText = names.slice(0, 6).join(", ");
      const namesCell = names.length
        ? el("details", {}, [
          el("summary", { text: previewText || "(empty)" }),
          el("div", { class: "muted", style: "margin-top:4px;white-space:normal;line-height:1.5;", text: names.join(", ") }),
        ])
        : el("span", { class: "muted", text: "-" });
      const docsOnlyCell = docsOnlyNames.length
        ? el("details", {}, [
          el("summary", { text: docsOnlyNames.slice(0, 4).join(", ") }),
          el("div", { class: "muted", style: "margin-top:4px;white-space:normal;line-height:1.5;", text: docsOnlyNames.join(", ") }),
        ])
        : el("span", { class: "muted", text: "-" });
      skillEffectiveTbody.appendChild(
        el("tr", {}, [
          el("td", { text: String(x.role || "") }),
          el("td", { text: String(x.total || 0) }),
          el("td", { text: String(x.workspace_total || 0) }),
          el("td", { text: String(x.workspace_direct || 0) }),
          el("td", { text: String(x.workspace_inherited_manager || 0) }),
          el("td", { text: String(x.workspace_resolved_tool_match || 0) }),
          el("td", { text: String(x.workspace_docs_only || 0) }),
          el("td", { text: String(x.mcp_total || 0) }),
          el("td", { text: String(x.tool_total || 0) }),
          el("td", {}, [docsOnlyCell]),
          el("td", {}, [namesCell]),
        ]),
      );
    });
    if (!rows.length) {
      skillEffectiveTbody.appendChild(el("tr", {}, [el("td", { text: "-", colspan: "11" })]));
    }
  };
  const loadSkillEffective = async () => {
    try {
      const r = await apiGet("/admin/api/skills/effective");
      skillEffectiveState.items = Array.isArray(r.items) ? r.items : [];
      renderSkillEffectiveDashboard();
    } catch (e) {
      skillEffectiveState.items = [];
      renderSkillEffectiveDashboard();
      skillBindingStatus.textContent = `effective: ${String(e && e.message ? e.message : e)}`;
    }
  };
  const renderSkillBindingList = () => {
    const current = String(skillRoleSelect.value || "");
    const draft = skillBindingState.mapping;
    const existing = Array.isArray(draft[current]) ? draft[current].map((x) => String(x)) : [];
    const selected = new Set(existing);
    skillBindingListWrap.innerHTML = "";
    const skills =
      skillBindingState.names.length > 0
        ? skillBindingState.names
        : (Array.isArray(rowsState.items) ? rowsState.items.map((x) => String(x.name || "").trim()).filter(Boolean) : []);
    if (!skills.length) {
      skillBindingListWrap.appendChild(el("div", { class: "muted", text: "No installed skills yet." }));
      return;
    }
    skills.forEach((nm) => {
      const cb = el("input", { type: "checkbox" });
      cb.checked = selected.has(nm);
      cb.addEventListener("change", () => {
        const prev = new Set(Array.isArray(draft[current]) ? draft[current].map((x) => String(x)) : []);
        if (cb.checked) prev.add(nm);
        else prev.delete(nm);
        draft[current] = Array.from(prev);
      });
      skillBindingListWrap.appendChild(el("label", { class: "row", style: "gap:6px;align-items:center;" }, [cb, el("span", { text: nm })]));
    });
  };
  const loadSkillBinding = async () => {
    try {
      const r = await apiGet("/admin/api/skills/binding");
      skillBindingState.roles = Array.isArray(r.available_roles) ? r.available_roles : [];
      skillBindingState.names = (Array.isArray(r.installed_skills) ? r.installed_skills : [])
        .map((x) => String(x.name || "").trim())
        .filter(Boolean);
      skillBindingState.mapping = r.mapping && typeof r.mapping === "object" ? { ...r.mapping } : {};
      skillBindingState.enabled = !!r.enabled;
      skillBindingState.managerInherit = Object.prototype.hasOwnProperty.call(r, "manager_inherit") ? !!r.manager_inherit : true;
      skillBindingEnabledCb.checked = skillBindingState.enabled;
      skillBindingManagerInheritCb.checked = skillBindingState.managerInherit;
      if (r.enabled_env_present) {
        skillBindingEnvHint.style.display = "block";
        const stored = !!r.enabled_stored;
        const eff = !!r.enabled;
        skillBindingEnvHint.textContent =
          "Process env AIA_SKILL_ROLE_BINDING_ENABLED is set: it overrides the Admin/SQLite value at runtime. " +
          "The checkbox reflects the effective (env) value. Remove or unset that variable on the oclaw process to use Admin only. " +
          `(stored in DB: ${String(stored)}, effective: ${String(eff)}).`;
      } else {
        skillBindingEnvHint.style.display = "none";
        skillBindingEnvHint.textContent = "";
      }
      skillRoleSelect.innerHTML = "";
      skillBindingState.roles.forEach((role) => {
        skillRoleSelect.appendChild(el("option", { value: role, text: role }));
      });
      if (skillBindingState.roles.length && !skillRoleSelect.value) {
        skillRoleSelect.value = skillBindingState.roles[0];
      }
      renderSkillBindingList();
      renderSkillBindingDashboard();
      await loadSkillEffective();
      skillBindingStatus.textContent = "";
    } catch (e) {
      skillBindingStatus.textContent = `binding: ${String(e && e.message ? e.message : e)}`;
      skillBindingListWrap.innerHTML = "";
    }
  };
  skillRoleSelect.addEventListener("change", () => renderSkillBindingList());
  const btnSaveSkillBinding = el("button", {
    class: "btn btn--primary",
    text: "Save skill role binding",
    onclick: async () => {
      try {
        const r = await apiPost("/admin/api/skills/binding", {
          enabled: !!skillBindingEnabledCb.checked,
          manager_inherit: !!skillBindingManagerInheritCb.checked,
          mapping: skillBindingState.mapping,
        });
        skillBindingState.mapping = r.mapping && typeof r.mapping === "object" ? { ...r.mapping } : {};
        skillBindingState.enabled = !!r.enabled;
        skillBindingState.managerInherit = Object.prototype.hasOwnProperty.call(r, "manager_inherit") ? !!r.manager_inherit : true;
        skillBindingEnabledCb.checked = skillBindingState.enabled;
        skillBindingManagerInheritCb.checked = skillBindingState.managerInherit;
        if (r.enabled_env_present) {
          skillBindingEnvHint.style.display = "block";
          const stored = !!r.enabled_stored;
          const eff = !!r.enabled;
          skillBindingEnvHint.textContent =
            "Process env AIA_SKILL_ROLE_BINDING_ENABLED is set: it overrides the Admin/SQLite value at runtime. " +
            "The checkbox reflects the effective (env) value. Remove or unset that variable on the oclaw process to use Admin only. " +
            `(stored in DB: ${String(stored)}, effective: ${String(eff)}).`;
        } else {
          skillBindingEnvHint.style.display = "none";
          skillBindingEnvHint.textContent = "";
        }
        skillBindingStatus.textContent = `saved: enabled=${String(r.enabled)} manager_inherit=${String(skillBindingState.managerInherit)}`;
        renderSkillBindingList();
        renderSkillBindingDashboard();
        await loadSkillEffective();
      } catch (e) {
        skillBindingStatus.textContent = String(e && e.message ? e.message : e);
      }
    },
  });
  const skillBindingBox = el("details", { style: "margin:10px 0 14px 0;" }, [
    el("summary", { text: "Skill role binding (manager + specialists)", style: "cursor:pointer;user-select:none;" }),
    el("div", {
      class: "muted",
      style: "margin:8px 0;line-height:1.5;",
      text:
        "When enabled, the model skills catalog is filtered per role: each role sees only skills bound to that role (and optionally manager-bound skills), plus skills under skills/_workspace/public/. If nothing is bound yet, non-public skills are hidden until you assign them.",
    }),
    skillBindingStatus,
    skillBindingPersistHint,
    skillBindingEnvHint,
    el("label", { class: "row", style: "gap:8px;align-items:center;margin-top:6px;" }, [
      skillBindingEnabledCb,
      el("span", { text: "Enable role binding (AIA_SKILL_ROLE_BINDING_ENABLED)" }),
    ]),
    el("label", { class: "row", style: "gap:8px;align-items:center;margin-top:6px;" }, [
      skillBindingManagerInheritCb,
      el("span", { text: "Inherit manager skills to other roles (AIA_SKILL_ROLE_BINDING_MANAGER_INHERIT)" }),
    ]),
    el("div", { class: "row", style: "gap:8px;flex-wrap:wrap;margin-top:8px;align-items:center;" }, [
      el("label", { text: "Role" }),
      skillRoleSelect,
      btnSaveSkillBinding,
    ]),
    el("div", { class: "muted", style: "margin:8px 0 4px 0;", text: "Role binding dashboard" }),
    el("div", { class: "table-wrap" }, [
      el("table", { class: "table table--compact" }, [
        el("thead", {}, [el("tr", {}, [el("th", { text: "role" }), el("th", { text: "direct skills" }), el("th", { text: "effective" })])]),
        skillBindingDashTbody,
      ]),
    ]),
    el("div", { class: "muted", style: "margin:8px 0 4px 0;", text: "Effective skills dashboard (binding + inherited + MCP + tools)" }),
    el("div", { class: "table-wrap" }, [
      el("table", { class: "table table--compact" }, [
        el("thead", {}, [el("tr", {}, [
          el("th", { text: "role" }),
          el("th", { text: "total effective" }),
          el("th", { text: "workspace" }),
          el("th", { text: "direct bind" }),
          el("th", { text: "inherited manager" }),
          el("th", { text: "workspace resolved" }),
          el("th", { text: "workspace docs-only" }),
          el("th", { text: "mcp converted" }),
          el("th", { text: "other tools" }),
          el("th", { text: "docs-only names" }),
          el("th", { text: "names preview" }),
        ])]),
        skillEffectiveTbody,
      ]),
    ]),
    skillBindingListWrap,
  ]);

  const internalToolsState = { role: "", available_roles: [], tools: [], skipped_public: [], skipped_expert: [] };
  const lazyLoadState = { internalLoaded: false, llmLoaded: false, selfCheckLoaded: false, skillHealthLoaded: false };
  const internalToolsStatus = el("div", { class: "muted", text: "" });
  const internalRoleSelect = el("select", { class: "input" }, []);
  const internalToolsTbody = el("tbody");
  const internalSkippedPre = el("pre", { class: "muted pre", text: "" });
  const renderInternalTools = () => {
    internalToolsTbody.innerHTML = "";
    const rows = Array.isArray(internalToolsState.tools) ? internalToolsState.tools : [];
    rows.forEach((x) => {
      internalToolsTbody.appendChild(
        el("tr", {}, [
          el("td", { text: String(x.source || "") }),
          el("td", { text: String(x.name || "") }),
          el("td", { text: shortText(String(x.description || ""), 120) }),
          el("td", { text: String((Array.isArray(x.tags) ? x.tags.join(", ") : x.tags) || "") }),
          el("td", { text: String(x.read_only ? "1" : "0") }),
          el("td", { text: String(x.risk_level || "") }),
        ]),
      );
    });
    if (!rows.length) {
      internalToolsTbody.appendChild(el("tr", {}, [el("td", { text: "-", colspan: "6" })]));
    }
    const skipped = {
      skipped_public: Array.isArray(internalToolsState.skipped_public) ? internalToolsState.skipped_public : [],
      skipped_expert: Array.isArray(internalToolsState.skipped_expert) ? internalToolsState.skipped_expert : [],
    };
    internalSkippedPre.textContent = JSON.stringify(skipped, null, 2);
  };
  const loadInternalToolsPreview = async (role) => {
    const r = String(role || internalRoleSelect.value || "").trim();
    if (!r) return;
    internalToolsStatus.textContent = `${t("chat.loading")}...`;
    try {
      const resp = await apiGet(`/admin/api/tools/internal/preview?role=${encodeURIComponent(r)}`);
      internalToolsState.role = String(resp.role || "");
      internalToolsState.available_roles = Array.isArray(resp.available_roles) ? resp.available_roles : [];
      internalToolsState.tools = Array.isArray(resp.tools) ? resp.tools : [];
      internalToolsState.skipped_public = Array.isArray(resp.skipped_public) ? resp.skipped_public : [];
      internalToolsState.skipped_expert = Array.isArray(resp.skipped_expert) ? resp.skipped_expert : [];
      internalToolsStatus.textContent = `role=${internalToolsState.role} tools=${internalToolsState.tools.length}`;
      renderInternalTools();
    } catch (e) {
      internalToolsState.tools = [];
      internalToolsStatus.textContent = `preview: ${String(e && e.message ? e.message : e)}`;
      renderInternalTools();
    }
  };
  const btnInternalPreview = el("button", {
    class: "btn btn--primary",
    text: "Preview",
    onclick: async () => await loadInternalToolsPreview(internalRoleSelect.value),
  });
  const internalToolsBox = el("details", { style: "margin:10px 0 14px 0;" }, [
    el("summary", { text: "Internal tools preview (public + expert)", style: "cursor:pointer;user-select:none;" }),
    el("div", { class: "muted", style: "margin:8px 0;line-height:1.5;", text: "Preview dynamically loaded builtin tools for a role (public shared + expert-scoped)." }),
    internalToolsStatus,
    el("div", { class: "row", style: "gap:8px;flex-wrap:wrap;margin-top:8px;align-items:center;" }, [
      el("label", { text: "Role" }),
      internalRoleSelect,
      btnInternalPreview,
      el("button", {
        class: "btn",
        text: "Clear cache",
        onclick: async () => {
          try {
            await apiPost("/admin/api/tools/internal/reload", {});
            internalToolsStatus.textContent = "cache cleared";
            await loadInternalToolsPreview(internalRoleSelect.value);
          } catch (e) {
            internalToolsStatus.textContent = `reload: ${String(e && e.message ? e.message : e)}`;
          }
        },
      }),
    ]),
    el("div", { class: "table-wrap", style: "margin-top:8px" }, [
      el("table", { class: "table table--compact" }, [
        el("thead", {}, [el("tr", {}, [
          el("th", { text: "source" }),
          el("th", { text: "name" }),
          el("th", { text: "description" }),
          el("th", { text: "tags" }),
          el("th", { text: "read_only" }),
          el("th", { text: "risk" }),
        ])]),
        internalToolsTbody,
      ]),
    ]),
    el("div", { class: "muted", style: "margin-top:8px", text: "Skipped modules / factory errors" }),
    internalSkippedPre,
  ]);

  const llmToolsState = { role: "", tools_raw: [], tools_wired: [], removed_mcp_names: [], meta: {} };
  const llmToolsStatus = el("div", { class: "muted", text: "" });
  const llmRoleSelect = el("select", { class: "input" }, []);
  const llmTracePlanCb = el("input", { type: "checkbox" });
  const llmToolsTbody = el("tbody");
  const llmRemovedPre = el("pre", { class: "muted pre", text: "" });
  const llmModeBadge = el("span", { class: "badge badge--mode-restricted", text: "restricted" });
  const llmDiffPre = el("pre", { class: "muted pre", text: "" });
  const llmDiffTbody = el("tbody");
  const llmDiffTableWrap = el("div", { class: "table-wrap", style: "margin-top:8px" }, [
    el("table", { class: "table table--compact" }, [
      el("thead", {}, [el("tr", {}, [
        el("th", { text: "type" }),
        el("th", { text: "name" }),
        el("th", { text: "kind" }),
        el("th", { text: "details" }),
      ])]),
      llmDiffTbody,
    ]),
  ]);
  const selfCheckStatus = el("div", { class: "muted", text: "" });
  const selfCheckSummary = el("div", { class: "muted", text: "" });
  const selfCheckTbody = el("tbody");
  const selfCheckState = { data: null };
  const renderSelfCheck = (data) => {
    const body = data && typeof data === "object" ? data : {};
    selfCheckState.data = body;
    const summary = body.summary && typeof body.summary === "object" ? body.summary : {};
    const rolesTotal = Number(body.roles_total || 0);
    const totalInternal = Number(summary.total_internal_tools || 0);
    const totalWired = Number(summary.total_wired_tools || 0);
    const totalPermBan = Number(summary.total_perm_ban_9999 || 0);
    const items = Array.isArray(body.items) ? body.items : [];
    selfCheckSummary.textContent = `roles=${rolesTotal} internal=${totalInternal} wired=${totalWired} permBan9999=${totalPermBan}`;
    selfCheckTbody.innerHTML = "";
    items.forEach((x) => {
      const removedMcp = Number(x.removed_mcp_total || 0);
      const wired = Number(x.wired_count || 0);
      const mode = String(x.role_mode || "restricted");
      let health = "ok";
      if (mode === "forbidden" && wired === 0) health = "forbidden";
      else if (mode === "unrestricted") health = "unrestricted";
      else if (removedMcp > 0) health = "warning";
      const badgeCls =
        health === "warning"
          ? "badge badge--mode-restricted"
          : health === "forbidden"
            ? "badge badge--bad"
            : health === "unrestricted"
              ? "badge badge--mode-unrestricted"
              : "badge badge--ok";
      selfCheckTbody.appendChild(
        el("tr", {}, [
          el("td", { text: String(x.role || "") }),
          el("td", {}, [el("span", { class: badgeCls, text: health })]),
          el("td", { text: String(x.role_mode || "") }),
          el("td", { text: String(x.internal_count || 0) }),
          el("td", { text: String(x.raw_count || 0) }),
          el("td", { text: String(x.wired_count || 0) }),
          el("td", { text: String(x.removed_mcp_total || 0) }),
          el("td", { text: String(x.policy_perm_ban_9999 || 0) }),
        ]),
      );
    });
    if (!items.length) selfCheckTbody.appendChild(el("tr", {}, [el("td", { text: "-", colspan: "8" })]));
  };
  const runSelfCheck = async () => {
    selfCheckStatus.textContent = `${t("chat.loading")}...`;
    try {
      const resp = await apiGet("/admin/api/tools/self-check");
      renderSelfCheck(resp);
      selfCheckStatus.textContent = "self-check complete";
    } catch (e) {
      selfCheckStatus.textContent = `self-check: ${String(e && e.message ? e.message : e)}`;
      renderSelfCheck({});
    }
  };
  const exportSelfCheckJson = () => {
    const data = selfCheckState.data;
    if (!data || typeof data !== "object") {
      selfCheckStatus.textContent = "no self-check data to export";
      return;
    }
    try {
      const blob = new Blob([`${JSON.stringify(data, null, 2)}\n`], { type: "application/json;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const ts = new Date().toISOString().replace(/[:.]/g, "-");
      const a = document.createElement("a");
      a.href = url;
      a.download = `tools-self-check-${ts}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      selfCheckStatus.textContent = "self-check exported";
    } catch (e) {
      selfCheckStatus.textContent = `export failed: ${String(e && e.message ? e.message : e)}`;
    }
  };
  const selfCheckBox = el("details", { style: "margin:10px 0 14px 0;" }, [
    el("summary", { text: "Tools self-check", style: "cursor:pointer;user-select:none;" }),
    el("div", { class: "muted", style: "margin:8px 0;line-height:1.5;", text: "Run one-shot diagnostics across roles for internal/wired tools, role mode and permanent bans." }),
    selfCheckStatus,
    el("div", { class: "row", style: "gap:8px;align-items:center;margin-top:8px;" }, [
      el("button", { class: "btn btn--primary", text: "Run self-check", onclick: runSelfCheck }),
      el("button", { class: "btn", text: "Export self-check JSON", onclick: exportSelfCheckJson }),
      selfCheckSummary,
    ]),
    el("div", { class: "table-wrap", style: "margin-top:8px" }, [
      el("table", { class: "table table--compact" }, [
        el("thead", {}, [el("tr", {}, [
          el("th", { text: "role" }),
          el("th", { text: "health" }),
          el("th", { text: "mode" }),
          el("th", { text: "internal" }),
          el("th", { text: "raw" }),
          el("th", { text: "wired" }),
          el("th", { text: "removed mcp" }),
          el("th", { text: "perm ban(9999)" }),
        ])]),
        selfCheckTbody,
      ]),
    ]),
  ]);
  const skillHealthStatus = el("div", { class: "muted", text: "" });
  const skillHealthSummary = el("div", { class: "muted", text: "" });
  const skillHealthClassifyTbody = el("tbody");
  const skillHealthExecTbody = el("tbody");
  const skillHealthFailedOnlyCb = el("input", { type: "checkbox" });
  const skillHealthState = { data: null };
  const renderSkillHealthExecRows = () => {
    const body = skillHealthState.data && typeof skillHealthState.data === "object" ? skillHealthState.data : {};
    const checks = Array.isArray(body.execution_checks) ? body.execution_checks : [];
    const failedOnly = !!skillHealthFailedOnlyCb.checked;
    skillHealthExecTbody.innerHTML = "";
    checks
      .filter((x) => (failedOnly ? !x.ok : true))
      .slice(0, 30)
      .forEach((x) => {
        const ok = !!x.ok;
        const code = String(x.error_code || "");
        const truncated = !!x.output_truncated;
        skillHealthExecTbody.appendChild(
          el("tr", {}, [
            el("td", { text: String(x.name || "") }),
            el("td", {}, [ok ? el("span", { class: "badge badge--ok", text: "ok" }) : el("span", { class: "badge badge--bad", text: "fail" })]),
            el("td", { text: code || "-" }),
            el("td", { text: truncated ? "1" : "0" }),
            el("td", {}, [
              el("button", {
                class: "btn",
                text: "Test-run with args...",
                disabled: !String(x.name || "").trim(),
                onclick: () => {
                  const nm = String(x.name || "").trim();
                  if (!nm) return;
                  openSkillTestRunModal(nm);
                },
              }),
            ]),
          ]),
        );
      });
    if (!skillHealthExecTbody.children.length) {
      skillHealthExecTbody.appendChild(el("tr", {}, [el("td", { text: "-", colspan: "5" })]));
    }
  };
  const renderSkillHealthCheck = (data) => {
    const body = data && typeof data === "object" ? data : {};
    skillHealthState.data = body;
    const counts = body.classification_counts && typeof body.classification_counts === "object" ? body.classification_counts : {};
    const checks = Array.isArray(body.execution_checks) ? body.execution_checks : [];
    const skillsTotal = Number(body.skills_total || 0);
    const execTotal = Number(body.executable_total || 0);
    const checked = Number(body.execution_checked_total || 0);
    skillHealthSummary.textContent = `skills=${skillsTotal} executable=${execTotal} checked=${checked}`;
    skillHealthClassifyTbody.innerHTML = "";
    const countRows = Object.entries(counts).sort((a, b) => Number(b[1] || 0) - Number(a[1] || 0));
    countRows.forEach(([k, v]) => {
      skillHealthClassifyTbody.appendChild(el("tr", {}, [el("td", { text: String(k || "") }), el("td", { text: String(Number(v || 0)) })]));
    });
    if (!countRows.length) {
      skillHealthClassifyTbody.appendChild(el("tr", {}, [el("td", { text: "-", colspan: "2" })]));
    }
    renderSkillHealthExecRows();
  };
  skillHealthFailedOnlyCb.addEventListener("change", () => renderSkillHealthExecRows());
  const runSkillHealthCheck = async () => {
    skillHealthStatus.textContent = `${t("chat.loading")}...`;
    try {
      const resp = await apiGet("/admin/api/skills/self-check?include_execution=true");
      renderSkillHealthCheck(resp);
      skillHealthStatus.textContent = "skill self-check complete";
    } catch (e) {
      skillHealthStatus.textContent = `skill self-check: ${String(e && e.message ? e.message : e)}`;
      renderSkillHealthCheck({});
    }
  };
  const exportSkillHealthJson = () => {
    const data = skillHealthState.data;
    if (!data || typeof data !== "object") {
      skillHealthStatus.textContent = "no skills self-check data to export";
      return;
    }
    try {
      const blob = new Blob([`${JSON.stringify(data, null, 2)}\n`], { type: "application/json;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const ts = new Date().toISOString().replace(/[:.]/g, "-");
      const a = document.createElement("a");
      a.href = url;
      a.download = `skills-self-check-${ts}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      skillHealthStatus.textContent = "skills self-check exported";
    } catch (e) {
      skillHealthStatus.textContent = `export failed: ${String(e && e.message ? e.message : e)}`;
    }
  };
  const skillHealthBox = el("details", { style: "margin:10px 0 14px 0;" }, [
    el("summary", { text: "Skills health self-check", style: "cursor:pointer;user-select:none;" }),
    el("div", { class: "muted", style: "margin:8px 0;line-height:1.5;", text: "Run executable skill diagnostics and show failure code distribution." }),
    skillHealthStatus,
    el("div", { class: "row", style: "gap:8px;align-items:center;margin-top:8px;" }, [
      el("button", { class: "btn btn--primary", text: "Run skills self-check", onclick: runSkillHealthCheck }),
      el("button", { class: "btn", text: "Export skills self-check JSON", onclick: exportSkillHealthJson }),
      el("label", { class: "row", style: "gap:6px;align-items:center;" }, [
        skillHealthFailedOnlyCb,
        el("span", { class: "muted", text: "Only failed items" }),
      ]),
      skillHealthSummary,
    ]),
    el("div", { class: "row", style: "gap:12px;align-items:flex-start;flex-wrap:wrap;margin-top:8px;" }, [
      el("div", { class: "table-wrap", style: "min-width:280px;flex:1;" }, [
        el("div", { class: "muted", style: "margin:0 0 6px 0;", text: "classification_counts" }),
        el("table", { class: "table table--compact" }, [
          el("thead", {}, [el("tr", {}, [el("th", { text: "code" }), el("th", { text: "count" })])]),
          skillHealthClassifyTbody,
        ]),
      ]),
      el("div", { class: "table-wrap", style: "min-width:360px;flex:2;" }, [
        el("div", { class: "muted", style: "margin:0 0 6px 0;", text: "execution_checks (top 30)" }),
        el("table", { class: "table table--compact" }, [
          el("thead", {}, [el("tr", {}, [el("th", { text: "skill" }), el("th", { text: "status" }), el("th", { text: "error_code" }), el("th", { text: "output_truncated" }), el("th", { text: "action" })])]),
          skillHealthExecTbody,
        ]),
      ]),
    ]),
  ]);

  const _renderLLMToolRows = (tools) => {
    llmToolsTbody.innerHTML = "";
    const rows = Array.isArray(tools) ? tools : [];
    rows.forEach((ent) => {
      const fn = ent && typeof ent === "object" ? ent.function : null;
      const name = fn && typeof fn === "object" ? String(fn.name || "") : "";
      const desc = fn && typeof fn === "object" ? String(fn.description || "") : "";
      const params = fn && typeof fn === "object" ? fn.parameters : null;
      llmToolsTbody.appendChild(
        el("tr", {}, [
          el("td", { text: name }),
          el("td", { text: shortText(desc, 140) }),
          el("td", { text: name.startsWith("mcp__") ? "mcp" : "internal" }),
          el("td", { text: params ? shortText(JSON.stringify(params), 120) : "" }),
        ]),
      );
    });
    if (!rows.length) {
      llmToolsTbody.appendChild(el("tr", {}, [el("td", { text: "-", colspan: "4" })]));
    }
  };

  const loadLLMToolsPreview = async (role) => {
    const r = String(role || llmRoleSelect.value || "").trim();
    if (!r) return;
    llmToolsStatus.textContent = `${t("chat.loading")}...`;
    try {
      const resp = await apiGet(`/admin/api/tools/llm/preview?role=${encodeURIComponent(r)}`);
      llmToolsState.role = String(resp.role || "");
      llmToolsState.tools_raw = Array.isArray(resp.tools_raw) ? resp.tools_raw : [];
      llmToolsState.tools_wired = Array.isArray(resp.tools_wired) ? resp.tools_wired : [];
      llmToolsState.removed_mcp_names = Array.isArray(resp.removed_mcp_names) ? resp.removed_mcp_names : [];
      llmToolsState.meta = resp && typeof resp === "object" ? resp : {};
      const mode = String(resp.role_mode || "restricted");
      llmModeBadge.textContent = mode;
      llmModeBadge.className = `badge badge--mode-${mode}`;
      llmToolsStatus.textContent = `role=${llmToolsState.role} raw=${llmToolsState.tools_raw.length} wired=${llmToolsState.tools_wired.length} mcp_enabled=${String(!!resp.mcp_enabled)}`;
      llmRemovedPre.textContent = JSON.stringify(
        {
          removed_mcp_names: llmToolsState.removed_mcp_names,
          role_mode: resp.role_mode,
          wire_policy_effective: !!resp.wire_policy_effective,
          policy_keys: resp.policy_keys,
          skipped_public: resp.skipped_public || [],
          skipped_expert: resp.skipped_expert || [],
        },
        null,
        2,
      );
      const _toMap = (arr) => {
        const m = new Map();
        (Array.isArray(arr) ? arr : []).forEach((ent) => {
          const fn = ent && typeof ent === "object" ? ent.function : null;
          const nm = fn && typeof fn === "object" ? String(fn.name || "") : "";
          if (!nm) return;
          const desc = fn && typeof fn === "object" ? String(fn.description || "") : "";
          const params = fn && typeof fn === "object" ? fn.parameters : null;
          m.set(nm, { description: desc, parameters: params });
        });
        return m;
      };
      const rawMap = _toMap(llmToolsState.tools_raw);
      const wiredMap = _toMap(llmToolsState.tools_wired);
      const rawNames = Array.from(rawMap.keys());
      const wiredNames = Array.from(wiredMap.keys());
      const rawSet = new Set(rawNames);
      const wiredSet = new Set(wiredNames);
      const removed = rawNames.filter((n) => !wiredSet.has(n)).sort();
      const added = wiredNames.filter((n) => !rawSet.has(n)).sort();
      const changed = [];
      wiredNames.forEach((n) => {
        if (!rawSet.has(n)) return;
        const a = rawMap.get(n) || {};
        const b = wiredMap.get(n) || {};
        const d0 = String(a.description || "");
        const d1 = String(b.description || "");
        const p0 = a.parameters ? JSON.stringify(a.parameters) : "";
        const p1 = b.parameters ? JSON.stringify(b.parameters) : "";
        if (d0 !== d1 || p0 !== p1) changed.push(n);
      });
      llmDiffPre.textContent = JSON.stringify(
        {
          added,
          removed,
          changed,
          counts: { raw: rawNames.length, wired: wiredNames.length, added: added.length, removed: removed.length, changed: changed.length },
        },
        null,
        2,
      );

      llmDiffTbody.innerHTML = "";
      const _kind = (nm) => (String(nm || "").startsWith("mcp__") ? "mcp" : "internal");
      const _pushRow = (tp, nm, detailEl) => {
        llmDiffTbody.appendChild(
          el("tr", {}, [
            el("td", { text: tp }),
            el("td", { text: nm }),
            el("td", { text: _kind(nm) }),
            el("td", {}, [detailEl]),
          ]),
        );
      };
      const _detailsCompare = (nm) => {
        const a = rawMap.get(nm) || {};
        const b = wiredMap.get(nm) || {};
        const d0 = String(a.description || "");
        const d1 = String(b.description || "");
        const p0 = a.parameters ? JSON.stringify(a.parameters, null, 2) : "";
        const p1 = b.parameters ? JSON.stringify(b.parameters, null, 2) : "";
        const box = el("details", {}, [
          el("summary", { text: "compare", style: "cursor:pointer;user-select:none;" }),
          el("div", { class: "muted", style: "margin-top:6px;" }, [el("div", { text: "raw.description" }), el("pre", { class: "muted pre", text: d0 })]),
          el("div", { class: "muted", style: "margin-top:6px;" }, [el("div", { text: "wired.description" }), el("pre", { class: "muted pre", text: d1 })]),
          el("div", { class: "muted", style: "margin-top:6px;" }, [el("div", { text: "raw.parameters" }), el("pre", { class: "muted pre", text: p0 })]),
          el("div", { class: "muted", style: "margin-top:6px;" }, [el("div", { text: "wired.parameters" }), el("pre", { class: "muted pre", text: p1 })]),
        ]);
        return box;
      };
      added.forEach((nm) => _pushRow("added", nm, el("span", { class: "muted", text: "present in wired only" })));
      removed.forEach((nm) => _pushRow("removed", nm, el("span", { class: "muted", text: "present in raw only" })));
      changed.sort().forEach((nm) => _pushRow("changed", nm, _detailsCompare(nm)));
      if (!added.length && !removed.length && !changed.length) {
        llmDiffTbody.appendChild(el("tr", {}, [el("td", { text: "-", colspan: "4" })]));
      }

      _renderLLMToolRows(llmToolsState.tools_wired);
    } catch (e) {
      llmToolsState.tools_wired = [];
      llmToolsStatus.textContent = `preview: ${String(e && e.message ? e.message : e)}`;
      llmRemovedPre.textContent = "";
      llmDiffPre.textContent = "";
      llmDiffTbody.innerHTML = "";
      _renderLLMToolRows([]);
    }
  };

  const btnLLMPreview = el("button", {
    class: "btn btn--primary",
    text: "Preview",
    onclick: async () => await loadLLMToolsPreview(llmRoleSelect.value),
  });
  const loadExposureTraceSetting = async () => {
    try {
      const resp = await apiGet("/admin/api/tools/exposure-trace-setting");
      llmTracePlanCb.checked = !!(resp && resp.enabled);
    } catch (_) {
      llmTracePlanCb.checked = false;
    }
  };
  const saveExposureTraceSetting = async () => {
    try {
      const resp = await apiPost("/admin/api/tools/exposure-trace-setting", { enabled: !!llmTracePlanCb.checked });
      llmTracePlanCb.checked = !!(resp && resp.enabled);
      llmToolsStatus.textContent = `trace_exposure_plan=${llmTracePlanCb.checked ? "on" : "off"}`;
    } catch (e) {
      llmToolsStatus.textContent = `trace setting: ${String(e && e.message ? e.message : e)}`;
    }
  };
  const btnLLMToggle = el("button", {
    class: "btn",
    text: "Toggle raw/wired",
    onclick: () => {
      const showing = String(btnLLMToggle.dataset.showing || "wired");
      const next = showing === "wired" ? "raw" : "wired";
      btnLLMToggle.dataset.showing = next;
      _renderLLMToolRows(next === "wired" ? llmToolsState.tools_wired : llmToolsState.tools_raw);
      btnLLMToggle.textContent = next === "wired" ? "Toggle raw/wired" : "Toggle raw/wired";
    },
  });
  const llmToolsBox = el("details", { style: "margin:10px 0 14px 0;" }, [
    el("summary", { text: "LLM tools preview (after wire policy)", style: "cursor:pointer;user-select:none;" }),
    el("div", { class: "muted", style: "margin:8px 0;line-height:1.5;", text: "Preview the final tools injected to the model for a role (internal + MCP + role_mode + permanent bans + wire policy tiers/penalty)." }),
    llmToolsStatus,
    el("div", { class: "row", style: "gap:8px;flex-wrap:wrap;margin-top:8px;align-items:center;" }, [
      el("label", { text: "Role" }),
      llmRoleSelect,
      btnLLMPreview,
      btnLLMToggle,
      el("button", {
        class: "btn",
        text: "Clear cache",
        onclick: async () => {
          try {
            await apiPost("/admin/api/tools/internal/reload", {});
            llmToolsStatus.textContent = "cache cleared";
            await loadLLMToolsPreview(llmRoleSelect.value);
          } catch (e) {
            llmToolsStatus.textContent = `reload: ${String(e && e.message ? e.message : e)}`;
          }
        },
      }),
      el("span", { class: "muted", text: "role_mode:" }),
      llmModeBadge,
      el("label", { class: "row", style: "gap:6px;align-items:center;" }, [
        llmTracePlanCb,
        el("span", { class: "muted", text: "Trace exposure plan" }),
      ]),
      el("button", { class: "btn", text: "Save trace setting", onclick: saveExposureTraceSetting }),
    ]),
    el("div", { class: "table-wrap", style: "margin-top:8px" }, [
      el("table", { class: "table table--compact" }, [
        el("thead", {}, [el("tr", {}, [el("th", { text: "name" }), el("th", { text: "description" }), el("th", { text: "kind" }), el("th", { text: "parameters" })])]),
        llmToolsTbody,
      ]),
    ]),
    el("div", { class: "muted", style: "margin-top:8px", text: "Diff / diagnostics" }),
    llmRemovedPre,
    el("div", { class: "muted", style: "margin-top:8px", text: "raw vs wired diff (added/removed/changed)" }),
    llmDiffPre,
    llmDiffTableWrap,
  ]);

  const tbody = el("tbody");
  const auditTbody = el("tbody");
  let skillActionMenuEl = null;
  let skillTestRunName = "";
  const closeSkillActionMenu = () => {
    if (skillActionMenuEl && skillActionMenuEl.parentNode) {
      skillActionMenuEl.parentNode.removeChild(skillActionMenuEl);
    }
    skillActionMenuEl = null;
  };
  const skillTestRunModal = el("div", { class: "session-monitor-modal", style: "display:none;" });
  const skillTestRunTitle = el("div", { class: "card__title", text: "Skill test run" });
  const skillTestRunArgs = el("textarea", { class: "input", rows: "8", style: "width:100%;min-width:0;font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;", placeholder: "{}" });
  const skillInstallModal = el("div", { class: "session-monitor-modal", style: "display:none;" });
  const skillInstallTitle = el("div", { class: "card__title", text: "Skill installation" });
  const skillInstallMsg = el("div", { class: "muted", style: "line-height:1.5;" });
  const closeSkillInstallModal = () => {
    skillInstallModal.style.display = "none";
  };
  const openSkillInstallModal = (msg) => {
    skillInstallTitle.textContent = "Skill installation";
    skillInstallMsg.textContent = String(msg || "");
    skillInstallModal.style.display = "flex";
  };
  const finishSkillInstallModal = (ok, msg) => {
    skillInstallTitle.textContent = ok ? "Skill installation success" : "Skill installation failed";
    skillInstallMsg.textContent = String(msg || "");
    setTimeout(() => {
      closeSkillInstallModal();
    }, 1200);
  };
  skillInstallModal.addEventListener("click", (e) => {
    if (e.target === skillInstallModal) closeSkillInstallModal();
  });
  const skillInstallCard = el("div", { class: "card session-monitor-modal__card", style: "width:min(560px,96vw);" }, [
    skillInstallTitle,
    skillInstallMsg,
    el("div", { class: "row", style: "justify-content:flex-end;margin-top:10px;" }, [
      el("button", { class: "btn", text: "Close", onclick: closeSkillInstallModal }),
    ]),
  ]);
  skillInstallModal.appendChild(skillInstallCard);
  const closeSkillTestRunModal = () => {
    skillTestRunModal.style.display = "none";
    skillTestRunName = "";
  };
  const openSkillTestRunModal = (name) => {
    skillTestRunName = String(name || "");
    skillTestRunTitle.textContent = `Test run: ${skillTestRunName}`;
    skillTestRunArgs.value = "{}";
    skillTestRunModal.style.display = "flex";
    setTimeout(() => skillTestRunArgs.focus(), 0);
  };
  skillTestRunModal.addEventListener("click", (e) => {
    if (e.target === skillTestRunModal) closeSkillTestRunModal();
  });
  const skillTestRunRunBtn = el("button", {
    class: "btn btn--primary",
    text: "Run",
    onclick: async () => {
      if (!skillTestRunName) return;
      let args = {};
      try {
        const raw = String(skillTestRunArgs.value || "").trim();
        args = raw ? JSON.parse(raw) : {};
      } catch (e) {
        status.textContent = `invalid json: ${String(e && e.message ? e.message : e)}`;
        return;
      }
      try {
        const r = await apiPost("/admin/api/skills/test-run", { name: skillTestRunName, args });
        status.textContent = `test-run: ${skillTestRunName} => ${JSON.stringify((r && r.result) || {}, null, 0)}`;
        closeSkillTestRunModal();
      } catch (e) {
        status.textContent = `test-run: ${String(e && e.message ? e.message : e)}`;
      }
    },
  });
  const skillTestRunCancelBtn = el("button", { class: "btn", text: "Cancel", onclick: closeSkillTestRunModal });
  const skillTestRunCard = el("div", { class: "card session-monitor-modal__card", style: "width:min(760px,96vw);" }, [
    skillTestRunTitle,
    el("div", { class: "muted", style: "margin-bottom:8px;", text: "Input JSON args passed to the executable skill runtime." }),
    skillTestRunArgs,
    el("div", { class: "row", style: "gap:8px;justify-content:flex-end;margin-top:10px;" }, [skillTestRunCancelBtn, skillTestRunRunBtn]),
  ]);
  skillTestRunModal.appendChild(skillTestRunCard);
  const retryableOnlyCb = el("input", { type: "checkbox" });
  const retryableOnlyStored = String(localStorage.getItem(SKILL_AUDIT_RETRYABLE_ONLY_KEY) || "").trim().toLowerCase();
  retryableOnlyCb.checked = retryableOnlyStored ? retryableOnlyStored !== "0" && retryableOnlyStored !== "false" : true;
  const _parseSourceFromAudit = (it) => {
    const d = it && typeof it.detail === "object" ? it.detail : {};
    const s = String(d.source || "").trim().toLowerCase();
    if (s === "local" || s === "registry" || s === "auto") return s;
    return "";
  };
  const _parseRetryTargetFromAudit = (it) => {
    const d = it && typeof it.detail === "object" ? it.detail : {};
    const inputTarget = String(d.input_target || "").trim();
    if (inputTarget) return inputTarget;
    return String((it && it.target_id) || "").trim();
  };
  const _isRetryableAudit = (it) => {
    const action = String((it && it.action) || "").trim().toLowerCase();
    if (action !== "skill_install_failed") return false;
    const src = _parseSourceFromAudit(it);
    const target = _parseRetryTargetFromAudit(it);
    return Boolean(src && target);
  };
  const loadRows = async () => {
    const data = await apiGet("/admin/api/skills");
    rowsState.items = Array.isArray(data.items) ? data.items : [];
  };
  const loadAudits = async () => {
    const data = await apiGet("/admin/api/admin-audit?limit=80");
    const items = Array.isArray(data.items) ? data.items : [];
    auditState.items = items
      .filter((x) => String(x.action || "").startsWith("skill_"))
      .slice(0, 20);
  };
  const repaint = () => {
    const rows = rowsState.items || [];
    tbody.innerHTML = "";
    rows.forEach((x) => {
      const name = String(x.name || "");
      const enabled = !!x.enabled;
      const executable = !!x.executable;
      const runtime = x && typeof x.runtime === "object" ? x.runtime : null;
      const runtimeType = runtime && typeof runtime.type === "string" ? String(runtime.type) : "";
      const runtimeEntry = runtime && typeof runtime.entry === "string" ? String(runtime.entry) : "";
      const toggleBtn = el("button", {
        class: "chat-sess-menu-item",
        text: enabled ? "Disable" : "Enable",
        onclick: async () => {
          try {
            closeSkillActionMenu();
            await apiPost(enabled ? "/admin/api/skills/disable" : "/admin/api/skills/enable", { name });
            status.textContent = `${enabled ? "Disabled" : "Enabled"}: ${name}`;
            await loadRows();
            repaint();
          } catch (e) {
            status.textContent = String(e && e.message ? e.message : e);
          }
        },
      });
      const testRunBtn = el("button", {
        class: "chat-sess-menu-item",
        text: "Test run...",
        disabled: !executable,
        onclick: () => {
          closeSkillActionMenu();
          openSkillTestRunModal(name);
        },
      });
      const repairDepsBtn = el("button", {
        class: "chat-sess-menu-item",
        text: "Repair deps",
        onclick: async () => {
          closeSkillActionMenu();
          try {
            status.textContent = `repair deps: ${name}...`;
            const r = await apiPost("/admin/api/skills/repair-deps", { name });
            assertSkillMutationOk(r, "Repair deps failed");
            status.textContent = `repair deps: ${JSON.stringify((r && r.result) || {}, null, 0)}`;
            await loadRows();
            await loadAudits();
            repaint();
          } catch (e) {
            status.textContent = `repair deps failed: ${String(e && e.message ? e.message : e)}`;
          }
        },
      });
      const uninstallBtn = el("button", {
        class: "chat-sess-menu-item",
        text: "Uninstall",
        onclick: async () => {
          closeSkillActionMenu();
          if (!confirm(`Uninstall skill "${name}"?`)) return;
          try {
            status.textContent = `uninstalling: ${name}...`;
            const r = await apiPost("/admin/api/skills/uninstall", { name });
            assertSkillMutationOk(r, "Uninstall failed");
            status.textContent = `uninstall success: ${JSON.stringify((r && r.result) || {}, null, 0)}`;
            await loadRows();
            await loadAudits();
            repaint();
          } catch (e) {
            status.textContent = `uninstall failed: ${String(e && e.message ? e.message : e)}`;
          }
        },
      });
      const actionMenuBtn = el("button", {
        class: "chat-sess-more",
        text: "⋯",
        title: "Skill actions",
        onclick: (ev) => {
          ev.stopPropagation();
          closeSkillActionMenu();
          const menu = el("div", { class: "chat-sess-menu-pop", style: "position:fixed;z-index:250;" }, [
            toggleBtn,
            testRunBtn,
            repairDepsBtn,
            uninstallBtn,
          ]);
          const rect = ev.currentTarget.getBoundingClientRect();
          document.body.appendChild(menu);
          const mrect = menu.getBoundingClientRect();
          const pad = 8;
          let left = rect.left - 120;
          let top = rect.bottom + 4;
          if (top + mrect.height > window.innerHeight - pad) {
            top = rect.top - 4 - mrect.height;
          }
          left = Math.max(pad, Math.min(left, window.innerWidth - pad - mrect.width));
          top = Math.max(pad, Math.min(top, window.innerHeight - pad - mrect.height));
          menu.style.left = `${left}px`;
          menu.style.top = `${top}px`;
          skillActionMenuEl = menu;
          const close = (e) => {
            if (!menu.contains(e.target)) {
              closeSkillActionMenu();
              document.removeEventListener("click", close);
            }
          };
          setTimeout(() => document.addEventListener("click", close), 0);
        },
      });
      tbody.appendChild(
        el("tr", {}, [
          el("td", { text: name }),
          el("td", { text: String(x.description || "") }),
          el("td", { text: String(x.enabled ? "1" : "0") }),
          el("td", {}, [executable ? el("span", { class: "badge badge--ok", text: `${runtimeType || "runtime"}` }) : el("span", { class: "muted", text: "docs-only" })]),
          el("td", { text: executable ? `${runtimeEntry}` : "-" }),
          el("td", { text: String(x.skill_dir || "") }),
          el("td", { class: "table__cell-actions" }, [actionMenuBtn]),
        ]),
      );
    });

    auditTbody.innerHTML = "";
    const auditRows = (auditState.items || []).filter((x) => (!retryableOnlyCb.checked ? true : _isRetryableAudit(x)));
    for (const x of auditRows) {
      const src = _parseSourceFromAudit(x);
      const isRetryable = _isRetryableAudit(x);
      const retryBtn = el("button", {
        class: "btn",
        text: "Retry",
        disabled: !isRetryable,
        onclick: async () => {
          try {
            const target = _parseRetryTargetFromAudit(x);
            if (!src || !target || !isRetryable) {
              status.textContent = "retry skipped: missing source/target";
              return;
            }
            const r = await apiPost("/admin/api/skills/retry-install", { source: src, target });
            assertSkillMutationOk(r, "Retry install failed");
            status.textContent = `retry: ${JSON.stringify(r.result || {})}`;
            await loadRows();
            await loadAudits();
            repaint();
          } catch (e) {
            status.textContent = String(e && e.message ? e.message : e);
          }
        },
      });
      auditTbody.appendChild(
        el("tr", {}, [
          el("td", { text: String(x.timestamp || "") }),
          el("td", { text: String(x.action || "") }),
          el("td", { text: String(x.target_id || "") }),
          el("td", { text: String(x.status || "") }),
          el("td", { text: shortText(JSON.stringify(x.detail || {}), 180) }),
          el("td", {}, [retryBtn]),
        ]),
      );
    }
  };
  const refreshSkillsState = async () => {
    await loadRows();
    await loadAudits();
    await loadSkillBinding();
    repaint();
    renderSkillBindingList();
  };
  try {
    await loadRows();
    await loadAudits();
    await loadSkillBinding();
    await loadSkillMode();
    const rolesForPreview = (Array.isArray(skillBindingState.roles) && skillBindingState.roles.length ? skillBindingState.roles : ["generalist", "ops", "image", "manager"]).map((x) => String(x));
    internalRoleSelect.innerHTML = "";
    rolesForPreview.forEach((role) => internalRoleSelect.appendChild(el("option", { value: role, text: role })));
    internalRoleSelect.value = rolesForPreview.includes("generalist") ? "generalist" : rolesForPreview[0];
    internalToolsStatus.textContent = "expand this section to load preview";
    llmRoleSelect.innerHTML = "";
    rolesForPreview.forEach((role) => llmRoleSelect.appendChild(el("option", { value: role, text: role })));
    llmRoleSelect.value = internalRoleSelect.value;
    llmToolsStatus.textContent = "expand this section to load preview";
    selfCheckStatus.textContent = "expand this section to run self-check";
  } catch (e) {
    return el("div", { class: "card" }, [
      el("div", { class: "card__title", text: t("title.skills") }),
      el("div", { class: "muted", text: String(e && e.message ? e.message : e) }),
    ]);
  }
  repaint();

  const btnCreate = el("button", {
    class: "btn btn--primary",
    text: "Create Skill",
    onclick: async () => {
      try {
        const r = await apiPost("/admin/api/skills/create", {
          name: String(nameInp.value || "").trim(),
          description: String(descInp.value || "").trim(),
          body_markdown: String(bodyInp.value || ""),
        });
        assertSkillMutationOk(r, "Create skill failed");
        status.textContent = `create: ${JSON.stringify(r.result || {})}`;
        await loadRows();
        await loadAudits();
        repaint();
      } catch (e) {
        status.textContent = String(e && e.message ? e.message : e);
      }
    },
  });
  const btnInstallRegistry = el("button", {
    class: "btn",
    text: "Install From Registry",
    onclick: async () => {
      const prev = btnInstallRegistry.textContent;
      btnInstallRegistry.disabled = true;
      btnInstallRegistry.textContent = "Installing...";
      status.textContent = "installing from registry...";
      openSkillInstallModal("Installing skill from registry...");
      try {
        const r = await apiPost("/admin/api/skills/install-registry", {
          archive_url: String(regInp.value || "").trim(),
        });
        assertSkillMutationOk(r, "Registry install failed");
        status.textContent = `install-registry success: ${JSON.stringify(r.result || {})}`;
        await refreshSkillsState();
        finishSkillInstallModal(true, "Registry skill installed successfully.");
      } catch (e) {
        status.textContent = String(e && e.message ? e.message : e);
        finishSkillInstallModal(false, `Install failed: ${String(e && e.message ? e.message : e)}`);
      } finally {
        btnInstallRegistry.disabled = false;
        btnInstallRegistry.textContent = prev;
      }
    },
  });
  const btnInstallLocal = el("button", {
    class: "btn",
    text: "Install Local Dir",
    onclick: async () => {
      const prev = btnInstallLocal.textContent;
      btnInstallLocal.disabled = true;
      btnInstallLocal.textContent = "Installing...";
      status.textContent = "installing from local dir...";
      openSkillInstallModal("Installing skill from local directory...");
      try {
        const r = await apiPost("/admin/api/skills/install", {
          source_dir: String(localDirInp.value || "").trim(),
        });
        assertSkillMutationOk(r, "Local install failed");
        status.textContent = `install-local success: ${JSON.stringify(r.result || {})}`;
        await refreshSkillsState();
        finishSkillInstallModal(true, "Local skill installed successfully.");
      } catch (e) {
        status.textContent = String(e && e.message ? e.message : e);
        finishSkillInstallModal(false, `Install failed: ${String(e && e.message ? e.message : e)}`);
      } finally {
        btnInstallLocal.disabled = false;
        btnInstallLocal.textContent = prev;
      }
    },
  });
  const btnRefresh = el("button", {
    class: "btn",
    text: t("action.refresh"),
    onclick: async () => {
      try {
        await refreshSkillsState();
        status.textContent = "refreshed";
      } catch (e) {
        status.textContent = String(e && e.message ? e.message : e);
      }
    },
  });
  const btnRepairDepsAll = el("button", {
    class: "btn",
    text: "Repair all deps",
    onclick: async () => {
      const prev = btnRepairDepsAll.textContent;
      btnRepairDepsAll.disabled = true;
      btnRepairDepsAll.textContent = "Repairing...";
      try {
        const r = await apiPost("/admin/api/skills/repair-deps-all", {});
        const s = r && typeof r.summary === "object" ? r.summary : {};
        status.textContent = `repair all deps: total=${Number(s.total || 0)} ok=${Number(s.ok_count || 0)} warn=${Number(s.warn_count || 0)} fail=${Number(s.fail_count || 0)}`;
        await refreshSkillsState();
      } catch (e) {
        status.textContent = `repair all deps failed: ${String(e && e.message ? e.message : e)}`;
      } finally {
        btnRepairDepsAll.disabled = false;
        btnRepairDepsAll.textContent = prev;
      }
    },
  });
  retryableOnlyCb.addEventListener("change", () => {
    localStorage.setItem(SKILL_AUDIT_RETRYABLE_ONLY_KEY, retryableOnlyCb.checked ? "1" : "0");
    repaint();
  });
  const docsHint = el("div", { class: "muted", style: "margin-bottom:10px;line-height:1.5;" }, [
    el("div", { text: t("skills.docsTitle") }),
    el("div", { text: t("skills.docsTroubleshooting") }),
    el("div", { text: t("skills.docsTraceTaxonomy") }),
  ]);
  internalToolsBox.addEventListener("toggle", async () => {
    if (!internalToolsBox.open || lazyLoadState.internalLoaded) return;
    lazyLoadState.internalLoaded = true;
    await loadInternalToolsPreview(internalRoleSelect.value);
  });
  llmToolsBox.addEventListener("toggle", async () => {
    if (!llmToolsBox.open || lazyLoadState.llmLoaded) return;
    lazyLoadState.llmLoaded = true;
    await loadExposureTraceSetting();
    await loadLLMToolsPreview(llmRoleSelect.value);
  });
  selfCheckBox.addEventListener("toggle", async () => {
    if (!selfCheckBox.open || lazyLoadState.selfCheckLoaded) return;
    lazyLoadState.selfCheckLoaded = true;
    await runSelfCheck();
  });
  skillHealthBox.addEventListener("toggle", async () => {
    if (!skillHealthBox.open || lazyLoadState.skillHealthLoaded) return;
    lazyLoadState.skillHealthLoaded = true;
    await runSkillHealthCheck();
  });
  return el("div", { class: "card" }, [
    el("div", { class: "card__title", text: t("title.skills") }),
    el("div", { class: "row", style: "gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:8px;" }, [
      el("label", { class: "row", style: "gap:6px;align-items:center;" }, [skillPromptModeCb, el("span", { text: "Prompt mode (inject SKILL.md)" })]),
      el("label", { class: "row", style: "gap:6px;align-items:center;" }, [skillToolcallModeCb, el("span", { text: "Toolcall mode (runtime as tools)" })]),
      el("label", { class: "row", style: "gap:6px;align-items:center;flex-wrap:wrap;" }, [
        el("span", { text: "Market (AIA_SKILL_MARKET_PROVIDER)" }),
        skillMarketProviderSelect,
      ]),
      el("button", { class: "btn", text: "Save skill mode", onclick: saveSkillMode }),
      skillModeStatus,
    ]),
    docsHint,
    marketBox,
    el("details", { style: "margin:10px 0 14px 0;" }, [
      el("summary", { text: "Skill installation (local / registry)", style: "cursor:pointer;user-select:none;" }),
      el("div", { style: "height:8px" }),
      el("div", { class: "muted", style: "margin-bottom:8px;line-height:1.5;" }, [
        el("div", { text: "Local dir: 目录内必须包含 SKILL.md（支持绝对路径）。" }),
        el("div", { text: "Registry: zip/tar 的 URL（支持 file:// 本地 URI）。" }),
      ]),
      el("div", { class: "row", style: "gap:8px;flex-wrap:wrap;margin-bottom:8px;" }, [regInp, btnInstallRegistry]),
      el("div", { class: "row", style: "gap:8px;flex-wrap:wrap;margin-bottom:8px;" }, [localDirInp, btnInstallLocal]),
    ]),
    skillBindingBox,
    selfCheckBox,
    skillHealthBox,
    internalToolsBox,
    llmToolsBox,
    el("div", { class: "row", style: "gap:8px;flex-wrap:wrap;margin-bottom:8px;" }, [nameInp, descInp]),
    el("div", { style: "margin-bottom:8px;" }, [bodyInp]),
    el("div", { class: "row", style: "gap:8px;flex-wrap:wrap;margin-bottom:8px;" }, [btnCreate]),
    el("div", { class: "row", style: "gap:8px;flex-wrap:wrap;margin-bottom:8px;" }, [btnRefresh, btnRepairDepsAll]),
    el("div", { class: "table-wrap" }, [
      el("table", { class: "table table--compact" }, [
        el("thead", {}, [el("tr", {}, [
          el("th", { text: "name" }),
          el("th", { text: "description" }),
          el("th", { text: "enabled" }),
          el("th", { text: "kind" }),
          el("th", { text: "runtime entry" }),
          el("th", { text: "path" }),
          el("th", { text: "action" }),
        ])]),
        tbody,
      ]),
    ]),
    el("div", { style: "height:10px" }),
    el("div", { class: "row", style: "gap:8px;align-items:center;" }, [
      el("div", { class: "muted", text: "Recent skill install audit" }),
      el("label", { class: "row", style: "gap:6px;align-items:center;" }, [
        retryableOnlyCb,
        el("span", { class: "muted", text: "Only retryable failures" }),
      ]),
    ]),
    el("div", { class: "table-wrap" }, [
      el("table", { class: "table table--compact" }, [
        el("thead", {}, [el("tr", {}, [el("th", { text: "timestamp" }), el("th", { text: "action" }), el("th", { text: "target" }), el("th", { text: "status" }), el("th", { text: "detail" }), el("th", { text: "retry" })])]),
        auditTbody,
      ]),
    ]),
    skillTestRunModal,
    skillInstallModal,
    status,
  ]);
}

async function router() {
  const route = getRoute();
  const page = route.page;
  const tok = getStoredAuthToken();
  if (!authSession || !tok) {
    if (authSession || tok) {
      authStoreRemove(AUTH_TOKEN_KEY);
      authStoreRemove(AUTH_SESSION_KEY);
      authSession = null;
    }
    try {
      await apiPost("/admin/api/auth/bootstrap", {});
    } catch (_) {}
    const loginCard = await renderLogin();
    mount(loginCard);
    return;
  }
  applyI18nStatic();
  setActive(page);
  document.querySelectorAll(".nav__item").forEach((a) => {
    const p = String(a.dataset.page || "");
    if (p === "stack" && !hasPermission("admin:runtime:write")) a.style.display = "none";
    else if (p === "users" && !hasPermission("admin:user:read")) a.style.display = "none";
    else if (p === "session-monitor" && !isAdministratorUsername()) a.style.display = "none";
    else if (p === "admin-audit" && !hasPermission("admin:user:write")) a.style.display = "none";
    else if (p === "plugins" && !hasPermission("admin:user:write")) a.style.display = "none";
    else if (p === "skills" && !hasPermission("admin:read")) a.style.display = "none";
    else if (p === "attachments" && !isAdministratorUsername()) a.style.display = "none";
    else if (p === "workspace-paths" && !hasPermission("admin:user:read") && !hasPermission("admin:workspace_paths:read")) a.style.display = "none";
    else if (p === "api-grants" && !canManageApiGrants()) a.style.display = "none";
    else a.style.display = "";
  });
  const user = document.getElementById("authUser");
  if (user) {
    const name = String((authSession && (authSession.display_name || authSession.username || authSession.user_id)) || "");
    const role = String((authSession && authSession.role) || "");
    user.textContent = name ? `${name} (${role})` : "";
  }
  const forbiddenCard = () =>
    el("div", { class: "card" }, [el("div", { class: "card__title", text: t("common.forbidden") })]);
  let view;
  if (page === "stack") {
    mount(
      el("div", { class: "card" }, [
        el("div", { class: "card__title", text: t("title.stack") }),
        el("div", { class: "muted", text: t("chat.loading") }),
      ]),
    );
    view = await renderStack();
  }
  else if (page === "users") {
    view = hasPermission("admin:user:read") ? await renderUserManagement() : forbiddenCard();
  } else if (page === "memory") view = await renderMemory();
  else if (page === "models") view = await renderModels();
  else if (page === "api-grants") view = await renderApiGrants();
  else if (page === "audit") view = await renderAudit(route.params.get("session_id") || "");
  else if (page === "session-monitor") {
    view = isAdministratorUsername() ? await renderSessionMonitor() : el("div", { class: "card" }, [el("div", { class: "card__title", text: t("sessionMonitor.onlyAdministrator") })]);
  } else if (page === "admin-audit") {
    view = hasPermission("admin:user:write") ? await renderAdminAudit() : forbiddenCard();
  } else if (page === "plugins") {
    mount(
      el("div", { class: "card" }, [
        el("div", { class: "card__title", text: t("title.plugins") }),
        el("div", { class: "muted", text: t("chat.loading") }),
      ]),
    );
    view = hasPermission("admin:user:write") ? await renderPlugins() : forbiddenCard();
  } else if (page === "skills") {
    view = hasPermission("admin:read") ? await renderSkills() : forbiddenCard();
  } else if (page === "attachments") {
    view = isAdministratorUsername() ? await renderAttachments() : forbiddenCard();
  } else if (page === "workspace-paths") {
    view =
      hasPermission("admin:user:read") || hasPermission("admin:workspace_paths:read")
        ? await renderWorkspacePaths()
        : forbiddenCard();
  } else if (page === "profile") {
    view = await renderProfile();
  } else view = el("div", { class: "card" }, [el("div", { class: "card__title", text: t("common.notFound") })]);
  mount(view);
}

async function renderLogin() {
  applyI18nStatic();
  const username = el("input", { class: "input", placeholder: t("auth.username"), value: "" });
  const userHint = el("div", { class: "muted", text: t("auth.consoleUsernameHint") });
  const password = el("input", { class: "input", type: "password", placeholder: t("auth.password") });
  const status = el("div", { class: "muted", text: "" });
  const doLogin = async () => {
    const resp = await apiPost("/admin/api/auth/login", {
      tenant_id: "",
      username: username.value.trim(),
      password: password.value.trim(),
      purpose: "console",
    });
    if (!resp.ok || !resp.token) {
      const err = String(resp.error || "");
      status.textContent = err === "user_disabled" ? t("auth.disabled") : t("auth.invalid");
      return;
    }
    const newTok = String(resp.token || "").trim();
    authStoreSet(AUTH_TOKEN_KEY, newTok);
    authStoreSet(AUTH_SESSION_KEY, JSON.stringify(resp.session || {}));
    authSession = resp.session || null;
    await router();
  };
  const onEnterLogin = (ev) => {
    if (ev.key !== "Enter") return;
    ev.preventDefault();
    doLogin();
  };
  username.addEventListener("keydown", onEnterLogin);
  password.addEventListener("keydown", onEnterLogin);
  const btn = el("button", { class: "btn btn--primary", text: t("auth.login"), onclick: doLogin });
  // Focus after mount so users can type immediately.
  setTimeout(() => {
    try {
      username.focus();
    } catch (_) {}
  }, 0);
  return el("div", { class: "card" }, [
    el("div", { class: "card__title", text: t("auth.login") }),
    el("div", { class: "row" }, [username]),
    userHint,
    el("div", { class: "row" }, [password]),
    el("div", { class: "row" }, [btn]),
    status,
  ]);
}

window.addEventListener("hashchange", router);
const btnRefreshEl = document.getElementById("btnRefresh");
if (btnRefreshEl) btnRefreshEl.addEventListener("click", router);
const btnLangEl = document.getElementById("btnLang");
if (btnLangEl) btnLangEl.addEventListener("click", () => {
  toggleLang();
  router();
});
const adminThemeSelectEl = document.getElementById("adminThemeSelect");
if (adminThemeSelectEl && window.OclawAdminTheme) {
  adminThemeSelectEl.addEventListener("change", () => {
    try {
      window.OclawAdminTheme.persistAdminTheme(adminThemeSelectEl.value);
    } catch (_) {}
  });
}
const btnBackChatEl = document.getElementById("btnBackChat");
if (btnBackChatEl) {
  try {
    btnBackChatEl.setAttribute("href", resolveChatUrl());
  } catch (_) {}
  btnBackChatEl.addEventListener("click", (ev) => {
    // Keep SPA behavior explicit, while href remains fallback if JS fails earlier.
    ev.preventDefault();
    window.location.assign(resolveChatUrl());
  });
}
const btnLogoutEl = document.getElementById("btnLogout");
if (btnLogoutEl) btnLogoutEl.addEventListener("click", async () => {
  try {
    await apiPost("/admin/api/auth/logout", {});
  } catch (_) {}
  authStoreRemove(AUTH_TOKEN_KEY);
  authStoreRemove(AUTH_SESSION_KEY);
  authSession = null;
  await router();
});
try {
  authSession = JSON.parse(authStoreGet(AUTH_SESSION_KEY) || "null");
} catch (_) {
  authSession = null;
}
router().catch((err) => {
  mount(el("div", { class: "card" }, [el("div", { class: "card__title", text: t("common.error") }), el("div", { class: "pre", text: String(err) })]));
});

