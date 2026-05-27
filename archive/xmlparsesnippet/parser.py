from lxml import etree
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from qdrant_client.models import VectorParams, Distance
import pandas as pd
from sklearn.manifold import TSNE
import matplotlib.pyplot as plt

def extract_measures(root):

    measures = []

    for part in root.xpath("//part"):
        part_id = part.get("id")

        for measure in part.xpath("./measure"):
            measure_n = measure.get("number")

            notes = []

            for note in measure.xpath("./note"):

                if note.find("rest") is not None:
                    dur = note.findtext("duration")
                    notes.append(f"rest duration {dur}")
                    continue

                step = note.findtext("pitch/step")
                octave = note.findtext("pitch/octave")
                dur = note.findtext("duration")

                notes.append(f"{step}{octave} duration {dur}")

            text = f"Part {part_id} Measure {measure_n}: " + ", ".join(notes)

            measures.append({
                "text": text,
                "metadata": {
                    "part": part_id,
                    "measure": measure_n
                }
            })

    return measures

tree = etree.parse("MA001.xml")
root = tree.getroot()
measures = extract_measures(root)

model = SentenceTransformer("all-MiniLM-L6-v2")

texts = [m["text"] for m in measures]

embeddings = model.encode(texts)

client = QdrantClient(":memory:")

points = []

for i, m in enumerate(measures):

    points.append(
        PointStruct(
            id=i,
            vector=embeddings[i],
            payload=m["metadata"] | {"text": m["text"]}
        )
    )

client.create_collection(
    collection_name="scores",
    vectors_config=VectorParams(
        size=384,
        distance=Distance.COSINE
    )
)

client.upsert(
    collection_name="scores",
    points=points
)

print(len(points), "points inserted")

# # Print all notes
# for m in measures[:10]:
#     part = m["metadata"]["part"]
#     measure = m["metadata"]["measure"]
#     text = m["text"]
#     print(f"Part {part}, Measure {measure}: {text}")

# # Print only notes that have a pitch
# for m in measures[:20]:
#     if "rest" not in m["text"]:
#         print(m["text"])

# # Create dataframe
# df = pd.DataFrame(measures)
# print(df.head())
# df = pd.DataFrame([
#     {
#         "measure": m["metadata"]["measure"],
#         "text": m["text"]
#     }
#     for m in measures
# ])
# print(df)

# # Visualize embeddings
# tsne = TSNE(n_components=2, random_state=0)
# reduced = tsne.fit_transform(embeddings)

# x = reduced[:,0]
# y = reduced[:,1]

# plt.figure(figsize=(8,6))
# plt.scatter(x, y)

# for i, m in enumerate(measures[:20]):
#     plt.annotate(m["metadata"]["measure"], (x[i], y[i]))

# plt.title("Measure Embedding Visualization")
# plt.show()

