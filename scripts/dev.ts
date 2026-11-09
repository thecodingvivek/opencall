import { existsSync, mkdirSync, readFileSync, unlinkSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { createConnection } from "node:net";

const root = resolve(import.meta.dir, "..");
const backend = resolve(root, "backend");
const frontend = resolve(root, "frontend");
const python = resolve(backend, ".venv-voice/bin/python");
const pidFile = resolve(backend, "data/dev.pid");
const children = new Set<ReturnType<typeof Bun.spawn>>();
let stopping = false;

async function healthy(url: string, agent = false): Promise<boolean> {
  try {
    const response = await fetch(url, { signal: AbortSignal.timeout(800) });
    if (!response.ok) return false;
    return !agent || (await response.json()).agent_name === "opencall-conversation";
  } catch { return false; }
}

async function listening(port: number): Promise<boolean> {
  return new Promise(resolve => {
    const socket = createConnection({ host: "127.0.0.1", port });
    const finish = (open: boolean) => { socket.destroy(); resolve(open); };
    socket.setTimeout(800);
    socket.once("connect", () => finish(true));
    socket.once("error", () => finish(false));
    socket.once("timeout", () => finish(false));
  });
}

async function stop(code: number) {
  if (stopping) return;
  stopping = true;
  for (const child of children) child.kill("SIGTERM");
  await Promise.race([Promise.all([...children].map(child => child.exited)), Bun.sleep(35000)]);
  for (const child of children) if (child.exitCode === null) child.kill("SIGKILL");
  if (existsSync(pidFile)) unlinkSync(pidFile);
  process.exit(code);
}

async function service(name: string, command: string[], cwd: string, ready: () => Promise<boolean>, port: number, worker = false) {
  if (await listening(port)) {
    // A running Next.js server may still be compiling its first request.
    // Wait for it instead of starting a duplicate server on another port.
    const deadline = Date.now() + 45000;
    while (Date.now() < deadline && !stopping) {
      if (await ready()) {
        console.log(`[dev] Reusing running ${name}.`);
        return;
      }
      await Bun.sleep(250);
    }
    throw new Error(`Port ${port} is occupied but ${name} is not healthy. Check its original terminal.`);
  }
  let registered = !worker;
  let current: ReturnType<typeof Bun.spawn>;
  function launch() {
    if (stopping) return;
    registered = !worker;
    console.log(`[dev] Starting ${name}…`);
    const child = Bun.spawn(command, {
      cwd, env: { ...process.env, PYTHONUNBUFFERED: "1", PYTHONPATH: `${root}:${backend}` },
      stdout: worker ? "pipe" : "inherit", stderr: worker ? "pipe" : "inherit",
    });
    current = child;
    children.add(child);
    if (worker) {
      async function output(stream: ReadableStream<Uint8Array>) {
        const decoder = new TextDecoder();
        let recent = "";
        for await (const chunk of stream) {
          const text = decoder.decode(chunk, { stream: true });
          process.stdout.write(text);
          recent = (recent + text).slice(-2000);
          if (current === child && recent.includes("registered worker")) registered = true;
        }
      }
      void output(child.stdout as ReadableStream<Uint8Array>);
      void output(child.stderr as ReadableStream<Uint8Array>);
    }
    void child.exited.then(async code => {
      children.delete(child);
      if (stopping) return;
      console.error(`[dev] ${name} exited (${code}); restarting in one second.`);
      await Bun.sleep(1000);
      launch();
    });
  }
  launch();
  const deadline = Date.now() + 45000;
  while (Date.now() < deadline && !stopping) {
    if (registered && await ready()) {
      console.log(`[dev] ${name} ready.`);
      return;
    }
    await Bun.sleep(250);
  }
  throw new Error(`${name} did not become ready. See its logs above.`);
}

async function main() {
  if (!existsSync(python)) throw new Error("Create backend/.venv-voice and install backend/requirements.txt first.");
  mkdirSync(resolve(backend, "data"), { recursive: true });
  if (existsSync(pidFile)) {
    const pid = Number(readFileSync(pidFile, "utf8"));
    let alive = false;
    if (pid > 0) { try { process.kill(pid, 0); alive = true; } catch {} }
    if (alive) throw new Error(`OpenCall dev is already running (PID ${pid}). Use that terminal.`);
    unlinkSync(pidFile);
  }
  writeFileSync(pidFile, String(process.pid), { flag: "wx" });
  process.on("SIGINT", () => { void stop(0); });
  process.on("SIGTERM", () => { void stop(0); });
  try {
    const result = Bun.spawnSync([python, "-c", [
      "import json", "from app.core.config import get_settings", "s=get_settings()",
      "from observability.config import get_observability_settings", "o=get_observability_settings()",
      "print(json.dumps({'url':s.livekit_url,'worker_port':s.voice_worker_port,'remote_agent':s.voice_agent_remote,'providers':bool(s.gnani_api_key and s.groq_api_key),'dev_keys':s.livekit_api_key=='devkey' and s.livekit_api_secret.get_secret_value()=='secret','phoenix':o.enabled,'phoenix_port':o.port,'collector':o.collector_endpoint}))",
    ].join(";")], { cwd: backend });
    if (result.exitCode !== 0) throw new Error("Cannot load backend settings. Install backend/requirements.txt in .venv-voice.");
    const config = JSON.parse(result.stdout.toString());
    if (!config.providers) throw new Error("Set GNANI_API_KEY and GROQ_API_KEY in backend/.env.");
    const collector = new URL(config.collector);
    if (config.phoenix && ["localhost", "127.0.0.1", "[::1]"].includes(collector.hostname)) {
      await service("Phoenix", [python, "-m", "observability.server"], backend,
        () => healthy(`http://127.0.0.1:${config.phoenix_port}`), config.phoenix_port);
    }
    const url = new URL(config.url);
    if (["localhost", "127.0.0.1", "[::1]"].includes(url.hostname)) {
      if (!config.dev_keys || url.port !== "7880") {
        throw new Error("For automatic local startup, use ws://127.0.0.1:7880 with devkey/secret. Start a custom LiveKit server separately.");
      }
      if (!Bun.which("livekit-server")) throw new Error("Install LiveKit first: brew install livekit");
      await service("LiveKit", ["livekit-server", "--dev", "--bind", "127.0.0.1"], root,
        () => healthy("http://127.0.0.1:7880"), 7880);
    }
    const workerUrl = `http://127.0.0.1:${config.worker_port}`;
    if (!config.remote_agent) {
      await service("voice worker", [python, "-m", "voiceagent.worker", "dev"], backend,
        async () => await healthy(workerUrl) && await healthy(workerUrl + "/worker", true), config.worker_port, true);
    } else {
      if (["localhost", "127.0.0.1", "[::1]"].includes(url.hostname)) throw new Error("VOICE_AGENT_REMOTE requires a reachable LiveKit Cloud URL.");
      console.log("[dev] Using the remote voice agent; local worker startup skipped.");
    }
    await service("API", [python, "-m", "uvicorn", "app.main:app", "--reload", "--host", "127.0.0.1", "--port", "8000"], backend,
      () => healthy("http://127.0.0.1:8000/api/v1/health"), 8000);
    await service("frontend", ["bun", "run", "dev:frontend"], frontend,
      () => healthy("http://localhost:3000/login"), 3000);
    console.log("\n[dev] OpenCall ready: http://localhost:3000 — keep this terminal running. Ctrl+C stops managed services.\n");
    if (config.phoenix) console.log(`[dev] Phoenix traces: ${collector.origin}\n`);
    await new Promise(() => { setInterval(() => {}, 1000); });
  } catch (error) {
    console.error(`[dev] ${error instanceof Error ? error.message : error}`);
    await stop(1);
  }
}

main().catch(error => { console.error(`[dev] ${error.message}`); process.exitCode = 1; });
