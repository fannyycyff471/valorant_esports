import json
import datetime as dt
import requests
from importers.adapter_base import MatchSourceAdapter

class YourSourceAdapter(MatchSourceAdapter):
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key

    def fetch_matches(self, days: int) -> list[dict]:
        # TODO: 替换成你选的网站API
        # 先用假数据跑通
        return [{
            "id": "demo_1",
            "start_time": "2026-02-10T12:00:00Z",
            "league": "LCK",
            "team_a": "HLE",
            "team_b": "T1",
            "score_a": 2,
            "score_b": 1,
            "status": "finished",
            "bo": 3
        }]

    def normalize_match(self, raw: dict) -> dict:
        start_time = None
        if raw.get("start_time"):
            # 简单处理：把Z结尾当UTC
            s = raw["start_time"].replace("Z", "+00:00")
            start_time = dt.datetime.fromisoformat(s)

        return {
            "source": "your_source",
            "source_match_id": str(raw.get("id")),
            "start_time": start_time,
            "league": raw.get("league"),
            "team_a": raw.get("team_a"),
            "team_b": raw.get("team_b"),
            "score_a": raw.get("score_a"),
            "score_b": raw.get("score_b"),
            "winner": "A" if (raw.get("score_a", 0) > raw.get("score_b", 0)) else ("B" if (raw.get("score_b", 0) > raw.get("score_a", 0)) else None),
            "status": raw.get("status"),
            "bo": raw.get("bo"),
            "raw_json": json.dumps(raw, ensure_ascii=False)
        }
