########################################
# TraCSS Catalog from Metadata
########################################

#---------------------------------------
# Import Modules
#---------------------------------------

# Standard Library
import json
import os
from typing import Union, List

# External Dependencies
import pandas as pd

# Internal project imports
from utils.api_helpers import *
from utils.tracss.config import *

#---------------------------------------
# Get TraCSS Cat from Metadata
#---------------------------------------


def get_tracss_catalog(
    query_params: dict[str, str], 
) -> pd.DataFrame:
    page, size = 0, 5000
    all_records = []
    while True:
        query_params['page'] = str(page)

        data = api_call("tracss", TRACSS_CAT_URL, query_params)
        if not data:
            break

        json_records = json.loads(data)
        if not json_records:
            break

        all_records.extend(json_records)  # Add records to the list

        if len(json_records) >= size:
            page += 1
        else:
            break
    return all_records




