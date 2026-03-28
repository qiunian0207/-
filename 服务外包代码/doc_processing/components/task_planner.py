from __future__ import annotations

import json
import os
from typing import Any

try:
    from config.config import DETAIL_MODEL, SEMANTIC_MODEL, SUMMARY_MODEL
    from components.canonical_transformer import CanonicalTransformer
    from components.data_validator import DataValidator
    from components.document_parser import DocumentParser
    from components.document_understanding import DocumentUnderstanding
    from components.layout_analyzer import LayoutAnalyzer
    from components.natural_language_generator import NaturalLanguageGenerator
    from components.ocr_processor import OCRProcessor
    from components.semantic_analyzer import SemanticAnalyzer
    from components.structured_output import StructuredOutput
except ImportError:
    from doc_processing.config.config import DETAIL_MODEL, SEMANTIC_MODEL, SUMMARY_MODEL
    from doc_processing.components.canonical_transformer import CanonicalTransformer
    from doc_processing.components.data_validator import DataValidator
    from doc_processing.components.document_parser import DocumentParser
    from doc_processing.components.document_understanding import DocumentUnderstanding
    from doc_processing.components.layout_analyzer import LayoutAnalyzer
    from doc_processing.components.natural_language_generator import NaturalLanguageGenerator
    from doc_processing.components.ocr_processor import OCRProcessor
    from doc_processing.components.semantic_analyzer import SemanticAnalyzer
    from doc_processing.components.structured_output import StructuredOutput


