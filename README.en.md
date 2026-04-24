# Paper PPT Agent

English | [中文](./README.md)

A local tool for generating editable PowerPoint decks from academic papers. It supports paper PDFs and TeX sources, with a FastAPI backend and a React frontend.

![screenshot](./screenshot.png)

## Highlights

- Supports both `PDF` papers and `TeX` sources
- Recommended input: the full `TeX` source package
- Generates editable `PPTX` decks
- Includes feedback refinement after generation: revise a single slide or multiple slides
- Large revisions can optionally allow structural changes, including inserting, removing, and reordering slides

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Node.js 18+ and npm
- An API key for at least one supported provider:
  - OpenAI
  - DeepSeek
  - Anthropic
  - Gemini

## Quick Start

1. Copy `.env.example` to `.env` if you want backend defaults
2. Start the app directly

```powershell
.\start-dev.bat
```

OR

3. Install backend dependencies

```powershell
uv sync --locked
```

4. Install frontend dependencies

```powershell
cd frontend
npm install
```

5. Start the app

```powershell
cd ..
.\start-dev.bat
```

6. Open

- Backend: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- Frontend: [http://127.0.0.1:5173](http://127.0.0.1:5173)

## Manual Start

Backend:

```powershell
uv run python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload --reload-dir backend --reload-include=*.py
```

Frontend:

```powershell
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

## Tests

Backend tests:

```powershell
.\.venv\Scripts\python -m pytest -q
```

Frontend production build:

```powershell
cd frontend
npm run build
```

## Acknowledgements and References

This project references the following open-source projects for product ideas, pipeline structuring, and parts of the engineering approach:

- [PPTAgent](https://github.com/icip-cas/PPTAgent)
- [ppt-master](https://github.com/hugohe3/ppt-master)

If you plan to publish this repository, keep these references in place and verify the upstream license obligations so attribution and compatibility are handled correctly.
