---
name: knowledge-base-manager
description: 智能知识库管理助手，自动将新信息归类到正确的 PARA 分类（Projects/Areas/Resources/Archives），确保笔记结构规范化。带严格目录限制和完整 ID 映射。
user-invocable: true
disable-model-invocation: false
metadata: {"oclaw": {}}
---

# knowledge-base-manager

**Description**: 智能知识库管理助手，自动将新信息归类到正确的 PARA 分类（Projects/Areas/Resources/Archives），确保笔记结构规范化。

**Version**: 1.1 (带目录限制)  
**Author**: Oliver  
**Created**: 2026-04-11  
**Last Updated**: 2026-04-11

---

## ⚠️ 核心约束（必须遵守）

### 🚫 禁止操作
1. **严禁移动现有笔记** - 除非用户明确要求"移动 XXX 到 YYY"
2. **严禁删除任何笔记** - 除非用户明确要求"删除 XXX"
3. **严禁修改非授权目录** - 只能在以下允许的子目录下创建笔记
4. **严禁在根目录或其他区域创建笔记** - 必须遵循目录结构

### ✅ 允许操作的目录

**只能**在以下父节点的**子目录**下创建新笔记：

| 允许创建的父节点 | Note ID | 用途 |
|-----------------|---------|------|
| `00-Inbox` | `h9skuCU9czep` | 临时收集箱（默认） |
| `01-Projects` | `8C1UOi0hfib5` | 项目相关笔记 |
| `02-Areas/基础设施` | `pS6clLY4g5sd` | 基础设施领域 |
| `02-Areas/开发环境` | `b7lkhRneQk2a` | 开发环境领域 |
| `03-Resources` | `1AbShK4WDw38` | 参考资源 |
| `04-Archives` | `6rQ5acaYa7fZ` | 归档内容 |
| `99-Templates` | `RVjlkQmiHxaw` | 模板笔记 |

**重要**: 
- 创建新笔记时，`parentNoteId` **必须**是上述 ID 之一或其子节点
- 如果用户要求的位置不在上述列表中，**必须拒绝**并提示用户
- 不确定时，默认使用 `h9skuCU9czep` (Inbox)

---

## 📋 完整笔记 ID 映射表

### 🌟 知识库总览
```
🌟 知识库总览          → XTNCDr5hq9bG
📖 知识库使用指南      → hgILpr4yRkcS
📝 笔记记录规范       → [见使用指南子节点]
✅ 迁移完成报告        → [见使用指南子节点]
🚀 快速记录指南        → U4FnimoXwG1j
📋 ID 速查表           → Aa2aRAGLWuu4
```

### 📥 Inbox (临时收集箱)
```
00-Inbox              → h9skuCU9czep   ← 默认存放位置
```

### 🚀 Projects (进行中项目)
```
01-Projects           → 8C1UOi0hfib5
├── Oclaw 项目         → [待确认]
├── NETX 项目          → [待确认]
└── 计划               → THJbELUQ2Ecm
```

### 🏗️ Areas (持续责任)
```
02-Areas              → HFsgsHfH4nKN
├── 基础设施           → pS6clLY4g5sd
│   ├── QNAP-NAS      → 6CC2lab7vPDA
│   └── QNAP          → 9TRXB88ODggT
└── 开发环境           → b7lkhRneQk2a
    ├── API 密钥管理   → [待确认]
    ├── PG 数据库      → zdscNfnBnoqq
    ├── 启动命令       → 1tCnm2jbiJPW
    └── skill          → JRYSKzNWQaCp
```

### 📚 Resources (参考资源)
```
03-Resources          → 1AbShK4WDw38
├── Python            → M5wP7D0FZ819
├── PostgreSQL        → NZS3aOMlNJcp
├── Skills 开发指南    → yPold3qhllN1
│   └── Note-Taking Skill → TNyFX4lADEk5
├── Trilium Next 使用指南 → 2s26WHNqv0Q8
└── 学习              → l6OfBhJ804qL
```

### 🗄️ Archives (归档)
```
04-Archives           → 6rQ5acaYa7fZ
├── API (空)          → MLXD4mGL5mzh
└── 生活              → Gvn9zydADEYl
```

### 📝 Templates (模板)
```
99-Templates          → RVjlkQmiHxaw
```

---

## 🎯 功能说明

本 Skill 帮助用户在记录信息时自动判断最佳存放位置，遵循 PARA 知识管理方法，并**严格遵守目录限制**。

### 核心能力
1. **智能分类** - 根据内容自动推荐 Projects/Areas/Resources/Archives
2. **快速创建** - 一键在正确位置创建结构化笔记
3. **目录验证** - 强制验证父节点是否在允许列表中
4. **Inbox 管理** - 临时存储 + 定期整理提醒
5. **标签建议** - 自动添加合适的状态/优先级/类型标签
6. **关联推荐** - 推荐相关笔记建立链接

---

## 📋 触发条件

