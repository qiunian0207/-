from unstructured.partition.pdf import partition_pdf
from unstructured.partition.image import partition_image
from unstructured.partition.docx import partition_docx
from unstructured.partition.xlsx import partition_xlsx
import os

class DocumentParser:
    def __init__(self):
        pass
    
    def parse(self, file_path):
        """Parse document based on file extension"""
        file_extension = os.path.splitext(file_path)[1].lower()
        
        try:
            if file_extension == ".pdf":
                return self._parse_pdf(file_path)
            elif file_extension in [".jpg", ".jpeg", ".png", ".tiff"]:
                return self._parse_image(file_path)
            elif file_extension == ".docx":
                return self._parse_docx(file_path)
            elif file_extension == ".xlsx":
                return self._parse_xlsx(file_path)
            else:
                raise ValueError(f"Unsupported file format: {file_extension}")
        except Exception as e:
            return f"Error parsing document: {str(e)}"
    
    def _parse_pdf(self, file_path):
        """Parse PDF document"""
        elements = partition_pdf(file_path)
        content = "\n".join([str(element) for element in elements])
        return {
            "type": "pdf",
            "content": content,
            "elements": len(elements)
        }
    
    def _parse_image(self, file_path):
        """Parse image document"""
        elements = partition_image(file_path)
        content = "\n".join([str(element) for element in elements])
        return {
            "type": "image",
            "content": content,
            "elements": len(elements)
        }
    
    def _parse_docx(self, file_path):
        """Parse DOCX document"""
        elements = partition_docx(file_path)
        content = "\n".join([str(element) for element in elements])
        return {
            "type": "docx",
            "content": content,
            "elements": len(elements)
        }
    
    def _parse_xlsx(self, file_path):
        """Parse XLSX document"""
        elements = partition_xlsx(file_path)
        content = "\n".join([str(element) for element in elements])
        return {
            "type": "xlsx",
            "content": content,
            "elements": len(elements)
        }