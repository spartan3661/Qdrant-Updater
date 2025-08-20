from azure.storage.blob import BlobServiceClient
import os
from dotenv import load_dotenv

load_dotenv()
conn_str = os.getenv("AZURE_CSV_CONTAINER")
blob_service_client = BlobServiceClient.from_connection_string(str(conn_str))

def download_blob(container_name, blob_name, local_path):
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
    with open(local_path, "wb") as file:
        file.write(blob_client.download_blob().readall())

def upload_blob(container_name, blob_name, local_path):
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
    with open(local_path, "rb") as file:
        blob_client.upload_blob(file, overwrite=True)
