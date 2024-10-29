# src/config/settings.py

import os
from dotenv import load_dotenv
from dataclasses import dataclass

load_dotenv()

@dataclass
class Config:
    """Base configuration class."""
    DEBUG: bool = False
    TESTING: bool = True
    WEBSOCKET_URI="wss://mainnet.infura.io/ws/v3/1b5e6acd0c874a58bbc6d6ddb1b516bd"
    PRIVATE_KEY = os.getenv('PRIVATE_KEY')
    APP_ENV = os.getenv('APP_ENV')
    BUILDERS = [
        "beaverbuild.org", "Titan", "flashbots", "f1b.io", "rsync", "builder0x69",
        "EigenPhi", "boba-builder", "Gambit Labs", "payload",
        "Loki", "BuildAI", "JetBuilder", "tbuilder", "penguinbuild",
        "bobthebuilder", "BTCS", "bloXroute"
    ]

@dataclass
class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG: bool = False
    TESTING: bool = True

@dataclass
class ProductionConfig(Config):
    """Production configuration."""
    DEBUG: bool = False
    TESTING: bool = False
