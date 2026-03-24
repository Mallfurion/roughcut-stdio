import { execFile } from "node:child_process";
import { access } from "node:fs/promises";
import { promisify } from "node:util";
import path from "node:path";

const execFileAsync = promisify(execFile);

export async function GET() {
  const workspaceRoot = path.resolve(process.cwd(), "../..");
  const scriptPath = path.join(workspaceRoot, "services/analyzer/scripts/export_fcpxml.py");
  const generatedPath = path.join(workspaceRoot, "generated/project.json");
  const fixturePath = path.join(workspaceRoot, "fixtures/sample-project.json");
  const projectPath = (await fileExists(generatedPath)) ? generatedPath : fixturePath;

  try {
    const { stdout } = await execFileAsync("python3", [scriptPath, projectPath], {
      cwd: workspaceRoot,
      maxBuffer: 1024 * 1024
    });

    return new Response(stdout, {
      headers: {
        "Content-Type": "application/xml; charset=utf-8",
        "Content-Disposition": 'attachment; filename="timeline-cutter.fcpxml"'
      }
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown export failure";

    return new Response(message, {
      status: 500,
      headers: {
        "Content-Type": "text/plain; charset=utf-8"
      }
    });
  }
}

async function fileExists(targetPath: string): Promise<boolean> {
  try {
    await access(targetPath);
    return true;
  } catch {
    return false;
  }
}
