import os
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv
load_dotenv()

AZURE_BLOB_CONN_STRING = os.getenv("AZURE_BLOB_CONNECTION_STRING")
AZURE_BLOB_CONTAINER = os.getenv("AZURE_BLOB_CONTAINER", "meetings")

blob_service = BlobServiceClient.from_connection_string(AZURE_BLOB_CONN_STRING)
container_client = blob_service.get_container_client(AZURE_BLOB_CONTAINER)

def upload_file_to_blob(meeting_id, local_file_path, blob_filename=None):
    blob_filename = blob_filename or os.path.basename(local_file_path)
    blob_path = f"{meeting_id}/{blob_filename}"

    with open(local_file_path, "rb") as data:
        container_client.upload_blob(name=blob_path, data=data, overwrite=True)

    print(f"[✅ Uploaded] {blob_path}")
    return f"{container_client.url}/{blob_path}"
