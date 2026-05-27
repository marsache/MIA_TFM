from google import genai

client = genai.Client()

print("\nDELETING ALL FILE SEARCH STORES\n")

# List all available stores
stores = client.file_search_stores.list()

for store in stores:
    print(f"Deleting store and all its contents: {store.name}")
    try:
        # config={"force": True} automatically drops all documents inside the store first
        client.file_search_stores.delete(
            name=store.name,
            config={"force": True}
        )
        print("  Successfully deleted.")
    except Exception as e:
        print(f"  Failed to delete store: {e}")