/**
 * Oclaw 自我改进 Hook
 *
 * 在 agent:bootstrap 阶段注入学习沉淀提醒。
 */

import type { HookHandler } from 'oclaw/hooks';

const REMINDER_NAME = 'SELF_IMPROVEMENT_REMINDER.md';
const REMINDER_PATH = REMINDER_NAME;

const REMINDER_CONTENT = `## 自我改进提醒

任务完成后，请评估是否产生可沉淀学习。

仅在当前仓库/工作区启用 self-improvement 技能时记录。

记录前：
- 使用 memory_wiki_* 工具写入 \`improvement/\` 下的 Wiki 笔记
- 不记录密钥、令牌、私钥、环境变量或原始对话全文
- 优先使用简短摘要或脱敏片段，避免完整命令输出

**以下情况应记录：**
- 用户纠正你 → \`improvement/learnings.md\`
- 命令/操作失败 → \`improvement/errors.md\`
- 用户提出缺失能力 → \`improvement/feature-requests.md\`
- 发现认知错误 → \`improvement/learnings.md\`
- 发现更优做法 → \`improvement/learnings.md\`

**当模式被验证后进行提升：**
- 行为模式 → \`SOUL.md\`
- 工作流改进 → \`AGENTS.md\`
- 工具易错点 → \`TOOLS.md\`

条目保持简洁：时间、标题、发生了什么、后续应如何做。`;

function isObject(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === 'object';
}

function isInjectedReminderFile(value: unknown): boolean {
  if (!isObject(value) || value.path !== REMINDER_PATH) {
    return false;
  }

  return (
    value.virtual === true ||
    value.content === REMINDER_CONTENT
  );
}

const handler: HookHandler = async (event) => {
  // 事件结构安全检查
  if (!event || typeof event !== 'object') {
    return;
  }

  // 仅处理 agent:bootstrap 事件
  if (event.type !== 'agent' || event.action !== 'bootstrap') {
    return;
  }

  // context 安全检查
  if (!event.context || typeof event.context !== 'object') {
    return;
  }

  // 跳过子代理会话，避免引导污染
  const sessionKey = event.sessionKey || '';
  if (sessionKey.includes(':subagent:')) {
    return;
  }

  // 以虚拟 bootstrap 文件注入提醒
  if (Array.isArray(event.context.bootstrapFiles)) {
    const occupiedByOtherFile = event.context.bootstrapFiles.some(
      (file) => isObject(file) && file.path === REMINDER_PATH && !isInjectedReminderFile(file),
    );
    if (occupiedByOtherFile) {
      return;
    }

    const cleanedBootstrapFiles = event.context.bootstrapFiles.filter(
      (file, index, files) =>
        !isInjectedReminderFile(file) ||
        files.findIndex((candidate) => isInjectedReminderFile(candidate)) === index,
    );

    const reminderFile = {
      name: REMINDER_NAME,
      path: REMINDER_PATH,
      content: REMINDER_CONTENT,
      missing: false,
      virtual: true,
    };

    const existingIndex = cleanedBootstrapFiles.findIndex((file) => isInjectedReminderFile(file));
    if (existingIndex === -1) {
      cleanedBootstrapFiles.push(reminderFile);
    } else {
      cleanedBootstrapFiles[existingIndex] = reminderFile;
    }

    event.context.bootstrapFiles = cleanedBootstrapFiles;
  }
};

export default handler;
