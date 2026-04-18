import os
import requests
import feedparser
from datetime import datetime, timezone, timedelta
from deep_translator import GoogleTranslator

SLACK_WEBHOOK_URL = os.environ["SLACK_WEBHOOK_URL"]

KST = timezone(timedelta(hours=9))
today = datetime.now(KST).strftime("%Y-%m-%d")

CATEGORIES = {
    "⚔️ 군사 작전·공격": [
        "Iran US airstrike missile attack",
        "Iran Israel military strike bomb",
    ],
    "💀 피해 현황": [
        "Iran Iraq Syria casualties killed wounded civilian",
        "Yemen Lebanon missile casualties damage",
    ],
    "🇰🇼🇦🇪 쿠웨이트·UAE 동향": [
        "Kuwait Iran US military alert",
        "UAE Emirates Iran war evacuation",
    ],
    "🌍 주변국 반응": [
        "Iraq Syria Saudi Arabia Iran US conflict",
        "Jordan Lebanon Yemen Iran war response",
    ],
    "🕊️ 외교·협상": [
        "Iran US ceasefire negotiation diplomacy",
        "Iran Israel peace talks deal sanction",
    ],
}

def fetch_rss(query):
    url = f"https://news.google.com/rss/search?q={requests.utils.quote(query)}&hl=en-US&gl=US&ceid=US:en"
    feed = feedparser.parse(url)
    articles = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    for entry in feed.entries[:10]:
        published = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        if published and published < cutoff:
            continue
        articles.append({
            "title": entry.get("title", ""),
            "description": entry.get("summary", ""),
            "url": entry.get("link", ""),
            "source": entry.get("source", {}).get("title", "Google News"),
        })
    return articles[:3]

def translate(text):
    if not text:
        return ""
    try:
        return GoogleTranslator(source="en", target="ko").translate(text[:500])
    except Exception:
        return text

def analyze_situation(all_articles):
    titles = " ".join(a.get("title", "") for a in all_articles).lower()

    escalation_signals = ["airstrike", "missile launch", "nuclear", "mobilize", "invasion", "retaliation", "attack iran", "bomb"]
    ceasefire_signals = ["ceasefire", "negotiation", "talks", "deal", "diplomacy", "withdraw", "de-escalat"]

    esc_count = sum(1 for s in escalation_signals if s in titles)
    ces_count = sum(1 for s in ceasefire_signals if s in titles)

    if esc_count >= 4:
        esc_level, esc_bar = "매우 높음 🔴🔴🔴🔴🔴", "▓▓▓▓▓"
    elif esc_count >= 3:
        esc_level, esc_bar = "높음 🔴🔴🔴🔴", "▓▓▓▓░"
    elif esc_count >= 2:
        esc_level, esc_bar = "중간 🟡🟡🟡", "▓▓▓░░"
    elif esc_count >= 1:
        esc_level, esc_bar = "낮음 🟢🟢", "▓▓░░░"
    else:
        esc_level, esc_bar = "매우 낮음 🟢", "▓░░░░"

    if ces_count >= 3:
        ces_level, ces_bar = "높음 🟢🟢🟢🟢", "▓▓▓▓░"
    elif ces_count >= 2:
        ces_level, ces_bar = "중간 🟡🟡🟡", "▓▓▓░░"
    elif ces_count >= 1:
        ces_level, ces_bar = "낮음 🟡🟡", "▓▓░░░"
    else:
        ces_level, ces_bar = "매우 낮음 🔴", "▓░░░░"

    return esc_level, esc_bar, ces_level, ces_bar

def build_slack_message(categorized, all_articles):
    esc_level, esc_bar, ces_level, ces_bar = analyze_situation(all_articles)

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"🌏 이란-미국 전쟁 일일 브리핑 | {today} 07:00 KST"},
        },
        {"type": "divider"},
    ]

    for category, articles in categorized.items():
        if not articles:
            continue

        blocks.append({
            "type": "header",
            "text": {"type": "plain_text", "text": category},
        })

        for article in articles:
            title_ko = translate(article.get("title", ""))
            desc_ko = translate(article.get("description", ""))
            source = article.get("source", "Google News")
            url = article.get("url", "")

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"• *{title_ko}*\n"
                        f"  {desc_ko}\n"
                        f"  📌 {source} | <{url}|🔗 기사 보기>"
                    ),
                },
            })

        blocks.append({"type": "divider"})

    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": (
                f"*🤖 AI 상황 분석*\n\n"
                f"*확전 가능성:* {esc_level}\n"
                f"{esc_bar}\n\n"
                f"*휴전 가능성:* {ces_level}\n"
                f"{ces_bar}\n\n"
                f"_※ 최근 24시간 뉴스 키워드 빈도 기반 자동 분석_"
            ),
        },
    })

    return {"blocks": blocks}

def send_to_slack(message):
    res = requests.post(SLACK_WEBHOOK_URL, json=message)
    res.raise_for_status()

if __name__ == "__main__":
    categorized = {}
    all_articles = []

    for category, queries in CATEGORIES.items():
        articles = []
        for q in queries:
            articles.extend(fetch_rss(q))
        seen = set()
        deduped = []
        for a in articles:
            if a["title"] not in seen:
                seen.add(a["title"])
                deduped.append(a)
        categorized[category] = deduped[:3]
        all_articles.extend(deduped[:3])

    if not all_articles:
        print("뉴스 없음")
    else:
        message = build_slack_message(categorized, all_articles)
        send_to_slack(message)
        print(f"전송 완료: {len(all_articles)}건")
