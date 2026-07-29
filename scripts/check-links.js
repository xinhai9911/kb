#!/usr/bin/env node
/*
 * check-links.js — 校验知识库中的链接有效性
 *
 * 校验两类链接：
 *   1. Wikilinks  [[path]] 或 [[path|alias]]
 *      - path 相对仓库根目录（如 50-reference/vpp-usage），解析为 <path>.md
 *      - 也支持省略目录的短名（如 [[vpp-usage]]）？当前 vault 统一用带目录路径，
 *        故只解析 "path + .md"；找不到则报错。
 *   2. 外部 Markdown 链接 ](http...)
 *      - 默认跳过（--check-external 时发起 HEAD/GET 请求，失败报错）。
 *
 * 退出码：发现断链返回 1（供 CI 失败），否则 0。
 *
 * 用法：
 *   node scripts/check-links.js [--root <dir>] [--check-external] [--timeout <ms>]
 */
'use strict';

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const args = process.argv.slice(2);
function getArg(name, def) {
  const i = args.indexOf(name);
  return i >= 0 ? args[i + 1] : def;
}
const ROOT = path.resolve(getArg('--root', process.cwd()));
const CHECK_EXTERNAL = args.includes('--check-external');
const TIMEOUT = parseInt(getArg('--timeout', '8000'), 10);

// 递归收集所有 .md 文件（相对 ROOT 的 posix 路径，去扩展名）
function collectMd(dir, base, out) {
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    if (ent.name.startsWith('.')) continue; // 跳过 .git/.obsidian 等
    const full = path.join(dir, ent.name);
    const rel = base ? `${base}/${ent.name}` : ent.name;
    if (ent.isDirectory()) collectMd(full, rel, out);
    else if (ent.isFile() && ent.name.endsWith('.md'))
      out.push(rel.replace(/\.md$/, '')); // 存 "dir/file" 形式
  }
}

const allMd = [];
collectMd(ROOT, '', allMd);
const mdSet = new Set(allMd);

// 同时支持 Obsidian 风格短名解析：[[name]] 可匹配任意 <dir>/name.md
// 构建 basename(去扩展名) -> 完整相对路径 的映射（冲突时取首个，仅用于存在性判断）
const baseNameMap = new Map();
for (const rel of allMd) {
  const base = rel.includes('/') ? rel.split('/').pop() : rel;
  if (!baseNameMap.has(base)) baseNameMap.set(base, rel);
}
function resolveWikilink(target) {
  // 目录式链接 [[dir/]]：仅校验目录是否存在
  if (target.endsWith('/')) {
    const dir = target.replace(/\/$/, '');
    return fs.existsSync(path.join(ROOT, dir)) && fs.statSync(path.join(ROOT, dir)).isDirectory()
      ? dir
      : null;
  }
  // mdSet 存的是去扩展名的相对路径（如 "concepts/transformer-architecture"）
  // 1) 完整带目录路径：target 直接匹配
  if (mdSet.has(target)) return target;
  // 2) 短名：找任意 <dir>/target.md
  if (baseNameMap.has(target)) return baseNameMap.get(target);
  return null;
}

// 收集所有待查文件
const files = [];
collectMd(ROOT, '', files); // 这次需要带路径读内容，复用 allMd 即可但需全路径
const fileFullPaths = [];
(function walk(d, b) {
  for (const ent of fs.readdirSync(d, { withFileTypes: true })) {
    if (ent.name.startsWith('.')) continue;
    const full = path.join(d, ent.name);
    if (ent.isDirectory()) walk(full, b ? `${b}/${ent.name}` : ent.name);
    else if (ent.isFile() && ent.name.endsWith('.md'))
      fileFullPaths.push(full);
  }
})(ROOT, '');

const WIKILINK_RE = /\[\[([^\]]+)\]\]/g;
const EXT_RE = /\]\((https?:\/\/[^)\s]+)\)/g;

let broken = 0;
const brokenList = [];

// 1) Wikilink 校验
for (const fp of fileFullPaths) {
  const text = fs.readFileSync(fp, 'utf8');
  let m;
  while ((m = WIKILINK_RE.exec(text))) {
    const inner = m[1];
    const target = inner.split('|')[0].trim(); // 去 alias
    if (!target) continue;
    if (resolveWikilink(target) === null) {
      broken++;
      const kind = target.endsWith('/') ? '目录不存在' : '目标文件不存在';
      brokenList.push(
        `WIKILINK  ${path.relative(ROOT, fp)}  ->  [[${inner}]]  (${kind}: ${target})`
      );
    }
  }
}

// 2) 外部链接校验（可选）
if (CHECK_EXTERNAL) {
  const http = require('http');
  const https = require('https');
  const urls = new Set();
  for (const fp of fileFullPaths) {
    const text = fs.readFileSync(fp, 'utf8');
    let m;
    while ((m = EXT_RE.exec(text))) urls.add(m[1]);
  }
  const checkOne = (url) =>
    new Promise((resolve) => {
      const lib = url.startsWith('https') ? https : http;
      const req = lib.request(
        url,
        { method: 'HEAD', timeout: TIMEOUT },
        (res) => {
          // 有的服务器不支持 HEAD，回退 GET
          if (res.statusCode === 405 || res.statusCode === 403) {
            const req2 = lib.request(
              url,
              { method: 'GET', timeout: TIMEOUT },
              (res2) => {
                res2.resume();
                resolve(res2.statusCode < 400 ? null : `${url} -> ${res2.statusCode}`);
              }
            );
            req2.on('error', () => resolve(`${url} -> ERR`));
            req2.on('timeout', () => { req2.destroy(); resolve(`${url} -> TIMEOUT`); });
            req2.end();
          } else {
            res.resume();
            resolve(res.statusCode < 400 ? null : `${url} -> ${res.statusCode}`);
          }
        }
      );
      req.on('error', () => resolve(`${url} -> ERR`));
      req.on('timeout', () => { req.destroy(); resolve(`${url} -> TIMEOUT`); });
      req.end();
    });

  (async () => {
    for (const url of urls) {
      const err = await checkOne(url);
      if (err) {
        broken++;
        brokenList.push(`EXTERNAL  ${err}`);
      }
    }
    finish();
  })();
} else {
  finish();
}

function finish() {
  if (broken === 0) {
    console.log(`✅ 链接校验通过：扫描 ${fileFullPaths.length} 个文件，未发现断链。`);
    process.exit(0);
  } else {
    console.error(`❌ 发现 ${broken} 处断链：`);
    for (const l of brokenList) console.error('  - ' + l);
    process.exit(1);
  }
}
