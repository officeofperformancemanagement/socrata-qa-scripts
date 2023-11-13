from requests import get

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
