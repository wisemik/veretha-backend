import dotenv
import os
import uuid
import logging
from entity_secret import generate_entity_secret
from circle.web3 import developer_controlled_wallets
from circle.web3 import utils
import requests

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Load environment variables
dotenv.load_dotenv()

def create_transfer(from_wallet_id: str, amount: str, destination_address: str) -> None:

    entitySecretCipherText = generate_entity_secret()

    # wallet_id = "f89bfdb1-ccf3-517a-8046-12cffeb406de"

    #generate new uuid for idempotency key
    idempotencyKey = uuid.uuid4()

    # print(idempotencyKey)

    payload = {
        "idempotencyKey": str(idempotencyKey),
        "entitySecretCipherText": entitySecretCipherText,
        "amounts": [amount],
        "destinationAddress": destination_address,
        "feeLevel": "HIGH",
        "tokenId": "5797fbd6-3795-519d-84ca-ec4c5f80c3b1",
        "walletId": from_wallet_id
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer "+os.getenv('CIRCLE_API_KEY')
    }

    url = "https://api.circle.com/v1/w3s/developer/transactions/transfer"

    response = requests.post(url, json=payload, headers=headers)

    # print(response.text)

    return response.json().get('data').get('id')


def wallet_balance(wallet_id: str) -> str:
    api_key = os.getenv('CIRCLE_API_KEY')

    url = f"https://api.circle.com/v1/w3s/wallets/{wallet_id}/balances"
    headers = {
        "Authorization": f"Bearer {api_key}",  # Using the API key for authentication
        "Content-Type": "application/json"  # Ensuring the payload is sent as JSON
    }
    response = requests.request("GET", url, headers=headers)

    # Parse the response to get the amount
    try:
        data = response.json()
        token_balances = data.get("data", {}).get("tokenBalances", [])

        if token_balances:
            # Assuming we want to extract the first token balance
            token_balance = token_balances[0]
            token_amount = token_balance.get("amount", "0")  # Default to 0 if amount is missing
            print(f"Token amount: {token_amount}")
            return token_amount
        else:
            print("No token balances found.")
            return "0"
    except Exception as e:
        print(f"Error parsing wallet balance: {e}")
        return "0"


def create_wallet(email, name, ref_id):
    # Starting the wallet creation process
    # print("Starting the wallet creation process...")

    # Generate entity secret
    entitySecretCipherText = generate_entity_secret()
    # print(f"Generated entity secret: {entitySecretCipherText}")

    # Generate idempotency key
    idempotencyKey = uuid.uuid4()
    # print(f"Generated idempotencyKey: {idempotencyKey}")

    # Get API key from environment
    api_key = os.getenv('CIRCLE_API_KEY')
    if not api_key:
        print("Error: CIRCLE_API_KEY is not set in the environment!")
        return
    # print(f"Using API key: {api_key}")

    # Initialize developer-controlled wallets client
    # print("Initializing developer-controlled wallets client...")
    client = utils.init_developer_controlled_wallets_client(
        api_key=api_key,
        entity_secret=os.getenv("CIRCLE_HEX_ENCODED_ENTITY_SECRET_KEY")
    )

    # Create an instance of the WalletSets API
    wallet_sets_api = developer_controlled_wallets.WalletSetsApi(client)

    try:
        # Create wallet set request
        wallet_set_request = developer_controlled_wallets.CreateWalletSetRequest.from_dict({
            "name": email  # Using the email as the wallet set name
        })
        wallet_set_response = wallet_sets_api.create_wallet_set(wallet_set_request)

        # Access the wallet set object
        wallet_set = wallet_set_response.data.wallet_set

        # Extract the wallet set ID
        wallet_set_id = wallet_set.actual_instance.id
        # print(f"Created wallet set with ID: {wallet_set_id}")


        url = "https://api.circle.com/v1/w3s/developer/wallets"

        walletSetId = wallet_set_id

        payload = f"""{{
            "blockchains": [
                "ETH-SEPOLIA"
            ],
            "metadata": [
                {{
                    "name": "{name}",
                    "refId": "{ref_id}"
                }}
            ],
            "count": 1,
            "entitySecretCiphertext": "{entitySecretCipherText}",
            "idempotencyKey": "{idempotencyKey}",
            "walletSetId": "{walletSetId}"
        }}"""
        headers = {
            "Authorization": f"Bearer {api_key}",  # Using the API key for authentication
            "Content-Type": "application/json"  # Ensuring the payload is sent as JSON
        }

        response = requests.request("POST", url, headers=headers, data=payload)
        # print(response.text)
        return response.json().get('data', {}).get('wallets', [])[0].get('id'), response.json().get('data', {}).get('wallets', [])[0].get('address')


    except Exception as e:
        print(f"Error creating wallet set")


# Trigger wallet creation
# wallet_id, wallet_address = create_wallet("user@example.com", "23423", "3424")
# print(wallet_id, wallet_address)
# f89bfdb1-ccf3-517a-8046-12cffeb406de
print(wallet_balance("f89bfdb1-ccf3-517a-8046-12cffeb406de"))