# src/config/__init__.py

import os
from src.config.settings import DevelopmentConfig, ProductionConfig, Config
from dotenv import load_dotenv

load_dotenv()

def get_config() -> Config:
    """
    Retrieves the configuration settings based on the environment.

    :return: An instance of Config (DevelopmentConfig or ProductionConfig).
    """
    env = os.getenv('APP_ENV', 'development').lower()  # Use 'development' as the default environment
    if env == 'production':
        return ProductionConfig()
    else:
        return DevelopmentConfig()

# Usage example:
config: Config = get_config()
