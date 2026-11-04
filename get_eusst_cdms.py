########################################
# Get EUSST CDMs
########################################

#---------------------------------------
# Import Modules
#---------------------------------------

# Python Standard Library
import argparse
import os
import sys
import json
import datetime as dt

# External Dependencies
import polars as pl

# Internal project imports
from utils.eusst.cdm_data import *

#---------------------------------------
# Main function
#---------------------------------------

def main():
    parser = argparse.ArgumentParser(description="EU SST CDM Fetcher")
    parser.add_argument(
        '-o',
        '--output',
        help=''
    )
    parser.add_argument(
        '-p',
        '--params',
        nargs='+',
        help='API params as key=value pairs (e.g., -p noradId=123 page=0)'
    )
    args = parser.parse_args()

    query_params = {}
    if args.params:
        for item in args.params:
            if '=' in item:
                key, value = item.split('=', 1)
                query_params[key] = value
            else:
                print(
                    f"Warning: Skipping invalid parameter format '{item}'. Use key=value."
                )

    cdm_filename = f"EUSST_CDM_{args.output}"
    cdm_jsonfile = f"{cdm_filename}.json"
    cdm_output = os.path.join(EUSST_JSON_DATA, cdm_jsonfile)

    cdm_json = get_eusst_data("report",query_params)


    if cdm_json:
        with open(cdm_output, "w") as f:
            json.dump(cdm_json, f, indent=4)
        logger.info(f"Success! Processed and saved to {cdm_output}")


################ MAIN #################

if __name__ == "__main__":
    main()

# Example:
# python get_eusst_cdms.py -o "2026-06-23" -p '$filter=creationDate ge 2026-05-15 and creationDate le 2026-06-23' &