import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  t,
  normalizeLocale,
  apiError,
  apiOk,
  roleLabel,
  roleBadge,
  MESSAGES,
} from '../lib/i18n.js'

describe('uds-auth i18n', () => {
  it('normalizes locales', () => {
    assert.equal(normalizeLocale('en-US'), 'en')
    assert.equal(normalizeLocale('zh-CN'), 'zh')
    assert.equal(normalizeLocale(''), 'zh')
  })

  it('translates UI keys', () => {
    assert.equal(t('ui.logout', 'zh'), '退出登录')
    assert.equal(t('ui.logout', 'en'), 'Sign out')
  })

  it('interpolates vars', () => {
    assert.equal(t('ui.pager', 'en', { total: 3, page: 1, totalPages: 2 }), '3 users, page 1 / 2')
  })

  it('returns stable API error codes with localized message', () => {
    const zh = apiError('not_logged_in', 'zh')
    const en = apiError('not_logged_in', 'en')
    assert.equal(zh.error, 'not_logged_in')
    assert.equal(en.error, 'not_logged_in')
    assert.equal(zh.message, '未登录')
    assert.equal(en.message, 'Not signed in')
  })

  it('returns localized success messages', () => {
    assert.equal(apiOk('config_saved', 'en').message, 'Config saved')
  })

  it('role labels are consistent', () => {
    assert.equal(roleLabel('super_admin', 'zh'), '超级管理员')
    assert.equal(roleBadge('super_admin', 'zh'), '超管')
    assert.equal(roleLabel('super_admin', 'en'), 'Super admin')
  })

  it('zh and en tables share the same keys', () => {
    const zhKeys = Object.keys(MESSAGES.zh).sort()
    const enKeys = Object.keys(MESSAGES.en).sort()
    assert.deepEqual(zhKeys, enKeys)
  })
})
