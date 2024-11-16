# src/helpers/private_transaction_sender.py

import json
import requests
import logging
from typing import Optional, Tuple
from eth_account import messages, Account
from eth_account.signers.local import LocalAccount
from web3 import Web3
from web3.types import TxParams, TxReceipt
from flashbots import flashbot
from src.config.settings import Config
from web3.exceptions import TransactionNotFound, ContractLogicError

class PrivateTransactionSender:
    def __init__(self, web3: Optional[Web3] = None, websocket_uri: Optional[str] = None):
        """
        Initializes the PrivateTransactionSender.

        :param web3: Optional, an existing Web3 instance.
        :param websocket_uri: WebSocket URI for connecting to the Ethereum node.
        """
        self._initialize_logger()
        self._initialize_web3(web3, websocket_uri)
        self._initialize_flashbots()

        # Setup logging
        self.logger = logging.getLogger(self.__class__.__name__)
        log_level = logging.DEBUG if Config.DEBUG else logging.INFO
        self.logger.setLevel(log_level)
        ch = logging.StreamHandler()
        ch.setLevel(log_level)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)

        # Load private key
        self.private_key = Config.PRIVATE_KEY
        if not self.private_key:
            self.logger.error("Private key not found in configuration.")
            raise ValueError("Private key not found in configuration.")

        # Initialize Web3
        websocket_uri = websocket_uri or Config.WEBSOCKET_URI
        self.web3 = web3 or Web3(Web3.WebsocketProvider(websocket_uri))
        if not self.web3.is_connected():
            self.logger.error("Unable to connect to the Ethereum node via WebSocket.")
            raise ConnectionError("Unable to connect to the Ethereum node via WebSocket.")
        self.logger.info("Connected to Ethereum node.")

        # Setup Flashbots
        self.account: LocalAccount = Account.from_key(self.private_key)
        flashbot(self.web3, self.account)
        self.logger.info(f"Flashbots initialized for account: {self.account.address}")

    def _initialize_logger(self):
        """Setup logging for the class."""
        self.logger = logging.getLogger(self.__class__.__name__)
        log_level = logging.DEBUG if Config.DEBUG else logging.INFO
        self.logger.setLevel(log_level)
        ch = logging.StreamHandler()
        ch.setLevel(log_level)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)

    def _initialize_web3(self, web3: Optional[Web3], websocket_uri: Optional[str]):
        """Initialize the Web3 connection."""
        websocket_uri = websocket_uri or Config.WEBSOCKET_URI
        self.web3 = web3 or Web3(Web3.WebsocketProvider(websocket_uri))
        if not self.web3.is_connected():
            self.logger.error("Unable to connect to the Ethereum node via WebSocket.")
            raise ConnectionError("Unable to connect to the Ethereum node via WebSocket.")
        self.logger.info("Connected to Ethereum node.")

    def _initialize_flashbots(self):
        """Setup Flashbots with the configured account."""
        self.account: LocalAccount = Account.from_key(Config.PRIVATE_KEY)
        flashbot(self.web3, self.account)
        self.logger.info(f"Flashbots initialized for account: {self.account.address}")

    def send_private_transaction(self, tx: TxParams) -> Tuple[Optional[str], TxParams]:
        """
        Sends a private transaction via Flashbots.

        :param tx: Transaction data dictionary.
        :return: Tuple (tx_hash, tx) if successfully sent, otherwise (None, tx).
        """
        try:
            # Sign the transaction
            signed_tx = self.account.sign_transaction(tx)
            signed_tx_hex = signed_tx.rawTransaction.hex()
            self.logger.info(f"Signed transaction: {signed_tx_hex}")

            # Form JSON-RPC payload
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "eth_sendPrivateTransaction",
                "params": [{
                    "tx": signed_tx_hex,
                    "maxBlockNumber": self.web3.eth.block_number + 1,
                    "preferences": {
                        "fast": True,
                        "privacy": {
                            "builders": Config.BUILDERS
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

            self.logger.info(f"Sending Flashbots transaction payload: {request_body}")
            response = requests.post('https://relay.flashbots.net', data=request_body, headers=headers)

            if response.status_code != 200:
                self.logger.error(f"Flashbots relay error: {response.status_code}, {response.text}")
                return None, tx

            response_json = response.json()
            if 'error' in response_json:
                self.logger.error(f"Flashbots error: {response_json['error']['message']}")

            tx_hash = self.web3.keccak(signed_tx.rawTransaction).hex()
            self.logger.info(f"Transaction sent as private: {tx_hash}")
            return tx_hash, tx

        except requests.exceptions.RequestException as e:
            self.logger.exception(f"Network error: {e}")
            return None, tx
        except Exception as e:
            self.logger.exception(f"Unexpected error: {e}")
            return None, tx

    def monitor_transaction(self, tx_hash: str, timeout: int = 360) -> Optional[TxReceipt]:
        """
        Monitors a transaction until it is confirmed.

        :param tx_hash: Transaction hash to monitor.
        :param timeout: Maximum wait time in seconds.
        :return: Transaction receipt or None if unsuccessful.
        """
        try:
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)
            if receipt.status == 1:
                self.logger.info(f"Transaction {tx_hash} confirmed in block {receipt.blockNumber}")
                return receipt
            else:
                self.logger.error(f"Transaction {tx_hash} failed in block {receipt.blockNumber}")
                return None
        except TransactionNotFound:
            self.logger.error(f"Transaction {tx_hash} not found within timeout.")
            return None
        except Exception as e:
            self.logger.exception(f"Error monitoring transaction: {e}")
            return None


if __name__ == "__main__":
    try:
        private_tx_sender = PrivateTransactionSender()
        web3, account = private_tx_sender.web3, private_tx_sender.account

        # Example: Sending an approve transaction
        token_address = '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'  # USDC
        spender_address = '0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D'  # Uniswap V2 Router
        amount = web3.to_wei(1, 'ether')

        token_abi = [{
            "constant": False,
            "inputs": [
                {"name": "_spender", "type": "address"},
                {"name": "_value", "type": "uint256"}
            ],
            "name": "approve",
            "outputs": [{"name": "", "type": "bool"}],
            "type": "function"
        }]

        token_contract = web3.eth.contract(address=web3.to_checksum_address(token_address), abi=token_abi)

        base_fee = web3.eth.get_block('latest').get('baseFeePerGas', web3.to_wei(30, 'gwei'))
        priority_fee = web3.eth.max_priority_fee
        nonce = web3.eth.get_transaction_count(account.address)

        tx_params = {
            'from': account.address,
            'nonce': nonce,
            'maxPriorityFeePerGas': priority_fee,
            'maxFeePerGas': base_fee + priority_fee,
            'chainId': web3.eth.chain_id,
            'type': 2
        }

        gas = token_contract.functions.approve(spender_address, amount).estimate_gas({'from': account.address})
        tx_params['gas'] = gas

        tx = token_contract.functions.approve(spender_address, amount).build_transaction(tx_params)
        tx_hash, _ = private_tx_sender.send_private_transaction(tx)

        if tx_hash:
            receipt = private_tx_sender.monitor_transaction(tx_hash)
            if receipt:
                logging.info(f"Transaction confirmed in block {receipt.blockNumber}")
    except Exception as e:
        logging.exception(f"Error: {e}")