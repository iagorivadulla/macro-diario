from newspaper import Article, ArticleException
import requests
from selenium import webdriver
from bs4 import BeautifulSoup

def driver_scrape_cincodias(url):
    driver = webdriver.Chrome()
    driver.get(url)
    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')
    soup = soup.find('div', class_='Article__paragraphGroup')
    driver.quit()
    return soup.text


def scraper(url):
    try:
        article = Article(url)

        article.config.browser_user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/154.0.0.0 Safari/537.36"
        )

        article.download()
        article.parse()
        return article.text if article.text else None
    except ArticleException as e:
        return driver_scrape_cincodias(url) if not None else None
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
