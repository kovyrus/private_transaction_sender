import unittest
from unittest.mock import patch, MagicMock
from eth_account import Account
from src.helpers.private_transaction_sender import PrivateTransactionSender

class TestPrivateTransactionSender(unittest.TestCase):

    def setUp(self):
        self.mock_private_key = "0x" + "a" * 64  
        self.sender = PrivateTransactionSender()
        
        patcher = patch.object(self.sender, 'private_key', self.mock_private_key)
        self.addCleanup(patcher.stop)
        self.mock_private_key_patch = patcher.start()

    @patch('src.helpers.private_transaction_sender.Web3')
    def test_initialization(self, mock_web3):
        mock_instance = MagicMock()
        mock_web3.return_value = mock_instance
        
        self.sender = PrivateTransactionSender()
        self.assertEqual(self.sender.account.address, Account.from_key(self.mock_private_key).address)

    @patch('src.helpers.private_transaction_sender.Web3')
    def test_monitor_transaction_failure(self, mock_web3):
        mock_instance = MagicMock()
        mock_web3.return_value = mock_instance
        
        mock_instance.eth.get_transaction_receipt.return_value = {"status": 0}
        
        with self.assertRaises(Exception) as context:
            self.sender.monitor_transaction("mock_tx_hash")
        self.assertIn("Transaction failed", str(context.exception))

    @patch('src.helpers.private_transaction_sender.Web3')
    def test_monitor_transaction_success(self, mock_web3):
        mock_instance = MagicMock()
        mock_web3.return_value = mock_instance
        
        mock_instance.eth.get_transaction_receipt.return_value = {"status": 1}
        
        receipt = self.sender.monitor_transaction("mock_tx_hash")
        self.assertEqual(receipt["status"], 1)

    @patch('src.helpers.private_transaction_sender.Web3')
    def test_send_private_transaction_failure(self, mock_web3):
        mock_instance = MagicMock()
        mock_web3.return_value = mock_instance
        mock_instance.eth.send_raw_transaction.side_effect = Exception("Sending failed")
        
        with self.assertRaises(Exception) as context:
            self.sender.send_private_transaction("mock_signed_tx")
        self.assertIn("Sending failed", str(context.exception))

    @patch('src.helpers.private_transaction_sender.Web3')
    def test_send_private_transaction_success(self, mock_web3):
        mock_instance = MagicMock()
        mock_web3.return_value = mock_instance
        mock_instance.eth.send_raw_transaction.return_value = "mock_tx_hash"
        
        tx_hash = self.sender.send_private_transaction("mock_signed_tx")
        self.assertEqual(tx_hash, "mock_tx_hash")

if __name__ == "__main__":
    unittest.main()
