from cryptography.fernet import Fernet
import os
import json
from config.config import BASE_DIR

CREDENTIALS_FILE = os.path.join(BASE_DIR, "secrets/credentials.json.enc")

# Generate a key and save it to a file (do this once)
def generate_key():
    key = Fernet.generate_key()
    secret_key_path = os.path.join(BASE_DIR, "secrets/secret.key")
    with open(secret_key_path, 'wb') as key_file:
        key_file.write(key)
    os.chmod(secret_key_path, 0o600)  # Restrict permissions

# Load the key from the file
def load_key():
    secret_key_path = os.path.join(BASE_DIR, "secrets/secret.key")
    return open(secret_key_path, 'rb').read()

# Encrypt data
def encrypt_data(data: bytes) -> bytes:
    key = load_key()
    f = Fernet(key)
    return f.encrypt(data)

# Decrypt data
def decrypt_data(encrypted_data: bytes) -> bytes:
    key = load_key()
    f = Fernet(key)
    return f.decrypt(encrypted_data)

def save_credentials(credentials: dict):
    # Serialize to JSON and encrypt
    json_data = json.dumps(credentials).encode()
    encrypted_data = encrypt_data(json_data)

    # Write encrypted data to file
    with open(CREDENTIALS_FILE, 'wb') as f:
        f.write(encrypted_data)
    os.chmod(CREDENTIALS_FILE, 0o600)  # Restrict permissions

def load_credentials() -> dict:
    # Read encrypted data from file
    with open(CREDENTIALS_FILE, 'rb') as f:
        encrypted_data = f.read()

    # Decrypt and deserialize
    json_data = decrypt_data(encrypted_data)
    credentials = json.loads(json_data.decode())
    return credentials