class TaskPlanner:
    def __init__(
        self,
        semantic_model: str | None = None,
        detail_model: str | None = None,
        summary_model: str | None = None,
    ) -> None:
        self.semantic_model = semantic_model or SEMANTIC_MODEL
        self.detail_model = detail_model or DETAIL_MODEL or self.semantic_model
        self.summary_model = summary_model or SUMMARY_MODEL or self.semantic_model
        self.parser = DocumentParser()
        self.layout_analyzer = LayoutAnalyzer()
        self.ocr_processor = OCRProcessor()
        self.document_understanding = DocumentUnderstanding()
        self.semantic_analyzer = SemanticAnalyzer(
            model_type=self.semantic_model,
            detail_model_type=self.detail_model,
            summary_model_type=self.summary_model,
        )
        self.canonical_transformer = CanonicalTransformer()
        self.natural_language_generator = NaturalLanguageGenerator()
        self.validator = DataValidator()
        self.output_generator = StructuredOutput()

    def plan_and_execute(self, file_path: str, mode: str = "auto") -> dict[str, Any]:
        source_file = os.path.basename(file_path)
        parsed_document = self.parser.parse(file_path)
        pipeline: dict[str, Any] = {
            "source_file": source_file,
            "parse": parsed_document,
        }

        if self._has_error(parsed_document):
            pipeline["error"] = "parse_failed"
            return pipeline

        if mode in {"auto", "structured_to_natural"} and parsed_document.get("type") == "json":
            return self.process_structured_payload(
                parsed_document.get("json_data"),
                source_name=source_file,
                parse_result=parsed_document,
            )

        if mode == "structured_to_natural" and parsed_document.get("type") == "xlsx":
            return self._execute_natural_document(
                parsed_document=parsed_document,
                source_file=source_file,
                file_path=file_path,
                operation_mode="structured_to_natural",
            )

        return self._execute_natural_document(
            parsed_document=parsed_document,
            source_file=source_file,
            file_path=file_path,
        )

    def process_text(self, text: str, title: str = "manual_input.txt") -> dict[str, Any]:
        parsed_document = self._build_text_parse_result(text, title)
        return self._execute_natural_document(
            parsed_document=parsed_document,
            source_file=title,
            file_path=None,
        )

    def process_structured_payload(
        self,
        payload: Any,
        source_name: str = "structured_input.json",
        parse_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized = self.canonical_transformer.normalize_structured_input(payload, source_name=source_name)
        structured_data = normalized["structured_data"]
        canonical_data = normalized["canonical_data"]
        validation_result = self.validator.validate(structured_data)
        semantic_result = self.semantic_analyzer.build_structured_result(
            structured_data=structured_data,
            canonical_data=canonical_data,
            validation_result=validation_result,
            extraction_method="structured_input_normalization",
            timestamp=parse_result.get("metadata", {}).get("generated_at") if isinstance(parse_result, dict) else None,
        )
        natural_language = self.natural_language_generator.generate(
            semantic_result.get("structured_data", {}),
            semantic_result.get("canonical_data", {}),
            parse_result or self._build_structured_parse_result(payload, source_name),
        )

        pipeline = {
            "source_file": source_name,
            "operation_mode": "structured_to_natural",
            "parse": parse_result or self._build_structured_parse_result(payload, source_name),
            "layout": {},
            "ocr": {},
            "understanding": {
                "input_mode": "structured_json",
                "document_type": structured_data.get("document_type", "unknown"),
            },
            "semantic": semantic_result,
            "validation": validation_result,
            "natural_language": natural_language,
        }
        pipeline["output_files"] = self._generate_outputs(pipeline)
        return pipeline

    def _execute_natural_document(
        self,
        parsed_document: dict[str, Any],
        source_file: str,
        file_path: str | None,
        operation_mode: str = "natural_to_structured",
    ) -> dict[str, Any]:
        layout_result = self.layout_analyzer.analyze(file_path) if file_path else {}
        ocr_result = self.ocr_processor.process(file_path) if file_path else {}
        understanding_result = (
            self.document_understanding.understand(
                file_path,
                parsed_document=parsed_document,
                layout_result=layout_result,
                ocr_result=ocr_result,
            )
            if file_path
            else {"input_mode": "direct_text"}
        )
        semantic_input = self._build_semantic_input(parsed_document, ocr_result)
        detail_result = self.semantic_analyzer.extract_details(semantic_input)
        validation_result = self.validator.validate(detail_result.get("structured_data", {}))
        semantic_result = self.semantic_analyzer.build_structured_result(
            structured_data=detail_result.get("structured_data", {}),
            canonical_data=detail_result.get("canonical_data", {}),
            validation_result=validation_result,
            extraction_method=detail_result.get("extraction_method", "detail_rule_based_local"),
            timestamp=detail_result.get("timestamp"),
            preprocessing_result=detail_result.get("preprocessing", {}),
            routing_plan=detail_result.get("routing", {}),
            prompt_plan=detail_result.get("prompting", {}),
            postprocess_report=detail_result.get("postprocessing", {}),
        )
        natural_language = self.natural_language_generator.generate(
            semantic_result.get("structured_data", {}),
            semantic_result.get("canonical_data", {}),
            parsed_document,
        )

        pipeline: dict[str, Any] = {
            "source_file": source_file,
            "operation_mode": operation_mode,
            "parse": parsed_document,
            "layout": layout_result,
            "ocr": ocr_result,
            "understanding": understanding_result,
            "semantic": semantic_result,
            "validation": validation_result,
            "natural_language": natural_language,
        }
        pipeline["output_files"] = self._generate_outputs(pipeline)
        return pipeline

    def _generate_outputs(self, pipeline: dict[str, Any]) -> dict[str, Any]:
        return {
            "json": self.output_generator.generate(pipeline, "json"),
            "excel": self.output_generator.generate(pipeline, "excel"),
            "word": self.output_generator.generate(pipeline, "word"),
            "text": self.output_generator.generate(pipeline, "text"),
            "pdf": self.output_generator.generate(pipeline, "pdf"),
        }

    def _build_semantic_input(
        self,
        parsed_document: dict[str, Any],
        ocr_result: dict[str, Any],
    ) -> dict[str, Any]:
        semantic_input = dict(parsed_document)
        if ocr_result.get("text"):
            semantic_input["ocr_text"] = ocr_result.get("text", "")
        return semantic_input

    def _build_text_parse_result(self, text: str, title: str) -> dict[str, Any]:
        paragraphs = [line.strip() for line in text.splitlines() if line.strip()]
        return {
            "type": "txt",
            "content": text,
            "elements": len(paragraphs),
            "tables": [],
            "blocks": [
                {
                    "id": f"line_{index}",
                    "type": "paragraph",
                    "text": paragraph,
                    "source_anchor": {"line_index": index},
                }
                for index, paragraph in enumerate(paragraphs, start=1)
            ],
            "json_data": None,
            "metadata": {
                "file_name": title,
                "file_path": title,
                "file_size": len(text.encode("utf-8")),
                "title": paragraphs[0] if paragraphs else title,
            },
        }

    def _build_structured_parse_result(self, payload: Any, source_name: str) -> dict[str, Any]:
        serialized = json.dumps(payload, ensure_ascii=False, indent=2)
        return {
            "type": "json",
            "content": serialized,
            "elements": len(payload) if hasattr(payload, "__len__") else 1,
            "tables": [],
            "blocks": [
                {
                    "id": "structured_input",
                    "type": "json",
                    "text": serialized[:4000],
                    "source_anchor": {"source_file": source_name},
                }
            ],
            "json_data": payload,
            "metadata": {
                "file_name": source_name,
                "file_path": source_name,
                "file_size": len(serialized.encode("utf-8")),
                "title": os.path.splitext(source_name)[0],
            },
        }

    @staticmethod
    def _has_error(result: Any) -> bool:
        return isinstance(result, dict) and bool(result.get("error"))
