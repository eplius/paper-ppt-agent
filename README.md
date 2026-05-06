# Paper PPT Agent

[![MIT License](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)

中文 | [English](./README.en.md)

基于多智能体协作的学术论文演示文稿自动生成工具。上传论文 PDF 或 TeX 源码，由 AI 完成内容提炼、结构规划、版式设计与视觉质量审查，最终输出可编辑的 PowerPoint 文件。

![截图](./screenshot.png)

## 核心能力

### 内容生成

> 支持论文 PDF 与 TeX 源码输入，推荐上传完整的 TeX 压缩包以获得最佳解析效果。多智能体流水线（Strategist → Executor → Critic）协作完成内容提炼与版式生成，支持中英双语及自定义语言输出，可配置目标页数、详略程度和画布比例。

### 视觉质量保障

> 静态分析 Critic 自动检测文字溢出、元素重叠、装饰线遮挡等布局问题并触发修复；视觉 QA（实验性）调用多模态大模型对渲染图像进行审查。修复过程自动归档前后快照，支持逐轮对比与全屏实时预览。

### 图标与装饰

> 内置图标库，支持自动插入语义匹配的图标。可通过 RAG 语义搜索（基于 Gemini Embedding）从图标库中检索最合适的候选，也可独立开关图标装饰与 RAG 搜索。

### 反馈迭代

> 生成完成后可指定单页或多页进行反馈优化，支持结构调整（增删页、插页、重排）。每次迭代自动保存版本快照，支持版本对比与回溯。

### 日志与可观测性

> 实时 Agent 日志流展示各阶段事件与进度；Token 用量按模型、阶段、时间维度聚合，支持筛选与详情查看；Critic 事件面板逐页展示违规项、修复提示词与归档路径；结果页支持回溯完整运行配置。

## 环境要求

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Node.js 18+ 与 npm
- 至少一种模型提供商的 API Key：
  - OpenAI
  - DeepSeek
  - Anthropic
  - Gemini
  - 自定义 BaseURL 兼容接口（模型质量对生成效果有显著影响，推荐 `GPT-5.5` 和 `Gemini 3.1 Pro`）
- （可选）Gemini API Key：用于图标 RAG 语义搜索

## 快速开始

**Windows：**

```powershell
.\start-dev.bat
```

**Linux：**

```bash
sh start-dev.sh
```

启动脚本会自动安装依赖并启动前后端服务。

**手动启动（前后端分别启动）：**

```powershell
# 后端
uv run python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload --reload-dir backend --reload-include=*.py

# 前端
cd frontend && npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

手动启动前需先安装依赖：

```powershell
uv sync --locked
cd frontend && npm install && cd ..
```

启动后访问：

- 前端: [http://127.0.0.1:5173](http://127.0.0.1:5173)
- 后端: [http://127.0.0.1:8000](http://127.0.0.1:8000)

## 重要更新记录

- **Critic 日志落盘与详情面板**：将每次 Critic 检测的违规项、修复提示词、归档路径持久化为 `critic_history.json`，前端支持逐页查看详情
- **修复前后 SVG 对比**：自动归档修复前的 SVG 快照，支持逐轮对比与全屏实时预览
- **图标 RAG 语义搜索**：基于 Gemini Embedding 从图标库中语义检索匹配候选，可独立开关
- **图标装饰主开关**：支持在不使用图标的情况下生成纯形状幻灯片
- **视觉 QA（实验性）**：调用多模态大模型将幻灯片渲染为图像进行布局与对比度审查
- **静态 Critic 增强**：新增装饰线遮挡检测、低对比度文本检测，修复多行文字宽度估算误报
- **版本历史管理**：每次反馈迭代自动归档快照，支持版本对比与回溯
- **Token 日志筛选**：按模型、阶段、页码、任务筛选 LLM 调用记录，支持点击展开详情
- **生成取消**：支持在流水线运行中取消当前任务
- **DeepSeek 专用接口**：独立的 DeepSeek 提供商支持与思考模式配置
- **多智能体流水线**：Strategist → Executor → Critic 三阶段协作，支持 SVG 自动修复与反馈迭代

## 参考与致谢

本项目在产品思路、流程拆分和部分工程实现方式上参考了以下开源项目：

- [PPTAgent](https://github.com/icip-cas/PPTAgent)
- [ppt-master](https://github.com/hugohe3/ppt-master)

## 许可证

本项目基于 [MIT 许可证](./LICENSE) 开源。

## 联系方式

如有问题或建议，欢迎通过以下方式联系：

- GitHub Issues: [CRui5in/paper-ppt-agent](https://github.com/CRui5in/paper-ppt-agent/issues)
- Email: qinruoxuan2018@gmail.com

## 声明

本项目为学术研究辅助工具，生成的演示文稿内容由 AI 模型产出，仅供参考。使用者应对生成内容的准确性和合规性自行负责。使用本工具即表示您同意自行承担因使用生成内容而产生的一切风险。
