"""S-DES using the exact substitution tables in 要求.pdf."""
from .core import decrypt_block, encrypt_block, generate_subkeys

__all__ = ["encrypt_block", "decrypt_block", "generate_subkeys"]
