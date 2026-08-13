import sys
import warnings

sys.path.insert(0, ".")
warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

QUERIES = [
    "cheap flat to rent in Krakow, around 40 m2",
    "renting with a flatmate, we each need our own bedroom, up to 4000 including fees",
    "I want to buy a two bedroom flat with an open plan kitchen",
    "something nice",
]

for query in QUERIES:
    response = client.post("/search/intent", json={"query": query})
    if response.status_code != 200:
        print(f"[{response.status_code}] {query} -> {response.text[:200]}")
        continue
    body = response.json()
    defaults = {"page": 1, "page_size": 20}
    used = {
        k: v
        for k, v in body["filters"].items()
        if v is not None and v is not False and defaults.get(k) != v
    }
    print(f'"{query}"')
    print(f"   source: {body['source']}  results: {body['results']['total']}")
    print(f"   filters: {used}")
    print()
