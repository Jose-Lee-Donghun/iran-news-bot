import os
import requests
from datetime import datetime, timezone, timedelta
from deep_translator import GoogleTranslator

NEWS_API_KEY = os.environ["NEWS_API_KEY"]
SLACK_WEBHOOK_URL = os.environ["SLACK_WEBHOOK_URL"]

KST = timezone(timedelta(hours=9))
today = datetime.now(KST).strftime("%Y-%m-%d")

CATEGORIES = {
    "⚔️ 군사 작전·공격": {
        "q": "(Iran OR Israel) AND (US OR America) AND (airstrike OR missile OR attack OR bomb OR military operation)",
        "keywords": ["strike", "attack", "missile", "bomb", "military", "airstrike", "operation"],
    },
    "💀 피해 현황": {
        "q": "(Iran OR Iraq OR Syria OR Yemen OR Lebanon) AND (casualties OR killed OR wounded OR civilian OR damage)",
        "keywords": ["casualt", "killed", "dead", "wounded", "civilian", "victim", "damage"],
    },
    "🇰🇼🇦🇪 쿠웨이트·UAE 동향": {
        "q": "(Kuwait OR UAE OR Emirates) AND (Iran OR US OR military OR evacuation OR alert)",
        "keywords": ["kuwait", "uae", "emirates", "dubai", "abu dhabi"],
    },
    "🌍 주변국 반응": {
        "q": "(Iraq OR Syria OR Yemen OR Lebanon OR Saudi Arabia OR Jordan) AND (Iran OR US OR Israel) AND (war OR conflict OR response)",
        "keywords": ["iraq", "syria", "yemen", "lebanon", "saudi", "jordan"],
    },
    "🕊️ 외교·협상": {
        "q": "(Iran OR Israel) AND (US OR America) AND (ceasefire OR negotiation OR diplomacy OR sanction OR deal OR talks)",
        "keywords": ["ceasefire", "negotiat", "diplomac", "sanction", "deal", "talks", "peace"],
    },
}

def fetch_category(query):
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": query,
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
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*{category}*"},
        })

        for article in articles[:3]:
            title_ko = translate(article.get("title", ""))
            desc_ko = translate(article.get("description", ""))
            source = article.get("source", {}).get("name", "알 수 없음")
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

    for category, config in CATEGORIES.items():
        articles = fetch_category(config["q"])
        categorized[category] = articles
        all_articles.extend(articles)

    if not all_articles:
        print("뉴스 없음")
    else:
        message = build_slack_message(categorized, all_articles)
        send_to_slack(message)
        print(f"전송 완료: {len(all_articles)}건")
