# Configuration file for document processing project

# API Keys
OPENAI_API_KEY = "your-openai-api-key"
QWEN_API_KEY = "your-qwen-api-key"

# Model configurations
OCR_MODEL = "paddleocr"
DOCUMENT_UNDERSTANDING_MODEL = "layoutlmv3"  # or "donut"
SEMANTIC_MODEL = "qwen"  # or "gpt"

# Directories
UPLOAD_DIR = "outputs/uploads"
PROCESSED_DIR = "outputs/processed"
OUTPUT_DIR = "outputs/results"

# Processing settings
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
SUPPORTED_FORMATS = [".pdf", ".jpg", ".jpeg", ".png", ".tiff", ".md", ".txt", ".docx", ".xlsx"]

# Validation rules
VALIDATION_RULES = {
    "email": r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
    "phone": r"\d{11}",
    "id_card": r"[1-9]\d{5}(18|19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[0-9Xx]",
    "date": r"\d{4}-\d{2}-\d{2}"
}