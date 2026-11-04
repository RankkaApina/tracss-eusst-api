########################################
# Get TraCSS CDMs
########################################

#---------------------------------------
# Import Modules
#---------------------------------------

# Python Standard Library
import os
import json
import datetime as dt

# External Dependencies
import polars as pl

# Internal project imports
from utils.tracss.cdm_data import *

#---------------------------------------
# Main function
#---------------------------------------


def json_cdms(query_params):

  cdms = get_cdms(query_params)

  tod = dt.datetime.today().strftime('%Y-%m-%d')
  output_file = f"{tod}_tracss-cdms.json"
  output_path = os.path.join(TRACSS_JSON_DATA, output_file)
  os.makedirs(TRACSS_JSON_DATA, exist_ok=True)

  if cdms:
    data_dict = json.loads(cdms)
    cdm_list = data_dict["tracssCdms"]
    with open(output_path, "w") as f:
      json.dump(cdm_list, f, indent=4)
  else:
    print("There were no CDMs with the given parameters.")


def df_cdms(cdm_list: dict):
  cdm_df = pl.DataFrame(cdm_list)

  tod = dt.datetime.today().strftime('%Y-%m-%d')
  csv_file = f"{tod}_tracss-cdms.csv"
  csv_output = os.path.join(TRACSS_CSV_DATA, csv_file)

  # Save dataframe to CSV
  cdm_df.write_csv(csv_output)
  print(f"Success! Processed and saved to {csv_output}")


################ MAIN #################

if __name__ == "__main__":

  query_params = {}

  json_cdms(query_params)

  json_file = "2026-06-05_tracss-cdms.json"
  json_path = os.path.join(TRACSS_JSON_DATA, json_file)

  with open(json_path, "r") as f:
    cdm_list = json.load(f)

  df_cdms(cdm_list)
