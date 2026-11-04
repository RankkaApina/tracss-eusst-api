########################################
# Get CDMs / OCMs from bulkdata
########################################

#---------------------------------------
# Import Modules
#---------------------------------------

# Python Standard Library

import datetime as dt

# Internal project imports
from utils.tracss.bulk_data import bulkDownloader, bulkTransformer, logger

################ MAIN #################

#idfile = "norad_ids.txt"
prefix = "TRACSS_CDM"

# Define your start and end dates
start_date = dt.datetime(2026, 7, 15)
end_date = dt.datetime(2026, 7, 15)

current_date = start_date

#with open(f"configs/{idfile}", "r") as file:
#  sat_list = file.read().splitlines()
#norad_ids = ",".join(sat_list)

current_date = start_date

# Loop backwards until we pass the end_date
while current_date <= end_date:
  # Create fresh objects with a clean state
  cdm_downloader = bulkDownloader(datatype='cdm')
  cdm_transformer = bulkTransformer(datatype='cdm')

  # Extract year, month, and day parameters dynamically if needed
  year = current_date.year
  month = current_date.month
  day = current_date.day

  # Calculate the offsets for the parameters
  prev_date = current_date - dt.timedelta(days=1)
  next_date = current_date + dt.timedelta(days=1)

  start_utc = f"{prev_date.strftime('%Y-%m-%d')}T23:59:59Z"
  end_utc = f"{next_date.strftime('%Y-%m-%d')}T00:00:00Z"

  # Build variables
  cdm_foldername = f"{prefix}_{current_date.strftime('%Y-%m-%d')}"

  cdm_params = {
    #    "object1ObjectDesignator": norad_ids,
    "creationDate": f"{start_utc}...{end_utc}",
  }

  logger.info(
    f"Starting API pull | Date: {current_date.strftime('%Y-%m-%d')} | Folder: {cdm_foldername}"
  )

  # Pull data from bulkdata
  cdm_downloader.run(
    folder=cdm_foldername, query_params=cdm_params
  )
  # Build list of jsons from raw data
  cdm_transformer.run(folder=cdm_foldername, fmt="json")

  # Step forward by 1 day
  current_date += dt.timedelta(days=1)
