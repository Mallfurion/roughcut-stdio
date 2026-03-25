from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse, PlainTextResponse

from .service import export_project_fcpxml, load_project, runtime_capabilities, scan_and_analyze_media_root


app = FastAPI(title="Roughcut Stdio Analyzer")

ROOT = Path(__file__).resolve().parents[3]
SAMPLE_PROJECT = ROOT / "fixtures" / "sample-project.json"


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/capabilities")
def capabilities() -> dict[str, bool]:
    return runtime_capabilities()


@app.get("/projects/sample")
def get_sample_project() -> JSONResponse:
    project = load_project(SAMPLE_PROJECT)
    return JSONResponse(project.to_dict())


@app.get("/projects/sample/export/fcpxml")
def get_sample_fcpxml() -> PlainTextResponse:
    return PlainTextResponse(
        export_project_fcpxml(SAMPLE_PROJECT),
        media_type="application/xml",
        headers={"Content-Disposition": 'attachment; filename="roughcut-stdio-sample.fcpxml"'},
    )


@app.get("/projects/scan")
def scan_project_root(
    root: str = Query(..., description="Filesystem path to a media root"),
    name: str = Query("Scanned Project", description="Project name"),
    story_prompt: str = Query("Build a coherent rough cut.", description="Narrative goal"),
) -> JSONResponse:
    root_path = Path(root).expanduser()
    if not root_path.exists():
        raise HTTPException(status_code=404, detail="Media root does not exist.")

    project = scan_and_analyze_media_root(
        project_name=name,
        media_roots=[str(root_path.resolve())],
        story_prompt=story_prompt,
        artifacts_root=ROOT / "generated" / "analysis",
    )
    return JSONResponse(project.to_dict())
