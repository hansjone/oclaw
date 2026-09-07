import { join } from 'node:path';
import { readdirSync, existsSync } from 'node:fs';

const searchPaths = [
  join(process.cwd(), 'node_modules', '@deepseek-ai'),
  'C:/Users/10329667/AppData/Local/npm-cache/_npx/1e7f6d9597241db0/node_modules/@deepseek-ai'
];

for (const p of searchPaths) {
  if (existsSync(p)) {
    console.log('Found:', p);
    const items = readdirSync(p);
    items.forEach(i => console.log(' ', i));
  }
}
