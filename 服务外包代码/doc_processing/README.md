# 文档处理系统

## 项目简介

本项目是一个基于Streamlit的文档处理系统，使用多种AI技术来处理和分析文档，包括文档解析、版面理解、OCR识别、文档理解、语义理解与字段对齐、数据校验和结构化输出。

## 技术栈

- **Web界面**: Streamlit
- **任务规划**: LangChain
- **文档解析**: Unstructured
- **版面理解**: LayoutParser
- **OCR识别**: PaddleOCR
- **文档理解**: LayoutLMv3 / Donut
- **语义理解与字段对齐**: Qwen / GPT
- **数据校验**: 规则 + LLM
- **结构化输出**: JSON → Excel / Word

## 项目结构

```
doc_processing/
├── app/                 # 主应用目录
│   └── main.py          # Streamlit主应用
├── components/          # 组件模块目录
│   ├── task_planner.py        # LangChain任务规划
│   ├── document_parser.py     # 文档解析
│   ├── layout_analyzer.py     # 版面理解
│   ├── ocr_processor.py       # OCR识别
│   ├── document_understanding.py  # 文档理解
│   ├── semantic_analyzer.py   # 语义理解与字段对齐
│   ├── data_validator.py      # 数据校验
│   └── structured_output.py   # 结构化输出
├── config/              # 配置文件目录
│   └── config.py        # 配置设置
├── utils/               # 工具函数目录
├── outputs/             # 输出目录
│   ├── uploads/         # 上传文件目录
│   ├── processed/       # 处理文件目录
│   └── results/         # 结果输出目录
├── requirements.txt     # 依赖包列表
└── README.md            # 项目说明
```

## 安装和运行

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置API密钥

在 `config/config.py` 文件中配置以下API密钥：

- `OPENAI_API_KEY`: OpenAI API密钥
- `QWEN_API_KEY`: 阿里云Qwen API密钥

### 3. 运行应用

```bash
cd app
streamlit run main.py
```

> ⚠️ **导入错误排查**
>
> 如果启动应用时出现类似
> `ModuleNotFoundError: No module named 'config'`，请确认：
>
> 1. 目录 `doc_processing`, `config`, `app` 和 `components` 下均有
>    `__init__.py` 文件（使其成为Python包）。
> 2. 启动时将顶层 `doc_processing` 目录加入 `PYTHONPATH`，或者在
>    `app/main.py` 中插入以下代码片段，以便 Python 找到 `config` 包：
>
> ```python
> import os, sys
> parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
> if parent not in sys.path:
>     sys.path.insert(0, parent)
> ```
>
> 这样不论你是直接运行脚本还是通过 `streamlit run`，都能正确导入配置。

## 使用方法

1. 打开浏览器，访问Streamlit应用地址（默认为 http://localhost:8501）
2. 点击"浏览文件"按钮上传要处理的文档
3. 等待系统自动处理文档
4. 处理完成后，点击相应的按钮下载结果（JSON、Excel或Word格式）

## 支持的文件格式

- PDF
- JPG/JPEG
- PNG
- TIFF
- MD (Markdown)
- TXT (纯文本)
- DOCX (Word文档)
- XLSX (Excel表格)

## 处理流程

1. **文档解析**: 使用Unstructured库解析文档内容
2. **版面理解**: 使用LayoutParser分析文档版面结构
3. **OCR识别**: 使用PaddleOCR识别文档中的文本
4. **文档理解**: 使用LayoutLMv3或Donut模型理解文档内容
5. **语义理解与字段对齐**: 使用Qwen或GPT模型进行语义理解和字段对齐
6. **数据校验**: 结合规则和LLM进行数据校验
7. **结构化输出**: 生成JSON、Excel或Word格式的结构化输出

## 注意事项

- 请确保网络连接正常，因为需要调用多个API
- 处理大文件可能需要较长时间，请耐心等待
- 请确保配置了正确的API密钥，否则某些功能可能无法正常工作