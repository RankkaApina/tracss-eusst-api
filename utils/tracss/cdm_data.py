########################################
# CDM DATA CALLS
########################################

#---------------------------------------
# Import Modules
#---------------------------------------

# Python Standard Library
import os
import json
import datetime as dt
from pathlib import Path

# External Dependencies
import polars as pl

# Internal project imports
from utils.api_helpers import *

#---------------------------------------
# Get CDMs
#---------------------------------------


def get_cdms(
    query_params: dict = {},
    datatype: str = 'metadata',
) -> any:

    # Execute call
    data = api_call("tracss", TRACSS_CDM_URL, query_params)

    return data


#---------------------------------------
# Process CDMs to JSON or DF
#---------------------------------------


def tracss_cdms_json(query_params) -> list:

    cdms = get_cdms(query_params)
    query_params["format"] = "json"

    if cdms:
        data_dict = json.loads(cdms)
        cdm_list = data_dict["tracssCdms"]
    else:
        cdm_list = []
        print(
            "There were no CDMs with the given parameters."
        )

    return cdm_list



