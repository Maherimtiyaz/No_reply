"""
Rule-based fallback parser for transaction extraction.

Provides deterministic parsing using regex patterns and heuristics
when AI parsing fails or has low confidence.
"""
import re
from typing import Dict, Any, Optional, List
from datetime import datetime
from decimal import Decimal


class RuleBasedParser:
    """
    Rule-based transaction parser using regex patterns and heuristics.
    
    This parser serves as a fallback when AI parsing fails or returns
    low confidence scores. It uses deterministic rules to extract
    transaction information.
    """
    
    # Common merchant patterns
    MERCHANT_PATTERNS = [
        r'(?:at|from|to)\s+([A-Z][A-Za-z0-9\s&\'-]+?)(?:\s+on|\s+for|\s*\$|\s*USD|\.)',
        r'(?:purchase|payment|transaction)(?:\s+at)?\s+([A-Z][A-Za-z0-9\s&\'-]+?)(?:\s+on|\s+for)',
        r'([A-Z][A-Z0-9\s&\'-]{2,30})(?:\s+charged|\s+transaction)',
    ]
    
    # Amount patterns (various currency formats)
    AMOUNT_PATTERNS = [
        r'\$\s*(\d{1,10}(?:,\d{3})*(?:\.\d{2})?)',  # $1,234.56
        r'(\d{1,10}(?:,\d{3})*(?:\.\d{2})?)\s*USD',  # 1234.56 USD
        r'USD\s*(\d{1,10}(?:,\d{3})*(?:\.\d{2})?)',  # USD 1234.56
        r'(?:total|amount|charged|paid)[\s:]+\$?\s*(\d{1,10}(?:,\d{3})*(?:\.\d{2})?)',
    ]
    
    # Date patterns
    DATE_PATTERNS = [
        r'(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',  # MM/DD/YYYY or DD-MM-YYYY
        r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})',    # YYYY-MM-DD
        r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4})',  # Jan 15, 2024
    ]
    
    # Card patterns
    CARD_PATTERNS = [
        r'card\s+(?:ending\s+(?:in\s+)?|#)?(\d{4})',
        r'x+(\d{4})',
        r'\*+(\d{4})',
    ]
    
    # Transaction type indicators
    DEBIT_KEYWORDS = [
        'purchase', 'charged', 'payment', 'paid', 'spent', 'bought',
        'transaction', 'withdrawal', 'debit', 'order', 'invoice'
    ]
    
    CREDIT_KEYWORDS = [
        'refund', 'credit', 'deposit', 'received', 'reimbursement',
        'cashback', 'return', 'reversal'
    ]
    
    # Non-transaction indicators
    NON_TRANSACTION_KEYWORDS = [
        'newsletter', 'subscription', 'welcome', 'verify', 'confirm your email',
        'reset password', 'unsubscribe', 'privacy policy', 'terms of service',
        'marketing', 'promotional', 'survey'
    ]
    
    def __init__(self):
        """Initialize the rule-based parser"""
        self.compiled_patterns = {
            'merchant': [re.compile(p, re.IGNORECASE) for p in self.MERCHANT_PATTERNS],
            'amount': [re.compile(p, re.IGNORECASE) for p in self.AMOUNT_PATTERNS],
            'date': [re.compile(p, re.IGNORECASE) for p in self.DATE_PATTERNS],
            'card': [re.compile(p, re.IGNORECASE) for p in self.CARD_PATTERNS],
        }
    
    def parse(self, email_content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse email content using rule-based extraction.
        
        Args:
            email_content: Dictionary with subject, sender, body, received_at
            
        Returns:
            Parsed transaction dictionary
        """
        subject = email_content.get("subject", "")
        sender = email_content.get("sender", "")
        body = email_content.get("body", "")
        
        # Combine subject and body for analysis
        full_text = f"{subject}\n{body}"
        
        # Check if this looks like a transaction email
        is_transaction = self._is_transaction_email(full_text, sender)
        
        if not is_transaction:
            return {
                "is_transaction": False,
                "transaction_type": None,
                "amount": None,
                "currency": "USD",
                "merchant": None,
                "description": None,
                "transaction_date": None,
                "confidence_score": 0.0,
                "extracted_fields": {},
                "parsing_method": "rule_based"
            }
        
        # Extract transaction details
        amount = self._extract_amount(full_text)
        merchant = self._extract_merchant(full_text, sender)
        transaction_type = self._extract_transaction_type(full_text)
        transaction_date = self._extract_date(full_text)
        card_last_4 = self._extract_card_number(full_text)
        
        # Calculate confidence based on extracted fields
        confidence = self._calculate_confidence(
            amount, merchant, transaction_type, transaction_date
        )
        
        return {
            "is_transaction": True,
            "transaction_type": transaction_type,
            "amount": amount,
            "currency": "USD",  # Default to USD, can be enhanced
            "merchant": merchant,
            "description": f"Transaction at {merchant}" if merchant else "Transaction",
            "transaction_date": transaction_date,
            "confidence_score": confidence,
            "extracted_fields": {
                "card_last_4": card_last_4,
                "category": None,
                "location": None,
                "reference_number": None
            },
            "parsing_method": "rule_based"
        }
    
    def _is_transaction_email(self, text: str, sender: str) -> bool:
        """
        Determine if the email contains a transaction.
        
        Args:
            text: Email text to analyze
            sender: Email sender address
            
        Returns:
            True if this appears to be a transaction email
        """
        text_lower = text.lower()
        
        # Check for non-transaction keywords
        for keyword in self.NON_TRANSACTION_KEYWORDS:
            if keyword in text_lower:
                return False
        
        # Check for transaction keywords
        has_debit = any(kw in text_lower for kw in self.DEBIT_KEYWORDS)
        has_credit = any(kw in text_lower for kw in self.CREDIT_KEYWORDS)
        
        # Check for amount pattern
        has_amount = any(pattern.search(text) for pattern in self.compiled_patterns['amount'])
        
        # Financial domains
        financial_domains = [
            'paypal', 'venmo', 'chase', 'bankofamerica', 'wellsfargo',
            'citi', 'amex', 'discover', 'capitalone', 'amazon', 'stripe',
            'square', 'shopify', 'ebay'
        ]
        has_financial_sender = any(domain in sender.lower() for domain in financial_domains)
        
        # Consider it a transaction if:
        # - Has amount AND (transaction keywords OR financial sender)
        return has_amount and (has_debit or has_credit or has_financial_sender)
    
    def _extract_amount(self, text: str) -> Optional[str]:
        """Extract monetary amount from text"""
        for pattern in self.compiled_patterns['amount']:
            match = pattern.search(text)
            if match:
                amount_str = match.group(1).replace(',', '')
                try:
                    # Validate it's a valid number
                    amount = Decimal(amount_str)
                    if 0 < amount < 1000000:  # Reasonable transaction range
                        return f"{amount:.2f}"
                except:
                    continue
        return None
    
    def _extract_merchant(self, text: str, sender: str) -> Optional[str]:
        """Extract merchant name from text or sender"""
        # Try patterns first
        for pattern in self.compiled_patterns['merchant']:
            match = pattern.search(text)
            if match:
                merchant = match.group(1).strip()
                if len(merchant) > 2 and len(merchant) < 50:
                    return merchant
        
        # Fallback to sender domain
        if '@' in sender:
            domain = sender.split('@')[1]
            # Extract main part of domain (before .com, .net, etc.)
            merchant = domain.split('.')[0]
            if merchant and len(merchant) > 2:
                return merchant.capitalize()
        
        return None
    
    def _extract_transaction_type(self, text: str) -> str:
        """Determine if transaction is debit or credit"""
        text_lower = text.lower()
        
        # Check credit keywords first (more specific)
        if any(kw in text_lower for kw in self.CREDIT_KEYWORDS):
            return "credit"
        
        # Default to debit for purchases
        return "debit"
    
    def _extract_date(self, text: str) -> Optional[str]:
        """Extract transaction date from text"""
        for pattern in self.compiled_patterns['date']:
            match = pattern.search(text)
            if match:
                date_str = match.group(1)
                try:
                    # Try to parse and normalize to YYYY-MM-DD
                    # This is a simplified version, can be enhanced
                    return date_str
                except:
                    continue
        return None
    
    def _extract_card_number(self, text: str) -> Optional[str]:
        """Extract last 4 digits of card number"""
        for pattern in self.compiled_patterns['card']:
            match = pattern.search(text)
            if match:
                return match.group(1)
        return None
    
    def _calculate_confidence(
        self,
        amount: Optional[str],
        merchant: Optional[str],
        transaction_type: Optional[str],
        transaction_date: Optional[str]
    ) -> float:
        """
        Calculate confidence score based on extracted fields.
        
        Rule-based parsing typically has lower confidence than AI parsing
        but is deterministic.
        """
        score = 0.0
        
        # Base score for identifying a transaction
        score += 0.3
        
        # Add points for each extracted field
        if amount:
            score += 0.25
        if merchant:
            score += 0.25
        if transaction_type:
            score += 0.1
        if transaction_date:
            score += 0.1
        
        # Rule-based parsing is capped at 0.7 confidence
        # (AI parsing can achieve higher confidence)
        return min(score, 0.7)
