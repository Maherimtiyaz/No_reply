"""
Tests for AI transaction parsing engine.

Tests cover:
- LLM abstraction layer
- Prompt templates
- Rule-based parsing
- Parsing engine orchestration
- Confidence scoring
- Fallback mechanisms
"""
import pytest
import anyio
from datetime import datetime
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from src.db.models import User, RawEmail, Transaction, ParsingLog, EmailStatus, ParsingStatus, TransactionType
from src.parsing.llm_service import LLMService, LLMProvider, MockLLMClient, LLMResponse
from src.parsing.prompt_templates import PromptTemplates
from src.parsing.rule_parser import RuleBasedParser
from src.parsing.parsing_engine import ParsingEngine


class TestLLMService:
    """Test LLM abstraction layer"""
    
    def test_mock_llm_client_initialization(self):
        """Test mock LLM client can be initialized"""
        client = MockLLMClient(model="test-model")
        assert client.model == "test-model"
    
    def test_mock_llm_generate(self):
        """Test mock LLM client generates response"""
        async def _test():
            client = MockLLMClient()
            response = await client.generate("test prompt")
            
            assert isinstance(response, LLMResponse)
            assert response.provider == LLMProvider.MOCK
            assert response.content is not None
            assert response.tokens_used == 100
        
        anyio.run(_test)
    
    def test_llm_service_initialization_mock(self):
        """Test LLM service initializes with mock provider"""
        service = LLMService(provider=LLMProvider.MOCK)
        assert service.provider == LLMProvider.MOCK
        assert isinstance(service.client, MockLLMClient)
    
    def test_llm_service_requires_api_key_for_openai(self):
        """Test OpenAI provider requires API key"""
        with pytest.raises(ValueError, match="API key required"):
            LLMService(provider=LLMProvider.OPENAI)
    
    def test_llm_service_requires_api_key_for_anthropic(self):
        """Test Anthropic provider requires API key"""
        with pytest.raises(ValueError, match="API key required"):
            LLMService(provider=LLMProvider.ANTHROPIC)
    
    def test_llm_service_generate(self):
        """Test LLM service can generate responses"""
        async def _test():
            service = LLMService(provider=LLMProvider.MOCK)
            response = await service.generate("test prompt")
            
            assert isinstance(response, LLMResponse)
            assert response.provider == LLMProvider.MOCK
        
        anyio.run(_test)


class TestPromptTemplates:
    """Test prompt template generation"""
    
    def test_transaction_extraction_prompt(self):
        """Test basic transaction extraction prompt"""
        email_content = {
            "subject": "Your purchase receipt",
            "sender": "store@example.com",
            "body": "Thank you for your purchase of $50.00"
        }
        
        prompt = PromptTemplates.transaction_extraction_prompt(email_content)
        
        assert "Your purchase receipt" in prompt
        assert "store@example.com" in prompt
        assert "$50.00" in prompt
        assert "JSON" in prompt
        assert "is_transaction" in prompt
    
    def test_few_shot_examples(self):
        """Test few-shot examples are generated"""
        examples = PromptTemplates.few_shot_examples()
        
        assert "Example 1" in examples
        assert "Amazon" in examples
        assert "Starbucks" in examples
    
    def test_transaction_extraction_with_examples(self):
        """Test prompt with few-shot examples"""
        email_content = {
            "subject": "Test",
            "sender": "test@example.com",
            "body": "Test body"
        }
        
        prompt = PromptTemplates.transaction_extraction_with_examples(email_content)
        
        assert "Example 1" in prompt
        assert "CONFIDENCE SCORING" in prompt
        assert "is_transaction" in prompt
    
    def test_validate_transaction_output_valid(self):
        """Test validation of valid transaction output"""
        output = """
        {
            "is_transaction": true,
            "transaction_type": "debit",
            "amount": "25.00",
            "currency": "USD",
            "merchant": "Test Store",
            "confidence_score": 0.9
        }
        """
        
        result = PromptTemplates.validate_transaction_output(output)
        
        assert result["is_transaction"] is True
        assert result["transaction_type"] == "debit"
        assert result["amount"] == "25.00"
        assert result["confidence_score"] == 0.9
    
    def test_validate_transaction_output_invalid_json(self):
        """Test validation fails on invalid JSON"""
        output = "This is not JSON"
        
        with pytest.raises(ValueError, match="Invalid JSON"):
            PromptTemplates.validate_transaction_output(output)
    
    def test_validate_transaction_output_missing_fields(self):
        """Test validation handles missing fields"""
        output = '{"is_transaction": true, "confidence_score": 0.8}'
        
        # Should not raise, but lower confidence due to missing transaction fields
        result = PromptTemplates.validate_transaction_output(output)
        assert result["confidence_score"] <= 0.5


