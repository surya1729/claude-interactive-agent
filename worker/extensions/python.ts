import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { Type } from "@sinclair/typebox";
import { execFileSync } from "node:child_process";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const WORKER_DIR = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const PYTHON = resolve(WORKER_DIR, "../venv/Scripts/python.exe");
const KERNEL_EXEC = resolve(WORKER_DIR, "core", "kernel_exec.py");

console.error(`[python.ts] WORKER_DIR=${WORKER_DIR}`);
console.error(`[python.ts] PYTHON=${PYTHON}`);
console.error(`[python.ts] KERNEL_EXEC=${KERNEL_EXEC}`);

export default function (pi: ExtensionAPI) {
  pi.registerTool({
    name: "python",
    label: "Python",
    description: `Execute Python code in a persistent runtime. Variables, imports, and functions persist across calls.

This is a full Python environment — you can use imports, classes, try/except, list comprehensions, and everything else.

State is maintained: if you set x = 42 in one call, x is still available in the next call.

Use print() for output. The last expression's value is also returned.

Discover available tools:
  from libs import sdk
  sdk.list()          # see all available tools
  sdk.help("gmail")   # get full API for a specific tool

Then import and use:
  from libs.google_workspace import gmail
  emails = gmail.search("from:client", max_results=5)`,
    parameters: Type.Object({
      code: Type.String({ description: "Python code to execute" }),
    }),
    async execute(toolCallId, params, signal, onUpdate, ctx) {
      const { code } = params;
      const args = [KERNEL_EXEC, code, "--cwd", process.cwd()];

      try {
        const raw = execFileSync(PYTHON, args, {
          cwd: WORKER_DIR,
          timeout: 30000, // 30s — first call starts kernel (~3s)
          encoding: "utf-8",
        });

        const result = JSON.parse(raw.trim());

        if (result.error) {
          return {
            content: [{ type: "text", text: `Error: ${result.error}` }],
            details: { error: true },
          };
        }

        return {
          content: [{ type: "text", text: result.output }],
          details: {},
        };
      } catch (e: any) {
        return {
          content: [{ type: "text", text: `Execution failed: ${e.message}` }],
          details: { error: true },
        };
      }
    },
  });
}
