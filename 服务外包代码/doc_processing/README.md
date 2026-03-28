# 文档处理系统

## 项目简介

这是一个把非结构化或半结构化文档整理成结构化结果的课程项目。
当前版本重点是“本地优先、单一流水线、可降级运行”：

- 表格类文档优先抽取成字段 schema + 记录列表
- 普通文本优先抽取成键值、章节、指标
- OCR / 版面分析是可选增强，不会再阻塞主流程
- 所有结果统一写到 `doc_processing/outputs/results`

## 当前支持

- `XLSX`：抽取表头、记录和 schema
- `TXT / MD`：抽取标题、章节、指标、日期、键值字段
- `DOCX`：抽取段落和表格
- `PDF`：优先用 `pypdf` 提取文本，失败时再尝试 `unstructured`
- `JPG / PNG / TIFF`：保留图片元信息，可选叠加 OCR

## 安装

```bash
pip install -r requirements.txt
```

如果你需要 OCR 或版面分析增强能力，再额外安装这些可选依赖：

- `unstructured`
- `layoutparser`
- `paddleocr`
- `pdf2image`
- `torch`

## 配置

项目默认使用本地规则抽取，只保留一个必要环境变量：

```bash
export SEMANTIC_MODEL="local"
```

## 运行

```bash
cd /workspaces/-/服务外包代码/doc_processing/app
streamlit run main.py
```

## 输出目录

```text
doc_processing/outputs/results/
```

## 这次整理后解决的问题

- 删除了主页面和编排器里重复的一整套流水线实现
- 移除了不再生效的占位入口和无用配置常量
- 把重依赖改成懒加载 / 可降级模式
- 修复了输出路径混乱和代码职责混杂的问题
- 增加 `.gitignore`，把缓存与运行产物隔离开
