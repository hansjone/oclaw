# Ops IP 知识库快速参考

## 1) 根路径与工具参数

| 项 | 值 |
|----|-----|
| 根目录 | `docs/ip-knowledge-base` |
| 当前厂商分区 | `zte/` |
| 搜索工具 | `search_files` |
| 阅读工具 | `read_file` |
| 列目录 | `list_directory` |

**search_files 推荐参数**：

```json
{
  "pattern": "下一跳 NULL",
  "root": "docs/ip-knowledge-base",
  "file_glob": "**/*.md",
  "regex": false,
  "max_matches": 50
}
```

**read_file 分段阅读**（逻辑树/案例较长时）：

```json
{
  "path": "docs/ip-knowledge-base/zte/01_协议排障逻辑树/BGP/VPN跨域标签异常排查树.md",
  "offset": 1,
  "limit": 120
}
```

## 2) 六层目录职责

| 目录 | 回答的问题 | RAG 优先级（排障场景） |
|------|------------|------------------------|
| `01_协议排障逻辑树` | 怎么想 | 高（决策顺序） |
| `02_产品平台特性` | 设备特有行为 | 最高（模型不知道） |
| `03_配置规范与基线` | 应该怎么配 | 中 |
| `04_历史故障案例库` | 真实发生过什么 | 高（根因链） |
| `05_监控指标与告警阈值` | 什么算异常 | 中（告警解读） |
| `06_标准SOP与工具脚本` | 敲什么命令 | 高（操作动作） |

## 3) 当前已收录文档（截至维护时）

### 01 协议排障逻辑树

- `zte/01_协议排障逻辑树/BGP/VPN跨域标签异常排查树.md`

### 02 产品平台特性

- （占位，见目录 README）

### 03 配置规范与基线

- `zte/03_配置规范与基线/LDP_配置基线.md`
- `zte/03_配置规范与基线/BGP_跨域配置规范.md`

### 04 历史故障案例库

- `zte/04_历史故障案例库/BGP/标签与LDP类/BGP_跨域下一跳NULL_LDP策略与下一跳修复_20260720.md`
  - 案例编号：`BGP-CROSS-DOMAIN-001`
  - 关键词：`#下一跳NULL` `#LDP标签分配` `#access-fec` `#next-hop-self`

### 05 监控指标与告警阈值

- （占位，见目录 README）

### 06 标准 SOP 与工具脚本

- `zte/06_标准SOP与工具脚本/故障处理常用命令.md`
- `zte/06_标准SOP与工具脚本/命令探索方法论.md`

## 4) 按场景的检索关键词

| 场景 | 建议 pattern（可多次搜索） | 预期命中层 |
|------|---------------------------|------------|
| VPN 跨域不通 / 下一跳 NULL | `下一跳NULL`、`access-fec`、`next-hop-self`、`VPN跨域` | 01 + 04 + 03 |
| MPLS 标签缺失 / Interface NULL | `标签`、`mpls forwarding`、`LDP` | 01 + 04 + 06 |
| BGP 跨域怎么配 | `Option-B`、`跨域配置`、`next-hop-self` | 03 |
| 不认识 LDP 命令 | `access-fec`、`ldp instance` | 02 + 03 |
| 命令忘了怎么敲 | `show bgp`、`命令探索` | 06 |
| 告警是否严重 | `阈值`、`超限` | 05 |

## 5) BGP 跨域排障推荐阅读顺序（示例）

1. `search_files` → 命中案例 `BGP_跨域下一跳NULL...`
2. `read_file` 案例 §1 现象 + §3 根因表
3. `read_file` `VPN跨域标签异常排查树.md` 对应 If 分支
4. `read_file` `BGP_跨域配置规范.md` 检查清单（若涉及配置修复）
5. `mcp__netx__execManagedNe` 按树执行验证命令（只读）
6. 输出：结论 + 案例路径 + CLI 摘录

## 6) 与 UME 告警联动（可选）

当用户从告警切入排障：

1. `ops-netx-ume-playbook`：定位网元 `host_name`、告警 `event_type`/`native_probable_cause`
2. 将告警关键词代入 `search_files`（如 BGP、LDP、Fan）
3. 若 `05_监控指标与告警阈值` 有对应阈值文档，对照是否真异常
4. 需要设备侧确认时切 `ops-netx-managed-ne-playbook`

## 7) 知识沉淀（闭环后）

排障结束且用户同意记录时，新案例建议结构（写入 `04_历史故障案例库/`）：

- 案例元数据表（编号、协议、关键词、日期、等级）
- §1 现象特征（含命令输出）
- §2 理论锚点（简短，不抄 RFC）
- §3 根因推理表（层层递进）
- §4 修复与验证
- 维护者 + netx 实测网元

配套产出：从案例拆 `01` 逻辑树节点 + `06` 三五步速查。
