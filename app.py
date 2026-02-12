from flask import Flask, jsonify, request, render_template
from sqlalchemy import or_
import json

from db import Base, engine, SessionLocal
from models import Match
from importers.pandascore_valorant_adapter import PandaScoreValorantAdapter
from config_local import PANDASCORE_API_TOKEN


app = Flask(__name__)
Base.metadata.create_all(bind=engine)

# =========================
# API 接口
# =========================

@app.get("/api/matches")
def list_matches():
    session = SessionLocal()
    try:
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 50))
        page = max(page, 1)
        page_size = min(max(page_size, 1), 200)

        status = request.args.get("status")
        league_kw = request.args.get("league")
        team_kw = request.args.get("team")
        date_from = request.args.get("from")
        date_to = request.args.get("to")

        q = session.query(Match)

        if status:
            q = q.filter(Match.status == status)

        if league_kw:
            q = q.filter(Match.league.ilike(f"%{league_kw}%"))

        if team_kw:
            q = q.filter(or_(
                Match.team_a.ilike(f"%{team_kw}%"),
                Match.team_b.ilike(f"%{team_kw}%")
            ))

        if date_from:
            q = q.filter(Match.start_time >= f"{date_from}T00:00:00")
        if date_to:
            q = q.filter(Match.start_time <= f"{date_to}T23:59:59")

        total = q.count()

        items = (
            q.order_by(Match.start_time.desc().nullslast())
             .offset((page - 1) * page_size)
             .limit(page_size)
             .all()
        )

        return jsonify({
            "page": page,
            "page_size": page_size,
            "total": total,
            "items": [{
                "id": m.id,
                "source": m.source,
                "start_time": m.start_time,
                "league": m.league,
                "team_a": m.team_a,
                "team_b": m.team_b,
                "score_a": m.score_a,
                "score_b": m.score_b,
                "status": m.status,
                "bo": m.bo,
            } for m in items]
        })
    finally:
        session.close()


@app.get("/api/matches/<int:match_id>")
def match_detail(match_id: int):
    session = SessionLocal()
    try:
        m = session.query(Match).filter(Match.id == match_id).first()
        if not m:
            return jsonify({"error": "not found"}), 404
        return jsonify({
            "id": m.id,
            "source": m.source,
            "start_time": m.start_time,
            "league": m.league,
            "team_a": m.team_a,
            "team_b": m.team_b,
            "score_a": m.score_a,
            "score_b": m.score_b,
            "winner": m.winner,
            "status": m.status,
            "bo": m.bo,
            "raw_json": m.raw_json,
        })
    finally:
        session.close()


@app.route("/api/import", methods=["GET", "POST"])
def import_matches():
    days = int(request.args.get("days", 7))
    past_days = int(request.args.get("past_days", 180))
    adapter = PandaScoreValorantAdapter(api_key=PANDASCORE_API_TOKEN)
    
    raw_list = adapter.fetch_matches(days=days, past_days=past_days)
    
    session = SessionLocal()
    inserted, skipped = 0, 0

    try:
        raw_list = adapter.fetch_matches(days=days)

        for raw in raw_list:
            sid = str(raw.get("id") or "")
            if not sid:
                continue

            exists = session.query(Match).filter(Match.source_match_id == sid).first()
            if exists:
                skipped += 1
                continue

            norm = adapter.normalize_match(raw)
            session.add(Match(**norm))
            inserted += 1

        session.commit()
        return jsonify({"inserted": inserted, "skipped": skipped})
    finally:
        session.close()


@app.get("/api/leagues")
def list_leagues():
    session = SessionLocal()
    try:
        rows = session.query(Match.league).filter(Match.league.isnot(None)).all()
        leagues = sorted({r[0] for r in rows if r[0]})
        return jsonify(leagues)
    finally:
        session.close()

# =========================
# 页面路由（HTML）
# =========================

@app.get("/")
def home():
    return matches_page()


@app.get("/matches")
def matches_page():
    session = SessionLocal()
    try:
        items = (
            session.query(Match)
            .order_by(Match.start_time.desc().nullslast())
            .limit(100)
            .all()
        )
        return render_template("matches.html", matches=items)
    finally:
        session.close()


@app.get("/matches/<int:match_id>/view")
def match_view(match_id: int):
    session = SessionLocal()
    try:
        m = session.query(Match).filter(Match.id == match_id).first()
        if not m:
            return "Not Found", 404

        raw = {}
        try:
            raw = json.loads(m.raw_json) if m.raw_json else {}
        except Exception:
            pass

        return render_template("match_detail.html", match=m, raw=raw)
    finally:
        session.close()


@app.get("/league/<path:league_name>")
def league_view(league_name: str):
    session = SessionLocal()
    try:
        items = (
            session.query(Match)
            .filter(Match.league == league_name)
            .order_by(Match.start_time.desc().nullslast())
            .limit(200)
            .all()
        )
        return render_template("league.html", league=league_name, matches=items)
    finally:
        session.close()

# =========================
# 程序入口（一定放最后）
# =========================

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
