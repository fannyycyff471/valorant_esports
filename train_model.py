# ml/train_model.py
import os
import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, accuracy_score

from db import SessionLocal
from models import Match

RECENT_N = 10  # 最近N场
MODEL_PATH = os.path.join(os.path.dirname(__file__), "model.joblib")


def normalize_team_name(name: str | None) -> str | None:
    return name.strip().lower() if name else None


def get_finished_matches(session):
    # PandaScore：finished
    return (
        session.query(Match)
        .filter(Match.status == "finished")
        .filter(Match.team_a.isnot(None), Match.team_b.isnot(None))
        .filter(Match.score_a.isnot(None), Match.score_b.isnot(None))
        .all()
    )


def build_team_history_index(matches):
    """
    为了快速算胜率/近期胜率，把每支队的比赛按时间排序存起来。
    start_time 目前是 ISO 字符串，排序用字符串在 ISO 格式下可行。
    """
    team_games = {}
    for m in sorted(matches, key=lambda x: x.start_time or ""):
        a = normalize_team_name(m.team_a)
        b = normalize_team_name(m.team_b)
        if not a or not b:
            continue
        team_games.setdefault(a, []).append(m)
        team_games.setdefault(b, []).append(m)
    return team_games


def match_winner_label(m: Match) -> int | None:
    # label=1 表示 team_a 赢；0 表示 team_b 赢
    if m.score_a is None or m.score_b is None:
        return None
    if m.score_a == m.score_b:
        return None  # 平局直接丢弃（一般没有）
    return 1 if m.score_a > m.score_b else 0


def team_win_rate(team: str, team_games_index) -> float:
    games = team_games_index.get(team, [])
    if not games:
        return 0.5
    wins = 0
    valid = 0
    for g in games:
        y = match_winner_label(g)
        if y is None:
            continue
        valid += 1
        if normalize_team_name(g.team_a) == team:
            if y == 1:
                wins += 1
        else:
            # team在B侧，y==0代表team赢
            if y == 0:
                wins += 1
    return wins / valid if valid else 0.5


def team_recent_win_rate(team: str, team_games_index, n=RECENT_N) -> float:
    games = team_games_index.get(team, [])
    if not games:
        return 0.5
    # 取最近n场 finished
    recent = []
    for g in reversed(games):
        if g.status != "finished":
            continue
        if g.score_a is None or g.score_b is None:
            continue
        recent.append(g)
        if len(recent) >= n:
            break
    if not recent:
        return 0.5

    wins = 0
    for g in recent:
        y = match_winner_label(g)
        if y is None:
            continue
        if normalize_team_name(g.team_a) == team:
            wins += 1 if y == 1 else 0
        else:
            wins += 1 if y == 0 else 0
    return wins / len(recent)


def h2h_stats(team_a: str, team_b: str, all_matches) -> tuple[int, float]:
    """
    返回 (交战次数, A对B胜率)
    """
    cnt = 0
    a_wins = 0
    for m in all_matches:
        a = normalize_team_name(m.team_a)
        b = normalize_team_name(m.team_b)
        if not a or not b:
            continue
        if {a, b} != {team_a, team_b}:
            continue
        y = match_winner_label(m)
        if y is None:
            continue
        cnt += 1
        # 判断这场里“team_a(输入参数)”是否获胜
        if a == team_a:
            if y == 1:
                a_wins += 1
        else:
            # team_a 在B侧，y==0代表team_a赢
            if y == 0:
                a_wins += 1
    win_rate = a_wins / cnt if cnt else 0.5
    return cnt, win_rate


def build_dataset(session):
    finished = get_finished_matches(session)
    team_index = build_team_history_index(finished)

    X = []
    y = []

    for m in finished:
        label = match_winner_label(m)
        if label is None:
            continue

        A = normalize_team_name(m.team_a)
        B = normalize_team_name(m.team_b)
        if not A or not B:
            continue

        # 特征
        wrA = team_win_rate(A, team_index)
        wrB = team_win_rate(B, team_index)
        rwrA = team_recent_win_rate(A, team_index)
        rwrB = team_recent_win_rate(B, team_index)
        h2h_cnt, h2h_wrA = h2h_stats(A, B, finished)

        features = [
            wrA - wrB,          # 总胜率差
            rwrA - rwrB,        # 近期胜率差
            h2h_wrA,            # A对B交战胜率
            min(h2h_cnt, 20)    # 交战次数（截断避免极端值）
        ]
        X.append(features)
        y.append(label)

    return np.array(X, dtype=float), np.array(y, dtype=int)


def main():
    session = SessionLocal()
    try:
        X, y = build_dataset(session)
        print("dataset:", X.shape, y.shape)
        if len(y) < 50:
            print("WARNING: 数据量偏少，建议多导入一些比赛再训练。")

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y if len(set(y)) > 1 else None
        )

        model = LogisticRegression(max_iter=200)
        model.fit(X_train, y_train)

        # 简单评估
        prob = model.predict_proba(X_test)[:, 1]
        pred = (prob >= 0.5).astype(int)

        auc = roc_auc_score(y_test, prob) if len(set(y_test)) > 1 else None
        acc = accuracy_score(y_test, pred)

        print("accuracy:", acc)
        if auc is not None:
            print("auc:", auc)

        joblib.dump(model, MODEL_PATH)
        print("saved:", MODEL_PATH)
    finally:
        session.close()


if __name__ == "__main__":
    main()

