from datetime import datetime
from requests import get
from statistics import median

def get_all_assets(limit=10000):
  bases = [
    "https://internal.chattadata.org",
    "https://www.chattadata.org"
  ]

  urls = [(base, f"{base}/api/views/metadata/v1/?limit={limit}") for base in bases]

  # because we aren't using auth, this will just return all the PUBLIC assets
  assets = []
  ids = set()
  for base, url in urls:
    for asset in get(url).json():
      id = asset['id']

      # skip if we've seen this asset before
      if id not in ids:
        assets.append((base, asset))
        ids.add(id)
  
  return assets

def median_diff_dates(datetimes):
  diffs = []
  datetimes = sorted(list(datetimes), key = lambda dt: datetime.strftime(dt, "%Y-%m-%d"))
  if len(datetimes) == 0: return None
  for i in range(1, len(datetimes)):
    previous = datetimes[i - 1]
    current = datetimes[i]
    diff = (current - previous).days
    # print("diff between", previous, "and", current, "is", diff)
    diffs.append(diff)
  # print("diffs:", diffs)
  return median(diffs)
