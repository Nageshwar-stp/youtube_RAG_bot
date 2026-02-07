import os, re
from youtube_transcript_api import YouTubeTranscriptApi
from google import genai
import weaviate
from weaviate.classes.config import Property, DataType
from django.conf import settings
from weaviate.classes.query import MetadataQuery, Filter

EMBEDDING_MODEL = "gemini-embedding-001"
GEMINI_MODEL = "gemini-2.5-flash"

# Gemini
gclient = genai.Client(api_key=settings.GEMINI_API_KEY)

# Weaviate
wclient = weaviate.connect_to_weaviate_cloud(
    cluster_url=settings.WEAVIATE_URL,
    auth_credentials=settings.WEAVIATE_API_KEY,
)

CLASS = "TranscriptChunk"

def setup_schema():
    if not wclient.collections.exists(CLASS):
        wclient.collections.create(
            CLASS,
            properties=[
                Property(name="text", data_type=DataType.TEXT),
                Property(name="video_id", data_type=DataType.TEXT),
            ]
        )


def video_id(url):
    return re.search(r"v=([^&]+)", url).group(1)


def fetch_transcript(url):
    vid = video_id(url)
    yt_api = YouTubeTranscriptApi()

    # fetch available transcripts
    transcript_list = yt_api.list(vid)

    language_available = []
    for item in transcript_list:
        language_available.append(item.language_code)

    if len(language_available) == 0:
        return "No transcripts available for this video."

    data = yt_api.fetch(vid, languages=language_available)

    # join the transcript into a single string separated by spaces
    transcript = ""
    for snippet in data:
        transcript += " " + snippet.text

    return transcript


# Overlapping chunks
def chunk(text, size=800, overlap=150):
    words = text.split()
    out = []
    for i in range(0, len(words), size - overlap):
        out.append(" ".join(words[i:i+size]))
    return out


def embed(texts):
    result = gclient.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=texts
    )
    
    vectors = []
    for emb in result.embeddings:
        if hasattr(emb, 'values'):          
            vectors.append(emb.values)
        else:                               
            vectors.append(emb)
    
    print("First vector type:", type(vectors[0]))
    print("First vector length:", len(vectors[0]))
    print("First few values:", vectors[0][:8])
    
    return vectors



def ingest(url):
    setup_schema()
    vid = video_id(url)

    text = fetch_transcript(url)
    chunks = chunk(text)
    vectors = embed(chunks)

    collection = wclient.collections.use(CLASS)
    
    for c, v in zip(chunks, vectors):
        collection.data.insert(
            properties={
                "text": c,
                "video_id": vid
            },
            vector=v
        )




def rewrite_query(user_query):
    prompt = f"""
Rewrite this question to be detailed and optimized for semantic search.

Original: {user_query}

Rewritten:
"""

    res = gclient.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt
    )

    return res.text.strip()



def search(query, k=4):
    improved_query = rewrite_query(query)

    qvec = embed([improved_query])[0]

    collection = wclient.collections.use(CLASS)

    response = collection.query.near_vector(
        near_vector=qvec,
        limit=k,
        return_metadata=MetadataQuery(distance=True),
    )



    results = []
    for obj in response.objects:
        results.append({
            "text": obj.properties.get("text"),
            "distance": obj.metadata.distance,
            "uuid": obj.uuid,
        })
    
    print("Results:", results)

    if len(results) == 0:
        return "No results found."
    else:
        return results[0]["text"]



def answer(question):
    context = "\n\n".join(search(question))

    prompt = f"""
Use this context and answer the following question in detailed and consice manner without any extra text or formatting.

{context}

Question: {question}
"""

    res = gclient.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt
    )
    return res.text
