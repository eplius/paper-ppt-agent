# Paper PPT Agent

English | [中文](./README.zh-CN.md)

A local tool that converts a paper PDF or LaTeX source package into an editable PowerPoint deck, with a FastAPI backend and a React frontend.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Node.js 18+ and npm
- An API key for at least one supported provider:
  - OpenAI
  - Anthropic
  - Gemini

## Quick Start

1. Copy `.env.example` to `.env` if you want backend defaults
2. Install backend dependencies

```powershell
uv sync --locked
```

3. Install frontend dependencies

```powershell
cd frontend
npm install
```

4. Start the app

```powershell
cd ..
.\start-dev.bat
```

5. Open

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
