#!/usr/bin/env node
// Render all ```mermaid fenced blocks from a markdown file to PNGs.
// Usage: node docs-diagrams/render.mjs docs/system_diagram.md
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

const mdPath = process.argv[2] || 'docs/system_diagram.md';
const outDir = 'docs-diagrams/out';
fs.mkdirSync(outDir, { recursive: true });

const md = fs.readFileSync(mdPath, 'utf8');
// extract fenced mermaid blocks
const blocks = [...md.matchAll(/```mermaid\s*?\n([\s\S]*?)```/g)].map(m => m[1].trim());
if (blocks.length === 0) {
  console.log('No mermaid blocks found.');
  process.exit(0);
}

// HTML template that loads mermaid and renders one diagram per navigation
const html = String.raw`
<!doctype html><html>
<head>
  <meta charset="utf-8" />
  <style>body{margin:0;padding:0;background:transparent} #root{display:inline-block} .mermaid{display:inline-block} svg{width:auto!important;height:auto!important;}</style>
  <script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.0/dist/mermaid.min.js"></script>
</head>
<body>
<div id="root"></div>
<script>
  mermaid.initialize({ startOnLoad: false, flowchart: { htmlLabels: true } });
  window.renderDiagram = async (code) => {
    const transformed = code.replace(/\[([^\]]*?\\n[^\]]*?)\]/g, (match, label) => {
      const safe = label.replace(/"/g, '&quot;').replace(/\\n/g, '<br/>');
      return '["' + safe + '"]';
    });
    const normalized = transformed.replace(/\\n/g, '\n');
    const root = document.getElementById('root');
    root.innerHTML = '<div class="mermaid"></div>';
    const container = root.querySelector('.mermaid');
    container.innerHTML = normalized;
    try {
      await mermaid.run({ nodes: [container] });
    } catch (err) {
      console.error('Mermaid failed:', err);
      throw err;
    }
    const el = root.querySelector('svg');
    if (!el) {
      throw new Error('Mermaid did not render an SVG.');
    }
    const bbox = el.getBBox();
    const width = Math.max(1, Math.ceil(bbox.width));
    const height = Math.max(1, Math.ceil(bbox.height));
    el.setAttribute('width', width + 'px');
    el.setAttribute('height', height + 'px');
    el.style.width = width + 'px';
    el.style.height = height + 'px';
    return { w: width, h: height };
  };
</script>
</body></html>`;
const htmlPath = path.join(outDir, 'template.html');
fs.writeFileSync(htmlPath, html);

const browser = await chromium.launch({
  headless: true,
  args: [
    '--no-sandbox',
    '--disable-setuid-sandbox',
    '--disable-dev-shm-usage',
    '--disable-gpu',
    '--single-process',
    '--ignore-certificate-errors'
  ]
});
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
page.on('pageerror', err => console.error('PAGE ERROR:', err.stack || err));
page.on('console', msg => console.log('PAGE LOG:', msg.text()));
await page.goto('file://' + path.resolve(htmlPath));
await page.waitForFunction(() => typeof window.renderDiagram === 'function');

let i = 0;
for (const code of blocks) {
  i += 1;
  const base = `block-${String(i).padStart(2, '0')}`;
  const png = path.join(outDir, `${base}.png`);
  console.log('Rendering', base);
  try {
    const size = await page.evaluate(async (c) => await window.renderDiagram(c), code);
    await page.setViewportSize({ width: Math.max(size.w, 10), height: Math.max(size.h, 10) });
    const clip = { x: 0, y: 0, width: size.w, height: size.h };
    await page.screenshot({ path: png, clip, omitBackground: true });
    console.log(`Rendered ${png} (${size.w}×${size.h})`);
  } catch (err) {
    console.error(`Failed to render ${base}:`, err);
    throw err;
  }
}

await browser.close();
