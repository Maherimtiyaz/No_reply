"""
Main parsing engine that orchestrates AI and rule-based parsing.

Combines LLM-based parsing with rule-based fallback for robust transaction extraction.
"""
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime
import json

from .llm_service import LLMService, LLMProvider
from .prompt_templates import PromptTemplates
from .rule_parser import RuleBasedParser
from src.db.models import RawEmail, Transaction, ParsingLog, ParsingStatus, TransactionType, EmailStatus


class ParsingEngine:
    """
    Main parsing engine that orchestrates transaction extraction.
    
    This engine:
    1. Attempts AI-based parsing first
    2. Falls back to rule-based parsing if confidence is low
    3. Logs all parsing attempts
    4. Creates Transaction records for successful parses
    """
    
    def __init__(
        self,
        db: Session,
        llm_service: Optional[LLMService] = None,
        confidence_threshold: float = 0.6,
        use_few_shot: bool = True
    ):
        """
        Initialize the parsing engine.
        
        Args:
            db: Database session
            llm_service: LLM service instance (defaults to mock if not provided)
            confidence_threshold: Minimum confidence to accept AI parsing (0.0-1.0)
            use_few_shot: Whether to use few-shot examples in prompts
        """
        self.db = db
        self.llm_service = llm_service or LLMService(provider=LLMProvider.MOCK)
        self.confidence_threshold = confidence_threshold
        self.use_few_shot = use_few_shot
        self.rule_parser = RuleBasedParser()
    
    async def parse_email(self, raw_email: RawEmail) -> Optional[Transaction]:
        """
        Parse a raw email into a transaction.
        
        This method orchestrates the full parsing pipeline:
        1. Try AI parsing
        2. Fallback to rule-based if needed
        3. Create transaction if successful
        4. Log parsing attempt
        
        Args:
            raw_email: RawEmail object to parse
            
        Returns:
            Transaction object if successful, None otherwise
        """
        email_content = {
            "subject": raw_email.subject or "",
            "sender": raw_email.sender,
            "body": raw_email.raw_body,
            "received_at": raw_email.received_at.isoformat() if raw_email.received_at else None
        }
        
        # Try AI parsing first
        ai_result = await self._try_ai_parsing(email_content)
        
        # Determine if we should use AI result or fallback to rules
        if ai_result and ai_result.get("confidence_score", 0) >= self.confidence_threshold:
            parsing_result = ai_result
            parsing_method = "ai"
        else:
            # Fallback to rule-based parsing
            rule_result = self.rule_parser.parse(email_content)
            
            # Use whichever has higher confidence
            if rule_result.get("confidence_score", 0) > ai_result.get("confidence_score", 0):
                parsing_result = rule_result
                parsing_method = "rule_fallback"
            else:
                parsing_result = ai_result
                parsing_method = "ai_low_confidence"
        
        # Create transaction if this is a valid transaction
        transaction = None
        parsing_status = ParsingStatus.FAILED
        error_message = None
        
        if parsing_result.get("is_transaction"):
            try:
                transaction = self._create_transaction(raw_email, parsing_result, parsing_method)
                parsing_status = ParsingStatus.SUCCESS
                raw_email.status = EmailStatus.PARSED
            except Exception as e:
                parsing_status = ParsingStatus.FAILED
                error_message = f"Failed to create transaction: {str(e)}"
                raw_email.status = EmailStatus.FAILED
        else:
            # Not a transaction email
            parsing_status = ParsingStatus.SUCCESS
            raw_email.status = EmailStatus.IGNORED
        
        # Log parsing attempt
        self._create_parsing_log(
            raw_email,
            parsing_status,
            parsing_result,
            error_message
        )
        
        # Commit changes
        self.db.commit()
        
        return transaction
    
    async def _try_ai_parsing(self, email_content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Attempt to parse email using AI/LLM.
        
        Args:
            email_content: Email content dictionary
            
        Returns:
            Parsed transaction dictionary
        """
        try:
            # Generate prompt
            if self.use_few_shot:
                prompt = PromptTemplates.transaction_extraction_with_examples(email_content)
            else:
                prompt = PromptTemplates.transaction_extraction_prompt(email_content)
            
            # Call LLM
            response = await self.llm_service.generate(prompt)
            
            # Validate and parse output
            parsed = PromptTemplates.validate_transaction_output(response.content)
            
            # Add metadata
            parsed["parsing_method"] = "ai"
            parsed["llm_provider"] = response.provider.value
            parsed["llm_model"] = response.model
            parsed["tokens_used"] = response.tokens_used
            
            return parsed
            
        except Exception as e:
            # Return a failed parse result
            return {
                "is_transaction": False,
                "confidence_score": 0.0,
                "error": str(e),
                "parsing_method": "ai_failed"
            }
    
    def _create_transaction(
        self,
        raw_email: RawEmail,
        parsing_result: Dict[str, Any],
        parsing_method: str
    ) -> Transaction:
        """
        Create a Transaction record from parsing result.
        
        Args:
            raw_email: The source email
            parsing_result: Parsed transaction data
            parsing_method: Method used for parsing
            
        Returns:
            Created Transaction object
            
        Raises:
            ValueError: If required transaction fields are missing
        """
        # Validate required fields
        required = ["transaction_type", "amount", "currency"]
        missing = [f for f in required if not parsing_result.get(f)]
        if missing:
            raise ValueError(f"Missing required transaction fields: {missing}")
        
        # Parse transaction date
        transaction_date = None
        if parsing_result.get("transaction_date"):
            try:
                transaction_date = datetime.fromisoformat(parsing_result["transaction_date"])
            except:
                # Fallback to email received date
                transaction_date = raw_email.received_at
        else:
            transaction_date = raw_email.received_at
        
        # Create metadata
        metadata = {
            "confidence_score": parsing_result.get("confidence_score"),
            "parsing_method": parsing_method,
            "extracted_fields": parsing_result.get("extracted_fields", {}),
            "llm_provider": parsing_result.get("llm_provider"),
            "llm_model": parsing_result.get("llm_model"),
            "tokens_used": parsing_result.get("tokens_used"),
        }
        
        # Create transaction
        transaction = Transaction(
            user_id=raw_email.user_id,
            raw_email_id=raw_email.id,
            transaction_type=TransactionType(parsing_result["transaction_type"]),
            amount=str(parsing_result["amount"]),
            currency=parsing_result["currency"],
            description=parsing_result.get("description"),
            merchant=parsing_result.get("merchant"),
            transaction_date=transaction_date,
            extra_metadata=metadata
        )
        
        self.db.add(transaction)
        return transaction
    
    def _create_parsing_log(
        self,
        raw_email: RawEmail,
        status: ParsingStatus,
        parsed_data: Dict[str, Any],
        error_message: Optional[str] = None
    ):
        """
        Create a parsing log entry.
        
        Args:
            raw_email: The email that was parsed
            status: Parsing status
            parsed_data: The parsed data (can be partial)
            error_message: Error message if parsing failed
        """
        log = ParsingLog(
            raw_email_id=raw_email.id,
            status=status,
            parsed_data=parsed_data,
            error_message=error_message
        )
        self.db.add(log)
    
    async def batch_parse_emails(
        self,
        raw_emails: list[RawEmail],
        max_concurrent: int = 5
    ) -> Dict[str, Any]:
        """
        Parse multiple emails in batch.
        
        Args:
            raw_emails: List of RawEmail objects to parse
            max_concurrent: Maximum concurrent parsing operations
            
        Returns:
            Dictionary with batch parsing statistics
        """
        results = {
            "total": len(raw_emails),
            "success": 0,
            "failed": 0,
            "ignored": 0,
            "transactions_created": 0
        }
        
        # For now, process sequentially
        # Can be enhanced with asyncio.gather for concurrent processing
        for email in raw_emails:
            if email.status != EmailStatus.PENDING:
                continue
            
            try:
                transaction = await self.parse_email(email)
                if transaction:
                    results["transactions_created"] += 1
                    results["success"] += 1
                elif email.status == EmailStatus.IGNORED:
                    results["ignored"] += 1
                else:
                    results["failed"] += 1
            except Exception as e:
                results["failed"] += 1
                print(f"Error parsing email {email.id}: {str(e)}")
        
        return results
    
    def get_parsing_statistics(self, user_id) -> Dict[str, Any]:
        """
        Get parsing statistics for a user.
        
        Args:
            user_id: User UUID (can be string or UUID object)
            
        Returns:
            Dictionary with parsing statistics
        """
        from sqlalchemy import func
        from uuid import UUID
        
        # Convert string to UUID if needed
        if isinstance(user_id, str):
            try:
                user_id = UUID(user_id)
            except ValueError:
                pass  # Keep as string if not a valid UUID
        
        # Count emails by status
        status_counts = dict(
            self.db.query(RawEmail.status, func.count(RawEmail.id))
            .filter(RawEmail.user_id == user_id)
            .group_by(RawEmail.status)
            .all()
        )
        
        # Count transactions
        transaction_count = self.db.query(func.count(Transaction.id)).filter(
            Transaction.user_id == user_id
        ).scalar() or 0
        
        # Count parsing logs by status
        parsing_status_counts = dict(
            self.db.query(ParsingLog.status, func.count(ParsingLog.id))
            .join(RawEmail, ParsingLog.raw_email_id == RawEmail.id)
            .filter(RawEmail.user_id == user_id)
            .group_by(ParsingLog.status)
            .all()
        )
        
        return {
            "email_status": {k.value: v for k, v in status_counts.items()},
            "transactions_created": transaction_count,
            "parsing_status": {k.value: v for k, v in parsing_status_counts.items()},
        }
