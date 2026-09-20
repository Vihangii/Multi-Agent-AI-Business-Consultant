// `npm run dev` at the repo root: starts the FastAPI backend and the Next.js
// web app together in one terminal, with prefixed output. Ctrl+C stops both.
//
// Picks the first free port from 8000 for the API (another project often
// holds 8000) and tells the web app where it is via NEXT_PUBLIC_API_URL.

import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const web = path.join(root, "web");
const isWin = process.platform === "win32";
const python = isWin ? path.join(root, ".venv", "Scripts", "python.exe") : path.join(root, ".venv", "bin", "python");

if (!existsSync(python)) {
  console.error(`No virtualenv at ${python}.\nCreate it first:\n  py -3.12 -m venv .venv  (Windows)  |  python3.12 -m venv .venv\n  .venv\\Scripts\\pip install -r requirements.txt`);
  process.exit(1);
}
if (!existsSync(path.join(web, "node_modules"))) {
  console.error("web/node_modules missing — run:  cd web && npm install");
  process.exit(1);
}

// A port is "free" only if nothing answers on it AND we can bind it on all
// interfaces (binding 127.0.0.1 alone can succeed while 0.0.0.0 is taken).
const inUse = (port) =>
  new Promise((resolve) => {
    const sock = net.connect({ port, host: "127.0.0.1" });
    sock.once("connect", () => { sock.destroy(); resolve(true); });
    sock.once("error", () => resolve(false));
  });
const canBind = (port) =>
  new Promise((resolve) => {
    const srv = net.createServer();
    srv.once("error", () => resolve(false));
    srv.listen(port, () => srv.close(() => resolve(true)));
  });
const freePort = async (start) => {
  for (let p = start; p < start + 50; p++) {
    if (!(await inUse(p)) && (await canBind(p))) return p;
  }
  throw new Error(`No free port found from ${start}`);
};

const apiPort = await freePort(Number(process.env.BACKEND_PORT || 8000));
const webPort = await freePort(Number(process.env.PORT || 3000));
const apiUrl = `http://localhost:${apiPort}`;

const colors = { api: "\x1b[36m", web: "\x1b[35m", reset: "\x1b[0m" };
const pipe = (name, child) => {
  const tag = `${colors[name]}[${name}]${colors.reset} `;
  for (const stream of [child.stdout, child.stderr]) {
    let buf = "";
    stream.on("data", (d) => {
      buf += d.toString();
      const lines = buf.split(/\r?\n/);
      buf = lines.pop();
      for (const l of lines) if (l.trim()) process.stdout.write(tag + l + "\n");
    });
  }
};

console.log(`\n  API      ->  ${apiUrl}   (docs: ${apiUrl}/docs)\n  Web app  ->  http://localhost:${webPort}\n`);

const api = spawn(python, ["-m", "uvicorn", "backend.main:app", "--reload", "--port", String(apiPort)], {
  cwd: root,
  env: { ...process.env, PYTHONUTF8: "1" },
});
pipe("api", api);

// On Windows npm is a .cmd shim; run it through cmd.exe explicitly (no shell:true needed)
const npmCmd = isWin ? process.env.ComSpec || "cmd.exe" : "npm";
const npmArgs = isWin ? ["/d", "/s", "/c", "npm run dev -- --port " + webPort] : ["run", "dev", "--", "--port", String(webPort)];
const webProc = spawn(npmCmd, npmArgs, {
  cwd: web,
  env: { ...process.env, NEXT_PUBLIC_API_URL: apiUrl },
});
pipe("web", webProc);

const shutdown = () => {
  api.kill();
  webProc.kill();
  process.exit(0);
};
process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
api.on("exit", (code) => { if (code && code !== 0) console.error(`[api] exited with ${code}`); });
webProc.on("exit", (code) => { if (code && code !== 0) console.error(`[web] exited with ${code}`); });
