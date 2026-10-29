// Regenerate docs/assets/demo.gif from the real app. Requires the existing backend
// Windows: requires the existing backend virtualenv, frontend dependencies,
// Playwright Chromium, ffmpeg, and netstat on PATH.
import { spawn, spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { mkdtemp, copyFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import net from 'node:net';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const frontend = path.join(root, 'frontend');
const backend = path.join(root, 'backend');
const requireFrontend = createRequire(path.join(frontend, 'package.json'));
const { chromium, expect } = requireFrontend('@playwright/test');
if (process.platform !== 'win32') throw new Error('This capture script verifies port ownership with Windows netstat.');
const { createServer } = await import(pathToFileURL(requireFrontend.resolve('vite')).href);
const react = (await import(pathToFileURL(requireFrontend.resolve('@vitejs/plugin-react')).href)).default;
const tailwind = (await import(pathToFileURL(requireFrontend.resolve('@tailwindcss/vite')).href)).default;
const temp = await mkdtemp(path.join(tmpdir(), 'workforce-gif-'));
console.log(`Temporary synthetic data and recording: ${temp}`);
let api, vite, browser, context;

async function freePort() {
  return await new Promise((resolve, reject) => {
    const server = net.createServer();
    server.on('error', reject);
    server.listen(0, '127.0.0.1', () => {
      const port = server.address().port;
      server.close((err) => err ? reject(err) : resolve(port));
    });
  });
}
function run(command, args) {
  const result = spawnSync(command, args, { stdio: 'inherit' });
  if (result.error || result.status !== 0) throw result.error ?? new Error(`${command} exited ${result.status}`);
}
async function startApi(port) {
  const python = process.platform === 'win32' ? path.join(backend, '.venv', 'Scripts', 'python.exe') : path.join(backend, '.venv', 'bin', 'python');
  const db = path.join(temp, 'synthetic.db').replaceAll('\\', '/');
  api = spawn(python, ['-m', 'app.cli'], {
    cwd: backend, windowsHide: true,
    env: { ...process.env, APP_ENV: 'demo', HOST: '127.0.0.1', PORT: String(port), ALLOW_NETWORK_BIND: 'false', RESET_DEMO: 'false', DATABASE_URL: `sqlite:///${db}`, PYTHONDONTWRITEBYTECODE: '1' },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  let output = '';
  api.stdout.on('data', chunk => { output += chunk.toString(); });
  api.stderr.on('data', chunk => { output += chunk.toString(); });
  let failure;
  api.once('error', error => { failure = error; });
  const deadline = Date.now() + 60000;
  while (Date.now() < deadline) {
    if (failure || api.exitCode !== null) throw failure ?? new Error(`API exited ${api.exitCode}: ${output}`);
    try {
      const response = await fetch(`http://127.0.0.1:${port}/health`, { signal: AbortSignal.timeout(1000) });
      if (response.ok) {
        // Allow a failed bind to surface before doing anything that writes data.
        await new Promise(resolve => setTimeout(resolve, 1000));
        const pid = output.match(/Started server process \[(\d+)\]/)?.[1];
        const netstat = spawnSync('netstat', ['-ano', '-p', 'tcp'], { encoding: 'utf8' });
        const owned = netstat.status === 0 && netstat.stdout.split(/\r?\n/).some(line => {
          const columns = line.trim().split(/\s+/);
          return columns[1] === `127.0.0.1:${port}` && columns[3] === 'LISTENING' && columns[4] === pid;
        });
        if (api.exitCode === null && pid && owned) return;
      }
    } catch { /* Not ready yet. */ }
    await new Promise(resolve => setTimeout(resolve, 250));
  }
  throw new Error(`API startup timeout: ${output}`);
}

try {
  const apiPort = await freePort();
  let webPort = await freePort();
  while (webPort === apiPort) webPort = await freePort();
  await startApi(apiPort);
  vite = await createServer({
    configFile: false, envDir: false, root: frontend, cacheDir: path.join(temp, 'vite-cache'),
    plugins: [react(), tailwind()],
    define: { 'import.meta.env.VITE_API_BASE': JSON.stringify('') },
    server: { host: '127.0.0.1', port: webPort, strictPort: true, proxy: { '/api': `http://127.0.0.1:${apiPort}` } },
    logLevel: 'warn',
  });
  await vite.listen();
  browser = await chromium.launch({ headless: true });
  context = await browser.newContext({ viewport: { width: 1280, height: 800 }, deviceScaleFactor: 1, recordVideo: { dir: temp, size: { width: 1280, height: 800 } } });
  const page = await context.newPage();
  const origin = `http://127.0.0.1:${webPort}`;
  await page.goto(`${origin}/scenarios`);
  await expect(page.getByRole('heading', { name: 'Scenarios' })).toBeVisible();
  await expect(page.getByTestId('demo-banner')).toContainText('synthetic data');
  await page.waitForTimeout(1000);
  await page.getByTestId('scenario-optimal').click();
  await expect(page.getByTestId('scenario-timing')).toContainText('OPTIMAL', { timeout: 60000 });
  await expect(page.getByTestId('scenario-timing').locator('dd').nth(1)).toHaveText('OPTIMAL');
  await page.waitForTimeout(1500);
  await page.getByRole('link', { name: 'Solve', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Solve' })).toBeVisible();
  await page.waitForTimeout(500);
  await page.getByTestId('run-solve').click();
  await expect(page.getByTestId('solver-telemetry')).toContainText('SUCCEEDED', { timeout: 60000 });
  await expect(page.getByTestId('solver-telemetry')).toContainText('OPTIMAL');
  await page.waitForTimeout(1800);
  await page.getByRole('link', { name: 'Schedule', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Schedule' })).toBeVisible();
  await expect(page.getByRole('grid', { name: /Employee by day roster grid/ })).toBeVisible();
  await expect(page.getByText('No hard-constraint violations.')).toBeVisible();
  const validation = page.waitForResponse(r => /\/api\/schedules\/\d+\/validate$/.test(r.url()) && r.request().method() === 'POST');
  await page.getByTestId('revalidate').click();
  const validationResponse = await validation;
  if (!validationResponse.ok() || !(await validationResponse.json()).valid) throw new Error('Revalidation failed');
  await expect(page.getByText('No hard-constraint violations.')).toBeVisible();
  await page.waitForTimeout(2000);
  const video = page.video();
  await context.close(); context = undefined;
  const videoPath = await video.path();
  const gifPath = path.join(temp, 'demo.gif');
  // Palette generation and application happen in one filter graph to preserve real video frames.
  run('ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y', '-i', videoPath, '-filter_complex', 'fps=10,scale=960:-2:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=sierra2_4a', '-loop', '0', gifPath]);
  await copyFile(gifPath, path.join(root, 'docs', 'assets', 'demo.gif'));
  console.log(`Validated OPTIMAL scenario, successful solve and valid roster on isolated ports ${webPort}/${apiPort}; wrote docs/assets/demo.gif`);
} finally {
  if (context) await context.close();
  if (browser) await browser.close();
  if (vite) await vite.close();
  if (api && api.exitCode === null) {
    const exited = new Promise(resolve => api.once('exit', resolve));
    // The Windows virtualenv launcher creates a child Python process.
    if (process.platform === 'win32') spawnSync('taskkill', ['/pid', String(api.pid), '/t', '/f'], { stdio: 'ignore' });
    else api.kill();
    await Promise.race([exited, new Promise(resolve => setTimeout(resolve, 5000))]);
  }
  // Retain the isolated temporary directory for inspection; never delete user data.
}
