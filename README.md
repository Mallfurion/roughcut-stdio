# Timeline Cutter

Timeline Cutter is structured around one simple flow:

1. `npm run setup`
2. `npm run process`
3. `npm run view`
4. `npm run export`

That is the intended interaction model for this repository.

## Core Idea

- `setup` installs everything the repository needs locally
- `process` scans the repository `media/` path, matches proxies when available, analyzes footage, and writes a generated timeline
- `view` starts the timeline selector web app against the latest generated timeline
- `export` writes a DaVinci Resolve `FCPXML` file from that generated timeline

## Repository Paths

Important paths:

- `media/`
- `generated/project.json`
- `generated/timeline.fcpxml`
- `fixtures/sample-media/`
- `fixtures/sample-project.json`

`media/` is the canonical footage location for this repository.

That path can be:

- a normal folder inside the repo
- a symbolic link pointing at footage stored somewhere else

This means you can do either of these:

```bash
mkdir media
```

or:

```bash
ln -s /absolute/path/to/your/footage media
```

By default, `npm run setup` creates `media` as a symlink to `fixtures/sample-media` if `media` does not already exist. That gives you a working demo flow immediately.

## Prerequisites

Required:

- `Node.js 24+`
- `npm 11+`
- `Python 3.12+`

Optional but recommended for real footage analysis:

- `ffmpeg`
- `ffprobe`
- `PySceneDetect`
- `faster-whisper`

Optional for the analyzer API:

- `FastAPI`
- `uvicorn`

Notes:

- the pipeline still runs without those optional media tools
- when they are missing, the analyzer uses deterministic fallbacks
- silent b-roll workflows remain testable even without speech tooling
- clips without proxies are supported and processed as source-only media

## The Main Flow

### 1. Setup

Run:

```bash
npm run setup
```

What it does:

- runs `npm install`
- creates `.venv`
- creates `generated/`
- creates `media -> fixtures/sample-media` if `media` does not already exist

After setup, the next command is:

```bash
npm run process
```

### 2. Process

Run:

```bash
npm run process
```

What it does:

- reads footage from `media/`
- discovers candidate video files
- classifies source clips and proxy clips
- matches proxies to sources
- keeps source-only clips when no matching proxy exists
- generates candidate segments
- scores silent and spoken footage
- builds a timeline
- writes the result to `generated/project.json`

Output files:

- `generated/project.json`
- `generated/process.log`
- `generated/process-summary.txt`

You can customize the processing prompt with environment variables:

```bash
TIMELINE_PROJECT_NAME="Weekend Edit" \
TIMELINE_STORY_PROMPT="Build a cinematic sequence with a strong opener and a calm outro." \
npm run process
```

After processing, the next command is:

```bash
npm run view
```

### 3. View

Run:

```bash
npm run view
```

What it does:

- starts the Next.js timeline selector app
- loads `generated/project.json` if it exists
- falls back to `fixtures/sample-project.json` if nothing has been processed yet

Open:

- [http://localhost:3000](http://localhost:3000)
- [http://localhost:3000/api/project](http://localhost:3000/api/project)
- [http://localhost:3000/api/export/fcpxml](http://localhost:3000/api/export/fcpxml)

After review, the final command is:

```bash
npm run export
```

### 4. Export

Run:

```bash
npm run export
```

What it does:

- reads `generated/project.json`
- exports a DaVinci Resolve compatible `FCPXML`
- writes the result to `generated/timeline.fcpxml`

Output file:

- `generated/timeline.fcpxml`

You can then import that XML into DaVinci Resolve and validate clip order, trims, and relinking behavior.

## Simple End-To-End Demo

If you want the shortest possible test flow:

```bash
npm run setup
npm run process
npm run view
```

Then, in another terminal:

```bash
npm run export
```

This works immediately because `setup` points `media/` at the synthetic demo footage unless you already provided your own `media` path.

## Using Your Own Footage

Replace the default `media` symlink with your own footage location:

```bash
rm media
ln -s /absolute/path/to/your/footage media
```

Recommended structure:

```text
your-footage/
  Originals/
  Proxy/
```

No-proxy workflows are also supported:

```text
your-footage/
  DJI_0692.MP4
  DJI_0693.MP4
  A001_08101522_C001.mov
```

If no proxy exists for a clip:

- the clip is still processed
- the original file is used as the analysis reference
- the original file is used as the export reference
- `generated/process-summary.txt` lists it as `source-only`
- Resolve must be able to access that original file path when you import the XML

Proxy detection currently uses:

- directory names like `Proxy`, `Proxies`, `Optimized Media`
- filename markers like `proxy`, `prox`, `optimized`

Then rerun:

```bash
npm run process
npm run view
npm run export
```

## What `process` Uses Internally

If installed locally:

- `ffprobe` for media metadata
- `PySceneDetect` for scene boundaries
- `faster-whisper` for transcript excerpts

If not installed:

- metadata defaults are used
- deterministic segment windows are used
- transcript excerpts remain empty

That means:

- spoken clips work better with the optional tools installed
- silent b-roll still works without them
- source-only clips still participate in the timeline when no proxy is available

## Optional Manual Commands

The repository is now centered on npm scripts, but these lower-level commands still exist if you want to inspect the internals.

Run tests:

```bash
npm run test:python
```

Scan manually:

```bash
python3 services/analyzer/scripts/scan_media_root.py "Fixture Scan" media "Build a visual-first rough cut."
```

Export manually:

```bash
python3 services/analyzer/scripts/export_fcpxml.py generated/project.json > generated/timeline.fcpxml
```

Build the web app:

```bash
npm run build:web
```

## Optional Analyzer API

If you want the FastAPI server directly:

```bash
source .venv/bin/activate
python3 -m pip install -e './services/analyzer[api]'
```

Then run:

```bash
source .venv/bin/activate
uvicorn services.analyzer.app.main:app --reload
```

Useful endpoints:

- [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- [http://127.0.0.1:8000/capabilities](http://127.0.0.1:8000/capabilities)
- [http://127.0.0.1:8000/projects/sample](http://127.0.0.1:8000/projects/sample)
- [http://127.0.0.1:8000/projects/sample/export/fcpxml](http://127.0.0.1:8000/projects/sample/export/fcpxml)

## Testing Checklist

The intended test sequence is:

1. `npm run setup`
2. `npm run process`
3. `npm run view`
4. `npm run export`

Expected results:

- `generated/project.json` exists after `process`
- `generated/process-summary.txt` tells you how many clips are proxy-backed vs source-only
- the browser app shows a generated timeline after `view`
- `generated/timeline.fcpxml` exists after `export`

## Troubleshooting

### `npm run setup` fails during Python install

Make sure `python3` points to Python 3.12+.

Check:

```bash
python3 --version
```

### `npm run process` says `media` is missing

Run:

```bash
npm run setup
```

or create the symlink yourself:

```bash
ln -s /absolute/path/to/your/footage media
```

### `npm run process` completes but the timeline is weak

That usually means the optional media tooling is not installed, so the pipeline is using fallbacks.

Install:

```bash
brew install ffmpeg
source .venv/bin/activate
python3 -m pip install scenedetect faster-whisper
```

Then rerun:

```bash
npm run process
```

### `npm run export` fails

Make sure `generated/project.json` exists first.

Run:

```bash
npm run process
```

### The web app still shows sample data

That means `generated/project.json` does not exist yet. Run:

```bash
npm run process
```

## Main Commands

```bash
npm run setup
npm run process
npm run view
npm run export
```
