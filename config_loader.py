"""
Configuration loader with environment variable override support
"""
import json
import os

def load_config(config_file=None):
    """Load configuration with environment variable overrides"""
    # Determine config file
    if config_file is None:
        config_file = os.environ.get('CONFIG_FILE', 'config.json')
    
    # Load base config
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    # Add database configuration with environment overrides
    config['database'] = {
        'host': os.environ.get('MYSQL_HOST', config.get('database', {}).get('host', 'localhost')),
        'port': int(os.environ.get('MYSQL_PORT', config.get('database', {}).get('port', 3306))),
        'user': os.environ.get('MYSQL_USER', config.get('database', {}).get('user', 'cwt_user')),
        'password': os.environ.get('MYSQL_PASSWORD', config.get('database', {}).get('password', '')),
        'name': os.environ.get('MYSQL_DATABASE', config.get('database', {}).get('name', 'cryptowatch_bot'))
    }
    
    # Override API base URL based on environment
    if os.environ.get('MYSQL_HOST') == 'mysql':  # Running in Docker
        config['api_base_url'] = 'http://app:5173/api'
    elif 'api_base_url' not in config:
        # Default to production if not specified
        config['api_base_url'] = 'https://example.com/api'
    
    return config