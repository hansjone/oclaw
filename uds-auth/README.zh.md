# uds-auth

DeepSeek Harness 的UDS统一认证服务插件。利用现有UDS凭据实现自动单点登录(SSO)，并提供多租户会话隔离。

## 特性

- **自动单点登录**: 已登录UDS的用户无需再次扫码即可访问系统
- **多租户隔离**: 每个用户拥有独立的服务端会话，数据完全隔离
- **灵活的会话存储**: 支持内存（开发环境）和Redis（生产环境）两种存储方式
- **滑动过期**: 会话在活跃时自动延长，提升用户体验
- **标准API**: 业务组件可通过 `getUserContext()` 轻松获取当前用户

## 安装

```bash
dsh plugin --profile web add -w "github:your-org/uds-auth"
```

本地开发安装：

```bash
dsh plugin --profile web add -w "D:/code/gpt/uds-auth"
```

然后重启DeepSeek Harness。

## 配置

复制 `config.default.yaml` 到配置目录并自定义：

```yaml
udsAuth:
  baseUrl: https://uac.zte.com.cn
  systemCode: '100000456663'
  empNoHeader: X-Emp-No
  authValueHeader: X-Auth-Value
  langIdHeader: X-Lang-Id
  timeout: 5000

session:
  storeType: memory  # 或 'redis'（生产环境）
  redisUrl: redis://localhost:6379
  cookieName: UDS_SESSION
  cookieMaxAge: 1800000  # 30分钟
  cookieSecure: true
  cookieHttpOnly: true
  cookieSameSite: strict
  slidingExpiration: true
  slidingInterval: 300000  # 5分钟

loginPageUrl: https://uac.zte.com.cn/portal/login.html
```

## 使用方法

### 作为中间件

插件提供可集成到HTTP服务器的中间件：

```javascript
import udsAuthPlugin from 'uds-auth'
import { createServer } from 'http'

const config = {
  udsAuth: {
    baseUrl: 'https://uac.zte.com.cn',
    systemCode: '100000456663',
  },
  session: {
    storeType: 'memory',
    cookieMaxAge: 1800000,
  },
  loginPageUrl: 'https://uac.zte.com.cn/portal/login.html',
}

// 初始化插件
const ctx = {} // Cordis上下文
const plugin = await udsAuthPlugin(ctx, config)

// 获取服务
const { authMiddleware, apiHandlers } = plugin.services

// 在HTTP服务器中使用
const server = createServer(async (req, res) => {
  const ctx = { req, res }
  
  // 应用认证中间件
  await authMiddleware(ctx, async () => {
    // 如果ctx.userContext存在则用户已认证
    if (ctx.userContext) {
      res.writeHead(200, { 'Content-Type': 'application/json' })
      res.end(JSON.stringify({
        message: '你好 ' + ctx.userContext.username,
        user: ctx.userContext,
      }))
    } else {
      res.writeHead(401)
      res.end('未授权')
    }
  })
})

server.listen(3000)
```

### 获取当前用户

业务组件可以访问当前用户上下文：

```javascript
import { getUserContext, withUserContext } from 'uds-auth'

async function myBusinessLogic() {
  // 使用AsyncLocalStorage确保请求隔离
  await withUserContext(userContext, async () => {
    const user = getUserContext()
    
    if (!user) {
      throw new Error('未认证')
    }
    
    console.log('当前用户:', user.username)
    console.log('用户ID:', user.userId)
    console.log('部门:', user.department)
    
    // 继续业务逻辑...
  })
}
```

### API端点

插件暴露以下端点：

- `POST /api/uds-auth/logout` - 登出并销毁会话
- `GET /api/uds-auth/me` - 获取当前用户信息

集成示例：

```javascript
import { createApiHandlers } from 'uds-auth'

const apiHandlers = createApiHandlers(config, sessionStore)

// 在路由中
app.post('/api/logout', (req, res) => {
  apiHandlers.logout({ req, res })
})

app.get('/api/me', (req, res) => {
  apiHandlers.getCurrentUser({ req, res })
})
```

## 会话存储

### 内存存储（开发）

```javascript
const config = {
  session: {
    storeType: 'memory',
  },
}
```

会话存储在进程内存中，重启后丢失。仅适用于开发环境。

### Redis存储（生产）

```javascript
const config = {
  session: {
    storeType: 'redis',
    redisUrl: 'redis://your-redis-host:6379',
  },
}
```

需要安装 `redis` 包：

```bash
npm install redis
```

会话跨重启持久化，支持分布式部署。

## 安全考虑

- Session Cookie设置了`HttpOnly`、`Secure`和`SameSite=strict`属性
- Token值永远不会被记录到日志
- Session ID使用`crypto.randomUUID()`生成
- 不同用户的会话完全隔离

## 测试

运行测试：

```bash
cd uds-auth
node --test test/**/*.test.js
```

或使用手动测试运行器：

```bash
node test/config.test.js
node test/session/memory-store.test.js
node test/uds/client.test.js
node test/uds/validator.test.js
node test/middleware/auth-middleware.test.js
node test/context.test.js
node test/api.test.js
```

## 项目结构

```
uds-auth/
├── lib/
│   ├── config.js           # 配置加载和验证
│   ├── index.js           # 插件入口
│   ├── context.js         # AsyncLocalStorage用户上下文
│   ├── api.js            # API处理器（登出、获取当前用户）
│   ├── session/
│   │   ├── store.js       # 抽象会话存储基类
│   │   ├── memory-store.js # 内存会话存储
│   │   ├── redis-store.js # Redis会话存储
│   │   └── factory.js     # 会话存储工厂
│   ├── uds/
│   │   ├── client.js      # UDS验证客户端
│   │   └── validator.js   # 凭据提取和验证
│   └── middleware/
│       ├── auth-middleware.js      # 主认证中间件
│       └── session-middleware.js   # 会话管理中间件
├── test/
│   ├── config.test.js
│   ├── context.test.js
│   ├── api.test.js
│   ├── session/
│   ├── uds/
│   ├── middleware/
│   └── integration/
├── docs/
│   └── frontend-auth-analysis.md  # 前端认证分析文档
├── config.default.yaml      # 默认配置
├── cordis.patch.yml        # DeepSeekHarness插件配置
├── package.json
├── README.md
└── README.zh.md
```

## License

MIT
