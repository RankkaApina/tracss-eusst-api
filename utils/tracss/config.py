########################################
# GET TraCSS CONFIGS
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
CONFIG_FILE = BASE_DIR / "configs" / "tracss.toml"

with open(CONFIG_FILE, "rb") as f:
    _config = tomllib.load(f)

# Auth settings
TRACSS_CLIENT_ID = _config["auth"]["client_id"]
TRACSS_SECRET_KEY = _config["auth"]["secret_key"]
TRACSS_OAUTH_URL = _config["auth"]["oauth_url"]

# API params
TRACSS_CDM_URL = _config["api"]["cdm_url"]
TRACSS_CAT_URL = _config["api"]["cat_url"]
TRACSS_BULK_CDM_URL = _config["api"]["bulkcdm_url"]
TRACSS_BULK_OCM_URL = _config["api"]["bulkocm_url"]
# For bulk CDM/OCM calls
TRACSS_CDM_MAX_WORKERS = _config["api"]["cdm_max_workers"]
TRACSS_OCM_MAX_WORKERS = _config["api"]["ocm_max_workers"]
TRACSS_CDM_PAGE_SIZE = _config["api"]["cdm_page_size"]
TRACSS_OCM_PAGE_SIZE = _config["api"]["ocm_page_size"]

# Paths
TRACSS_TOKEN_CACHE = BASE_DIR / _config["paths"]["cache_file"]
TRACSS_JSON_DATA = BASE_DIR / _config["paths"]["data_json"]
TRACSS_CSV_DATA = BASE_DIR / _config["paths"]["data_csv"]
TRACSS_RAW_DATA = BASE_DIR / _config["paths"]["data_raw"]