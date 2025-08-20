from dotenv import load_dotenv
from langchain_openai import AzureOpenAIEmbeddings
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
from qdrant_client.http.exceptions import UnexpectedResponse
from langchain_core.documents import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
import pandas as pd
import uuid
from tqdm import tqdm
import os
import time
import tiktoken
from azure_blob_utils import download_blob


# ------------------------ Config ------------------------
load_dotenv()
TOKEN_LIMIT_PER_MINUTE = 750_000
BATCH_SIZE = 10
SLEEP_TIME = 60

# --------------------- Embedding Setup -------------------
embeddings = AzureOpenAIEmbeddings(
    deployment="text-embedding-3-small",
    model="text-embedding-3-small",
    azure_endpoint=os.getenv("OPENAI_EMBEDDINGS_ENDPOINT"),
    api_key=os.getenv("OPENAI_EMBEDDINGS_API"),
    api_version="2024-02-01"
)
tokenizer = tiktoken.get_encoding("cl100k_base")


# ----------------------- Data Load -----------------------
data = "posts.csv"
azure_container = "csv-file"
download_blob(azure_container, data, data)
posts_df = pd.read_csv(data)
#posts_df = posts_df.head(1000)

documents = [
    Document(
        page_content=f"{str(row['title']).strip()} {str(row['content']).strip()}",
        metadata={"date": row["date"], "author": row["author"], "link": row["link"]}
    )
    for _, row in posts_df.iterrows()
]
for doc in documents:
    print("Page Conent", doc.page_content)
    print("Metadata", doc.metadata)
    print("Author", doc.metadata["author"])


# ---------------------- Text Split -----------------------
text_splitter = RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=300)
splits = text_splitter.split_documents(documents)
splits_id = [str(uuid.uuid4()) for _ in splits]

texts = [doc.page_content for doc in splits]
metadatas = [doc.metadata for doc in splits]

# -------------------- Qdrant Setup -----------------------
qdrant_client = QdrantClient(host="172.206.104.110", port=6333)
collection_name = "articles"
if qdrant_client.collection_exists(collection_name):
    qdrant_client.delete_collection(collection_name)

qdrant_client.create_collection(
    collection_name=collection_name,
    vectors_config=VectorParams(size=1536, distance=Distance.COSINE)

)


# ------------------- Rate Limiting Utils -------------------

def get_batches(texts, metadatas, ids, tokenizer, token_limit, batch_size):
    i = 0
    while i < len(texts):
        token_accumulator = 0
        batch_texts, batch_metadatas, batch_ids = [], [], []

        while i < len(texts) and len(batch_texts) < batch_size:
            text = texts[i]
            token_count = len(tokenizer.encode(text))

            if token_accumulator + token_count > token_limit:
                break

            batch_texts.append(text)
            batch_metadatas.append(metadatas[i])
            batch_ids.append(ids[i])
            token_accumulator += token_count
            i += 1

        yield batch_texts, batch_metadatas, batch_ids, token_accumulator

def upload_batch_to_qdrant(client, collection_name, texts, metadatas, ids, embeddings):
    points = [
        PointStruct(id=ids[j], vector=embeddings[j], 
                    payload = {
                        **metadatas[j],
                        "page_content": texts[j]
                    }
        )
        for j in range(len(texts))
    ]
    #print(len(points[0].vector))
    client.upsert(collection_name=collection_name, points=points)

# ------------------- Main Processing Loop -------------------
p_bar = tqdm(total=len(texts))
for batch_texts, batch_metadatas, batch_ids, token_acc in get_batches(
    texts, metadatas, splits_id, tokenizer, TOKEN_LIMIT_PER_MINUTE, BATCH_SIZE
):
    batch_embeddings = embeddings.embed_documents(batch_texts)
    upload_batch_to_qdrant(qdrant_client, collection_name, batch_texts, batch_metadatas, batch_ids, batch_embeddings)
    p_bar.update(len(batch_texts))

    if token_acc >= TOKEN_LIMIT_PER_MINUTE:
        print(f"Hit {token_acc} tokens. Sleeping for {SLEEP_TIME} seconds...")
        with tqdm(total=SLEEP_TIME, desc="Sleeping", unit="s") as sleep_pbar:
            for _ in range(SLEEP_TIME):
                time.sleep(1)
                sleep_pbar.update(1)

p_bar.close()


""""""