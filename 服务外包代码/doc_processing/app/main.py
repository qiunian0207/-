import streamlit as st
import os
import time
from config.config import UPLOAD_DIR, PROCESSED_DIR, OUTPUT_DIR, MAX_FILE_SIZE, SUPPORTED_FORMATS

# Create necessary directories
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

st.set_page_config(
    page_title="文档处理系统",
    page_icon="📄",
    layout="wide"
)

st.title("📄 文档处理系统")
st.write("上传文档，系统将自动进行解析、识别和结构化处理")

# File upload section
st.header("上传文档")
uploaded_file = st.file_uploader(
    "选择要处理的文档",
    type=[fmt[1:] for fmt in SUPPORTED_FORMATS],
    accept_multiple_files=False
)

if uploaded_file is not None:
    # Check file size
    if uploaded_file.size > MAX_FILE_SIZE:
        st.error(f"文件大小超过限制 (最大 {MAX_FILE_SIZE // 1024 // 1024}MB)")
    else:
        # Save uploaded file
        file_path = os.path.join(UPLOAD_DIR, uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        st.success(f"文件上传成功: {uploaded_file.name}")
        
        # Processing steps visualization
        st.header("处理流程")
        processing_steps = [
            "文档解析 (Unstructured)",
            "版面理解 (LayoutParser)",
            "OCR识别 (PaddleOCR)",
            "文档理解 (LayoutLMv3/Donut)",
            "语义理解与字段对齐 (Qwen/GPT)",
            "数据校验 (规则 + LLM)",
            "结构化输出 (JSON → Excel / Word)"
        ]
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, step in enumerate(processing_steps):
            status_text.text(f"正在处理: {step}")
            # Simulate processing time
            time.sleep(1)
            progress_bar.progress((i + 1) / len(processing_steps))
        
        status_text.text("处理完成！")
        
        # Output section
        st.header("处理结果")
        st.write("处理完成，结果已保存到输出目录")
        
        # Download buttons
        st.subheader("下载结果")
        st.button("下载 JSON 文件")
        st.button("下载 Excel 文件")
        st.button("下载 Word 文件")

# Add sidebar information
st.sidebar.title("关于系统")
st.sidebar.write("本系统使用以下技术栈:")
st.sidebar.write("- Streamlit: Web界面")
st.sidebar.write("- LangChain: 任务规划")
st.sidebar.write("- Unstructured: 文档解析")
st.sidebar.write("- LayoutParser: 版面理解")
st.sidebar.write("- PaddleOCR: OCR识别")
st.sidebar.write("- LayoutLMv3/Donut: 文档理解")
st.sidebar.write("- Qwen/GPT: 语义理解")
st.sidebar.write("- 规则 + LLM: 数据校验")
st.sidebar.write("- JSON/Excel/Word: 结构化输出")