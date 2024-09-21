import dotenv
import os
dotenv.load_dotenv()

import base64
import codecs
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
from Crypto.Hash import SHA256

def generate_entity_secret():

    public_key_string = os.getenv('CIRCLE_PUBLIC_KEY')
    hex_encoded_entity_secret = os.getenv('CIRCLE_HEX_ENCODED_ENTITY_SECRET_KEY')

    entity_secret = bytes.fromhex(hex_encoded_entity_secret)

    if len(entity_secret) != 32:
        raise ValueError("Invalid entity secret length. Expected 32 bytes.")

    public_key = RSA.import_key(public_key_string)

    # Encrypt data using the public key
    cipher_rsa = PKCS1_OAEP.new(key=public_key, hashAlgo=SHA256)
    encrypted_data = cipher_rsa.encrypt(entity_secret)

    # Encode to base64
    encrypted_data_base64 = base64.b64encode(encrypted_data)

    # hex_encoded_entity_secret_output = codecs.encode(entity_secret, 'hex').decode()
    entity_secret_ciphertext = encrypted_data_base64.decode()

    return entity_secret_ciphertext

# Example usage:
# public_key_string = 'PASTE_YOUR_PUBLIC_KEY_HERE'
# hex_encoded_entity_secret = 'PASTE_YOUR_HEX_ENCODED_ENTITY_SECRET_KEY_HERE'
# hex_secret, ciphertext = generate_entity_secret(public_key_string, hex_encoded_entity_secret)
# print("Hex encoded entity secret:", hex_secret)
# print("Entity secret ciphertext:", ciphertext)
