from datetime import datetime, timedelta
from collections import defaultdict
import csv
from functools import lru_cache
import os
from requests import get
import sys
import time
from urllib.request import urlretrieve

import dateparser

from utils import get_all_assets, median_diff_dates, Timer

# avoid _csv.Error: field larger than field limit (131072)
csv.field_size_limit(sys.maxsize)


@lru_cache(maxsize=8192)
def parse_date(str):
    for date_format in ["%m/%d/%Y %H:%M:%S %p", "%m/%d/%Y", "%B %d, %Y %H:%M %p"]:
        try:
            return datetime.strptime(datestr, date_format)
        except Exception as e:
            pass

    return dateparser.parse(
        str,
        languages=["en"],
        settings={
            "STRICT_PARSING": False,  # allow dates like Jan 1990
            "TIMEZONE": "+0000",
        },
    )


skiplist = []

select_asset_ids = [
    # "89n8-dwxx",
    # "k7u5-cfs3",
    # "8qb9-5fja",
    # "auia-u263"
]

# row_limit = 1
row_limit = 1_000_000
row_count = 0

# grab all assets
limit = 10000

# adding a little slack of 4 days to account for weekends and holidays
now = datetime.now()
threshold_timestamps = {
    "daily": (now - timedelta(days=1 + 3)).timestamp(),
    "weekly": (now - timedelta(days=7 + 6)).timestamp(),
    "monthly": (now - timedelta(days=31 + 9)).timestamp(),
    "yearly": (now - timedelta(days=365 * 12)).timestamp(),
}

assets = get_all_assets(limit)

# write output csv
fieldnames = [
    "id",
    "type",
    "name",
    "data_updated_at",
    "updated_at",
    "most_recent_found",
    "oldest_found",
    "frequency",
    "status",
    "median_days_between_entries",
    "notes",
]
out_filepath = "./results/frequency_analysis.csv"
with open(out_filepath, "w") as outfile:
    csv.DictWriter(outfile, fieldnames=fieldnames).writeheader()

