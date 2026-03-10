from langchain.agents import AgentType, initialize_agent, Tool
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain.llms import OpenAI
from config.config import OPENAI_API_KEY

class TaskPlanner:
    def __init__(self):
        # Initialize LLM
        self.llm = OpenAI(api_key=OPENAI_API_KEY, temperature=0.7)
        
        # Define tools for document processing
        self.tools = [
            Tool(
                name="DocumentParser",
                func=self.parse_document,
                description="Parse document using Unstructured library"
            ),
            Tool(
                name="LayoutAnalyzer",
                func=self.analyze_layout,
                description="Analyze document layout using LayoutParser"
            ),
            Tool(
                name="OCRProcessor",
                func=self.process_ocr,
                description="Perform OCR using PaddleOCR"
            ),
            Tool(
                name="DocumentUnderstanding",
                func=self.understand_document,
                description="Understand document content using LayoutLMv3 or Donut"
            ),
            Tool(
                name="SemanticAnalyzer",
                func=self.analyze_semantics,
                description="Analyze semantics and align fields using Qwen or GPT"
            ),
            Tool(
                name="DataValidator",
                func=self.validate_data,
                description="Validate data using rules and LLM"
            ),
            Tool(
                name="StructuredOutput",
                func=self.generate_output,
                description="Generate structured output in JSON, Excel, or Word format"
            )
        ]
        
        # Initialize agent
        self.agent = initialize_agent(
            tools=self.tools,
            llm=self.llm,
            agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
            verbose=True
        )
    
    def parse_document(self, file_path):
        """Parse document using Unstructured library"""
        from components.document_parser import DocumentParser
        parser = DocumentParser()
        return parser.parse(file_path)
    
    def analyze_layout(self, file_path):
        """Analyze document layout using LayoutParser"""
        from components.layout_analyzer import LayoutAnalyzer
        analyzer = LayoutAnalyzer()
        return analyzer.analyze(file_path)
    
    def process_ocr(self, file_path):
        """Perform OCR using PaddleOCR"""
        from components.ocr_processor import OCRProcessor
        ocr = OCRProcessor()
        return ocr.process(file_path)
    
    def understand_document(self, file_path):
        """Understand document content using LayoutLMv3 or Donut"""
        from components.document_understanding import DocumentUnderstanding
        understanding = DocumentUnderstanding()
        return understanding.understand(file_path)
    
    def analyze_semantics(self, content):
        """Analyze semantics and align fields using Qwen or GPT"""
        from components.semantic_analyzer import SemanticAnalyzer
        analyzer = SemanticAnalyzer()
        return analyzer.analyze(content)
    
    def validate_data(self, data):
        """Validate data using rules and LLM"""
        from components.data_validator import DataValidator
        validator = DataValidator()
        return validator.validate(data)
    
    def generate_output(self, data, output_format):
        """Generate structured output in JSON, Excel, or Word format"""
        from components.structured_output import StructuredOutput
        output = StructuredOutput()
        return output.generate(data, output_format)
    
    def plan_and_execute(self, file_path):
        """Plan and execute document processing tasks"""
        prompt = f"Process the document at {file_path} through the complete pipeline: "
        prompt += "1. Parse the document "
        prompt += "2. Analyze the layout "
        prompt += "3. Perform OCR "
        prompt += "4. Understand document content "
        prompt += "5. Analyze semantics and align fields "
        prompt += "6. Validate data "
        prompt += "7. Generate structured output in JSON, Excel, and Word formats"
        
        return self.agent.run(prompt)