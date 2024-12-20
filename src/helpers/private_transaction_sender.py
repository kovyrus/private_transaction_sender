import json
import requests
import logging
import time  # Added for retry delays
from typing import Optional, Tuple
from eth_account import messages, Account
from eth_account.signers.local import LocalAccount
from web3 import Web3
from web3.types import TxParams, TxReceipt
from flashbots import flashbot
from src.config import config
from web3.exceptions import TransactionNotFound

class PrivateTransactionSender:
    def __init__(self, web3: Optional[Web3] = None, websocket_uri: Optional[str] = None):
        """
        Initializes the PrivateTransactionSender.

        :param web3: Optional, an existing Web3 instance.
        :param websocket_uri: WebSocket URI for connecting to the Ethereum node.
        """
        # Setup logging
        self.logger = logging.getLogger(self.__class__.__name__)
        # Set the logging level based on config.DEBUG
        log_level = logging.DEBUG if config.DEBUG else logging.INFO
        self.logger.setLevel(log_level)

        # Create a console handler and add it to the logger
        ch = logging.StreamHandler()
        ch.setLevel(log_level)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)

        # Load private key from config
        self.private_key = config.PRIVATE_KEY
        if not self.private_key:
            self.logger.error("Private key not found in configuration.")
            raise ValueError("Private key not found in configuration.")

        # Initialize Web3 connection
        websocket_uri = websocket_uri or config.WEBSOCKET_URI
        self.web3 = web3 or Web3(Web3.WebsocketProvider(websocket_uri))

        if not self.web3.is_connected():
            self.logger.error("Unable to connect to the Ethereum node via WebSocket.")
            raise ConnectionError("Unable to connect to the Ethereum node via WebSocket.")
        self.logger.info("Connected to Ethereum node via WebSocket.")

        # Setup Flashbots for private transactions
        self.account: LocalAccount = Account.from_key(self.private_key)
        self.logger.info(f"Using account: {self.account.address}")

        flashbot(self.web3, self.account)
        self.logger.info("Flashbots setup completed.")

    def send_private_transaction(self, tx: TxParams) -> Tuple[Optional[str], TxParams]:
        """
        Sends a private transaction via Flashbots with proper signing and payload formatting.

        :param tx: Transaction data dictionary.
        :return: Tuple (tx_hash, tx) if successfully sent, otherwise (None, tx).
        """
        MAX_RETRIES = 3
        RETRY_DELAY = 2  # seconds

        for attempt in range(MAX_RETRIES):
            try:
                # Update gas parameters for better inclusion probability
                if 'maxFeePerGas' not in tx or 'maxPriorityFeePerGas' not in tx:
                    latest_block = self.web3.eth.get_block('latest')
                    base_fee = latest_block.get('baseFeePerGas', self.web3.to_wei(30, 'gwei'))
                    priority_fee = self.web3.eth.max_priority_fee * 2  # Double priority fee
                    tx['maxPriorityFeePerGas'] = priority_fee
                    tx['maxFeePerGas'] = base_fee * 2 + priority_fee  # Double base fee for buffer

                # Sign the transaction
                signed_tx = self.account.sign_transaction(tx)
                signed_tx_hex = signed_tx.rawTransaction.hex()
                self.logger.info(f"Signed transaction: {signed_tx_hex}")

                # Calculate target block numbers
                current_block = self.web3.eth.block_number
                max_block_number = current_block + 1

                # Form JSON-RPC payload with improved inclusion parameters
                payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "eth_sendPrivateTransaction",
                    "params": [{
                        "tx": signed_tx_hex,
                        "maxBlockNumber": max_block_number,
                        "preferences": {
                            "fast": True,
                            "privacy": {
                                "builders": config.BUILDERS
                            },
                            "inclusion": {  # Added inclusion preferences
                                "block": current_block + 1,
                                "maxBlock": max_block_number
                            }
                        }
                    }]
                }

                request_body = json.dumps(payload)
                message = messages.encode_defunct(text=Web3.keccak(text=request_body).hex())
                signature = f"{self.account.address}:{self.account.sign_message(message).signature.hex()}"

                headers = {
                    'Content-Type': 'application/json',
                    'X-Flashbots-Signature': signature
                }

                self.logger.info(f"Sending POST request to Flashbots relay with payload: {request_body}")
                response = requests.post('https://relay.flashbots.net', data=request_body, headers=headers)

                if response.status_code == 200:
                    response_json = response.json()
                    if 'error' not in response_json:
                        tx_hash = self.web3.keccak(signed_tx.rawTransaction).hex()
                        self.logger.info(f"Transaction sent as private: {tx_hash}")
                        return tx_hash, tx

                self.logger.warning(f"Attempt {attempt + 1} failed. Response: {response.text}")
                
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
                    continue

            except requests.exceptions.RequestException as e:
                self.logger.exception(f"Network error while sending transaction: {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
                    continue

            except Exception as e:
                self.logger.exception(f"Exception occurred while sending private transaction: {e}")
                break

        return None, tx

    def monitor_transaction(self, tx_hash: str, timeout: int = 360) -> Optional[TxReceipt]:
        """
        Monitors a transaction until it is confirmed.

        :param tx_hash: Transaction hash to monitor.
        :param timeout: Maximum wait time in seconds.
        :return: Transaction receipt or None if unsuccessful.
        """
        start_time = time.time()
        check_interval = 2  # seconds

        while time.time() - start_time < timeout:
            try:
                receipt = self.web3.eth.get_transaction_receipt(tx_hash)
                if receipt:
                    if receipt.status == 1:
                        self.logger.info(f"Transaction {tx_hash} confirmed in block {receipt.blockNumber}")
                        return receipt
                    else:
                        self.logger.error(f"Transaction {tx_hash} failed")
                        return receipt
            except TransactionNotFound:
                self.logger.debug(f"Transaction {tx_hash} not yet mined. Waiting...")
                time.sleep(check_interval)
                continue
            except Exception as e:
                self.logger.exception(f"Error while waiting for transaction receipt: {e}")
                return None

        self.logger.error(f"Transaction {tx_hash} not found within timeout.")
        return None

# Remaining example usage code stays the same
