import analytics.news_sentiment
import inspect

lines = inspect.getsourcelines(analytics.news_sentiment.NewsSentimentAnalyzer.get_latest_news)[0]
for i, line in enumerate(lines, 1):
    print(f'{i:3d}: {line}', end='')
