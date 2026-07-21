# BGP跨域配置规范（Option-B场景）

## 适用场景
- 不同AS之间的MPLS VPN互联（如AS100与AS200的VPN用户互通）
- 需要端到端的MPLS标签转发，避免在ASBR上解封装再封装

---
## Option-B架构说明

### 网络拓扑
```
CE1 --- PE1 --- ASBR1 ==== ASBR2 --- PE2 --- CE2
(AS100)         (AS100)  (AS200)     (AS200)
                 |        |
              EBGP会话   EBGP会话
              (带标签)   (带标签)
```

**关键特征**：
- ASBR1和ASBR2之间建立EBGP会话，交换VPNv4路由（带标签）
- ASBR向IBGP邻居（PE）宣告从EBGP学到的路由
- **核心要求**：ASBR必须配置`next-hop-self`，否则PE收到的BGP下一跳是对端ASBR的互联地址（非32位），导致LDP无法分配标签

---
## 标准配置模板

### ASBR配置（以ASBR1为例，AS100侧）
```bash
! BGP基础配置
router bgp 100
  neighbor 20.0.0.2 remote-as 200        ! EBGP邻居（ASBR2的互联地址）
  neighbor 20.0.0.2 ebgp-multihop 2      ! 若非直连需配多跳
  neighbor 20.0.0.2 update-source loopback0
  
  ! VPNv4地址族（关键！）
  address-family vpnv4
    neighbor 20.0.0.2 activate           ! 激活EBGP邻居
    neighbor 20.0.0.2 send-label         ! 发送标签（Cisco语法，5800-4X类似）
    
    ! 向IBGP邻居宣告时修改下一跳（最关键的一步！）
    neighbor 10.0.0.1 remote-as 100      ! IBGP邻居（PE路由器）
    neighbor 10.0.0.1 next-hop-self      ! ⭐ 强制将下一跳改为本机Loopback
    
  exit-address-family
  
  ! IPv4单播地址族（可选，用于底层IGP路由）
  address-family ipv4 unicast
    network 10.0.0.1 mask 255.255.255.255  ! 宣告Loopback
  exit-address-family
```

### PE配置（以PE1为例，AS100侧）
```bash
router bgp 100
  ! IBGP全互联或使用路由反射器
  neighbor 10.0.0.2 remote-as 100        ! ASBR1的Loopback
  neighbor 10.0.0.2 update-source loopback0
  
  address-family vpnv4
    neighbor 10.0.0.2 activate
    ! 不需要配next-hop-self，因为ASBR已经做了
  exit-address-family
  
  ! VRF配置（关联CE侧）
  vrf definition VPN-A
    rd 100:1
    route-target export 100:1
    route-target import 100:1
  exit-vrf-definition
  
  interface gei-1/1
    vrf forwarding VPN-A
    ip address 192.168.1.1 255.255.255.0
  end
```

---
## 关键配置检查清单

### ASBR必查项
- [ ] `address-family vpnv4`下配置了EBGP邻居并`activate`
- [ ] 配置了`send-label`或等价命令（启用标签分发）
- [ ] 向IBGP邻居宣告时配置了`next-hop-self`
- [ ] ASBR的Loopback地址通过IGP宣告（确保IBGP可达）

### PE必查项
- [ ] IBGP邻居关系使用Loopback地址建立
- [ ] VRF的RD和Route Target配置正确
- [ ] 从ASBR学到的VPNv4路由的下一跳是ASBR的Loopback（32位）

---
## 验证步骤

### 第1步：检查ASBR上的BGP路由
```bash
# 在ASBR1上执行
show bgp vpnv4 un addr <dest-prefix>

# 期望输出关键字段：
#   From 20.0.0.2 (20.0.0.2): 下一跳=20.0.0.2（EBGP对端）
#   From 10.0.0.1 (10.0.0.1): 下一跳=10.0.0.1（已改为本机Loopback）
```

