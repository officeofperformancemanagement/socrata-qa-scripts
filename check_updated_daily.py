from datetime import datetime, timedelta
from collections import defaultdict
import csv
from functools import lru_cache
import os
from requests import get
import sys
from urllib.request import urlretrieve

import dateparser

from utils import get_all_assets, median_diff_dates

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

# set threshold to be 3 days to account for weekends
threshold = datetime.now() - timedelta(days = 3)
threshold_timestamp = threshold.timestamp()
  
assets = get_all_assets(limit)

# write output csv
fieldnames = ['id', 'name', 'dataUpdatedAt', 'updatedAt', 'mostRecentFound', 'frequency', 'recentlyUpdated', 'medianDaysBetweenEntries']
out_filepath = "./results/datasets_updated_daily.csv"
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
  
  # sleep(1)

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
  
  temporal = len(date_columns) > 0

  frequency = metadata.get("metadata", {}).get("custom_fields", {}).get("Internal", {}).get("How often are data values updated?", None)
  print("frequency:", frequency)

  if frequency is None or frequency.lower().strip() != 'daily':
    print(f"skipping {id} because update frequency is not daily")
    continue

  print(f"{id} date_columns:", ",".join([col['name'] for col in date_columns]))

  most_recent = None
  median_time_between_entries = None

  if temporal:

    # download data if not currently in folder
    download_path = f"./data/{id}.csv"
    if not os.path.isfile(download_path):      
      download_url = f"{base}/api/views/{id}/rows.csv?accessType=DOWNLOAD"
      print(f'downloading {id} "{name}"')
      urlretrieve(download_url, download_path)
      print(f'downloaded {id} "{name}"')
    else:
      print(f'already downloaded {id} "{name}"')

    
    with open(download_path) as f:
      column_dates = defaultdict(set)
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

          column_dates[fieldName].add(dt.date())

          # print("timestamp:", timestamp)
          if most_recent is None or timestamp > most_recent['timestamp']:
            most_recent = {
              "str": datestr,
              "datetime": dt,
              "timestamp": timestamp,
              "row": row
            }

      print("most_recent:", most_recent)

      # print("column_dates:", column_dates)
      median_diffs = []
      for col, dates in column_dates.items():
        subresult = median_diff_dates(list(dates))
        if subresult is not None:
          # print("subresult:", subresult)
          median_diffs.append(subresult)
      median_days_between_entries = min(median_diffs) if len(median_diffs) > 0 else None
      
  if most_recent:
    recentlyUpdated = most_recent['timestamp'] > threshold_timestamp
  else:
    dataUpdatedAt = parse_date(asset['dataUpdatedAt']).timestamp()
    updatedAt = parse_date(asset["updatedAt"]).timestamp()
    recentlyUpdated = (dataUpdatedAt > threshold_timestamp) or (updatedAt > threshold_timestamp)

  with open(out_filepath, "a") as outfile:
    csv.DictWriter(outfile, fieldnames=fieldnames).writerow({
      "id": asset['id'],
      "name": asset['name'],
      "dataUpdatedAt": asset['dataUpdatedAt'],
      "updatedAt": asset['updatedAt'],
      "mostRecentFound": (most_recent['datetime'].isoformat() if most_recent else "n/a"),
      "frequency": frequency,
      "recentlyUpdated": ("true" if recentlyUpdated else "false"),
      "medianDaysBetweenEntries": median_days_between_entries
    })
