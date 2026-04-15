# Paper PPT Agent

[English](./README.md) | 中文

将论文 PDF 或 LaTeX 源码包转换为可编辑 PowerPoint 演示文稿的本地工具，后端基于 FastAPI，前端基于 React。

## 环境要求

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Node.js 18+ 与 npm
- 至少一种模型提供商的 API Key：
  - OpenAI
  - Anthropic
  - Gemini

## 快速开始

1. 如需后端默认配置，可将 `.env.example` 复制为 `.env`
2. 安装后端依赖

```powershell
uv sync --locked
```

3. 安装前端依赖

```powershell
cd frontend
npm install
```

4. 启动项目

```powershell
cd ..
.\start-dev.bat
```

5. 打开以下地址

- 后端: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- 前端: [http://127.0.0.1:5173](http://127.0.0.1:5173)

## 手动启动

后端：

```powershell
uv run python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload --reload-dir backend --reload-include=*.py
```

前端：

```powershell
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

## 测试

后端测试：

```powershell
.\.venv\Scripts\python -m pytest -q
```

前端生产构建：

```powershell
cd frontend
npm run build
```

## 参考与致谢

本项目在产品思路、流程拆分和部分工程实现方式上参考了以下开源项目：

- [PPTAgent](https://github.com/icip-cas/PPTAgent)
- [ppt-master](https://github.com/hugohe3/ppt-master)

如果你准备将当前仓库公开发布，建议保留上述引用，并进一步核对相关上游项目的许可证要求，确保说明、署名和兼容性处理完整。
