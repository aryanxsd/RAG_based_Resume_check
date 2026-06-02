import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';

const projectRoot = path.resolve(process.cwd(), '..');
const demoDir = path.join(projectRoot, 'demo-video');
const resumePath = path.join(projectRoot, 'backend', 'data', 'sample_resume.txt');
const answer = [
  'I would start by defining the task, metric, and expected experience source.',
  'Then I would split validation data carefully to avoid leakage and compare a baseline with a regularized model.',
  'For bias and variance I would inspect learning curves, tune model complexity, and use cross-validation before deployment.',
  'For the backend I would persist the session, retrieved chunks, generated question, and answer score for traceability.',
  'Finally I would monitor precision, recall, drift, and retrieval quality so failures can be debugged after release.',
].join(' ');

async function main() {
  fs.mkdirSync(demoDir, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 960 },
    recordVideo: { dir: demoDir, size: { width: 1440, height: 960 } },
  });
  const page = await context.newPage();

  await page.goto('http://127.0.0.1:5173/', { waitUntil: 'networkidle' });
  await page.waitForSelector('text=Candidate Screening RAG');
  await page.waitForTimeout(1200);

  await page.selectOption('select', 'ai_ml_engineer');
  await page.setInputFiles('input[type="file"]', resumePath);
  await page.waitForTimeout(900);
  await page.getByRole('button', { name: /Start Interview/i }).click();
  await page.waitForSelector('text=Question 1', { timeout: 15000 });
  await page.waitForTimeout(1800);

  for (let i = 0; i < 5; i += 1) {
    await page.locator('textarea').fill(`${answer} This is response ${i + 1}.`);
    await page.waitForTimeout(800);
    await page.getByRole('button', { name: /Submit Answer/i }).click();
    await page.waitForTimeout(1600);
  }

  await page.waitForSelector('text=Overall score', { timeout: 15000 });
  await page.waitForTimeout(2800);
  await context.close();
  await browser.close();

  const files = fs.readdirSync(demoDir).filter((file) => file.endsWith('.webm'));
  files.sort((a, b) => fs.statSync(path.join(demoDir, b)).mtimeMs - fs.statSync(path.join(demoDir, a)).mtimeMs);
  const latest = files[0];
  if (!latest) {
    throw new Error('No demo video was created.');
  }
  const finalPath = path.join(demoDir, 'candidate-screening-rag-demo.webm');
  fs.renameSync(path.join(demoDir, latest), finalPath);
  console.log(finalPath);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
