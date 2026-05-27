import requests

WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "MyWikidataApp/1.0 (maria@example.com)"
}


def run_query(query):
    response = requests.get(
        WIKIDATA_SPARQL_URL,
        params={"query": query},
        headers=HEADERS
    )
    
    if response.status_code != 200:
        print("Error:", response.status_code)
        print(response.text)
        return None
    
    return response.json()


# Search by label → get QID
def search_entity(label):
    query = f"""
    SELECT ?item ?itemLabel WHERE {{
      ?item rdfs:label "{label}"@en.
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    LIMIT 5
    """
    
    data = run_query(query)
    if not data:
        return []
    
    results = []
    
    for row in data["results"]["bindings"]:
        uri = row["item"]["value"]
        qid = uri.split("/")[-1]
        label = row["itemLabel"]["value"]
        results.append((qid, label))
    
    return results


# Get properties
def get_properties(qid):
    query = f"""
    SELECT ?property ?propertyLabel ?value ?valueLabel WHERE {{
      wd:{qid} ?prop ?value .
      ?property wikibase:directClaim ?prop .
      
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    LIMIT 50
    """
    
    data = run_query(query)
    if not data:
        return []
    
    results = []
    
    for row in data["results"]["bindings"]:
        prop = row["propertyLabel"]["value"]
        val = row.get("valueLabel", {}).get("value") or row["value"]["value"]
        results.append((prop, val))
    
    return results


# Get Wikipedia links
def get_wikipedia_links(qid):
    query = f"""
    SELECT ?wiki ?article WHERE {{
      VALUES ?item {{ wd:{qid} }}
      ?article schema:about ?item ;
               schema:isPartOf ?wiki .
    }}
    """
    
    data = run_query(query)
    if not data:
        return []
    
    results = []
    
    for row in data["results"]["bindings"]:
        wiki = row["wiki"]["value"]
        article = row["article"]["value"]
        results.append((wiki, article))
    
    return results


# ===== MAIN =====
label = "Cancionero Popular Vasco"

matches = search_entity(label)

if not matches:
    print(f"No results found for '{label}'")
else:
    print("Matches found:")
    for i, (qid, name) in enumerate(matches):
        print(f"{i}: {qid} - {name}")
    
    # pick the first result (you can change this logic)
    qid, name = matches[0]
    
    print(f"\nUsing: {qid} - {name}")
    
    print("\n=== PROPERTIES ===")
    for prop, val in get_properties(qid):
        print(f"{prop}: {val}")
    
    print("\n=== WIKIPEDIA LINKS ===")
    for wiki, article in get_wikipedia_links(qid):
        print(f"{wiki} → {article}")