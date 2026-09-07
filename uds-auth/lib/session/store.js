/**
 * Session store — 单索引: empNo → userData
 * 
 * 一个工号 = 一个会话，不需要 sessionId，不需要额外 cookie。
 * 多终端同工号自动共享同一个会话条目。
 */
export class SessionStore {
  /** 按 empNo 获取会话 */
  async get(empNo) { throw new Error('SessionStore#get must be implemented') }
  /** 按 empNo 存储会话 */
  async set(empNo, userData) { throw new Error('SessionStore#set must be implemented') }
  /** 按 empNo 存储并设置过期(秒) */
  async setex(empNo, seconds, userData) { throw new Error('SessionStore#setex must be implemented') }
  /** 按 empNo 删除会话 */
  async delete(empNo) { throw new Error('SessionStore#delete must be implemented') }
  /** 检查 empNo 是否存在 */
  async has(empNo) { throw new Error('SessionStore#has must be implemented') }
  /** 清空所有会话 */
  async clear() { throw new Error('SessionStore#clear must be implemented') }
  /** 列出所有活跃会话 */
  async keys() { throw new Error('SessionStore#keys must be implemented') }
}
