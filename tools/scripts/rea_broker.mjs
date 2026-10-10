// REA MCP 常驻 broker。
// 存在理由：CodeBuddy 工具调用有 30 分钟硬编码空闲超时（genie 扩展 waitForExecuted(18e5)），
// 而 62MB IL2CPP 的 Ghidra 全量分析远超 30 分钟，且调用被取消时 REA 会丢弃临时数据库。
// 本进程不设超时、独立于会话存活，持有 MCP 服务器会话，经文件中转转发请求。
//
// 协议：轮询 $REA_BROKER_DIR/request.json（{seq, tool, args}，seq 变化即视为新请求），
//       结果写 response.json（{seq, ok, elapsedMs, result|error}），状态写 status.json。
// 用法：REA_BROKER_DIR=<目录> node tools/scripts/rea_broker.mjs

import { spawn } from 'node:child_process';
import { appendFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';

const DIR = process.env.REA_BROKER_DIR;
if (!DIR) throw new Error('REA_BROKER_DIR 未设置');
mkdirSync(DIR, { recursive: true });

const REQ = `${DIR}/request.json`;
const RES = `${DIR}/response.json`;
const STATUS = `${DIR}/status.json`;
const LOG = `${DIR}/broker.log`;

function log(msg) {
  appendFileSync(LOG, `${new Date().toISOString()} ${msg}\n`);
}
function writeJson(path, value) {
  writeFileSync(path, JSON.stringify(value, null, 2));
}

let nextId = 2; // id=1 留给 initialize
const pending = new Map();
let child;

function startServer() {
  log('starting rea mcp server');
  child = spawn('npx', ['-y', 'rea-agents@6.1.0', 'mcp'], {
    env: {
      ...process.env,
      GHIDRA_INSTALL_DIR: process.env.GHIDRA_INSTALL_DIR ?? `${process.env.HOME}/tools/ghidra_12.1.4_PUBLIC`,
      // 堆必须显式给大：REA 默认 -Xmx2G（GhidraJavaLaunch.js），对 62MB IL2CPP 会慢到超时
      GHIDRA_HEADLESS_MAXMEM: process.env.GHIDRA_HEADLESS_MAXMEM ?? '8G',
      // 4h：实测默认 2G 堆下 1h 不够；给足分析时间，避免 provider_timeout 白跑
      REA_GHIDRA_STARTUP_TIMEOUT_MS: process.env.REA_GHIDRA_STARTUP_TIMEOUT_MS ?? '14400000',
    },
    stdio: ['pipe', 'pipe', 'pipe'],
  });
  child.stderr.on('data', (d) => log(`[server stderr] ${String(d).trim()}`));
  child.on('exit', (code) => log(`[server exit] code=${code}`));

  let buf = '';
  child.stdout.on('data', (d) => {
    buf += String(d);
    // MCP stdio 按行分隔 JSON-RPC，逐行解析，避免粘包
    let idx;
    while ((idx = buf.indexOf('\n')) >= 0) {
      const line = buf.slice(0, idx).trim();
      buf = buf.slice(idx + 1);
      if (!line) continue;
      let msg;
      try {
        msg = JSON.parse(line);
      } catch {
        log(`[unparsed] ${line.slice(0, 200)}`);
        continue;
      }
      if (msg.id !== undefined && pending.has(msg.id)) {
        const entry = pending.get(msg.id);
        pending.delete(msg.id);
        const elapsedMs = Date.now() - entry.startedAt;
        log(`[tool done] seq=${entry.seq} tool=${entry.tool} ok=${!msg.error} ${Math.round(elapsedMs / 1000)}s`);
        writeJson(RES, {
          seq: entry.seq,
          tool: entry.tool,
          ok: !msg.error,
          elapsedMs,
          result: msg.result ?? null,
          error: msg.error ?? null,
        });
        writeJson(STATUS, { state: 'ready', lastSeq: entry.seq, updatedAt: new Date().toISOString() });
      }
    }
  });

  const send = (obj) => child.stdin.write(`${JSON.stringify(obj)}\n`);
  send({
    jsonrpc: '2.0',
    id: 1,
    method: 'initialize',
    params: {
      protocolVersion: '2024-11-05',
      capabilities: {},
      clientInfo: { name: 'rea-broker', version: '1' },
    },
  });
  send({ jsonrpc: '2.0', method: 'notifications/initialized' });
  log('initialize sent');
}

function callTool(seq, tool, args) {
  const id = nextId++;
  pending.set(id, { seq, tool, startedAt: Date.now() });
  writeJson(STATUS, { state: 'running', seq, tool, startedAt: new Date().toISOString() });
  log(`[tool start] seq=${seq} tool=${tool}`);
  child.stdin.write(
    `${JSON.stringify({ jsonrpc: '2.0', id, method: 'tools/call', params: { name: tool, arguments: args ?? {} } })}\n`,
  );
}

startServer();

// 轮询请求文件：对比 seq 变化而非 mtime，避免同秒内覆盖丢失
let lastSeq = 0;
setInterval(() => {
  if (!existsSync(REQ)) return;
  let req;
  try {
    req = JSON.parse(readFileSync(REQ, 'utf8'));
  } catch (e) {
    log(`[bad request] ${e.message}`);
    return;
  }
  if (!req || typeof req.seq !== 'number' || req.seq === lastSeq) return;
  if (pending.size > 0) {
    log(`[busy] 已有请求在跑，忽略 seq=${req.seq}`);
    return;
  }
  lastSeq = req.seq;
  callTool(req.seq, req.tool, req.args);
}, 1000);

writeJson(STATUS, { state: 'idle', updatedAt: new Date().toISOString() });
log('broker ready');