### 第2步：检查PE上的BGP路由和标签
```bash
# 在PE1上执行
show bgp vpnv4 un addr <dest-prefix>

# 期望输出：
#   Next hop: 10.0.0.2（ASBR1的Loopback，32位主机路由）
#   Label: 16001（明确的MPLS标签）

show ip forwarding route vrf VPN-A <dest-prefix>

# 期望输出：
#   Interface: gei-1/2（实际出接口，不是NULL）
#   Gw: 10.0.0.2（下一跳可达）
```

### 第3步：端到端连通性测试
```bash
# 从CE1 ping CE2的地址
ping vrf VPN-A <CE2-IP> source <CE1-IP>

# 若不通，用tracerace定位断点
traceroute vrf VPN-A <CE2-IP>
```

---
## 常见故障与根因

### 故障1：PE上VRF路由下一跳为NULL
**现象**：`show ip forwarding route vrf`显示Interface=NULL

**可能根因**：
1. **ASBR未配next-hop-self** → PE收到的下一跳是对端ASBR的互联地址（/30），LDP不分配标签
2. **LDP配置了access-fec过滤** → 即使下一跳是32位，也可能被过滤掉

**排障流程**：
```bash
# 步骤1：查看BGP下一跳
show bgp vpnv4 un addr <prefix> | include Next

# 步骤2：若下一跳是/30地址（如20.0.0.2/30），则ASBR肯定没配next-hop-self
# 步骤3：若下一跳是32位但仍无标签，检查LDP策略
show running-config mpls ldp | include access-fec
```

**关联案例**：参见 `04_历史故障案例库/BGP/标签与LDP类/BGP_跨域下一跳NULL_LDP策略与下一跳修复_20260720.md`

---
### 故障2：ASBR上EBGP邻居无法建立
**现象**：`show ip bgp summary`中EBGP邻居状态为Idle或Active

**可能根因**：
1. TCP端口179被ACL阻断
2. EBGP多跳未配置（若非直连）
3. MD5认证不匹配
4. Update-source配置错误

**排障命令**：
```bash
show ip bgp neighbors <ip>                # 查看邻居详细状态
show access-lists | include 179           # 检查ACL是否阻断BGP
show running-config | include router bgp  # 验证ebgp-multihop和update-source
```

---
### 故障3：标签分配正常但业务仍不通
**现象**：MPLS转发表有标签，但ping不通

**可能根因**：
1. **VRF路由泄露问题**：Route Target配置错误，导致PE没有导入对端路由
2. **CEF转发异常**：硬件转发表未正确编程
3. **MTU不匹配**：MPLS报文超过链路MTU被丢弃

**排障命令**：
```bash
# 检查VRF路由表
show ip route vrf VPN-A

# 检查MPLS转发统计
show mpls forwarding-table statistics

# 检查接口MTU
show interface <interface> | include MTU
```

---
## 配置优化建议

### 1. 使用路由反射器简化IBGP全互联
对于大型网络，PE之间不必全互联建IBGP：
```bash
# 指定RR（路由反射器）
router bgp 100
  neighbor 10.0.0.100 remote-as 100      # RR的Loopback
  neighbor 10.0.0.100 route-reflector-client  # 仅在RR上配
  
# PE侧无需特殊配置，RR会自动反射路由
```

### 2. 启用BGP PIC（快速重收敛）
```bash
router bgp 100
  bgp fast-external-failover             # 链路Down立即撤销路由
  neighbor <ip> fall-over bfd            # 与BFD联动检测
```

### 3. 限制接收的前缀数量（防攻击）
```bash
router bgp 100
  neighbor <ip> maximum-prefix 10000 90  # 最多1万条，90%时告警
```

---
**维护建议**：
- 每次新增跨域业务前，必须在实验室模拟Option-B场景验证配置
- 定期审查ASBR的next-hop-self配置（现场变更可能误删）
- 对于重要客户VPN，部署BFD实现亚秒级故障检测

**关联文档**：
- `01_协议排障逻辑树/BGP/VPN跨域标签异常排查树.md`
- `02_产品平台特性/协议实现差异.md`（BGP next-hop-self行为差异）
