import datetime as dt
import requests


class PandaScoreValorantAdapter:
    """
    Data source: https://developers.pandascore.co
    Game: Valorant
    """

    BASE_URL = "https://api.pandascore.co/valorant/matches"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def fetch_matches(self, days: int = 7, past_days: int = 180) -> list[dict]:
        """
        Fetch matches in range:
        [now - past_days , now + days]

        This will include finished + running + not_started matches
        """
        now = dt.datetime.utcnow()
        start = (now - dt.timedelta(days=past_days)).date().isoformat()
        end = (now + dt.timedelta(days=days)).date().isoformat()

        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }

        params = {
            "sort": "-begin_at",
            "page[size]": 100,
            "range[begin_at]": f"{start},{end}",
        }

        all_items: list[dict] = []
        page = 1

        while True:
            params["page[number]"] = page
            resp = requests.get(
                self.BASE_URL,
                headers=headers,
                params=params,
                timeout=20,
            )
            resp.raise_for_status()

            items = resp.json()
            if not items:
                break

            all_items.extend(items)

            # PandaScore: 一页不满 size 说明到头了
            if len(items) < params["page[size]"]:
                break

            page += 1
            if page > 20:  # 安全阈值，防止无限分页
                break

        return all_items

    def normalize_match(self, raw: dict) -> dict:
        """
        Normalize PandaScore match JSON -> Match ORM fields
        """
        begin_at = raw.get("begin_at")

        start_time = None
        if begin_at:
            start_time = dt.datetime.fromisoformat(
                begin_at.replace("Z", "+00:00")
            )

        opponents = raw.get("opponents") or []
        team_a = opponents[0]["opponent"]["name"] if len(opponents) > 0 else None
        team_b = opponents[1]["opponent"]["name"] if len(opponents) > 1 else None

        score_a = None
        score_b = None
        results = raw.get("results") or []
        if len(results) >= 2:
            score_a = results[0].get("score")
            score_b = results[1].get("score")

        winner = None
        if raw.get("winner_id"):
            if opponents and raw["winner_id"] == opponents[0]["opponent"]["id"]:
                winner = "A"
            elif len(opponents) > 1 and raw["winner_id"] == opponents[1]["opponent"]["id"]:
                winner = "B"

        league = None
        if raw.get("league"):
            league = raw["league"].get("name")

        tournament = None
        if raw.get("tournament"):
            tournament = raw["tournament"].get("name")

        league_field = league
        if tournament:
            league_field = f"{league} / {tournament}" if league else tournament

        return {
            "source": "pandascore",
            "source_match_id": str(raw.get("id")),
            "start_time": start_time,
            "league": league_field,
            "team_a": team_a,
            "team_b": team_b,
            "score_a": score_a,
            "score_b": score_b,
            "winner": winner,
            "status": raw.get("status"),
            "bo": raw.get("number_of_games"),
            "raw_json": json.dumps(raw, ensure_ascii=False),
        }