当用户提到以下关键词时触发：
- "记一下"、"记录"、"保存"、"添加笔记"
- "新建笔记"、"创建文档"、"写个笔记"
- "放在哪里"、"归到哪类"、"怎么分类"
- "inbox"、"整理笔记"、"归档"
- "项目笔记"、"技术文档"、"参考资料"

---

## 🔄 工作流程

### 1. 接收信息
用户提供要记录的内容或想法

### 2. 分析分类
根据内容特征判断所属类别：

| 特征 | 分类 | 示例 |
|------|------|------|
| 有明确目标/截止日期 | **Projects** | "Oclaw 新功能开发计划" |
| 持续责任/维护领域 | **Areas** | "NAS 备份策略"、"API 密钥更新" |
| 知识点/参考资料 | **Resources** | "Python 异步编程笔记"、"PostgreSQL 优化技巧" |
| 已完成/过时内容 | **Archives** | "2023 年项目总结" |
| 不确定/临时信息 | **Inbox** | "稍后整理的会议记录" |

### 3. 目录验证（关键步骤）
```javascript
// 验证父节点是否在允许列表中
const allowedParents = [
  'h9skuCU9czep',  // Inbox
  '8C1UOi0hfib5',  // Projects
  'pS6clLY4g5sd',  // Areas/基础设施
  'b7lkhRneQk2a',  // Areas/开发环境
  '1AbShK4WDw38',  // Resources
  '6rQ5acaYa7fZ',  // Archives
  'RVjlkQmiHxaw'   // Templates
];

if (!allowedParents.includes(parentNoteId)) {
  throw new Error("❌ 无法在指定位置创建笔记");
}
```

### 4. 创建笔记
- 在确定的父节点下创建新笔记
- 使用描述性标题
- 应用标准模板（如适用）
- 添加基础标签

### 5. 确认反馈
向用户展示：
- ✅ 已创建笔记的位置
- 📝 笔记标题和预览
- 🏷️ 应用的标签
- 🔗 推荐的相关笔记
- ⚠️ 如有目录限制问题，说明原因

---

## 📂 分类决策树

```
用户提供信息
    ↓
是否有明确的项目目标？
├─ 是 → Projects/[项目名称] (8C1UOi0hfib5)
│   └─ 如果项目不存在 → 先询问是否创建新项目
└─ 否 → 是否是持续责任领域？
    ├─ 是 → Areas/[领域名称]
    │   ├─ 基础设施 → pS6clLY4g5sd
    │   └─ 开发环境 → b7lkhRneQk2a
    └─ 否 → 是否是参考知识？
        ├─ 是 → Resources/[主题] (1AbShK4WDw38)
        │   └─ 技术栈、教程、文档、最佳实践
        └─ 否 → 是否已过时？
            ├─ 是 → Archives/ (6rQ5acaYa7fZ)
            └─ 否 → Inbox/ (h9skuCU9czep) ← 默认
```

---

## 🏷️ 标签系统

### 自动应用的标签

#### 状态标签
- `#status/active` - 进行中项目/任务
- `#status/pending` - 待处理事项
- `#status/completed` - 已完成
- `#status/archived` - 已归档

#### 优先级标签
- `#priority/high` - 高优先级（包含"紧急"、"重要"、"尽快"等词）
- `#priority/medium` - 中优先级（默认）
- `#priority/low` - 低优先级（包含"有空时"、"参考"等词）

#### 类型标签
- `#type/note` - 普通笔记
- `#type/task` - 任务清单（包含"待办"、"要做"等词）
- `#type/reference` - 参考资料
- `#type/meeting` - 会议记录
- `#type/idea` - 想法/灵感

#### 领域标签
- `#domain/tech` - 技术相关（代码、工具、框架等）
- `#domain/business` - 业务相关
- `#domain/personal` - 个人生活
- `#domain/learning` - 学习内容

---

## 💬 使用示例

### 示例 1: 记录项目任务
**用户**: "记一下，明天要完成 Oclaw 的搜索功能优化"

**助手**: 
```
✅ 已创建笔记

📍 位置：Projects/Oclaw 项目/搜索功能优化
🏷️ 标签：#status/active #priority/high #type/task #domain/tech
📅 截止：明天

是否需要设置提醒或添加到待办清单？
```

### 示例 2: 保存技术知识
**用户**: "记录一个 PostgreSQL 的性能优化技巧：使用 EXPLAIN ANALYZE 分析慢查询"

**助手**:
```
✅ 已创建笔记

📍 位置：Resources/PostgreSQL/性能优化技巧
🏷️ 标签：#type/reference #domain/tech #database
🔗 相关：PostgreSQL 使用指南

需要补充更多细节或示例吗？
```

### 示例 3: 临时想法
**用户**: "先记下来，周末再整理：关于技能市场化的想法"

**助手**:
```
✅ 已放入 Inbox

📍 位置：00-Inbox/技能市场化想法
🏷️ 标签：#status/pending #type/idea #domain/business
⏰ 提醒：周末整理

需要在周末提醒你整理这条笔记吗？
```

### 示例 4: 尝试在非授权目录创建（应拒绝）
**用户**: "把这个笔记放到根目录下"

