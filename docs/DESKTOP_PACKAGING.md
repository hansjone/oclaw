# oclaw 桌面端打包与交付（Windows）

本文档用于你后续自行打包并传递安装包，按步骤执行即可。

## 1) 前置环境

- Windows 10/11
- Python 3.10+（`python` 在 PATH 中可用）
- Node.js 20+（含 npm）

在项目根目录先安装 Python 依赖：

```powershell
python -m pip install -r requirements.txt
```

## 2) 安装桌面端依赖

```powershell
cd .\desktop
npm install
```

## 3) 一键打包

```powershell
npm run pack:win
```

这个命令会自动做两件事：

1. 执行 `prepare:icon`，从 `oclaw/admin/static/oliver.svg` 生成 `desktop/assets/oclaw.ico`
2. 调用 `electron-builder` 生成 NSIS 安装包

## 4) 打包产物位置

产物位于 `desktop/dist/`，重点关注：

- `oclaw-setup-<version>.exe`（安装包，给用户分发这个）
- `oclaw-setup-<version>.exe.blockmap`（增量更新元数据，可选）
- `win-unpacked/oclaw.exe`（免安装可执行目录）

## 5) 传递建议（你说的“直接传递”）

推荐传递：

- 首选：`oclaw-setup-<version>.exe`
- 可选补充：`SHA256` 校验值（用于校验完整性）

如果需要免安装运行，再额外传 `win-unpacked` 目录压缩包。

## 6) 本地自测清单（打包后）

安装后至少验证以下项：

1. 双击应用，默认进入 `/chat`
2. “设置/审计”入口可正常跳转到 admin 页面
3. 插件页、运行页进入时有“加载中”提示
4. 点击插件/运行操作不弹黑色控制台窗口
5. 关闭应用后，后端进程被回收

## 7) 常见问题

- **提示找不到 Python**
  - 安装 Python 3.10+，或设置环境变量 `PYTHON_EXECUTABLE`
- **图标不对**
  - 重新执行：`npm run prepare:icon`
- **打包失败**
  - 先清理并重装：删除 `desktop/node_modules` 后 `npm install`

