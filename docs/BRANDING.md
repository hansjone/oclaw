# Branding Guide

This project supports **external-first branding**.  
Put your branding assets under `_local/branding`, and Oclaw will use them first.  
If an external file is missing, Oclaw falls back to built-in defaults.

## Directory

Create this folder in the repository root:

`_local/branding/`

## Supported Files

- `logo.svg`
  - Used by admin sidebar logo and chat assistant logo/avatar.
  - URL path: `/admin/brand-assets/logo.svg`
- `desktop.ico` (recommended on Windows)
  - Preferred desktop window icon for Electron.
- `logo.png` (desktop fallback)
  - Used as desktop icon fallback when `desktop.ico` is absent.

## Resolution Order

### Web UI (Admin + Chat)

1. `_local/branding/logo.svg`
2. Built-in fallback: `interfaces/admin/static/oliver.svg`

### Desktop (Electron window icon)

1. `_local/branding/desktop.ico`
2. `_local/branding/logo.png`
3. `_local/branding/logo.svg`
4. Built-in fallback: `interfaces/admin/static/oliver.svg`

## How to Apply

1. Put your files into `_local/branding/`.
2. Restart gateway (and desktop app if using Electron).
3. Hard refresh browser page if needed.

## Notes

- `/admin/brand-assets/*` is served with no-cache headers to reduce stale asset issues.
- `_local/*` is git-ignored by default, so tenant/customer branding stays local.
