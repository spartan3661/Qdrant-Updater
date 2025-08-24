import pandas as pd
import requests
import os
import time
import html2text
import re

def get_wordpress_results(url, content_id, author_lookup):
    params={"page": 1, "per_page": 100, "_embed": True}

    response = requests.get(url, params=params)
    total_pages = int(response.headers.get("X-WP-TotalPages", 1))

    #print(str(total_pages) + "\n")

    new_content = []

    for pages in range(1, total_pages + 1):
        response = requests.get(url,
                                params={"per_page": 100, "page": pages, "_embed": True})
        if response.status_code != 200:
            print(f"Failed to fetch page {pages}")
            continue
        content = response.json()
        if not content:
            break

        new_content.extend(content)
        #print(str(pages) +"\n")
        time.sleep(1)

    
    filtered_posts = []
    for p in new_content:
        if p["id"] not in content_id:
            filtered_posts.append({
                "id": p["id"],
                "date": p["date"],
                "title": html_to_markdown(p["title"]["rendered"]),
                "content": html_to_markdown(p["content"]["rendered"]),
                "link": p["link"],
                "author": author_lookup.get(p["author"], "Unknown")
            })

    return filtered_posts


def build_author_dict():
    params = {"page": 1, "per_page": 100}
    url = "https://libertarianchristians.com/wp-json/wp/v2/users"

    author_response = requests.get("https://libertarianchristians.com/wp-json/wp/v2/users", params=params)
    num_author_pages = int(author_response.headers.get("X-WP-TotalPages", 1))

    #print(str(num_author_pages) + "\n")

    author_lookup = {}

    for author_page in range(1, num_author_pages + 1):
        response = requests.get(url, params={"per_page": 100, "page": author_page})
        if response.status_code != 200:
            print(f"Failed to fetch page {author_page}")
            continue

        authors_response = response.json()
        if not authors_response:
            break

        author_lookup.update({user["id"]: user["name"] for user in authors_response})

        #print(str(author_page) +"\n")
        time.sleep(1)
    return author_lookup


def read_csv(path, columns):
    if not os.path.exists(path) or os.stat(path).st_size == 0:
        return pd.DataFrame(columns)
    return pd.read_csv(path)

def html_to_markdown(html):
    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = True
    h.body_width = 0

    invisible_unicode_pattern = r'[\u200B\u200C\u200D\uFEFF\u2060\u200E\u200F\u202C\u202A\u202B\u202D\u202E\u00A0\u202F\u180E\u00AD]'

    markdown = h.handle(html)
    markdown = re.sub(r'\n{2,}', '\n\n', markdown)
    markdown = re.sub(r'[ \t]', ' ', markdown)
    markdown = re.sub(invisible_unicode_pattern, '', markdown)

    return markdown.strip()

def update_csv(posts_csv_path, pages_csv_path):
    columns=["id", "date", "title", "author", "content", "link"]

    posts_df = read_csv(posts_csv_path, columns)

    pages_df = read_csv(pages_csv_path, columns)

    post_ids = set(posts_df['id'])
    page_ids = set(pages_df['id'])

    url_template = "https://libertarianchristians.com/wp-json/wp/v2/{content_type}"
    post_url= url_template.format(content_type="posts")
    pages_url = url_template.format(content_type="pages")
    
    author_lookup = build_author_dict()

    filtered_posts = get_wordpress_results(post_url, post_ids, author_lookup)
    filtered_pages = get_wordpress_results(pages_url, page_ids, author_lookup)


    new_posts_df = pd.DataFrame(filtered_posts)
    posts_df = pd.concat([posts_df, new_posts_df], ignore_index=True)
    posts_df.drop_duplicates(subset="id", inplace=True)
    posts_df.to_csv(posts_csv_path, index=False)


    new_pages_df = pd.DataFrame(filtered_pages)
    pages_df = pd.concat([pages_df, new_pages_df], ignore_index=True)
    pages_df.drop_duplicates(subset="id", inplace=True)
    pages_df.to_csv(pages_csv_path, index=False)

