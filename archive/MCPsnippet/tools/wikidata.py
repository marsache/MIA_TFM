import requests
import json

WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"
HEADERS = {
    "Accept": "application/json",
    "User-Agent": "MCP-WikidataTool/1.0 (example@example.com)"
}

def run_query(query):
    response = requests.get(
        WIKIDATA_SPARQL_URL,
        params={"query": query},
        headers=HEADERS
    )
    if response.status_code != 200:
        raise RuntimeError(f"Query failed: {response.status_code}\n{response.text}")
    return response.json()


def wikidata_mcp_tool_json(label: str, pick_first=True) -> str:
    """
    MCP tool to search Wikidata by label and return JSON string.
    """
    # --- 1. Search by label ---
    search_query = f"""
    SELECT ?item ?itemLabel WHERE {{
      ?item rdfs:label "{label}"@en.
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    LIMIT 5
    """
    data = run_query(search_query)
    matches = [
        (row["item"]["value"].split("/")[-1], row["itemLabel"]["value"])
        for row in data["results"]["bindings"]
    ]
    
    if not matches:
        result = {"found": False, "label": label, "matches": []}
        return json.dumps(result, indent=2)
    
    qid, name = matches[0] if pick_first else matches
    
    # --- 2. Get properties ---
    prop_query = f"""
    SELECT ?property ?propertyLabel ?value ?valueLabel WHERE {{
      wd:{qid} ?prop ?value .
      ?property wikibase:directClaim ?prop .
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    LIMIT 50
    """
    data = run_query(prop_query)
    properties = [
        (row["propertyLabel"]["value"], row.get("valueLabel", {}).get("value") or row["value"]["value"])
        for row in data["results"]["bindings"]
    ]
    
    # --- 3. Get Wikipedia links ---
    wiki_query = f"""
    SELECT ?wiki ?article WHERE {{
      VALUES ?item {{ wd:{qid} }}
      ?article schema:about ?item ;
               schema:isPartOf ?wiki .
    }}
    """
    data = run_query(wiki_query)
    wikipedia_links = [
        (row["wiki"]["value"], row["article"]["value"])
        for row in data["results"]["bindings"]
    ]
    
    result = {
        "found": True,
        "qid": qid,
        "label": name,
        "properties": properties,
        "wikipedia_links": wikipedia_links,
        "matches": matches
    }
    
    # Convert dict to JSON string
    return json.dumps(result, indent=2)