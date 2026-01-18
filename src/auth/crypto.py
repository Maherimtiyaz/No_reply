"""
Token encryption and decryption utilities.
Uses Fernet (symmetric encryption) to securely store OAuth tokens.
"""
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import base64
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from config import settings


class TokenEncryption:
    """Handles encryption and decryption of OAuth tokens"""
    
    def __init__(self):
        """Initialize encryption with key derived from settings"""
        self._fernet = self._get_fernet()
    
    def _get_fernet(self) -> Fernet:
        """
        Create Fernet instance with key derived from SECRET_KEY
        Uses PBKDF2HMAC to derive a proper 32-byte key
        """
        # Get encryption key with fallback to SECRET_KEY
        encryption_key = getattr(settings, 'ENCRYPTION_KEY', '') or getattr(settings, 'SECRET_KEY', 'default-secret-key-for-testing')
        
        # Derive a proper 32-byte key using PBKDF2HMAC
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'noreply-salt-change-in-prod',  # In production, use proper salt management
            iterations=100000,
            backend=default_backend()
        )
        key = base64.urlsafe_b64encode(kdf.derive(encryption_key.encode()))
        return Fernet(key)
    
    def encrypt_token(self, token: str) -> str:
        """
        Encrypt a token string
        
        Args:
            token: Plain text token to encrypt
            
        Returns:
            Encrypted token as string
        """
        if not token:
            return ""
        
        encrypted_bytes = self._fernet.encrypt(token.encode())
        return encrypted_bytes.decode()
    
    def decrypt_token(self, encrypted_token: str) -> str:
        """
        Decrypt an encrypted token
        
        Args:
            encrypted_token: Encrypted token string
            
        Returns:
            Decrypted plain text token
        """
        if not encrypted_token:
            return ""
        
        try:
            decrypted_bytes = self._fernet.decrypt(encrypted_token.encode())
            return decrypted_bytes.decode()
        except Exception as e:
            raise ValueError(f"Failed to decrypt token: {str(e)}")


# Singleton instance
token_encryptor = TokenEncryption()
