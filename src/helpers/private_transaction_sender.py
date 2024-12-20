import json
import requests
import logging
from typing import Optional, Tuple, Dict, Any
from eth_account import messages, Account
from eth_account.signers.local import LocalAccount
from web3 import Web3
from web3.types import TxParams, TxReceipt
from web3.exceptions import TransactionNotFound
from src.config import config

class PrivateTransactionSender:
    FLASHBOTS_RELAY_URL = 'https://relay.flashbots.net'
    MAX_RETRIES = 3
    BACKOFF_TIME = 2  # seconds

    def __init__(self, web3: Optional[Web3] = None, websocket_uri: Optional[str] = None):
        self.logger = self._setup_logging()
        self.private_key = self._load_private_key()
        self.web3 = self._initialize_web3(web3, websocket_uri)
        self.account: LocalAccount = Account.from_key(self.private_key)
        self.logger.info(f"Initialized with account: {self.account.address}")

    def _setup_logging(self) -> logging.Logger:
        logger = logging.getLogger(self.__class__.__name__)
        log_level = logging.DEBUG if config.DEBUG else logging.INFO
        logger.setLevel(log_level)
        
        if not logger.handlers:
            ch = logging.StreamHandler()
            ch.setLevel(log_level)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            ch.setFormatter(formatter)
            logger.addHandler(ch)
        
        return logger

    def _load_private_key(self) -> str:
        if not config.PRIVATE_KEY:
            raise ValueError("Private key not found in configuration")
        return config.PRIVATE_KEY

    def _initialize_web3(self, web3: Optional[Web3], websocket_uri: Optional[str]) -> Web3:
        if web3:
            return web3
        
        websocket_uri = websocket_uri or config.WEBSOCKET_URI
        web3 = Web3(Web3.WebsocketProvider(websocket_uri))
        
        if not web3.is_connected():
            raise ConnectionError("Unable to connect to Ethereum node via WebSocket")
            
        return web3

    def _prepare_flashbots_request(self, tx: TxParams) -> Tuple[Dict[str, Any], str]:
        signed_tx = self.account.sign_transaction(tx)
        signed_tx_hex = signed_tx.rawTransaction.hex()

        # Calculate target block numbers
        current_block = self.web3.eth.block_number
        max_block_number = current_block + 1

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
                    "inclusion": {
                        "block": current_block + 1,
                        "maxBlock": max_block_number
                    }
                }
            }]
        }

        request_body = json.dumps(payload)
        message = messages.encode_defunct(text=Web3.keccak(text=request_body).hex())
        signature = f"{self.account.address}:{self.account.sign_message(message).signature.hex()}"

        return payload, signature

    def _calculate_gas_parameters(self) -> Dict[str, int]:
        latest_block = self.web3.eth.get_block('latest')
        base_fee = latest_block.get('baseFeePerGas', self.web3.to_wei(30, 'gwei'))
        
        # Increase priority fee for better inclusion probability
        priority_fee = self.web3.eth.max_priority_fee * 2
        max_fee = base_fee * 2 + priority_fee  # Double base fee for buffer

        return {
            'maxPriorityFeePerGas': priority_fee,
            'maxFeePerGas': max_fee
        }

    def send_private_transaction(self, tx: TxParams) -> Tuple[Optional[str], TxParams]:
        """
        Sends a private transaction via Flashbots with improved inclusion probability.
        """
        try:
            # Update gas parameters for better inclusion
            gas_params = self._calculate_gas_parameters()
            tx.update(gas_params)

            payload, signature = self._prepare_flashbots_request(tx)
            
            headers = {
                'Content-Type': 'application/json',
                'X-Flashbots-Signature': signature
            }

            for attempt in range(self.MAX_RETRIES):
                try:
                    response = requests.post(
                        self.FLASHBOTS_RELAY_URL,
                        json=payload,
                        headers=headers,
                        timeout=10
                    )
                    
                    if response.status_code == 200:
                        response_data = response.json()
                        if 'result' in response_data:
                            tx_hash = self.web3.keccak(
                                self.account.sign_transaction(tx).rawTransaction
                            ).hex()
                            self.logger.info(f"Transaction sent successfully: {tx_hash}")
                            return tx_hash, tx
                    
                    self.logger.warning(
                        f"Attempt {attempt + 1} failed. Status: {response.status_code}, "
                        f"Response: {response.text}"
                    )
                    
                except requests.exceptions.RequestException as e:
                    self.logger.warning(f"Request failed on attempt {attempt + 1}: {e}")
                
                if attempt < self.MAX_RETRIES - 1:
                    self.logger.info(f"Retrying in {self.BACKOFF_TIME} seconds...")
                    time.sleep(self.BACKOFF_TIME)
            
            return None, tx

        except Exception as e:
            self.logger.exception(f"Failed to send private transaction: {e}")
            return None, tx

    def monitor_transaction(self, tx_hash: str, timeout: int = 360) -> Optional[TxReceipt]:
        """
        Monitors transaction status with improved error handling and logging.
        """
        start_time = time.time()
        check_interval = 2  # seconds

        while time.time() - start_time < timeout:
            try:
                receipt = self.web3.eth.get_transaction_receipt(tx_hash)
                if receipt:
                    if receipt.status == 1:
                        self.logger.info(
                            f"Transaction {tx_hash} confirmed in block {receipt.blockNumber}. "
                            f"Gas used: {receipt.gasUsed}"
                        )
                        return receipt
                    else:
                        self.logger.error(f"Transaction {tx_hash} failed. Receipt: {receipt}")
                        return receipt

            except TransactionNotFound:
                self.logger.debug(f"Transaction {tx_hash} not yet mined. Waiting...")
                time.sleep(check_interval)
                continue
                
            except Exception as e:
                self.logger.error(f"Error checking transaction status: {e}")
                return None

        self.logger.error(f"Transaction {tx_hash} not confirmed within {timeout} seconds")
        return None
