# uds-auth

UDS (Unified Authentication Service) authentication plugin for DeepSeek Harness. Provides automatic SSO authentication using existing UDS credentials and multi-tenant session isolation.

## Features

- **Automatic SSO**: Users already logged into UDS can access the system without scanning QR codes again
- **Multi-tenant isolation**: Each user gets an independent server-side session with complete data isolation
- **Flexible session storage**: Choose between in-memory (development) or Redis (production)
- **Sliding expiration**: Sessions automatically extend on activity for better UX
- **Standard API**: Easy integration with business components via `getUserContext()`

## Installation

```bash
dsh plugin --profile web add -w "github:your-org/uds-auth"
```

Or for local development:

```bash
dsh plugin --profile web add -w "D:/code/gpt/uds-auth"
```

Then restart DeepSeek Harness.

## Configuration

Copy `config.default.yaml` to your config directory and customize:

```yaml
udsAuth:
  baseUrl: https://uac.zte.com.cn
  systemCode: '100000456663'
  empNoHeader: X-Emp-No
  authValueHeader: X-Auth-Value
  langIdHeader: X-Lang-Id
  timeout: 5000

session:
  storeType: memory  # or 'redis' for production
  redisUrl: redis://localhost:6379
  cookieName: UDS_SESSION
  cookieMaxAge: 1800000  # 30 minutes
  cookieSecure: true
  cookieHttpOnly: true
  cookieSameSite: strict
  slidingExpiration: true
  slidingInterval: 300000  # 5 minutes

loginPageUrl: https://uac.zte.com.cn/portal/login.html
```

## Usage

### As Middleware

The plugin provides middleware that can be integrated into your HTTP server:

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

// Initialize plugin
const ctx = {} // Your Cordis context
const plugin = await udsAuthPlugin(ctx, config)

// Access services
const { authMiddleware, apiHandlers } = plugin.services

// Use in your HTTP server
const server = createServer(async (req, res) => {
  const ctx = { req, res }
  
  // Apply auth middleware
  await authMiddleware(ctx, async () => {
    // User is authenticated if ctx.userContext exists
    if (ctx.userContext) {
      res.writeHead(200, { 'Content-Type': 'application/json' })
      res.end(JSON.stringify({
        message: 'Hello ' + ctx.userContext.username,
        user: ctx.userContext,
      }))
    } else {
      res.writeHead(401)
      res.end('Unauthorized')
    }
  })
})

server.listen(3000)
```

### Getting Current User

Business components can access the current user context:

```javascript
import { getUserContext, withUserContext } from 'uds-auth'

async function myBusinessLogic() {
  // Using AsyncLocalStorage for request isolation
  await withUserContext(userContext, async () => {
    const user = getUserContext()
    
    if (!user) {
      throw new Error('Not authenticated')
    }
    
    console.log('Current user:', user.username)
    console.log('User ID:', user.userId)
    console.log('Department:', user.department)
    
    // Proceed with business logic...
  })
}
```

### API Endpoints

The plugin exposes these endpoints:

- `POST /api/uds-auth/logout` - Logout and destroy session
- `GET /api/uds-auth/me` - Get current user info

Example integration:

```javascript
import { createApiHandlers } from 'uds-auth'

const apiHandlers = createApiHandlers(config, sessionStore)

// In your router
app.post('/api/logout', (req, res) => {
  apiHandlers.logout({ req, res })
})

app.get('/api/me', (req, res) => {
  apiHandlers.getCurrentUser({ req, res })
})
```

## Session Storage

### Memory Store (Development)

```javascript
const config = {
  session: {
    storeType: 'memory',
  },
}
```

Sessions are stored in process memory and lost on restart. Suitable for development only.

### Redis Store (Production)

```javascript
const config = {
  session: {
    storeType: 'redis',
    redisUrl: 'redis://your-redis-host:6379',
  },
}
```

Requires the `redis` package:

```bash
npm install redis
```

Sessions persist across restarts and support distributed deployments.

## Security Considerations

- Session cookies are set with `HttpOnly`, `Secure`, and `SameSite=strict` attributes
- Token values are never logged
- Session IDs are generated using `crypto.randomUUID()`
- Different users' sessions are completely isolated

## Testing

Run tests:

```bash
cd uds-auth
node --test test/**/*.test.js
```

Or use the manual test runner:

```bash
node test/config.test.js
node test/session/memory-store.test.js
node test/uds/client.test.js
node test/uds/validator.test.js
node test/middleware/auth-middleware.test.js
node test/context.test.js
node test/api.test.js
```

## Project Structure

```
uds-auth/
├── lib/
│   ├── config.js           # Configuration loading and validation
│   ├── index.js           # Plugin entry point
│   ├── context.js         # AsyncLocalStorage user context
│   ├── api.js             # API handlers (logout, getCurrentUser)
│   ├── session/
│   │   ├── store.js       # Abstract session store base class
│   │   ├── memory-store.js # In-memory session store
│   │   ├── redis-store.js # Redis-backed session store
│   │   └── factory.js     # Session store factory
│   ├── uds/
│   │   ├── client.js      # UDS verification client
│   │   └── validator.js   # Credential extraction and validation
│   └── middleware/
│       ├── auth-middleware.js      # Main authentication middleware
│       └── session-middleware.js   # Session management middleware
├── test/
│   ├── config.test.js
│   ├── context.test.js
│   ├── api.test.js
│   ├── session/
│   ├── uds/
│   ├── middleware/
│   └── integration/
├── docs/
│   └── frontend-auth-analysis.md  # Frontend authentication analysis
├── config.default.yaml      # Default configuration
├── cordis.patch.yml        # DeepSeekHarness plugin configuration
├── package.json
├── README.md
└── README.zh.md
```

## License

MIT