**助手**:
```
❌ 抱歉，我无法在指定位置创建笔记。

⚠️ 目录限制规则：
为确保知识库结构稳定，我只能在规定目录下创建新笔记。

✅ 允许的目录：
- Inbox (h9skuCU9czep) - 临时收集
- Projects (8C1UOi0hfib5) - 项目相关
- Areas/基础设施 (pS6clLY4g5sd)
- Areas/开发环境 (b7lkhRneQk2a)
- Resources (1AbShK4WDw38) - 参考资料
- Archives (6rQ5acaYa7fZ) - 归档内容
- Templates (RVjlkQmiHxaw) - 模板

💡 建议：先放入 Inbox，之后可以手动移动。

是否要放入 Inbox？[是] [取消]
```

### 示例 5: 询问分类
**用户**: "这个 NAS 维护文档应该放在哪里？"

**助手**:
```
📂 建议分类：Areas/基础设施/QNAP-NAS

理由：
- NAS 维护是持续责任领域（Area）
- 属于基础设施范畴
- 已有 QNAP-NAS 子分类
- 父节点 ID: pS6clLY4g5sd

是否立即在此位置创建笔记？
```

---

## 🛠️ 工具调用

### Trilium Next API
- `create_note` - 创建新笔记（必须先验证父节点）
- `move_note` - 移动笔记到正确位置（仅当用户明确要求）
- `search_notes` - 查找相关笔记建立关联
- `read_attributes` - 读取现有标签
- `manage_attributes` - 添加/更新标签

### 可选集成
- Todo 系统 - 同步任务类笔记
- 日历系统 - 设置时间相关提醒
- Git - 备份重要笔记

---

## 📊 统计与报告

### 每周自动生成
- 新增笔记数量按分类统计
- Inbox 整理情况
- 最活跃的项目/领域
- 标签使用分布

### 每月回顾
- 完成项目归档
- 过时资源清理
- 分类体系优化建议

---

## ⚙️ 配置选项

### 用户偏好
```yaml
default_inbox_review: weekly  # Inbox 整理频率
auto_tag_priority: true       # 自动识别优先级
suggest_related: true         # 推荐相关笔记
backup_enabled: true          # 启用 Git 备份
```

### 目录限制（强制）
```yaml
directory_restrictions:
  enabled: true  # ⚠️ 必须为 true
  allowed_parents:
    - h9skuCU9czep   # Inbox
    - 8C1UOi0hfib5   # Projects
    - pS6clLY4g5sd   # Areas/基础设施
    - b7lkhRneQk2a   # Areas/开发环境
    - 1AbShK4WDw38   # Resources
    - 6rQ5acaYa7fZ   # Archives
    - RVjlkQmiHxaw   # Templates
  default_fallback: h9skuCU9czep  # 不确定时默认放入 Inbox
  strict_mode: true  # 严格模式，禁止任何越界操作
```

### 自定义分类
用户可以扩展默认分类：
- 新增 Projects
- 自定义 Areas
- 扩展 Resources 子分类

---

## 🚨 错误处理

### 常见问题

**Q: 找不到合适的分类？**  
A: 默认放入 Inbox (`h9skuCU9czep`)，并提示用户手动选择

**Q: 笔记标题重复？**  
A: 自动添加时间戳或序号区分

**Q: 父节点不存在？**  
A: 询问用户是否创建新分类或直接放入 Inbox

**Q: 尝试在非授权目录创建？**  
A: **拒绝**并显示允许目录列表，建议使用 Inbox

---

## 📈 最佳实践

### 给用户的建议
1. **及时记录** - 想法出现时立即记下
2. **信任系统** - 让 Skill 自动分类，事后可以调整
3. **定期整理** - 每周花 10 分钟整理 Inbox
4. **善用标签** - 不要过度标签化（3-5 个为宜）
5. **建立关联** - 主动链接相关笔记

### Skill 行为准则
1. **优先确认** - 不确定时询问用户而非猜测
2. **保持一致** - 同类内容使用相同分类逻辑
3. **最小干扰** - 快速创建，减少打断
4. **主动提醒** - 定期提示整理 Inbox 和归档
5. **严格遵守** - 绝不违反目录限制规则

---

## 🔮 未来增强

- [ ] AI 辅助摘要生成
- [ ] 自动提取关键词作为标签
- [ ] 智能关联推荐（基于内容相似度）
- [ ] 语音输入支持
- [ ] 多语言笔记支持
- [ ] 团队协作功能
- [ ] 自动审计目录合规性

---

## 📚 参考资源

- [PARA 方法](https://fortelabs.com/blog/para/)
- [Trilium Next 文档](https://triliumnext.org/)
- [知识管理最佳实践](Resources/Knowledge Management)
- [笔记记录规范](hgILpr4yRkcS)
- [知识库 ID 速查表](Aa2aRAGLWuu4)

---

**最后更新**: 2026-04-11  
**版本**: 1.1 (带目录限制)  
**⚠️ 重要**: 严格遵守目录限制，禁止在非授权位置创建笔记！
