# 文档处理系统

## 项目简介

这是一个面向课程与竞赛场景的文档理解系统，用来把原始文档、图片、表格和结构化数据转换为更容易交付的结果。当前版本围绕一个统一的 `TaskPlanner` 流水线组织能力，并通过 Streamlit 提供可视化入口。

系统支持两种主要工作模式：

- `文档/自然语言 -> 结构化`
  把上传文件或手工输入文本解析为结构化摘要、字段记录、章节信息、指标信息和标准化导出文件。
- `结构化数据 -> 调查报告`
  把 JSON 或 Excel 等结构化数据整理为更接近调查报告、分析稿、情况说明的自然语言内容，并同步生成配套导出文件。

## 当前能力

### 输入支持

- `PDF`
- `DOCX`
- `XLSX`
- `TXT`
- `MD`
- `JSON`
- `JPG / JPEG / PNG / TIFF`

### 输出支持

系统会在一次处理完成后统一生成以下文件：

- `JSON`
- `Excel`
- `Word`
- `TXT`
- `PDF`

### 处理链路

当前代码中的核心处理链路如下：

1. `DocumentParser`
   负责解析不同格式输入，统一产出文本块、表格、元数据和结构化载荷。
2. `LayoutAnalyzer` 与 `OCRProcessor`
   作为版面分析与 OCR 增强模块，在图片或复杂文档场景下补充信息。
3. `DocumentUnderstanding`
   汇总文档理解上下文，补足输入模式和文档类型信号。
4. `SemanticAnalyzer`
   进行细节抽取、结构化构建、路由信息记录和提示链路整理。
5. `CanonicalTransformer`
   对结构化输入做标准化整理，便于后续统一生成。
6. `DataValidator`
   对字段结果进行基础校验。
7. `NaturalLanguageGenerator`
   生成自然语言报告内容。
8. `StructuredOutput`
   输出 `json / excel / word / text / pdf` 五类结果。

## 项目结构

```text
doc_processing/
├── app/
│   └── main.py
├── components/
│   ├── canonical_transformer.py
│   ├── chart_renderer.py
│   ├── data_validator.py
│   ├── document_parser.py
│   ├── document_understanding.py
│   ├── layout_analyzer.py
│   ├── model_router.py
│   ├── natural_language_generator.py
│   ├── ocr_processor.py
│   ├── postprocessor.py
│   ├── preprocessor.py
│   ├── prompt_registry.py
│   ├── semantic_analyzer.py
│   ├── structured_output.py
│   └── task_planner.py
├── config/
│   └── config.py
├── examples/
│   └── formal_report_demo.py
├── outputs/
│   ├── uploads/
│   └── results/
├── requirements.txt
└── setup.py
```

## 安装

推荐使用 Python 3.10 及以上版本。

### 基础依赖

```bash
pip install -r requirements.txt
```

当前基础依赖包括：

- `streamlit`
- `pandas`
- `openpyxl`
- `python-docx`
- `pypdf`
- `pillow`
- `matplotlib`

### 可选增强依赖

如果你需要更强的 OCR、版面分析或文档解析能力，可以按需额外安装：

- `unstructured`
- `layoutparser`
- `paddleocr`
- `pdf2image`
- `torch`
- `transformers`
- `opencv-python`

这些依赖不是主流程启动的硬前提，缺失时系统会尽量以降级方式继续执行。

## 配置

核心配置位于 [config.py](/workspaces/-/服务外包代码/doc_processing/config/config.py)。

常用环境变量包括：

- `SEMANTIC_MODEL`
- `ROUTER_MODEL`
- `DETAIL_MODEL`
- `SUMMARY_MODEL`
- `DETAIL_MODEL_CANDIDATES`
- `SUMMARY_MODEL_CANDIDATES`
- `PROMPT_VERSION`
- `ENABLE_PREPROCESSING`
- `ENABLE_POSTPROCESSING`
- `ENABLE_PROMPT_OPTIMIZATION`
- `ENABLE_SUMMARY_SELF_CHECK`
- `SEMANTIC_CHUNK_CHARS`
- `MAX_FILE_SIZE`

默认情况下，本项目可以用本地模式直接运行：

```bash
export SEMANTIC_MODEL=local
export ROUTER_MODEL=local_router
```

## 运行方式

### 启动 Web 界面

```bash
cd /workspaces/-/服务外包代码/doc_processing/app
streamlit run main.py
```

启动后，界面中可以选择两种模式：

- `文档/自然语言 -> 结构化`
- `结构化数据 -> 调查报告`

### 示例脚本

项目中提供了示例脚本：

- [formal_report_demo.py](/workspaces/-/服务外包代码/doc_processing/examples/formal_report_demo.py)

## 输出目录

运行过程中会自动创建以下目录：

- [outputs/uploads](/workspaces/-/服务外包代码/doc_processing/outputs/uploads)
- [outputs/results](/workspaces/-/服务外包代码/doc_processing/outputs/results)

其中 `outputs/results` 会保存每次生成的导出文件，例如：

- 结构化 JSON
- Excel 工作簿
- Word 报告
- TXT 文本
- PDF 文档

## 当前代码特征

和早期版本相比，当前代码有几个更明确的特点：

- 以 `TaskPlanner` 作为统一编排入口
- 同时支持“结构化抽取”和“报告生成”两种方向
- 输出格式固定且完整，便于课程展示和竞赛交付
- OCR、版面分析和高级解析组件采用可选增强策略
- Streamlit 页面与底层组件已经按职责拆分

## 适用场景

- 统计公报解析
- 报告类文档结构化抽取
- 表格数据汇总与标准化导出
- 结构化结果转自然语言报告
- 课程演示、竞赛展示和原型验证
