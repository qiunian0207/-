from langchain.llms import OpenAI
from config.config import OPENAI_API_KEY, QWEN_API_KEY
import requests
import json

class SemanticAnalyzer:
    def __init__(self, model_type="qwen"):
        self.model_type = model_type
        if model_type == "gpt":
            self.llm = OpenAI(api_key=OPENAI_API_KEY, temperature=0.7)
        elif model_type == "qwen":
            self.api_key = QWEN_API_KEY
        else:
            raise ValueError("Unsupported model type. Choose 'qwen' or 'gpt'")
    
    def analyze(self, content):
        """Analyze semantics and align fields"""
        try:
            if self.model_type == "gpt":
                return self._analyze_with_gpt(content)
            else:
                return self._analyze_with_qwen(content)
        except Exception as e:
            return f"Error analyzing semantics: {str(e)}"
    
    def _analyze_with_gpt(self, content):
        """Analyze semantics with GPT"""
        prompt = f"""Analyze the following document content and extract structured information:

{content}

Please extract the following fields if present:
- Name
- Address
- Phone number
- Email
- Date
- Amount
- ID number

Format the output as JSON with clear field names."""
        
        response = self.llm(prompt)
        
        # Parse JSON response
        try:
            structured_data = json.loads(response)
        except json.JSONDecodeError:
            structured_data = {"error": "Failed to parse response"}
        
        return {
            "model": "gpt",
            "structured_data": structured_data
        }
    
    def _analyze_with_qwen(self, content):
        """Analyze semantics with Qwen"""
        url = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        data = {
            "model": "qwen-turbo",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful assistant that extracts structured information from documents."
                },
                {
                    "role": "user",
                    "content": f"Analyze the following document content and extract structured information:\n\n{content}\n\nPlease extract the following fields if present:\n- Name\n- Address\n- Phone number\n- Email\n- Date\n- Amount\n- ID number\n\nFormat the output as JSON with clear field names."
                }
            ],
            "temperature": 0.7
        }
        
        response = requests.post(url, headers=headers, json=data)
        response_data = response.json()
        
        # Extract structured data
        structured_data = response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        # Parse JSON response
        try:
            structured_data = json.loads(structured_data)
        except json.JSONDecodeError:
            structured_data = {"error": "Failed to parse response"}
        
        return {
            "model": "qwen",
            "structured_data": structured_data
        }