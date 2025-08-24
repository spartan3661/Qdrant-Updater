from update_csv import update_csv
from azure_blob_utils import download_blob, upload_blob
from build_qdrant import update_qdrant

def main():
    posts = "posts.csv"
    pages = "pages.csv"
    container = "csv-file"

    print("Download CSV Files")
    download_blob(container, posts, posts)
    download_blob(container, pages, pages)

    print("Adding Entries")
    update_csv(posts, pages)

    print("Upload CSV Files")
    upload_blob(container, posts, posts)
    upload_blob(container, pages, pages)

    print("Update Qdrant server with new csv entries")
    update_qdrant()



if __name__ == "__main__":
    main()
