import configparser
import os
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default configuration values
DEFAULT_CONFIG = {
    'security': {
        'custom_ca_path': None
    }
}

def load_config(file_path='config/custom_config.ini', default_config=DEFAULT_CONFIG):
    # Initialize the ConfigParser
    config = configparser.ConfigParser()

    # Check if the configuration file exists
    if not os.path.exists(file_path):
        logger.warning(f"Configuration file {file_path} not found. Using default values.")
        return default_config

    # Read the configuration file
    config.read(file_path)

    # Load configuration values with fallbacks to default
    loaded_config = {}

    for section, defaults in default_config.items():
        loaded_config[section] = {}
        for key, default_value in defaults.items():
            try:
                value = config.get(section, key)
                # Convert to appropriate type if necessary
                if isinstance(default_value, bool):
                    value = config.getboolean(section, key)
                elif isinstance(default_value, int):
                    value = config.getint(section, key)
                loaded_config[section][key] = value
            except (configparser.NoSectionError, configparser.NoOptionError) as e:
                logger.warning(f"Missing {section}.{key} in config. Using default: {default_value}")
                loaded_config[section][key] = default_value

    return loaded_config

