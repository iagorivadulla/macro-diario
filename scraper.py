from newspaper import Article, ArticleException

def scraper(url):
    try:
        article = Article(url)
        article.download()
        article.parse()
        return article.text if article.text else None
    except ArticleException as e:
        print(f"Skipped (ArticleException): {url} — {e}")
        return None
    except Exception as e:
        print(f"Skipped (error inesperado): {url} — {e}")
        return None

def get_articles(lists: list) -> list:

    for i in lists:
        link = i['link']
        article = scraper(link)
        if article:
            i['article'] = article
        else:
            i['article'] = None

    return lists