class TestRuleBasedParser:
    """Test rule-based fallback parser"""
    
    def test_parser_initialization(self):
        """Test parser initializes correctly"""
        parser = RuleBasedParser()
        assert parser is not None
    
    def test_parse_transaction_email(self):
        """Test parsing a clear transaction email"""
        parser = RuleBasedParser()
        
        email_content = {
            "subject": "Card transaction alert",
            "sender": "alerts@chase.com",
            "body": "Your card ending in 1234 was charged $125.50 at STARBUCKS on 01/15/2024"
        }
        
        result = parser.parse(email_content)
        
        assert result["is_transaction"] is True
        assert result["transaction_type"] == "debit"
        assert result["amount"] == "125.50"
        assert "STARBUCKS" in result["merchant"].upper()
        assert result["confidence_score"] > 0.5
        assert result["extracted_fields"]["card_last_4"] == "1234"
    
    def test_parse_non_transaction_email(self):
        """Test parsing a non-transaction email"""
        parser = RuleBasedParser()
        
        email_content = {
            "subject": "Weekly Newsletter",
            "sender": "newsletter@example.com",
            "body": "Check out our latest tips and tricks for saving money!"
        }
        
        result = parser.parse(email_content)
        
        assert result["is_transaction"] is False
        assert result["confidence_score"] == 0.0
    
    def test_parse_credit_transaction(self):
        """Test parsing a credit/refund transaction"""
        parser = RuleBasedParser()
        
        email_content = {
            "subject": "Refund processed",
            "sender": "support@amazon.com",
            "body": "Your refund of $49.99 has been processed"
        }
        
        result = parser.parse(email_content)
        
        assert result["is_transaction"] is True
        assert result["transaction_type"] == "credit"
        assert result["amount"] == "49.99"
    
    def test_extract_amount_various_formats(self):
        """Test amount extraction with various formats"""
        parser = RuleBasedParser()
        
        test_cases = [
            ("You were charged $25.00", "25.00"),
            ("Total: $1,234.56", "1234.56"),
            ("Amount: 50.99 USD", "50.99"),
            ("USD 100.00 processed", "100.00"),
        ]
        
        for text, expected_amount in test_cases:
            amount = parser._extract_amount(text)
            assert amount == expected_amount, f"Failed for: {text}"
    
    def test_confidence_scoring(self):
        """Test confidence scoring based on extracted fields"""
        parser = RuleBasedParser()
        
        # All fields present - capped at 0.7 for rule-based
        confidence = parser._calculate_confidence("25.00", "Store", "debit", "2024-01-15")
        assert confidence == 0.7  # Maximum for rule-based
        
        # Only amount
        confidence = parser._calculate_confidence("25.00", None, None, None)
        assert 0.5 < confidence < 0.6
        
        # No fields
        confidence = parser._calculate_confidence(None, None, None, None)
        assert confidence == 0.3  # Base score only


