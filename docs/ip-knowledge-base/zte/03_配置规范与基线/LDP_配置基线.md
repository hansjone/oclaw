# LDP配置基线

## 标准配置模板

### 基础LDP配置
```bash
mpls ldp instance 1
  discovery hello holdtime 180
  discovery targeted-hello holdtime 180
  graceful-restart
  graceful-restart timer max-recovery 600
  graceful-restart timer neighbor-liveness 300
  access-fec ip-prefix host-route-only  ! 显示指定仅主机路由分配标签
  interface smartgroup1  ！接口使能ldp
  $
  router-id loopback1  ! 显式指定Router-ID（推荐用Loopback地址）
  target-session 10.26.63.152  ! 通过 target-session 配置ldp

```
---
## 关键参数推荐值

| 参数　　　　　　　| 推荐值　　　　　　　　| 说明　　　　　　　　　　　　　　　　 |
| -------------------| -----------------------| --------------------------------------|
| Router-ID　　　　 | Loopback0地址（32位） | 必须全网唯一且稳定　　　　　　　　　 |
| 传输地址　　　　　| Loopback地址　　　　　| 避免物理接口Down导致LDP会话中断　　　|
| Hello间隔（链路） | 5秒　　　　　　　　　 | 默认值，直连邻居发现　　　　　　　　 |
| Hello间隔（目标） | 15秒　　　　　　　　　| 用于非直连邻居（需配`neighbor`命令） |
| Keepalive间隔　　 | 45秒　　　　　　　　　| TCP连接保活　　　　　　　　　　　　　|
| Hold Time　　　　 | 180秒　　　　　　　　 | Hello保持时间（4倍Hello间隔）　　　　|
| 标签分配模式　　　| DU（下游主动）　　　　| 默认模式，无需配置　　　　　　　　　 |
| FEC过滤策略　　　 | 不过滤（默认）　　　　| 除非有安全或资源限制需求　　　　　　 |

---
## 常见配置陷阱与规避

### ⚠️ 陷阱1：access-fec过滤导致标签缺失
**现象**：某些非32位FEC没有分配到标签，MPLS转发出接口为NULL

**错误配置示例**：
```bash
mpls ldp nstance 1
  access-fec ip-prefix host-route-only  ! 只给32位主机路由分标签
```

**问题根因**：
- 该配置强制LDP只为/32掩码的主机路由分配标签
- 对于/30或/31的互联地址，即使LDP默认会分配标签，也会被过滤掉
- **后果**：跨域VPN场景中，若BGP下一跳是互联地址（非32位），会导致标签缺失→流量黑洞

**规避方案**：
- 评估业务需求，若无特殊安全要求，**不要配置**`access-fec`过滤
- 若必须限制标签分配范围，使用更精细的prefix-list：
  ```bash
  ip prefix-list ALLOW-HOST-ROUTES seq 5 permit 0.0.0.0/0 le 32
  mpls ldp
    access-fec ip-prefix prefix-list ALLOW-HOST-ROUTES  ! 允许所有前缀
  ```

**关联案例**：参见 `04_历史故障案例库/BGP/标签与LDP类/BGP_跨域下一跳NULL_LDP策略与下一跳修复_20260720.md`

---
## 验证命令速查

```bash
# 查看ldp是否存在告警
show alarm current typeid ldp
# 查看LDP会话状态
show mpls ldp neighbor brief instance 1
show mpls ldp neighbor <ldp-neighbor> detail instance 1
show mpls ldp neighbor detail instance 1

# 查看标签绑定关系
show mpls ldp bindings 10.0.0.8 32 detail instance 1 ! 优先使用
show mpls ldp bindings 10.0.0.8 32 instance 1 ! 优先使用
show mpls ldp bindings instance 1 
# 查看标签转发表
show mpls forwarding-table 10.0.0.8 32
show mpls forwarding-table

# 查看LDP配置
show running-config ldp

```

---
**维护建议**：
- 每季度审查一次LDP配置基线，确保与现网实践一致
- 新增LDP邻居前，必须在变更窗口内验证MD5认证和标签分配
- 对于跨域Option-B场景，务必同步检查BGP next-hop-self配置

**关联文档**：
- `06_标准SOP与工具脚本/MPLS标签排障命令速查.md`
