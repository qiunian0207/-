import re
from langchain.llms import OpenAI
from config.config import OPENAI_API_KEY, VALIDATION_RULES

class DataValidator:
    def __init__(self):
        self.llm = OpenAI(api_key=OPENAI_API_KEY, temperature=0.7)
        self.validation_rules = VALIDATION_RULES
    
    def validate(self, data):
        """Validate data using rules and LLM"""
        try:
            # Rule-based validation
            rule_validation = self._validate_with_rules(data)
            
            # LLM-based validation
            llm_validation = self._validate_with_llm(data)
            
            return {
                "rule_validation": rule_validation,
                "llm_validation": llm_validation,
                "is_valid": all(rule_validation.values()) and llm_validation.get("is_valid", True)
            }
        except Exception as e:
            return f"Error validating data: {str(e)}"
    
    def _validate_with_rules(self, data):
        """Validate data with predefined rules"""
        validation_results = {}
        
        for field, value in data.items():
            if field in self.validation_rules:
                pattern = self.validation_rules[field]
                validation_results[field] = bool(re.match(pattern, str(value)))
            else:
                # For fields without specific rules, check if value is not empty
                validation_results[field] = bool(value)
        
        return validation_results
    
    def _validate_with_llm(self, data):
        """Validate data with LLM"""
        prompt = f"""Validate the following extracted data for consistency and accuracy:

{data}

Please check:
1. Are the values reasonable for their respective fields?
2. Is there any inconsistency between fields?
3. Are there any obvious errors or formatting issues?

Provide a brief validation report and indicate if the data is generally valid."""
        
        response = self.llm(prompt)
        
        # Determine if data is valid based on LLM response
        is_valid = "valid" in response.lower() or "consistent" in response.lower()
        
        return {
            "report": response,
            "is_valid": is_valid
        }