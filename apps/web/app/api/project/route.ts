import { NextResponse } from "next/server";

import { loadActiveProject } from "../../../lib/project";

export async function GET() {
  const loaded = await loadActiveProject();
  return NextResponse.json({
    source: loaded.source,
    filePath: loaded.filePath,
    project: loaded.project
  });
}
