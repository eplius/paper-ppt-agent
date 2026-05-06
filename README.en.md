# Paper PPT Agent

[![MIT License](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)

English | [中文](./README.md)

A multi-agent pipeline for automatically generating editable PowerPoint presentations from academic papers. Upload a PDF or TeX source, and the AI handles content extraction, structural planning, layout design, and visual quality assurance.

![screenshot](./screenshot.png)

## Core Capabilities

### Content Generation

> Supports paper PDF and TeX source input; uploading the full TeX archive is recommended for best results. The multi-agent pipeline (Strategist → Executor → Critic) collaborates on content extraction and layout generation. Supports Chinese, English, bilingual, and custom language output with configurable page count, detail level, and canvas format.

### Visual Quality Assurance

> The static Critic automatically detects text overflow, element overlap, and decorative-line occlusion, then triggers self-repair. Visual QA (experimental) invokes a multimodal LLM to inspect rendered slide images. Repair cycles archive pre/post snapshots for side-by-side comparison with real-time full-screen preview.

### Icons and Decoration

> Built-in icon library with automatic semantic matching to slide content. RAG semantic search (via Gemini Embedding) retrieves the most relevant icon candidates. Icon decoration and RAG search can be independently toggled.

### Feedback Iteration

> After generation, specify one or more slides for targeted feedback refinement, with optional structural changes (insert, remove, reorder). Each iteration automatically saves version snapshots with comparison and rollback support.

### Logging and Observability

> Real-time Agent log stream shows stage-level events and progress. Token usage is aggregated by model, stage, and time period with filtering and detail drill-down. The Critic event panel displays per-page violations, repair prompts, and archived SVG paths. The result page includes a full run configuration viewer.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Node.js 18+ and npm
- An API key for at least one supported provider:
  - OpenAI
  - DeepSeek
  - Anthropic
  - Gemini
  - Custom BaseURL-compatible APIs (model quality has a significant impact on results; recommended: `GPT-5.5` and `Gemini 3.1 Pro`)
- (Optional) Gemini API Key: required for icon RAG semantic search

## Quick Start

**Windows:**

```powershell
.\start-dev.bat
```

**Linux:**

```bash
sh start-dev.sh
```

The startup script installs dependencies and launches both frontend and backend automatically.

**Manual start (run backend and frontend separately):**

```powershell
# Backend
uv run python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload --reload-dir backend --reload-include=*.py

# Frontend
cd frontend && npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

For manual start, install dependencies first:

```powershell
uv sync --locked
cd frontend && npm install && cd ..
```

After starting:

- Frontend: [http://127.0.0.1:5173](http://127.0.0.1:5173)
- Backend: [http://127.0.0.1:8000](http://127.0.0.1:8000)

## Notable Changes

- **Critic History Persistence**: Saves violations, repair prompts, and archive paths to `critic_history.json`; frontend detail panel for per-page drill-down
- **Pre-repair SVG Comparison**: Archives SVG snapshots before repair with side-by-side comparison and real-time full-screen preview
- **Icon RAG Semantic Search**: Uses Gemini Embedding to retrieve matching icon candidates from the library; independently toggleable
- **Icon Decoration Master Switch**: Generate slides with plain SVG shapes only, without icon insertion
- **Visual QA (Experimental)**: Multimodal LLM renders each slide as an image to inspect layout and contrast
- **Static Critic Enhancements**: Accent-line occlusion detection, low-contrast text detection, multi-line text width estimation fix
- **Version History**: Automatic snapshot archival per feedback iteration with comparison and rollback
- **Token Log Filtering**: Filter LLM calls by model, stage, page, and job with click-to-expand detail view
- **Generation Cancellation**: Cancel a running pipeline mid-execution
- **DeepSeek Provider**: Dedicated provider support with thinking mode configuration
- **Multi-Agent Pipeline**: Strategist → Executor → Critic with automatic SVG repair and feedback iteration

## Acknowledgements and References

This project references the following open-source projects for product ideas, pipeline structuring, and parts of the engineering approach:

- [PPTAgent](https://github.com/icip-cas/PPTAgent)
- [ppt-master](https://github.com/hugohe3/ppt-master)

## License

This project is licensed under the [MIT License](./LICENSE).

## Contact

For questions or suggestions, please reach out via:

- GitHub Issues: [CRui5in/paper-ppt-agent](https://github.com/CRui5in/paper-ppt-agent/issues)
- Email: qinruoxuan2018@gmail.com

## Disclaimer

This project is an academic research assistance tool. The generated presentation content is produced by AI models and is for reference only. Users are solely responsible for the accuracy and compliance of the generated content. By using this tool, you agree to assume all risks arising from the use of the generated content.
