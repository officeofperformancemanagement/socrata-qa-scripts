import csv
from requests import get
import sys

# avoid _csv.Error: field larger than field limit (131072)
csv.field_size_limit(sys.maxsize)

skiplist = []

# grab all assets
limit = 10000
  
bases = [
  "https://internal.chattadata.org",
  "https://www.chattadata.org"
]

urls = [(base, f"{base}/api/views/metadata/v1/?limit={limit}") for base in bases]

# because we aren't using auth, this will just return all the PUBLIC assets
assets = []
for base, url in urls:
  assets += [(base, asset) for asset in get(url).json()]

# write output csv
fieldnames = ['id', 'createdAt', 'name', 'data_types']
out_filepath = "./results/dataset_static.csv"
with open(out_filepath, "w") as outfile:
  csv.DictWriter(outfile, fieldnames=fieldnames).writeheader()

rows = []

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
  
  data_types = sorted(list(set([column['dataTypeName'] for column in columns])))
  
  temporal = "calendar_date" in data_types

  if temporal:
    print(f"skipping {id} because it has date columns")
    continue

  print(f"{id} data_types:", ",".join(data_types))

  with open(out_filepath, "a") as outfile:
    row = {
      "id": asset['id'],
      "createdAt": asset['createdAt'].split("T")[0], # not showing hours and minutes
      "name": asset['name'],
      "data_types": ",".join(data_types)
    }
    rows.append(row)
    csv.DictWriter(outfile, fieldnames=fieldnames).writerow(row)

# filter duplicates
id_to_row = dict([(row['id'], row) for row in rows])
sorted_ids = sorted(list(id_to_row.keys()))
rows = [id_to_row[id] for id in sorted_ids]

# write over temporary unsorted version of file
with open(out_filepath, "w") as outfile:
  csv.DictWriter(outfile, fieldnames=fieldnames).writeheader()
  for row in rows:
    csv.DictWriter(outfile, fieldnames=fieldnames).writerow(row)