for i, (base, asset) in enumerate(assets):
    id = asset["id"]
    name = asset["name"]
    # print("asset:", asset)

    print(f'\n[{id}] checking "{name}" ({i}/{len(assets)})')

    if len(select_asset_ids) >= 1 and id not in select_asset_ids:
        print(f"[{id}] skipping because it's not in the select asset ids")
        continue

    if id in skiplist:
        print(f"[{id}] skipping because it's in skiplist")
        continue

    # skip community assets
    if asset["provenance"] != "OFFICIAL":
        print(f'[{id}] skipping unofficial asset "{name}"')
        continue

    # sleep(1)

    metadata_url = f"{base}/api/views/{id}.json"
    print(f"[{id}] fetching " + metadata_url)
    with Timer(f"[{id}] fetching metadata"):
        metadata = get(metadata_url).json()

    if "error" in metadata:
        if "message" in metadata:
            print(metadata["message"])
            continue

    print(f"[{id}] assetType:", metadata["assetType"])
    if metadata["assetType"] not in ["dataset", "filter"]:
        print(f"[{id}] skipping because it's not a dataset or filter")
        continue

    notes = []

    columns = metadata["columns"]

    date_columns = [
        column for column in columns if column["dataTypeName"] == "calendar_date"
    ]

    temporal = len(date_columns) > 0

    if len(date_columns) == 0:
        notes.append("no calendar date columns")

    frequency = (
        metadata.get("metadata", {})
        .get("custom_fields", {})
        .get("Internal", {})
        .get("How often are data values updated?", None)
    )
    print(f"[{id}] frequency: {frequency}")

    if frequency is None or frequency.lower().strip() not in [
        "daily",
        "weekly",
        "monthly",
    ]:
        print(
            f"[{id}] skipping because update frequency is not daily, weekly, nor monthly"
        )
        continue

    print(f"[{id}] date_columns:", ",".join([col["name"] for col in date_columns]))

    most_recent = None
    oldest = None
    median_time_between_entries = None

    if temporal:
        # download data if not currently in folder
        download_path = f"./data/{id}.csv"
        if not os.path.isfile(download_path):
            time.sleep(5)
            download_url = f"{base}/api/views/{id}/rows.csv?accessType=DOWNLOAD"
            print(f'[{id}] downloading "{name}"')
            with Timer(f"[{id}] retrieving data"):
                urlretrieve(download_url, download_path)
            print(f'[{id}] downloaded "{name}"')
        else:
            print(f'[{id}] already downloaded {id} "{name}"')

        with Timer(f"[{id}] processing dates"):
            with open(download_path) as f:
                column_dates = defaultdict(set)

                # check if all date_columns are empty

                all_date_columns_are_empty = True

                for irow, row in enumerate(csv.DictReader(f)):
                    # print("irow:", irow)

                    for col in date_columns:
                        # print("col:", col)
                        fieldName = col["fieldName"]
                        name = col["name"]
                        datestr = row[name]

                        # skipping blank cells
                        if datestr == "":
                            continue

                        all_date_columns_are_empty = False

                        dt = parse_date(datestr)
                        if dt is None:
                            print("row:", row)
                            print(f"failed to parse '{datestr}'")
                            raise Exception(f"failed to parse '{datestr}'")
                        # print("dt:", dt)

                        timestamp = dt.timestamp()
                        # print("timestamp:", timestamp)

                        column_dates[fieldName].add(dt.date())

                        # print("timestamp:", timestamp)
                        if most_recent is None or timestamp > most_recent["timestamp"]:
                            most_recent = {
                                "str": datestr,
                                "datetime": dt,
                                "timestamp": timestamp,
                                "row": row,
                            }
                            # print("set most_recent")

                        if oldest is None or timestamp < oldest["timestamp"]:
                            oldest = {
                                "str": datestr,
                                "datetime": dt,
                                "timestamp": timestamp,
                                "row": row,
                            }
                            # print("set oldest")

                # print("most_recent:", most_recent)

                # print("column_dates:", column_dates)
                median_diffs = []
                for col, dates in column_dates.items():
                    subresult = median_diff_dates(list(dates))
                    if subresult is not None:
                        # print("subresult:", subresult)
                        median_diffs.append(subresult)
                median_days_between_entries = (
                    min(median_diffs) if len(median_diffs) > 0 else "n/a"
                )

            if all_date_columns_are_empty:
                notes.append("all calendar date columns are empty")

    # print("most_recent:", most_recent)

    if most_recent:
        recentlyUpdated = (
            most_recent["timestamp"] > threshold_timestamps[frequency.lower()]
        )
    else:
        dataUpdatedAt = parse_date(asset["dataUpdatedAt"]).timestamp()
        updatedAt = parse_date(asset["updatedAt"]).timestamp()
        recentlyUpdated = (dataUpdatedAt > threshold_timestamps[frequency.lower()]) or (
            updatedAt > threshold_timestamps[frequency.lower()]
        )

    mostRecentFound = most_recent["datetime"].isoformat() if most_recent else "n/a"

    oldestFound = oldest["datetime"].isoformat() if oldest else "n/a"
    # print("mostRecentFound:", mostRecentFound)

    if "assetType" not in metadata:
        print("asset type not in metadata")
        print(metadata)
        continue

    with open(out_filepath, "a") as outfile:
        csv.DictWriter(outfile, fieldnames=fieldnames).writerow(
            {
                "id": asset["id"],
                "type": metadata["assetType"],
                "name": asset["name"],
                "data_updated_at": asset["dataUpdatedAt"].split("T")[0],
                "updated_at": asset["updatedAt"].split("T")[0],
                "most_recent_found": mostRecentFound.split("T")[0],
                "oldest_found": oldestFound.split("T")[0],
                "frequency": frequency,
                "status": ("ok" if recentlyUpdated else "needs review"),
                "median_days_between_entries": median_days_between_entries,
                "notes": "; ".join(notes),
            }
        )
        print(f"[{id}] wrote row")
        row_count += 1

        if row_count >= row_limit:
            print(f"hit maximum number of {row_limit} rows, so breaking")
            break

print("done")
