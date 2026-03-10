from transformers import LayoutLMv3Processor, LayoutLMv3ForSequenceClassification
from transformers import DonutProcessor, VisionEncoderDecoderModel
from PIL import Image
import torch
import os

class DocumentUnderstanding:
    def __init__(self, model_type="layoutlmv3"):
        self.model_type = model_type
        if model_type == "layoutlmv3":
            self.processor = LayoutLMv3Processor.from_pretrained("microsoft/layoutlmv3-base")
            self.model = LayoutLMv3ForSequenceClassification.from_pretrained("microsoft/layoutlmv3-base")
        elif model_type == "donut":
            self.processor = DonutProcessor.from_pretrained("naver-clova-ix/donut-base-finetuned-cord-v2")
            self.model = VisionEncoderDecoderModel.from_pretrained("naver-clova-ix/donut-base-finetuned-cord-v2")
        else:
            raise ValueError("Unsupported model type. Choose 'layoutlmv3' or 'donut'")
    
    def understand(self, file_path):
        """Understand document content"""
        try:
            # Check if file is an image
            file_extension = os.path.splitext(file_path)[1].lower()
            if file_extension in [".jpg", ".jpeg", ".png", ".tiff"]:
                image = Image.open(file_path)
            else:
                # For PDF files, convert first page to image
                from pdf2image import convert_from_path
                images = convert_from_path(file_path, first_page=1, last_page=1)
                image = images[0]
            
            if self.model_type == "layoutlmv3":
                return self._process_with_layoutlmv3(image)
            else:
                return self._process_with_donut(image)
        except Exception as e:
            return f"Error understanding document: {str(e)}"
    
    def _process_with_layoutlmv3(self, image):
        """Process document with LayoutLMv3"""
        # Preprocess image
        encoding = self.processor(image, return_tensors="pt")
        
        # Forward pass
        with torch.no_grad():
            outputs = self.model(**encoding)
        
        # Get predictions
        predictions = torch.nn.functional.softmax(outputs.logits, dim=-1)
        predicted_class = torch.argmax(predictions, dim=-1).item()
        
        return {
            "model": "layoutlmv3",
            "predicted_class": predicted_class,
            "confidence": predictions[0][predicted_class].item()
        }
    
    def _process_with_donut(self, image):
        """Process document with Donut"""
        # Preprocess image
        pixel_values = self.processor(image, return_tensors="pt").pixel_values
        
        # Generate output
        task_prompt = "<s_cord-v2>"
        decoder_input_ids = self.processor.tokenizer(task_prompt, add_special_tokens=False, return_tensors="pt").input_ids
        
        with torch.no_grad():
            outputs = self.model.generate(
                pixel_values,
                decoder_input_ids=decoder_input_ids,
                max_length=1024,
                early_stopping=True,
                pad_token_id=self.processor.tokenizer.pad_token_id,
                eos_token_id=self.processor.tokenizer.eos_token_id,
                use_cache=True
            )
        
        # Decode output
        output = self.processor.tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        return {
            "model": "donut",
            "output": output
        }