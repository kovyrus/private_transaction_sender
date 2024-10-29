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
                            "builders": config.BUILDERS  # Assumes BUILDERS is defined in configuration
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

            if response.status_code != 200:
                self.logger.error(f"Error in Flashbots response: {response.status_code}, {response.text}")
                return None, tx

            response_json = response.json()
            if 'error' in response_json:
                self.logger.error(f"Flashbots error: {response_json['error']}")
                return None, tx

            tx_hash = self.web3.keccak(signed_tx.rawTransaction).hex()
            self.logger.info(f"Transaction sent as private: {tx_hash}")
            return tx_hash, tx

        except requests.exceptions.RequestException as e:
            self.logger.exception(f"Network error while sending transaction: {e}")
            return None, tx
        except Exception as e:
            self.logger.exception(f"Exception occurred while sending private transaction: {e}")
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
            self.logger.info(f"Transaction {tx_hash} confirmed in block {receipt.blockNumber}")
            return receipt
        except TransactionNotFound:
            self.logger.error(f"Transaction {tx_hash} not found within timeout.")
            return None
        except Exception as e:
            self.logger.exception(f"Error while waiting for transaction receipt: {e}")
            return None

# Example usage
# python3 -m src.helpers.private_transaction_sender
if __name__ == "__main__":
    import sys
    from web3.exceptions import ContractLogicError

    # Set up basic configuration for the main log based on DEBUG setting
    log_level = logging.DEBUG if config.DEBUG else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    try:
        # Initialize PrivateTransactionSender
        private_tx_sender = PrivateTransactionSender()
        web3, account = private_tx_sender.web3, private_tx_sender.account

        # Example: Sending an approve transaction
        token_address = '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48' # USDC
        spender_address = '0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D' # Uniswap V2 Router
        amount = web3.to_wei(1, 'ether')  # Amount to approve

        # Validate addresses
        if not web3.is_address(token_address) or not web3.is_address(spender_address):
            logging.error("Invalid token or spender address.")
            sys.exit(1)
        token_address = web3.to_checksum_address(token_address)
        spender_address = web3.to_checksum_address(spender_address)

        # ABI for the approve function (ERC-20 standard)
        token_abi = [
            {
                "constant": False,
                "inputs": [
                    {"name": "_spender", "type": "address"},
                    {"name": "_value", "type": "uint256"}
                ],
                "name": "approve",
                "outputs": [{"name": "", "type": "bool"}],
                "type": "function"
            }
        ]

        # Load token contract
        token_contract = web3.eth.contract(address=token_address, abi=token_abi)

        # Get current network fees
        latest_block = web3.eth.get_block('latest')
        base_fee_per_gas = latest_block.get('baseFeePerGas', web3.to_wei(30, 'gwei'))  # Default value
        self_priority_fee = web3.eth.max_priority_fee  # Current maxPriorityFeePerGas value
        max_priority_fee_per_gas = self_priority_fee
        max_fee_per_gas = base_fee_per_gas + max_priority_fee_per_gas

        logging.debug(f"Base fee per gas: {base_fee_per_gas}")
        logging.debug(f"Max priority fee per gas: {max_priority_fee_per_gas}")
        logging.debug(f"Max fee per gas: {max_fee_per_gas}")

        # Build approve transaction
        nonce = web3.eth.get_transaction_count(account.address, 'pending')
        tx_params = {
            'from': account.address,
            'nonce': nonce,
            'maxPriorityFeePerGas': max_priority_fee_per_gas,
            'maxFeePerGas': max_fee_per_gas,
            'chainId': web3.eth.chain_id,
            'type': 2
        }

        # Estimate gas for the transaction
        try:
            gas_estimate = token_contract.functions.approve(spender_address, amount).estimate_gas({
                'from': account.address,
            })
            tx_params['gas'] = gas_estimate
            logging.debug(f"Estimated gas: {gas_estimate}")
        except ContractLogicError as e:
            logging.error(f"Contract logic error during gas estimation: {e}")
            sys.exit(1)
        except Exception as e:
            logging.error(f"Failed to estimate gas: {e}")
            sys.exit(1)

        # Build approve transaction
        tx = token_contract.functions.approve(spender_address, amount).build_transaction(tx_params)

        logging.info(f"Built approve transaction: {tx}")

        # Send transaction as private
        tx_hash, sent_tx = private_tx_sender.send_private_transaction(tx)

        if tx_hash:
            logging.info(f"Transaction sent successfully: https://etherscan.io/tx/{tx_hash}")

            # Monitor transaction
            receipt = private_tx_sender.monitor_transaction(tx_hash)
            if receipt:
                logging.info(f"Transaction confirmed in block {receipt.blockNumber}")
            else:
                logging.error("Failed to confirm transaction.")
        else:
            logging.error("Failed to send transaction.")

    except Exception as e:
        logging.exception(f"An unexpected error occurred: {e}")
        sys.exit(1)