class TestParsingEngine:
    """Test main parsing engine orchestration"""
    
    def test_parse_email_with_mock_llm(self, db_session: Session, test_user: User):
        """Test parsing email with mock LLM service"""
        async def _test():
            # Create a raw email
            raw_email = RawEmail(
                user_id=test_user.id,
                message_id="<test123@example.com>",
                subject="Card transaction",
                sender="alerts@chase.com",
                received_at=datetime.now(),
                raw_body="Your card was charged $50.00 at Test Store",
                status=EmailStatus.PENDING
            )
            db_session.add(raw_email)
            db_session.commit()
            
            # Initialize parsing engine
            llm_service = LLMService(provider=LLMProvider.MOCK)
            engine = ParsingEngine(db_session, llm_service=llm_service, confidence_threshold=0.5)
            
            # Parse the email
            transaction = await engine.parse_email(raw_email)
            
            # Verify transaction was created
            assert transaction is not None
            assert transaction.user_id == test_user.id
            assert transaction.raw_email_id == raw_email.id
            assert raw_email.status == EmailStatus.PARSED
            
            # Verify parsing log was created
            parsing_log = db_session.query(ParsingLog).filter(
                ParsingLog.raw_email_id == raw_email.id
            ).first()
            assert parsing_log is not None
            assert parsing_log.status == ParsingStatus.SUCCESS
        
        anyio.run(_test)
    
    def test_parse_non_transaction_email(self, db_session: Session, test_user: User):
        """Test parsing a non-transaction email"""
        async def _test():
            raw_email = RawEmail(
                user_id=test_user.id,
                message_id="<newsletter123@example.com>",
                subject="Weekly Newsletter",
                sender="newsletter@example.com",
                received_at=datetime.now(),
                raw_body="Check out our latest updates and news!",
                status=EmailStatus.PENDING
            )
            db_session.add(raw_email)
            db_session.commit()
            
            llm_service = LLMService(provider=LLMProvider.MOCK)
            engine = ParsingEngine(db_session, llm_service=llm_service)
            
            transaction = await engine.parse_email(raw_email)
            
            # Should not create transaction
            assert transaction is None
            assert raw_email.status == EmailStatus.IGNORED
        
        anyio.run(_test)
    
    def test_confidence_threshold_fallback(self, db_session: Session, test_user: User):
        """Test that low confidence triggers rule-based fallback"""
        async def _test():
            raw_email = RawEmail(
                user_id=test_user.id,
                message_id="<test_fallback@example.com>",
                subject="Transaction alert",
                sender="bank@example.com",
                received_at=datetime.now(),
                raw_body="Card charged $100.00 at Store XYZ",
                status=EmailStatus.PENDING
            )
            db_session.add(raw_email)
            db_session.commit()
            
            llm_service = LLMService(provider=LLMProvider.MOCK)
            engine = ParsingEngine(
                db_session,
                llm_service=llm_service,
                confidence_threshold=0.95  # Very high threshold to force fallback
            )
            
            transaction = await engine.parse_email(raw_email)
            
            # Should still create transaction using rule-based fallback
            # (if rule parser finds it)
            assert raw_email.status in [EmailStatus.PARSED, EmailStatus.IGNORED]
        
        anyio.run(_test)
    
    def test_batch_parse_emails(self, db_session: Session, test_user: User):
        """Test batch parsing multiple emails"""
        async def _test():
            # Create multiple emails
            emails = []
            for i in range(3):
                email = RawEmail(
                    user_id=test_user.id,
                    message_id=f"<batch{i}@example.com>",
                    subject=f"Transaction {i}",
                    sender="store@example.com",
                    received_at=datetime.now(),
                    raw_body=f"Purchase of ${i*10}.00",
                    status=EmailStatus.PENDING
                )
                db_session.add(email)
                emails.append(email)
            
            db_session.commit()
            
            llm_service = LLMService(provider=LLMProvider.MOCK)
            engine = ParsingEngine(db_session, llm_service=llm_service)
            
            results = await engine.batch_parse_emails(emails)
            
            assert results["total"] == 3
            assert results["success"] + results["failed"] + results["ignored"] == 3
        
        anyio.run(_test)
    
    def test_get_parsing_statistics(self, db_session: Session, test_user: User):
        """Test getting parsing statistics"""
        # Create some test data
        raw_email = RawEmail(
            user_id=test_user.id,
            message_id="<stats_test@example.com>",
            subject="Test",
            sender="test@example.com",
            received_at=datetime.now(),
            raw_body="Test body",
            status=EmailStatus.PARSED
        )
        db_session.add(raw_email)
        db_session.commit()
        
        transaction = Transaction(
            user_id=test_user.id,
            raw_email_id=raw_email.id,
            transaction_type=TransactionType.DEBIT,
            amount="50.00",
            currency="USD",
            transaction_date=datetime.now()
        )
        db_session.add(transaction)
        
        parsing_log = ParsingLog(
            raw_email_id=raw_email.id,
            status=ParsingStatus.SUCCESS,
            parsed_data={"test": "data"}
        )
        db_session.add(parsing_log)
        db_session.commit()
        
        llm_service = LLMService(provider=LLMProvider.MOCK)
        engine = ParsingEngine(db_session, llm_service=llm_service)
        
        stats = engine.get_parsing_statistics(test_user.id)
        
        assert "email_status" in stats
        assert "transactions_created" in stats
        assert "parsing_status" in stats
        assert stats["transactions_created"] >= 1


class TestParsingAccuracy:
    """Test parsing accuracy with various email formats"""
    
    def test_parse_amazon_email(self, db_session: Session, test_user: User):
        """Test parsing Amazon-style transaction email"""
        parser = RuleBasedParser()
        
        email_content = {
            "subject": "Your Amazon.com order",
            "sender": "auto-confirm@amazon.com",
            "body": """
                Thank you for your order!
                
                Order Total: $49.99
                
                Items:
                - Product Name
                
                Shipped to: 123 Main St
            """
        }
        
        result = parser.parse(email_content)
        
        assert result["is_transaction"] is True
        assert result["amount"] == "49.99"
        assert result["transaction_type"] == "debit"
    
    def test_parse_bank_alert_email(self, db_session: Session, test_user: User):
        """Test parsing bank alert style email"""
        parser = RuleBasedParser()
        
        email_content = {
            "subject": "Card Alert",
            "sender": "alerts@chase.com",
            "body": "Card ending in 5678 charged $234.56 at WHOLE FOODS on 01/20/2024"
        }
        
        result = parser.parse(email_content)
        
        assert result["is_transaction"] is True
        assert result["amount"] == "234.56"
        assert result["extracted_fields"]["card_last_4"] == "5678"
        assert "WHOLE FOODS" in result["merchant"].upper()
