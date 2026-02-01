"""
Prompt templates for AI-powered transaction parsing.

Provides standardized prompts for extracting transaction information from emails.
"""
from typing import Dict, Any
import json


class PromptTemplates:
    """
    Collection of prompt templates for transaction parsing.
    
    These templates are designed to work across different LLM providers
    and optimize for deterministic, structured outputs.
    """
    
    @staticmethod
    def transaction_extraction_prompt(email_content: Dict[str, Any]) -> str:
        """
        Create a prompt for extracting transaction information from an email.
        
        Args:
            email_content: Dictionary containing email fields:
                - subject: Email subject line
                - sender: Email sender address
                - body: Email body content
                - received_at: When the email was received
                
        Returns:
            Formatted prompt string
        """
        subject = email_content.get("subject", "")
        sender = email_content.get("sender", "")
        body = email_content.get("body", "")
        
        prompt = f"""You are a financial transaction parser. Extract transaction information from the following email.

EMAIL DETAILS:
Subject: {subject}
From: {sender}

EMAIL BODY:
{body}

INSTRUCTIONS:
1. Identify if this email contains a financial transaction (purchase, payment, refund, etc.)
2. Extract ALL relevant transaction details
3. Return ONLY a valid JSON object with the following structure (no additional text):

{{
  "is_transaction": true/false,
  "transaction_type": "debit" or "credit",
  "amount": "XX.XX",
  "currency": "USD" or other currency code,
  "merchant": "merchant name",
  "description": "brief description of the transaction",
  "transaction_date": "YYYY-MM-DD" or null if not found,
  "confidence_score": 0.0 to 1.0,
  "extracted_fields": {{
    "card_last_4": "XXXX" or null,
    "category": "category if mentioned" or null,
    "location": "location if mentioned" or null,
    "reference_number": "reference if mentioned" or null
  }}
}}

IMPORTANT:
- If this is NOT a transaction email, set "is_transaction" to false and confidence_score to 0.0
- For transaction_type: use "debit" for purchases/payments, "credit" for refunds/deposits
- Amount should be numeric string without currency symbols
- Confidence score should reflect how certain you are about the extraction
- Return ONLY the JSON object, no explanations or additional text
"""
        return prompt
    
    @staticmethod
    def confidence_scoring_guidelines() -> str:
        """
        Guidelines for confidence scoring.
        
        Returns:
            Explanation of confidence scoring criteria
        """
        return """
CONFIDENCE SCORING GUIDELINES:

1.0 - Perfect extraction:
  - All key fields explicitly stated (amount, merchant, date, type)
  - Clear transaction notification from known financial institution
  - No ambiguity in any field

0.8-0.9 - High confidence:
  - All key fields found
  - Minor ambiguity in non-critical fields (e.g., exact category)
  - Transaction clearly identifiable

0.6-0.7 - Medium confidence:
  - Most key fields found
  - Some fields inferred from context
  - Transaction type clear but details may be incomplete

0.4-0.5 - Low confidence:
  - Only some transaction indicators present
  - Significant ambiguity in amount or merchant
  - May require manual review

0.0-0.3 - Very low/no confidence:
  - Not a transaction email
  - Missing critical information
  - Too ambiguous to parse reliably
"""
    
    @staticmethod
    def few_shot_examples() -> str:
        """
        Provide few-shot learning examples for better parsing accuracy.
        
        Returns:
            Example transactions with correct parsing
        """
        examples = [
            {
                "email": {
                    "subject": "Your Amazon purchase",
                    "sender": "auto-confirm@amazon.com",
                    "body": "Thank you for your order. Total: $49.99. Shipped to: 123 Main St."
                },
                "output": {
                    "is_transaction": True,
                    "transaction_type": "debit",
                    "amount": "49.99",
                    "currency": "USD",
                    "merchant": "Amazon",
                    "description": "Amazon purchase",
                    "transaction_date": None,
                    "confidence_score": 0.9,
                    "extracted_fields": {
                        "card_last_4": None,
                        "category": "shopping",
                        "location": None,
                        "reference_number": None
                    }
                }
            },
            {
                "email": {
                    "subject": "Card transaction alert",
                    "sender": "alerts@chase.com",
                    "body": "Card ending in 1234 was charged $125.50 at STARBUCKS on 01/15/2024"
                },
                "output": {
                    "is_transaction": True,
                    "transaction_type": "debit",
                    "amount": "125.50",
                    "currency": "USD",
                    "merchant": "Starbucks",
                    "description": "Card transaction at Starbucks",
                    "transaction_date": "2024-01-15",
                    "confidence_score": 1.0,
                    "extracted_fields": {
                        "card_last_4": "1234",
                        "category": "dining",
                        "location": None,
                        "reference_number": None
                    }
                }
            },
            {
                "email": {
                    "subject": "Newsletter: Weekly Tips",
                    "sender": "newsletter@example.com",
                    "body": "Check out these great tips for saving money..."
                },
                "output": {
                    "is_transaction": False,
                    "transaction_type": None,
                    "amount": None,
                    "currency": None,
                    "merchant": None,
                    "description": None,
                    "transaction_date": None,
                    "confidence_score": 0.0,
                    "extracted_fields": {}
                }
            }
        ]
        
        formatted = "FEW-SHOT EXAMPLES:\n\n"
        for i, example in enumerate(examples, 1):
            formatted += f"Example {i}:\n"
            formatted += f"Email: {json.dumps(example['email'], indent=2)}\n"
            formatted += f"Output: {json.dumps(example['output'], indent=2)}\n\n"
        
        return formatted
    
    @staticmethod
    def transaction_extraction_with_examples(email_content: Dict[str, Any]) -> str:
        """
        Create a prompt with few-shot examples for better accuracy.
        
        Args:
            email_content: Email content to parse
            
        Returns:
            Enhanced prompt with examples
        """
        base_prompt = PromptTemplates.transaction_extraction_prompt(email_content)
        examples = PromptTemplates.few_shot_examples()
        guidelines = PromptTemplates.confidence_scoring_guidelines()
        
        return f"{examples}\n\n{guidelines}\n\n{base_prompt}"
    
    @staticmethod
    def validate_transaction_output(output: str) -> Dict[str, Any]:
        """
        Validate and parse the LLM output.
        
        Args:
            output: Raw LLM output string
            
        Returns:
            Parsed and validated transaction dictionary
            
        Raises:
            ValueError: If output is invalid JSON or missing required fields
        """
        try:
            # Try to parse as JSON
            data = json.loads(output)
            
            # Validate required fields
            required_fields = ["is_transaction", "confidence_score"]
            for field in required_fields:
                if field not in data:
                    raise ValueError(f"Missing required field: {field}")
            
            # If it's a transaction, validate transaction fields
            if data.get("is_transaction"):
                transaction_fields = ["transaction_type", "amount", "currency", "merchant"]
                missing = [f for f in transaction_fields if not data.get(f)]
                if missing:
                    # Lower confidence if fields are missing
                    data["confidence_score"] = min(data.get("confidence_score", 0.5), 0.5)
            
            # Ensure confidence_score is a float between 0 and 1
            confidence = float(data.get("confidence_score", 0.0))
            data["confidence_score"] = max(0.0, min(1.0, confidence))
            
            return data
            
        except json.JSONDecodeError as e:
            # Try to extract JSON from markdown code blocks
            if "```" in output:
                # Extract JSON from code blocks
                import re
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', output, re.DOTALL)
                if json_match:
                    return PromptTemplates.validate_transaction_output(json_match.group(1))
            
            raise ValueError(f"Invalid JSON output from LLM: {str(e)}")
        except Exception as e:
            raise ValueError(f"Error validating LLM output: {str(e)}")
