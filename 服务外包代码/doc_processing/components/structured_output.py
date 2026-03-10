import json
import pandas as pd
from docx import Document
import os
from config.config import OUTPUT_DIR

class StructuredOutput:
    def __init__(self):
        os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    def generate(self, data, output_format):
        """Generate structured output in specified format"""
        try:
            if output_format == "json":
                return self._generate_json(data)
            elif output_format == "excel":
                return self._generate_excel(data)
            elif output_format == "word":
                return self._generate_word(data)
            else:
                raise ValueError(f"Unsupported output format: {output_format}")
        except Exception as e:
            return f"Error generating output: {str(e)}"
    
    def _generate_json(self, data):
        """Generate JSON output"""
        output_path = os.path.join(OUTPUT_DIR, "output.json")
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return {
            "format": "json",
            "path": output_path,
            "size": os.path.getsize(output_path)
        }
    
    def _generate_excel(self, data):
        """Generate Excel output"""
        output_path = os.path.join(OUTPUT_DIR, "output.xlsx")
        
        # Convert data to DataFrame
        df = pd.DataFrame([data])
        
        # Write to Excel
        df.to_excel(output_path, index=False)
        
        return {
            "format": "excel",
            "path": output_path,
            "size": os.path.getsize(output_path)
        }
    
    def _generate_word(self, data):
        """Generate Word output"""
        output_path = os.path.join(OUTPUT_DIR, "output.docx")
        
        # Create Word document
        doc = Document()
        doc.add_heading("Document Processing Result", level=1)
        
        # Add data to document
        for key, value in data.items():
            doc.add_heading(key, level=2)
            doc.add_paragraph(str(value))
        
        # Save document
        doc.save(output_path)
        
        return {
            "format": "word",
            "path": output_path,
            "size": os.path.getsize(output_path)
        }