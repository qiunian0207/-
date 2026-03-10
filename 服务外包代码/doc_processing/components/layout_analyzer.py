import layoutparser as lp
from PIL import Image
import numpy as np
import os

class LayoutAnalyzer:
    def __init__(self):
        # Load pre-trained model
        self.model = lp.Detectron2LayoutModel(
            config_path="lp://PubLayNet/mask_rcnn_X_101_32x8d_FPN_3x/config",
            label_map={0: "Text", 1: "Title", 2: "List", 3: "Table", 4: "Figure"},
            extra_config=["MODEL.ROI_HEADS.SCORE_THRESH_TEST", 0.8]
        )
    
    def analyze(self, file_path):
        """Analyze document layout"""
        try:
            # Check if file is an image
            file_extension = os.path.splitext(file_path)[1].lower()
            if file_extension in [".jpg", ".jpeg", ".png", ".tiff"]:
                image = Image.open(file_path)
                image = np.array(image)
            else:
                # For PDF files, convert first page to image
                from pdf2image import convert_from_path
                images = convert_from_path(file_path, first_page=1, last_page=1)
                image = np.array(images[0])
            
            # Detect layout
            layout = self.model.detect(image)
            
            # Process layout elements
            elements = []
            for block in layout:
                elements.append({
                    "type": block.type,
                    "coordinates": block.coordinates.tolist(),
                    "score": block.score
                })
            
            return {
                "layout_elements": elements,
                "total_elements": len(elements)
            }
        except Exception as e:
            return f"Error analyzing layout: {str(e)}"