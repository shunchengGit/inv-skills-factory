"""王者荣耀+和平精英 iOS 畅销榜排名。

数据源：Apple App Store 中国区 Top Grossing RSS
genre=6014 = Games 类别
"""

import datetime
import requests

APPLE_RSS_CN_GROSSING = (
    "https://itunes.apple.com/cn/rss/topgrossingapplications/limit=30/genre=6014/json"
)

TARGET_GAMES = {
    "王者荣耀": "王者荣耀",
    "和平精英": "和平精英",
    "三角洲行动": "三角洲行动",  # 腾讯自研新游
    "英雄联盟手游": "英雄联盟手游",
    "无畏契约": "无畏契约：源能行动",
    "火影忍者": "火影忍者",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}


def fetch_game_rankings() -> dict:
    """获取王者荣耀、和平精英等腾讯核心游戏的 iOS 畅销榜排名。

    返回 {
        "rankings": {
            "王者荣耀": {"rank": 1, "in_top30": true},
            "和平精英": {"rank": 2, "in_top30": true},
            ...
        },
        "summary": "...",
        "source": "apple_app_store_rss",
        "parse_status": "success" | "failed",
        "fetched_at": "...",
    }
    """
    result = {
        "rankings": {},
        "summary": "",
        "source": "apple_app_store_rss",
        "fetched_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }

    try:
        resp = requests.get(APPLE_RSS_CN_GROSSING, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        entries = data.get("feed", {}).get("entry", [])

        for i, entry in enumerate(entries):
            name = entry.get("im:name", {}).get("label", "")
            for key, pattern in TARGET_GAMES.items():
                if pattern in name and key not in result["rankings"]:
                    result["rankings"][key] = {
                        "rank": i + 1,
                        "in_top30": True,
                        "full_name": name,
                    }

        # 未上榜的标记
        for key in TARGET_GAMES:
            if key not in result["rankings"]:
                result["rankings"][key] = {
                    "rank": None,
                    "in_top30": False,
                    "full_name": TARGET_GAMES[key],
                }

        # 构建摘要
        wz = result["rankings"].get("王者荣耀", {})
        hp = result["rankings"].get("和平精英", {})
        parts = []
        if wz.get("rank"):
            parts.append(f"王者荣耀 #{wz['rank']}")
        else:
            parts.append("王者荣耀 未入TOP30")
        if hp.get("rank"):
            parts.append(f"和平精英 #{hp['rank']}")
        else:
            parts.append("和平精英 未入TOP30")

        other_tencent = {k: v for k, v in result["rankings"].items()
                        if k not in ("王者荣耀", "和平精英") and v.get("rank")}
        if other_tencent:
            other_str = ", ".join(f"{k}#{v['rank']}" for k, v in sorted(
                other_tencent.items(), key=lambda x: x[1]["rank"]))
            parts.append(f"其他腾讯: {other_str}")

        result["summary"] = " | ".join(parts)
        result["parse_status"] = "success"

    except Exception as e:
        result["parse_status"] = "failed"
        result["error"] = str(e)[:200]

    return result
