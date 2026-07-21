# BGP VPN跨域标签异常排查树

## 现象：VRF路由下一跳为NULL或出接口为NULL

### 第零层排查：业务层连通性测试（起点！）

#### 子步骤0.1：Ping测业务地址
- **命令**：`ping vrf <vrf-name> <dest-ip>`
- **示例**：`ping vrf test 4.1.1.1`
- **目的**：确认业务是否真正中断，区分是路由问题还是转发问题
- **预期结果**：
  - 通 → 业务正常，无需进一步排查
  - 不通 → 进入下一步trace定位断点

#### 子步骤0.2：Trace定位路径
- **命令**：`trace vrf <vrf-name> <dest-ip>`
- **目的**：确定报文在哪一跳丢失，判断是本地问题还是远端问题
- **典型场景**：
  - 第一跳就失败 → 本地VRF路由或直连问题
  - 中间某跳失败 → 该节点标签或IGP问题
  - 能到最后一跳但不通 → 对端CE设备或业务侧问题

---

### If `show ip forwarding route vrf <vrf-name>`显示Interface为NULL
- **Then第一层排查：MPLS标签分配**
  - `show mpls forwarding-table <next-hop-ip>` → 查看Outgoing Label
  - 若为"no label"或"pop"，说明LDP未分配标签
  
#### 子步骤1.1：检查LDP会话状态
- `show mpls ldp neighbor brief instance <instance-id>` → 确认LDP邻居为Established
- `show mpls ldp neighbor detail instance <id>` → 查看标签分发能力

#### 子步骤1.2：检查LDP策略配置（关键！）
- `show running-config ldp` → 查找access-fec、fec-filter等过滤配置
- `show mpls ldp binding instance <id>` → 查看实际分配的标签绑定
- **常见陷阱**：`access-fec ip-prefix host-route-only`会强制LDP只给32位主机路由分配标签
- **排障动作**：评估必要性，若非强制需求则去除该限制
- **示例输出**：
```
!<ldp>
mpls ldp instance 1
  access-fec ip-prefix host-route-only
  discovery hello holdtime 180
  discovery targeted-hello holdtime 180
  interface smartgroup1
  router-id loopback1
  target-session 10.26.63.152
$
!</ldp>
```

#### 子步骤1.3：检查下一跳地址的掩码长度
- `show ip forwarding route <next-hop-ip>` → 查看掩码是否为/32
- **原理**：LDP默认只为32位主机路由分配标签（倒数第二跳弹出机制前提）
- 若为/30或/31互联地址，LDP可能不分配标签

---

### If 标签分配正常但业务仍不通
- **Then第二层排查：BGP下一跳属性**
  - `show bgp vpnv4 unicast vrf <vrf-name> route` → 查看完整的BGP VPNv4路由表
  - `show bgp vpnv4 unicast labels` → 查看标签信息
  - **关键字段**：Next Hop（下一跳）、Label（标签）、Path（AS_PATH）

#### 子步骤2.1：检查ASBR配置
- 登录对端ASBR，查看BGP配置
- **关键配置缺失**：ASBR向IBGP宣告EBGP路由时未配置`neighbor <ibgp-peer> next-hop-self`
- **排障动作**：在ASBR上配置`neighbor <ibgp-peer> next-hop-self`
- **验证命令**：`show bgp vpnv4 unicast vrf <vrf-name> neighbor <peer-ip> advertised-routes`

#### 子步骤2.2：验证修复效果
- 配置next-hop-self后，PE上BGP路由的下一跳应变为ASBR的Loopback地址（32位）
- LDP为主机路由分配标签 → `show mpls forwarding-table`应显示明确的Outgoing Label
- `show ip forwarding route vrf <vrf-name>`应显示实际出接口

---

### If BGP路由正常但IGP不可达
- **Then第三层排查：IGP邻接关系**
  - `show isis adjacency` → 检查ISIS邻接状态
  - `show isis hostname` → 查看系统ID映射
  - `show ip ospf neighbor` → 检查OSPF邻居状态

#### 子步骤3.1：检查IGP拓扑同步
- `show isis database` → 查看LSDB完整性
- `show ip ospf database` → 检查OSPF链路状态数据库
- **常见问题**：IGP未学习到BGP下一跳的路由

---

**完整排查流程图**：
```
业务不通
  ↓
ping vrf <vrf-name> <dest-ip> → 通 → 结束
  ↓ 不通
trace vrf <vrf-name> <dest-ip> → 定位断点
  ↓
show ip forwarding route vrf <vrf-name>
  ↓ Interface为NULL
show mpls forwarding-table <next-hop-ip>
  ↓ 无标签
show mpls ldp neighbor brief instance <id> → Down → 修复LDP会话
  ↓ Established                    ↓ 有标签
show mpls ldp binding instance <id>     show bgp vpnv4 unicast vrf <name> route
  ↓ access-fec限制                 ↓ NextHop非32位
移除限制或接受现状                ASBR配置next-hop-self
  ↓                                ↓
重新学习标签                      验证转发恢复
  ↓
show isis adjacency
  ↓ 无邻接
修复IGP邻接关系
```

**关键命令速查**：
```bash
# 业务层测试
ping vrf <vrf-name> <dest-ip>
trace vrf <vrf-name> <dest-ip>

# VRF路由转发信息
show ip forwarding route vrf <vrf-name>
show ip forwarding route vrf <vrf-name> <dest-ip>
show ip route vpn

# MPLS标签转发表
show mpls forwarding-table
show mpls forwarding-table <next-hop-ip>
show mpls forwarding-table vpnv4-lsp

# LDP会话与策略（必须指定instance！）
show mpls ldp neighbor brief instance <id>
show mpls ldp neighbor detail instance <id>
show mpls ldp binding instance <id>
show mpls ldp parameters instance <id>
show running-config ldp

# VPNv4路由属性
show bgp vpnv4 unicast vrf <vrf-name> route
show bgp vpnv4 unicast labels

# IGP邻接
show isis adjacency
show isis hostname
show ip ospf neighbor
```

**关联案例**：参见 `04_历史故障案例库/BGP/标签与LDP类/BGP_跨域下一跳NULL_LDP策略与下一跳修复_20260720.md`

**理论锚点**：
- LDP标签分配策略（默认只为/32主机路由分配标签）
- 跨域VPN Option-B转发模型（ASBR的next-hop-self作用）
- FEC过滤机制（access-fec等配置的影响）
- 标签转发与IP转发的协同工作原理
