from datetime import datetime, timedelta
import csv
from functools import lru_cache
import os
from requests import get
import sys
from urllib.request import urlretrieve

import dateparser

from utils import get_all_assets

# avoid _csv.Error: field larger than field limit (131072)
csv.field_size_limit(sys.maxsize)

@lru_cache(maxsize=8192)
def parse_date(str):
  return dateparser.parse(str, languages=['en'], settings={
    'STRICT_PARSING': False, # allow dates like Jan 1990
    'TIMEZONE': '+0000'
  })

skiplist = []

# grab all assets
limit = 10000

counts = { "active": 0, "inactive": 0 }

# set threshold to be 30 days previous
threshold = datetime.now() - timedelta(days = 30)
threshold_timestamp = threshold.timestamp()
  
assets = get_all_assets(limit)

# write output csv
fieldnames = ['id', 'name', 'createdAt', 'dataUpdatedAt', 'indexUpdatedAt', 'metadataUpdatedAt', 'rowsUpdatedAt', 'updatedAt', 'mostRecentFound']
out_filepath = "./results/dataset_dates.csv"
with open(out_filepath, "w") as outfile:
  csv.DictWriter(outfile, fieldnames=fieldnames).writeheader()
    
for base, asset in assets:
  id = asset['id']
  name = asset['name']

  print(f'\nchecking {id} "{name}"')

  if id in skiplist:
    print(f"skipping {id} because it's in skiplist")
    continue

  # skip community assets
  if asset['provenance'] != "OFFICIAL":
    print(f'skipping unofficial asset {id} "{name}"')
    continue
  
  metadata = get(f"{base}/api/views/{id}.json").json()

  if "error" in metadata:
    if "message" in metadata:
      print(metadata["message"])
      continue
  
  if metadata['assetType'] != "dataset":
    print(f"skipping {id} because it's not a dataset")
    continue
  
  columns = metadata['columns']
  
  date_columns = [column for column in columns if column['dataTypeName'] == "calendar_date"]
  
  if len(date_columns) == 0:
    print(f"skipping {id} because it doesn't have any date columns")
    continue

  print(f"{id} date_columns:", ",".join([col['name'] for col in date_columns]))
      
  # download data if not currently in folder
  download_path = f"./data/{id}.csv"
  if not os.path.isfile(download_path):      
    download_url = f"{base}/api/views/{id}/rows.csv?accessType=DOWNLOAD"
    print(f'downloading {id} "{name}"')
    urlretrieve(download_url, download_path)
    print(f'downloaded {id} "{name}"')
  else:
    print(f'already downloaded {id} "{name}"')

  most_recent = None
  
  with open(download_path) as f:
    for irow, row in enumerate(csv.DictReader(f)):
      # print("irow:", irow)

      for col in date_columns:
        # print("col:", col)
        fieldName = col['fieldName']
        name = col['name']
        datestr = row[name]

        # skipping blank cells
        if datestr == '': continue

        # print("datestr:", datestr)
        dt = parse_date(datestr)
        if dt is None:
          print("row:", row)
          print(f"failed to parse '{datestr}'")
          raise Exception(f"failed to parse '{datestr}'")
        # print("dt:", dt)

        timestamp = dt.timestamp()
        # print("timestamp:", timestamp)
        if most_recent is None or timestamp > most_recent['timestamp']:
          most_recent = {
            "str": datestr,
            "datetime": dt,
            "timestamp": timestamp,
            "row": row
          }

    print("most_recent:", most_recent)

    # sometimes this can happen if there's a data quality issue,
    # and the whole column or dataset is blank
    if most_recent is None: continue

    print("threshold_timestamp:", threshold_timestamp)
    inactive = most_recent['timestamp'] < threshold_timestamp
    if inactive:
      print("dataset doesn't have any data past the threshold of " + str(threshold))

    status = "inactive" if inactive else "active"
    print(f"{id} status: {status}")

    counts[status] += 1
    print("current counts:", counts)

  with open(out_filepath, "a") as outfile:
    csv.DictWriter(outfile, fieldnames=fieldnames).writerow({
      "id": asset['id'],
      "name": name,
      "createdAt": asset['createdAt'],
      "dataUpdatedAt": asset['dataUpdatedAt'],
      "indexUpdatedAt": asset["indexUpdatedAt"] if "indexUpdatedAt" in asset else "",
      "metadataUpdatedAt": asset['metadataUpdatedAt'],
      "rowsUpdatedAt": asset["rowsUpdatedAt"] if "rowsUpdatedAt" in asset else "",
      "updatedAt": asset['updatedAt'],
      "mostRecentFound": most_recent['datetime'].isoformat()
    })

  print("total status counts:", counts)
