########################################
# GET EU EUSST CONFIGS
########################################

#---------------------------------------
# Import Modules
#---------------------------------------

import tomllib
from pathlib import Path

#---------------------------------------
# Get configs
#---------------------------------------

# 1. Get the Project Root
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# 2. Define the path to the TOML inside the configs folder
CONFIG_FILE = BASE_DIR / "configs" / "eusst.toml"

with open(CONFIG_FILE, "rb") as f:
  _config = tomllib.load(f)

# Auth settings
EUSST_CLIENT_ID = _config["auth"]["client_id"]
EUSST_SECRET_KEY = _config["auth"]["client_secret"]
EUSST_USERNAME = _config["auth"]["username"]
EUSST_PASSWORD = _config["auth"]["password"]
EUSST_OAUTH_URL = _config["auth"]["oauth_url"]

# URL
EUSST_CDM_URL = _config["url"]["cdm"]
EUSST_EVENT_URL = _config["url"]["event"]
EUSST_REPORT_URL = _config["url"]["report"]

# Paths
EUSST_TOKEN_CACHE = BASE_DIR / _config["paths"]["cache_file"]
EUSST_JSON_DATA = BASE_DIR / _config["paths"]["data_json"]
EUSST_CSV_DATA = BASE_DIR / _config["paths"]["data_csv"]
EUSST_RAW_DATA = BASE_DIR / _config["paths"]["data_raw"]
