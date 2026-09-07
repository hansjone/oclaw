/**
 * uds-auth Cordis Client Plugin
 * 登录徽章 - 注册到 sidebar.brand.name (scope: root, 所有页面都显示)
 */
const CSS = `
.uds-auth-badge{display:flex;align-items:center;gap:6px;padding:4px 10px;border-radius:4px;background:var(--dsw-alias-bg-module-platform,rgba(242,243,245,1));border:1px solid var(--dsw-alias-border-l2,#dfe1e5);color:var(--dsw-alias-label-primary,#1f2329);font-size:13px;cursor:pointer;font-weight:500;transition:all .15s}.uds-auth-badge:hover{background:var(--dsw-alias-interactive-bg-hover,rgba(247,248,250,1))}.uds-auth-badge-unauth{color:var(--dsw-alias-label-tertiary,#8f959e)}.uds-auth-badge-unauth:hover{color:var(--dsw-alias-label-secondary,#646a73)}.uds-auth-avatar{width:22px;height:22px;border-radius:50%;background:linear-gradient(135deg,var(--dsw-alias-state-business-primary,#3370ff),var(--dsw-alias-state-success-primary,#20a162));display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;color:#fff;flex-shrink:0}.uds-auth-badge-unauth .uds-auth-avatar{background:var(--dsw-alias-bg-module-platform,rgba(242,243,245,1));color:var(--dsw-alias-label-tertiary,#8f959e)}.uds-auth-role-badge{font-size:10px;padding:1px 6px;border-radius:10px;font-weight:600}.uds-auth-role-super_admin{background:rgba(213,73,65,.12);color:var(--dsw-alias-state-error-primary,#d54941)}.uds-auth-role-admin{background:rgba(217,119,6,.12);color:var(--dsw-alias-state-warn-primary,#d97706)}.uds-auth-role-fallback_admin{background:rgba(51,112,255,.12);color:var(--dsw-alias-state-business-primary,#3370ff)}.uds-auth-dropdown{position:absolute;top:100%;right:0;margin-top:8px;background:var(--dsw-alias-bg-layer-1,#fff);border-radius:8px;border:1px solid var(--dsw-alias-border-l2,#dee0e3);box-shadow:0 8px 28px rgba(0,0,0,.08);min-width:220px;z-index:1000;overflow:hidden}.uds-auth-info{padding:14px 16px;border-bottom:1px solid var(--dsw-alias-border-l1,#eef0f3)}.uds-auth-info-name{font-weight:600;margin-bottom:4px;color:var(--dsw-alias-label-primary,#1f2329);font-size:14px}.uds-auth-info-detail{font-size:12px;color:var(--dsw-alias-label-secondary,#646a73);margin-top:2px;display:flex;justify-content:space-between}.uds-auth-info-detail-label{color:var(--dsw-alias-label-tertiary,#8f959e);margin-right:8px}.uds-auth-qr-container{padding:16px;text-align:center}.uds-auth-qr-canvas{display:block;margin:0 auto;width:160px;height:160px}.uds-auth-qr-img{display:block;margin:0 auto;width:160px;height:160px}.uds-auth-qr-status{font-size:12px;color:var(--dsw-alias-label-secondary,#646a73);margin-top:8px;text-align:center}.uds-auth-qr-refresh{margin-top:8px;padding:6px 12px;background:var(--dsw-alias-state-business-primary,#3370ff);color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:12px}.uds-auth-qr-refresh:hover{opacity:.9}.uds-auth-settings-btn{width:calc(100% - 32px);margin:8px 16px 0;padding:8px 12px;background:var(--dsw-alias-bg-module-platform,#f4f5f7);color:var(--dsw-alias-label-primary,#1f2329);border:1px solid var(--dsw-alias-border-l2,#dfe1e5);border-radius:4px;cursor:pointer;font-size:13px;text-align:left}.uds-auth-settings-btn:hover{background:var(--dsw-alias-interactive-bg-hover,#f7f8fa)}.uds-auth-logout{width:calc(100% - 32px);margin:8px 16px 16px;padding:8px 12px;background:rgba(213,73,65,.08);color:var(--dsw-alias-state-error-primary,#d54941);border:1px solid rgba(213,73,65,.2);border-radius:4px;cursor:pointer;font-size:13px}.uds-auth-logout:hover{background:rgba(213,73,65,.15)}.uds-auth-user-mgmt{padding:16px}.uds-auth-user-mgmt h4{font-size:14px;margin-bottom:12px}.uds-auth-user-table{width:100%;border-collapse:collapse;font-size:12px}.uds-auth-user-table th,.uds-auth-user-table td{padding:6px 8px;text-align:left;border-bottom:1px solid var(--dsw-alias-border-l1,#eef0f3)}.uds-auth-user-table th{color:var(--dsw-alias-label-tertiary,#8f959e);font-weight:500}.uds-auth-add-user{display:flex;gap:8px;margin-top:12px}.uds-auth-add-user input{flex:1;padding:6px 8px;border:1px solid var(--dsw-alias-border-l2,#dfe1e5);border-radius:4px;font-size:12px}.uds-auth-add-user select{padding:6px 8px;border:1px solid var(--dsw-alias-border-l2,#dfe1e5);border-radius:4px;font-size:12px}.uds-auth-add-user button{padding:6px 12px;background:var(--dsw-alias-state-business-primary,#3370ff);color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:12px}.uds-auth-del-btn{padding:3px 8px;background:rgba(213,73,65,.1);color:var(--dsw-alias-state-error-primary,#d54941);border:1px solid rgba(213,73,65,.2);border-radius:3px;cursor:pointer;font-size:11px}.uds-auth-modal{position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.4);z-index:9999;display:flex;align-items:center;justify-content:center}.uds-auth-modal-content{background:#fff;border-radius:8px;max-width:500px;width:90%;max-height:80vh;overflow-y:auto;box-shadow:0 12px 40px rgba(0,0,0,.15)}
`

