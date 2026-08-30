import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, '..');
const envPath = path.join(projectRoot, '.env');
const outputPath = path.join(projectRoot, 'frontend', 'config.js');

if (!fs.existsSync(envPath)) {
  console.error('Missing .env file at project root. Copy .env.example to .env and fill in the real values.');
  process.exit(1);
}

const envContent = fs.readFileSync(envPath, 'utf8');
const config = {};

for (const line of envContent.split(/\r?\n/)) {
  const trimmed = line.trim();
  if (!trimmed || trimmed.startsWith('#')) continue;

  const separatorIndex = trimmed.indexOf('=');
  if (separatorIndex === -1) continue;

  const key = trimmed.slice(0, separatorIndex).trim();
  const value = trimmed.slice(separatorIndex + 1).trim();
  config[key] = value;
}

const js = `window.__APP_CONFIG__ = ${JSON.stringify(config, null, 2)};\n`;
fs.writeFileSync(outputPath, js, 'utf8');
console.log(`Generated ${path.relative(projectRoot, outputPath)} from ${path.relative(projectRoot, envPath)}`);
