import feedparser
from datetime import datetime, timedelta, timezone
from sympy import public


def read_feed_yahoo():
    #search the yahoo rss feed
    feed = feedparser.parse('https://finance.yahoo.com/news/rssindex')
    print(f'Found {len(feed.entries)} yahoo entries')

    news = []

    now = datetime.now(timezone.utc)
    max_age = timedelta(hours=24)

    for entry in feed.entries:

        pub_datetime = datetime.strptime(
            entry.published,
            "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=timezone.utc)

        if pub_datetime == pub_datetime:
            news.append({
                'title': entry.title,
                'link': entry.link,
                'published': entry.published,
            })

    return news

def read_feed_expansion():
    from email.utils import parsedate_to_datetime

    feed = feedparser.parse('https://e01-expansion.uecdn.es/rss/portada.xml')
    print(f'Found expansion {len(feed.entries)} entries')

    news = []

    today = datetime.today().date()

    for entry in range(len(feed.entries)):

        pub_datetime = parsedate_to_datetime(feed.entries[entry].published)

        pub_date = pub_datetime.date()

        if pub_date == pub_date: #change this
            news.append({
            'title': feed.entries[entry].title,
            'link': feed.entries[entry].link,
            'published': feed.entries[entry].published,
        })

    return news

def read_feeds():

    #yahoo = read_feed_yahoo()
    #print(f'Passed {len(yahoo)} yahoo entries')
    expansion = read_feed_expansion()
    print(f'Passed {len(expansion)} expansion entries')

    news = expansion #yahoo + expansion
    print(f'Found {len(news)} entries')

    return news

if __name__ == '__main__':
    read_feeds()