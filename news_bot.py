import os
import requests
from datetime import datetime, timezone, timedelta
from deep_translator import GoogleTranslator

NEWS_API_KEY = os.environ["NEWS_API_KEY"]
SLACK_WEBHOOK_URL = os.environ["SLACK_WEBHOOK_URL"]

KST = timezone(timedelta(hours=9))
today = datetime.now(KST).strftime("%Y-%m-%d")

def fetch_news():
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": "(Iran OR 이란) AND (US OR USA OR America OR 미국) AND (war OR attack OR military OR missile OR sanction)",
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 5,
        "apiKey": NEWS_API_KEY,
    }
    res = requests.get(url, params=params)
    res.raise_for_status()
    return res.json().get("articles", [])

def translate(text):
    if not text:
        return ""
    try:
        return GoogleTranslator(source="en", target="ko").translate(text[:500])
    except Exception:
        return text

def build_slack_message(articles):
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"📰 이란-미국 전쟁 동향 | {today} 오전 7:00",
            },
        },
        {"type": "divider"},
    ]

    for i, article in enumerate(articles, 1):
        title_ko = translate(article.get("title", ""))
        desc_ko = translate(article.get("description", ""))
        source = article.get("source", {}).get("name", "알 수 없음")
        url = article.get("url", "")

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*{i}️⃣ {title_ko}*\n"
                    f"{desc_ko}\n"
                    f"📌 출처: {source} | <{url}|🔗 기사 보기>"
                ),
            },
        })
        blocks.append({"type": "divider"})

    return {"blocks": blocks}

def send_to_slack(message):
    res = requests.post(SLACK_WEBHOOK_URL, json=message)
    res.raise_for_status()

if __name__ == "__main__":
    articles = fetch_news()
    if not articles:
        print("뉴스 없음")
    else:
        message = build_slack_message(articles)
        send_to_slack(message)
        print(f"전송 완료: {len(articles)}건")
