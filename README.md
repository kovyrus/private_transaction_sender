# Private Transaction Sender

This project facilitates the sending of private transactions via the Flashbots API on the Ethereum network. The private transaction sender enables secure, private transaction submission, with support for major DeFi protocols. It is configured for flexibility and ease of use with environment-based settings.

## Flashbot Docs
https://docs.flashbots.net/flashbots-auction/advanced/rpc-endpoint#eth_sendprivatetransaction

## File Structure

The project is organized as follows:

```
private_transaction_sender/
├── src/
│   ├── config/
│   │   ├── __init__.py                # Config package initializer
│   │   └── settings.py                # Configuration settings for different environments
│   ├── helpers/
│   │   └── private_transaction_sender.py # Main script for sending private transactions
│   ├── models/                        # (Optional) Place to store any data models if needed
│   └── utils/                         # (Optional) Utilities for additional helper functions
├── .env.example                       # Example environment variable file
├── requirements.txt                   # List of dependencies
└── README.md                          # Project documentation
```

### Key Files

- **`src/config/settings.py`**: Contains the configuration settings, including environment variables and options for `development` and `production`.
- **`src/helpers/private_transaction_sender.py`**: Core module for sending private transactions. It leverages the Web3 and Flashbots libraries to securely submit transactions.
- **`.env.example`**: Template file for setting environment variables. Copy this file to `.env` and configure with your private key and environment settings.
- **`requirements.txt`**: Lists the required dependencies to run the project.

## Setup

### 1. Clone the repository:
```bash
git clone https://github.com/sergeychernyakov/private_transaction_sender.git
```

### 2. Create a virtual environment:
```bash
python3 -m venv venv
```

### 3. Activate the virtual environment:
- **On Linux/MacOS**:
  ```bash
  source venv/bin/activate
  ```
- **On Windows**:
  ```bash
  venv\Scripts\activate
  ```

### 4. Install the required dependencies:
Install packages listed in `requirements.txt`, including essential libraries for Web3 interaction, Flashbots API, and environment variable management.
```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables:
Copy the example `.env` file and configure it with your private Ethereum key and environment settings.
```bash
cp .env.example .env
```
Update `.env` with the following variables:
- **`PRIVATE_KEY`**: Your private key for signing transactions.
- **`APP_ENV`**: Set to `development` or `production` depending on the environment.

### 6. Export Installed Packages (Optional):
If you add new dependencies, update `requirements.txt` by running:
```bash
pip freeze > requirements.txt
```

### 7. Run the Script
To send a private transaction, execute the `private_transaction_sender` script as follows:
```bash
python3 -m src.helpers.private_transaction_sender
```

### Example Environment File (`.env.example`)

```plaintext
# .env.example
# Keys
PRIVATE_KEY='your_private_key_here'
APP_ENV='development'
```

Ensure that your `PRIVATE_KEY` is kept secure and not exposed publicly.

## Requirements

The project requires various dependencies, which are listed in the `requirements.txt`. Key libraries include:
- **`web3`**: For interacting with the Ethereum network.
- **`eth-account`**: Handles account and transaction signing.
- **`flashbots`**: API for private transaction submission.
- **`python-dotenv`**: For managing environment variables from `.env`.

For the full list of dependencies, refer to the [`requirements.txt`](requirements.txt) file.

## Author

Sergey Chernyakov  
Telegram: [@AIBotsTech](https://t.me/AIBotsTech)
