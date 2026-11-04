########################################
# Get TraCSS Catalog
########################################

#---------------------------------------
# Import Modules
#---------------------------------------

# Python Standard Library
import argparse
import os
import sys
import datetime as dt

# External Dependencies
import polars as pl

# Internal project imports
from utils.tracss.config import *
from utils.tracss.cat_data import *

#---------------------------------------
# Main function
#---------------------------------------


def main():
  parser = argparse.ArgumentParser(
    description="TraCSS Catalog Fetcher"
  )
  parser.add_argument(
    '-p',
    '--params',
    nargs='+',
    help=
    'API params as key=value pairs (e.g., -p noradId=123 page=0)'
  )
  args = parser.parse_args()

  # Parse the -p strings into the dictionary
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

  if not query_params:
    query_params = {
      'objectType': 'payload'
    }

  tod = dt.datetime.today().strftime('%Y-%m-%d')
  json_file = f"TRACSSCAT_{tod}.json"
  json_path = os.path.join(TRACSS_JSON_DATA, json_file)

  csv_file = f"TRACSSCAT_{tod}.csv"
  csv_path = os.path.join(TRACSS_CSV_DATA, csv_file)

  print(f"Fetching TraCSS catalog")
  catalog = get_tracss_catalog(
    query_params,
  )

  if catalog:
    with open(json_path, "w") as f:
      json.dump(catalog, f, indent=4)

    if isinstance(catalog, list):
      df = pl.DataFrame(catalog, infer_schema_length=None)
    else:
      df = pl.DataFrame(
        [catalog], infer_schema_length=None
      )    # Wraps single dict response in a list

    if "noradId" in df.columns:
      df = (
        df.with_columns(
        pl.col("noradId").cast(pl.Int64, strict=False)
        ).filter(pl.col("noradId") < 7996000)
      )

    list_cols = [
      col for col, dtype in df.schema.items()
      if dtype.base_type() == pl.List
    ]
    df_flat = df.with_columns(
      [
      pl.col(col).cast(pl.List(pl.String)).list.join(", ")
      for col in list_cols
      ]
    )

    df_flat.write_csv(csv_path)
  else:
    print(
      "There were no catalog items with the given parameters."
    )


################ MAIN #################

if __name__ == "__main__":
  main()
