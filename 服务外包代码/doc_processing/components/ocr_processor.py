from paddleocr import PaddleOCR
from PIL import Image
import numpy as np
import os

class OCRProcessor:
    def __init__(self):
        # Initialize PaddleOCR
        self.ocr = PaddleOCR(use_angle_cls=True, lang='ch')
    
    def process(self, file_path):
        """Process OCR on document"""
        try:
            # Check if file is an image
            file_extension = os.path.splitext(file_path)[1].lower()
            if file_extension in [".jpg", ".jpeg", ".png", ".tiff"]:
                # Process image directly
                result = self.ocr.ocr(file_path, cls=True)
            else:
                # For PDF files, convert to images first
                from pdf2image import convert_from_path
                images = convert_from_path(file_path)
                result = []
                for i, image in enumerate(images):
                    # Convert PIL image to numpy array
                    img_array = np.array(image)
                    # Process OCR
                    page_result = self.ocr.ocr(img_array, cls=True)
                    result.append({"page": i + 1, "result": page_result})
            
            # Process OCR results
            ocr_results = []
            if isinstance(result, list) and len(result) > 0:
                if "page" in result[0]:
                    # PDF case
                    for page in result:
                        page_text = []
                        if page["result"]:
                            for line in page["result"]:
                                if line and len(line) > 1:
                                    page_text.append({
                                        "text": line[1][0],
                                        "confidence": line[1][1],
                                        "coordinates": line[0]
                                    })
                        ocr_results.append({"page": page["page"], "texts": page_text})
                else:
                    # Image case
                    page_text = []
                    if result:
                        for line in result:
                            if line and len(line) > 1:
                                page_text.append({
                                    "text": line[1][0],
                                    "confidence": line[1][1],
                                    "coordinates": line[0]
                                })
                    ocr_results.append({"page": 1, "texts": page_text})
            
            return {
                "ocr_results": ocr_results,
                "total_pages": len(ocr_results)
            }
        except Exception as e:
            return f"Error processing OCR: {str(e)}"