// 内联 MD5 实现（jQuery.md5 兼容）
function md5(str) {
  function md5cycle(x, k) {
    var a = x[0], b = x[1], c = x[2], d = x[3]
    a = ff(a,b,c,d,k[0],7,-680876936); d = ff(d,a,b,c,k[1],12,-389564586)
    c = ff(c,d,a,b,k[2],17,606105819); b = ff(b,c,d,a,k[3],22,-1044525330)
    a = ff(a,b,c,d,k[4],7,-176418897); d = ff(d,a,b,c,k[5],12,1200080426)
    c = ff(c,d,a,b,k[6],17,-1473231341); b = ff(b,c,d,a,k[7],22,-45705983)
    a = ff(a,b,c,d,k[8],7,1770035416); d = ff(d,a,b,c,k[9],12,-1958414417)
    c = ff(c,d,a,b,k[10],17,-42063); b = ff(b,c,d,a,k[11],22,-1990404162)
    a = ff(a,b,c,d,k[12],7,1804603682); d = ff(d,a,b,c,k[13],12,-40341101)
    c = ff(c,d,a,b,k[14],17,-1502002290); b = ff(b,c,d,a,k[15],22,1236535329)
    a = gg(a,b,c,d,k[1],5,-165796510); d = gg(d,a,b,c,k[6],9,-1069501632)
    c = gg(c,d,a,b,k[11],14,643717713); b = gg(b,c,d,a,k[0],20,-373897302)
    a = gg(a,b,c,d,k[5],5,-701558691); d = gg(d,a,b,c,k[10],9,38016083)
    c = gg(c,d,a,b,k[15],14,-660478335); b = gg(b,c,d,a,k[4],20,-405537848)
    a = gg(a,b,c,d,k[9],5,568446438); d = gg(d,a,b,c,k[14],9,-1019803690)
    c = gg(c,d,a,b,k[3],14,-187363961); b = gg(b,c,d,a,k[8],20,1163531501)
    a = gg(a,b,c,d,k[13],5,-1444681467); d = gg(d,a,b,c,k[2],9,-51403784)
    c = gg(c,d,a,b,k[7],14,1735328473); b = gg(b,c,d,a,k[12],20,-1926607734)
    a = hh(a,b,c,d,k[5],4,-378558); d = hh(d,a,b,c,k[8],11,-2022574463)
    c = hh(c,d,a,b,k[11],16,1839030562); b = hh(b,c,d,a,k[14],23,-35309556)
    a = hh(a,b,c,d,k[1],4,-1530992060); d = hh(d,a,b,c,k[4],11,1272893353)
    c = hh(c,d,a,b,k[7],16,-155497632); b = hh(b,c,d,a,k[10],23,-1094730640)
    a = hh(a,b,c,d,k[13],4,681279174); d = hh(d,a,b,c,k[0],11,-358537222)
    c = hh(c,d,a,b,k[3],16,-722521979); b = hh(b,c,d,a,k[6],23,76029189)
    a = hh(a,b,c,d,k[9],4,-640364487); d = hh(d,a,b,c,k[12],11,-421815835)
    c = hh(c,d,a,b,k[15],16,530742520); b = hh(b,c,d,a,k[2],23,-995338651)
    a = ii(a,b,c,d,k[0],6,-198630844); d = ii(d,a,b,c,k[7],10,1126891415)
    c = ii(c,d,a,b,k[14],15,-1416354905); b = ii(b,c,d,a,k[3],21,-57434055)
    a = ii(a,b,c,d,k[10],6,1700485571); d = ii(d,a,b,c,k[1],10,-1894986606)
    c = ii(c,d,a,b,k[8],15,-1051523); b = ii(b,c,d,a,k[15],21,-2054922799)
    a = ii(a,b,c,d,k[6],6,1873313359); d = ii(d,a,b,c,k[13],10,-30611744)
    c = ii(c,d,a,b,k[4],15,-1560198380); b = ii(b,c,d,a,k[11],21,1309151649)
    a = ii(a,b,c,d,k[2],6,-145523070); d = ii(d,a,b,c,k[9],10,-1120210379)
    c = ii(c,d,a,b,k[0],15,718787259); b = ii(b,c,d,a,k[7],21,-343485551)
    x[0]=add32(a,x[0]);x[1]=add32(b,x[1]);x[2]=add32(c,x[2]);x[3]=add32(d,x[3])
  }
  function cmn(q,a,b,x,s,t){a=add32(add32(a,q),add32(x,t));return add32((a<<s)|(a>>>(32-s)),b)}
  function ff(a,b,c,d,x,s,t){return cmn((b&c)|((~b)&d),a,b,x,s,t)}
  function gg(a,b,c,d,x,s,t){return cmn((b&d)|(c&(~d)),a,b,x,s,t)}
  function hh(a,b,c,d,x,s,t){return cmn(b^c^d,a,b,x,s,t)}
  function ii(a,b,c,d,x,s,t){return cmn(c^(b|(~d)),a,b,x,s,t)}
  function md51(s){
    var n=s.length,state=[1732584193,-271733879,-1732584194,271733878],i
    for(i=64;i<=s.length;i+=64)md5cycle(state,md5blk(s.substring(i-64,i)))
    s=s.substring(i-64)
    var tail=[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
    for(i=0;i<s.length;i++)tail[i>>2]|=s.charCodeAt(i)<<((i%4)<<3)
    tail[i>>2]|=0x80<<((i%4)<<3)
    if(i>55){md5cycle(state,tail);tail=[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]}
    tail[14]=n*8;md5cycle(state,tail)
    return state
  }
  function md5blk(s){
    var md5blks=[],i
    for(i=0;i<64;i+=4)md5blks[i>>2]=s.charCodeAt(i)+(s.charCodeAt(i+1)<<8)+(s.charCodeAt(i+2)<<16)+(s.charCodeAt(i+3)<<24)
    return md5blks
  }
  var hex_chr='0123456789abcdef'.split('')
  function rhex(n){var s='',j=0;for(;j<4;j++)s+=hex_chr[(n>>(j*8+4))&0x0F]+hex_chr[(n>>(j*8))&0x0F];return s}
  function hex(x){for(var i=0;i<x.length;i++)x[i]=rhex(x[i]);return x.join('')}
  function add32(a,b){return(a+b)&0xFFFFFFFF}
  return hex(md51(str))
}

function getCookie(name) {
  var cookieName=encodeURIComponent(name)+'='
  var cookieStart=document.cookie.indexOf(cookieName)
  if(cookieStart===-1)return null
  var cookieEnd=document.cookie.indexOf(';',cookieStart)
  if(cookieEnd===-1)cookieEnd=document.cookie.length
  return decodeURIComponent(document.cookie.substring(cookieStart+cookieName.length,cookieEnd))
}

function setCookie(name,value,days){
  var expires=''
  if(days){var d=new Date();d.setTime(d.getTime()+(days*86400000));expires='; expires='+d.toUTCString()}
  document.cookie=encodeURIComponent(name)+'='+encodeURIComponent(value)+expires+'; path=/'
}

function getEmpNo() {
  return getCookie('PORTALSSOUser') || getCookie('ZTEDPGSSOUser') || null
}

function getAuthToken() {
  return getCookie('PORTALSSOCookie') || getCookie('ZTEDPGSSOCookie') || null
}

export default {
  name: 'uds-auth-client',
  inject: [],
  apply(ctx) {
    const slots = ctx.get('slots')
    if (!slots) return

    // 注入 CSS
    if (!document.getElementById('uds-auth-badge-css')) {
      const style = document.createElement('style')
      style.id = 'uds-auth-badge-css'
      style.textContent = CSS
      document.head.appendChild(style)
    }

    // 状态
    let currentUser = null
    let dropdownVisible = false
    let qrPollingTimer = null
    let currentQRKey = null
    let currentQRValue = null

    const LOGIN_SYSTEM_CODE = '100000455558'

    function updateBadge(user) {
      currentUser = user
      renderBadge()
    }

    function getRoleLabel(role) {
      return {super_admin:'超管',admin:'管理员',fallback_admin:'兜底',user:''}[role]||''
    }

    function renderBadge() {
      const el = document.getElementById('uds-auth-badge-el')
      if (!el) return

      if (!currentUser) {
        el.innerHTML = '<span class="uds-auth-avatar">?</span><span>未登录</span>'
        el.className = 'uds-auth-badge uds-auth-badge-unauth'
      } else {
        const name = currentUser.userName || currentUser.name || '用户' + currentUser.empNo
        const initials = name.slice(0, 2).toUpperCase()
        const roleLabel = getRoleLabel(currentUser.role)
        const roleBadge = roleLabel ? '<span class="uds-auth-role-badge uds-auth-role-' + currentUser.role + '">' + roleLabel + '</span>' : ''
        el.innerHTML = '<span class="uds-auth-avatar">' + initials + '</span><span>' + name + '</span>' + roleBadge
        el.className = 'uds-auth-badge'
      }
    }

    function renderDropdown() {
      const container = document.getElementById('uds-auth-dropdown-el')
      if (!container) return

      if (!currentUser) {
        container.innerHTML = `
          <div class="uds-auth-info"><div class="uds-auth-info-name">未登录</div><div class="uds-auth-info-detail">请扫码登录</div></div>
          <div class="uds-auth-qr-container">
            <div id="uds-qr-img-wrap" style="text-align:center"></div>
            <div id="uds-qr-status" class="uds-auth-qr-status">加载中...</div>
            <button id="uds-qr-refresh" class="uds-auth-qr-refresh">刷新二维码</button>
          </div>
        `
        document.getElementById('uds-qr-refresh').onclick = startQRLogin
        startQRLogin()
      } else {
        const name = currentUser.userName || currentUser.name || '用户' + currentUser.empNo
        const roleLabel = getRoleLabel(currentUser.role)
        const perms = currentUser.permissions || {}
        let html = '<div class="uds-auth-info"><div class="uds-auth-info-name">' + name + '</div>'
        html += '<div class="uds-auth-info-detail"><span class="uds-auth-info-detail-label">工号</span>' + (currentUser.empNo||'-') + '</div>'
        html += '<div class="uds-auth-info-detail"><span class="uds-auth-info-detail-label">角色</span>' + roleLabel + '</div>'
        if(currentUser.department) html += '<div class="uds-auth-info-detail"><span class="uds-auth-info-detail-label">部门</span>' + currentUser.department + '</div>'
        if(currentUser.email) html += '<div class="uds-auth-info-detail"><span class="uds-auth-info-detail-label">邮箱</span>' + currentUser.email + '</div>'
        if(currentUser.phone) html += '<div class="uds-auth-info-detail"><span class="uds-auth-info-detail-label">手机</span>' + currentUser.phone + '</div>'
        html += '</div>'
        if(perms.canManageUsers) html += '<button id="uds-user-mgmt-btn" class="uds-auth-settings-btn">👥 用户管理</button>'
        if(perms.canAccessSettings) html += '<button id="uds-settings-btn" class="uds-auth-settings-btn">⚙️ 系统设置</button>'
        html += '<button id="uds-logout-btn" class="uds-auth-logout">退出登录</button>'
        container.innerHTML = html

        document.getElementById('uds-settings-btn').onclick = () => { window.open('/settings', '_self') }
        document.getElementById('uds-user-mgmt-btn').onclick = openUserManagement
        document.getElementById('uds-logout-btn').onclick = () => {
          setCookie('PORTALSSOUser','',-1);setCookie('PORTALSSOCookie','',-1)
          setCookie('ZTEDPGSSOUser','',-1);setCookie('ZTEDPGSSOCookie','',-1)
          setCookie('UDS_FALLBACK_USER','',-1)
          location.reload()
        }
      }
    }

    function toggleDropdown() {
      const container = document.getElementById('uds-auth-dropdown-el')
      if (!container) return
      dropdownVisible = !dropdownVisible
      container.style.display = dropdownVisible ? 'block' : 'none'
      if (dropdownVisible) renderDropdown()
    }

    // 关闭下拉
    function closeDropdown() {
      const container = document.getElementById('uds-auth-dropdown-el')
      if (container) container.style.display = 'none'
      dropdownVisible = false
    }

    // QR 登录
    function startQRLogin() {
      if (qrPollingTimer) { clearInterval(qrPollingTimer); qrPollingTimer = null }
      const status = document.getElementById('uds-qr-status')
      const wrap = document.getElementById('uds-qr-img-wrap')
      if (!status) return
      status.textContent = '正在生成二维码...'

      // 加载 md5 插件
      loadUACMd5Plugin().then(() => {
        if (typeof window.jQuery.md5QrCode !== 'function') {
          status.textContent = '加密插件加载失败'
          return
        }
        const qrCodeStr = window.jQuery.md5QrCode('TwoDIMAuth')
        const parts = qrCodeStr.split(':')
        currentQRKey = parts[1]
        currentQRValue = parts[2]
        status.textContent = '请使用iCenter扫码登录...'
        if (wrap) wrap.innerHTML = '<img id="uds-qr-img" class="uds-auth-qr-img" src="/uds-auth/qr?data=' + encodeURIComponent(qrCodeStr) + '">'
        qrPollingTimer = setInterval(pollQRStatus, 2000)
      }).catch(() => {
        status.textContent = '加载加密插件失败'
      })
    }

    function loadUACMd5Plugin() {
      return new Promise((resolve, reject) => {
        if (window.jQuery && window.jQuery.md5QrCode) { resolve(); return }
        function loadScript(src) {
          return new Promise((res, rej) => {
            const s = document.createElement('script')
            s.src = src
            s.onload = res
            s.onerror = rej
            document.head.appendChild(s)
          })
        }
        loadScript('/uds-auth/vendor/jquery.min.js')
          .then(() => loadScript('/uds-auth/vendor/jquery.md5.min.js'))
          .then(resolve).catch(reject)
      })
    }

    function pollQRStatus() {
      if (!currentQRKey) return
      const source = currentQRKey + currentQRValue + '127.0.0.1' + LOGIN_SYSTEM_CODE + ''
      const verifyCode = window.jQuery ? window.jQuery.verfiyCode(source) : md5(source)

      const body = JSON.stringify({
        qrCodeKey: currentQRKey,
        qrCodeValue: currentQRValue,
        loginClientIp: '127.0.0.1',
        originSystemCode: '',
        loginSystemCode: LOGIN_SYSTEM_CODE,
        verifyCode: verifyCode
      })

      fetch('/uds-auth/qr-proxy', { method:'POST', headers:{'Content-Type':'application/json'}, body })
        .then(r => r.json())
        .then(handleQRResult)
        .catch(() => {
          const s = document.getElementById('uds-qr-status')
          if (s) s.textContent = '网络错误...'
        })
    }

    function handleQRResult(result) {
      const code = result.code || {}
      const bo = result.bo || {}
      const codeCode = code.code || ''
      const boCode = bo.code || ''
      const status = document.getElementById('uds-qr-status')

      if (codeCode === '0000' && boCode === '0000') {
        clearInterval(qrPollingTimer); qrPollingTimer = null
        currentQRKey = null; currentQRValue = null
        const other = result.other || {}
        const empNo = other.account || other.empNo || ''
        const token = other.token || other.authValue || ''
        if (empNo) {
          setCookie('PORTALSSOUser', empNo, 7)
          if (token) setCookie('PORTALSSOCookie', token, 7)
          if (status) status.textContent = '登录成功！'
          fetchUserInfo(() => {
            closeDropdown()
            fetchUserAndPermissions()
          })
        }
        return
      }
      if (codeCode === '0000' && boCode === '4002') {
        if (status) status.textContent = '等待扫码...'
        return
      }
      if (codeCode === '0000' && boCode === '1002') {
        clearInterval(qrPollingTimer); qrPollingTimer = null
        if (status) status.textContent = '二维码已过期，请刷新'
        currentQRKey = null; currentQRValue = null
        return
      }
      clearInterval(qrPollingTimer); qrPollingTimer = null
      if (status) status.textContent = '⚠️ ' + (bo.msg || boCode || '登录失败')
    }

    function fetchUserAndPermissions() {
      const empNo = getEmpNo()
      if (!empNo) { updateBadge(null); return }
      fetch('/uds-auth/api/me')
        .then(r => r.json())
        .then(me => {
          const permissions = me?.data?.permissions || {}
          const role = me?.data?.role || 'user'
          updateBadge({ empNo, userName: null, role, permissions })
          fetchUserInfo(user => {
            updateBadge(Object.assign({ role, permissions }, user))
          })
        })
        .catch(() => fetchUserInfo(cb => updateBadge(cb)))
    }

    function fetchUserInfo(cb) {
      const empNo = getEmpNo()
      if (!empNo) { cb({ empNo, userName: '用户' + empNo }); return }
      const token = getAuthToken()
      let url = '/uds-auth/user-info?empNo=' + encodeURIComponent(empNo)
      if (token) url += '&token=' + encodeURIComponent(token)
      fetch(url)
        .then(r => r.json())
        .then(result => {
          if (result.code && result.code.code === '0000' && result.bo && result.bo.length > 0) {
            const emp = result.bo[0]
            const dept = emp.deptName || emp.deptShortName || emp.deptFullName || emp.orgName || emp.department || ''
            const name = emp.name || emp.empName || emp.userName || '用户' + empNo
            cb({
              empNo: emp.employeeShortId || emp.employeeNO || empNo,
              userName: name,
              department: dept,
              email: emp.email || emp.mail || '',
              phone: emp.mobile || emp.phone || ''
            })
          } else {
            cb({ empNo, userName: '用户' + empNo })
          }
        })
        .catch(() => cb({ empNo, userName: '用户' + empNo }))
    }

    // 用户管理
    function openUserManagement() {
      fetch('/uds-auth/api/users')
        .then(r => r.json())
        .then(data => {
          const users = data.users || []
          let html = '<div class="uds-auth-user-mgmt"><h4>用户管理</h4>'
          html += '<table class="uds-auth-user-table"><thead><tr><th>工号</th><th>角色</th><th>操作</th></tr></thead><tbody>'
          users.forEach(u => {
            const roleOpts = '<option value="user"'+(u.role==='user'?' selected':'')+'>普通用户</option>' +
              '<option value="admin"'+(u.role==='admin'?' selected':'')+'>管理员</option>' +
              '<option value="super_admin"'+(u.role==='super_admin'?' selected':'')+'>超级管理员</option>'
            html += '<tr><td>'+u.empNo+'</td><td>'+u.role+'</td><td>' +
              '<select onchange="window.__udsChangeRole(\''+u.empNo+'\',this.value)">'+roleOpts+'</select> ' +
              '<button onclick="window.__udsDeleteUser(\''+u.empNo+'\')" class="uds-auth-del-btn">删除</button></td></tr>'
          })
          html += '</tbody></table>'
          html += '<div class="uds-auth-add-user"><input id="uds-new-empno" placeholder="工号"><select id="uds-new-role"><option value="user">普通用户</option><option value="admin">管理员</option></select><button onclick="window.__udsAddUser()">添加</button></div>'
          html += '</div>'

          const panel = document.createElement('div')
          panel.className = 'uds-auth-modal'
          panel.innerHTML = '<div class="uds-auth-modal-content">' + html + '</div>'
          document.body.appendChild(panel)
          panel.onclick = e => { if (e.target === panel) panel.remove() }
        })
    }

    window.__udsChangeRole = (empNo, role) => {
      fetch('/uds-auth/api/users/role', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({empNo,role})})
        .then(r=>r.json()).then(d=>{if(d.error)alert(d.error);openUserManagement()})
    }
    window.__udsDeleteUser = (empNo) => {
      if(!confirm('确认删除 '+empNo+'?'))return
      fetch('/uds-auth/api/users/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({empNo})})
        .then(r=>r.json()).then(d=>{if(d.error)alert(d.error);openUserManagement()})
    }
    window.__udsAddUser = () => {
      const empNo=document.getElementById('uds-new-empno').value.trim()
      const role=document.getElementById('uds-new-role').value
      if(!empNo)return
      fetch('/uds-auth/api/users',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({empNo,role})})
        .then(r=>r.json()).then(d=>{if(d.error)alert(d.error);openUserManagement()})
    }

    // 注册 sidebar.footer.action slot（显示在设置按钮旁边，所有页面都可见）
    slots.inject('sidebar.footer.action', () => {
      slots.register({ name: 'sidebar.footer.action', id: 'uds-auth-login', order: 100 }, (props) => {
        // React.createElement wrapper
        const h = React.createElement
        return h('div', { style: { position:'relative', display:'flex', alignItems:'center' } },
          h('button', {
            id: 'uds-auth-badge-el',
            className: 'uds-auth-badge uds-auth-badge-unauth',
            onClick: toggleDropdown,
            style: { display:'flex', alignItems:'center', gap:'6px', padding:'4px 10px', borderRadius:'4px',
              background:'var(--dsw-alias-bg-module-platform,rgba(242,243,245,1))',
              border:'1px solid var(--dsw-alias-border-l2,#dfe1e5)',
              color:'var(--dsw-alias-label-tertiary,#8f959e)', fontSize:'13px', cursor:'pointer', fontWeight:'500' }
          },
            h('span', { className:'uds-auth-avatar', style:{ width:'22px',height:'22px',borderRadius:'50%',
              background:'var(--dsw-alias-bg-module-platform,rgba(242,243,245,1))',
              color:'var(--dsw-alias-label-tertiary,#8f959e)', display:'flex',alignItems:'center',
              justifyContent:'center',fontSize:'10px',fontWeight:'700' } }, '?'),
            h('span', null, '未登录')
          ),
          h('div', {
            id: 'uds-auth-dropdown-el',
            className: 'uds-auth-dropdown',
            style: { display:'none', position:'absolute', bottom:'100%', left:'0', marginBottom:'8px',
              background:'var(--dsw-alias-bg-layer-1,#fff)', borderRadius:'8px',
              border:'1px solid var(--dsw-alias-border-l2,#dee0e3)',
              boxShadow:'0 8px 28px rgba(0,0,0,.08)', minWidth:'220px', zIndex:1000, overflow:'hidden' }
          })
        )
      })
    })

    // 点击外部关闭
    document.addEventListener('click', e => {
      const badge = document.getElementById('uds-auth-badge-el')
      const dropdown = document.getElementById('uds-auth-dropdown-el')
      if (dropdownVisible && badge && !badge.contains(e.target) && !dropdown.contains(e.target)) {
        closeDropdown()
      }
    })

    // 初始加载用户信息
    fetchUserAndPermissions()
  }
}
