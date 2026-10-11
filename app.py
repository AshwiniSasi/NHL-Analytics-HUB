"""
NHL Stats Explorer — Streamlit app

Install:  pip install streamlit streamlit-option-menu mysql-connector-python pandas
Run:      streamlit run app.py
"""
import mysql.connector
import pandas as pd
import streamlit as st
from streamlit_option_menu import option_menu

# ---------------- Settings ----------------
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "YourNewPassword123!",
    "database": "NHL_Analytics_HUB",
}
CURRENT_SEASON = "20252026"
STATE_LABELS = {"OFF": "Final", "FINAL": "Final", "FUT": "Upcoming", "PRE": "Pre-game",
                "LIVE": "Live", "CRIT": "Live"}

st.set_page_config(page_title="NHL Analytics HUB", page_icon="🏒", layout="wide")


# ---------------- Database helper ----------------
@st.cache_data(ttl=600)
def run_query(sql, params=None):
    """Run a SELECT query and return the result as a DataFrame."""
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute(sql, params or ())
    df = pd.DataFrame(cursor.fetchall(), columns=cursor.column_names)
    cursor.close()
    conn.close()
    return df


def first_row(sql, params=None):
    df = run_query(sql, params)
    return df.iloc[0] if not df.empty else None


# ---------------- Sidebar ----------------
with st.sidebar:
    st.markdown("## 🏒 NHL Analytics HUB")
    page = option_menu(
        menu_title=None,
        options=["Home", "Standings", "Team Info", "Player Search",
                 "Game Results", "Leaderboards", "SQL Query"],
        icons=["house", "trophy", "people", "search", "calendar-event", "bar-chart", "terminal"],
        default_index=0,
    )
    st.caption(f"Season {CURRENT_SEASON[:4]}-{CURRENT_SEASON[4:]}")


# =====================================================================
# HOME
# =====================================================================
if page == "Home":
    st.title("NHL Analytics HUB")
    st.caption("A quick look at the league this season")

    counts = first_row("""
        SELECT (SELECT COUNT(*) FROM teams)   AS teams,
               (SELECT COUNT(*) FROM players) AS players,
               (SELECT COUNT(*) FROM games)   AS games,
               (SELECT COALESCE(SUM(goals), 0) FROM skater_season_stats WHERE season = %s) AS goals
    """, (CURRENT_SEASON,))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Teams", int(counts["teams"]))
    c2.metric("Players", int(counts["players"]))
    c3.metric("Games", int(counts["games"]))
    c4.metric("Goals scored", f"{int(counts['goals']):,}")

    st.subheader("Highlights")
    top_scorer = first_row("""
        SELECT CONCAT(p.first_name, ' ', p.last_name) AS name, t.team_abbrev, s.points, s.goals, s.assists
        FROM skater_season_stats s
        JOIN players p ON s.player_id = p.player_id
        JOIN teams t ON s.team_id = t.team_id
        WHERE s.season = %s
        ORDER BY s.points DESC LIMIT 1
    """, (CURRENT_SEASON,))
    best_goalie = first_row("""
        SELECT CONCAT(p.first_name, ' ', p.last_name) AS name, t.team_abbrev, g.save_pct, g.wins
        FROM goalie_season_stats g
        JOIN players p ON g.player_id = p.player_id
        JOIN teams t ON g.team_id = t.team_id
        WHERE g.season = %s AND g.games_played >= 20
        ORDER BY g.save_pct DESC LIMIT 1
    """, (CURRENT_SEASON,))
    leader = first_row("""
        SELECT t.team_name, s.points, s.wins, s.losses, s.ot_losses
        FROM standings s JOIN teams t ON s.team_id = t.team_id
        ORDER BY s.points DESC, s.wins DESC LIMIT 1
    """)

    h1, h2, h3 = st.columns(3)
    with h1.container(border=True):
        st.markdown("**Top scorer**")
        if top_scorer is not None:
            st.markdown(f"### {top_scorer['name']}")
            st.write(f"{top_scorer['team_abbrev']} · {int(top_scorer['points'])} pts "
                     f"({int(top_scorer['goals'])} G, {int(top_scorer['assists'])} A)")
    with h2.container(border=True):
        st.markdown("**Best goalie** (min. 20 GP)")
        if best_goalie is not None:
            st.markdown(f"### {best_goalie['name']}")
            st.write(f"{best_goalie['team_abbrev']} · {best_goalie['save_pct']:.3f} SV% · "
                     f"{int(best_goalie['wins'])} wins")
    with h3.container(border=True):
        st.markdown("**League leader**")
        if leader is not None:
            st.markdown(f"### {leader['team_name']}")
            st.write(f"{int(leader['points'])} pts · {int(leader['wins'])}-"
                     f"{int(leader['losses'])}-{int(leader['ot_losses'])}")

    left, right = st.columns(2)
    with left:
        st.subheader("Top 10 teams by points")
        top_teams = run_query("""
            SELECT t.team_abbrev AS team, s.points
            FROM standings s JOIN teams t ON s.team_id = t.team_id
            ORDER BY s.points DESC LIMIT 10
        """)
        st.bar_chart(top_teams, x="team", y="points", sort="-points")
    with right:
        st.subheader("Top 10 goal scorers")
        top_goals = run_query("""
            SELECT CONCAT(p.first_name, ' ', p.last_name) AS player, s.goals
            FROM skater_season_stats s JOIN players p ON s.player_id = p.player_id
            WHERE s.season = %s
            ORDER BY s.goals DESC LIMIT 10
        """, (CURRENT_SEASON,))
        st.bar_chart(top_goals, x="player", y="goals", sort="-goals", horizontal=True)


# =====================================================================
# STANDINGS
# =====================================================================
elif page == "Standings":
    st.title("League Standings")

    df = run_query("""
        SELECT t.logo_url, t.team_name, t.conference_name, t.division_name,
               s.games_played, s.wins, s.losses, s.ot_losses, s.points,
               s.goals_for, s.goals_against, s.home_wins, s.away_wins,
               s.streak_type, s.streak_count
        FROM standings s JOIN teams t ON s.team_id = t.team_id
    """)

    c1, c2 = st.columns(2)
    conference = c1.selectbox("Conference", ["All"] + sorted(df["conference_name"].dropna().unique()))
    if conference != "All":
        df = df[df["conference_name"] == conference]
    division = c2.selectbox("Division", ["All"] + sorted(df["division_name"].dropna().unique()))
    if division != "All":
        df = df[df["division_name"] == division]

    df["goal_diff"] = df["goals_for"] - df["goals_against"]
    df["streak"] = df["streak_type"].fillna("") + df["streak_count"].fillna(0).astype(int).astype(str)
    df["streak"] = df["streak"].where(df["streak_type"].notna(), "-")
    df = df.sort_values(["points", "wins"], ascending=False).reset_index(drop=True)
    df.insert(0, "rank", range(1, len(df) + 1))

    st.dataframe(
        df[["rank", "logo_url", "team_name", "division_name", "games_played", "wins", "losses",
            "ot_losses", "points", "goals_for", "goals_against", "goal_diff",
            "home_wins", "away_wins", "streak"]],
        column_config={
            "rank": st.column_config.NumberColumn("#", width="small"),
            "logo_url": st.column_config.ImageColumn("", width="small"),
            "team_name": "Team", "division_name": "Division", "games_played": "GP",
            "wins": "W", "losses": "L", "ot_losses": "OTL",
            "points": st.column_config.ProgressColumn("PTS", format="%d", min_value=0,
                                                      max_value=int(df["points"].max() or 1)),
            "goals_for": "GF", "goals_against": "GA", "goal_diff": "DIFF",
            "home_wins": "Home W", "away_wins": "Away W", "streak": "Streak",
        },
        hide_index=True, use_container_width=True, height=min(35 * len(df) + 40, 1200),
    )


# =====================================================================
# TEAM INFO
# =====================================================================
elif page == "Team Info":
    st.title("Team Info")

    teams = run_query("SELECT * FROM teams ORDER BY team_name")
    team_name = st.selectbox("Choose a team", teams["team_name"])
    team = teams[teams["team_name"] == team_name].iloc[0]
    team_id = int(team["team_id"])

    logo_col, info_col = st.columns([1, 4])
    if team["logo_url"]:
        logo_col.image(team["logo_url"], width=140)
    info_col.markdown(f"## {team['team_name']}")
    info_col.write(f"{team['conference_name']} Conference · {team['division_name']} Division")

    record = first_row("SELECT * FROM standings WHERE team_id = %s", (team_id,))
    if record is not None:
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Points", int(record["points"]))
        m2.metric("Record", f"{int(record['wins'])}-{int(record['losses'])}-{int(record['ot_losses'])}")
        m3.metric("Goals for", int(record["goals_for"]))
        m4.metric("Goals against", int(record["goals_against"]))
        streak = (f"{record['streak_type']}{int(record['streak_count'])}"
                  if record["streak_type"] else "-")
        m5.metric("Streak", streak)

    st.subheader("Roster")
    roster = run_query("""
        SELECT headshot_url, jersey_number, CONCAT(first_name, ' ', last_name) AS name,
               position, shoots_catches, height_cm, weight_kg, birth_date, birth_country
        FROM players WHERE team_id = %s ORDER BY jersey_number IS NULL, jersey_number
    """, (team_id,))

    roster_config = {
        "headshot_url": st.column_config.ImageColumn("", width="small"),
        "jersey_number": "#", "name": "Name", "position": "Pos", "shoots_catches": "Shoots",
        "height_cm": st.column_config.NumberColumn("Height (cm)", format="%d"),
        "weight_kg": st.column_config.NumberColumn("Weight (kg)", format="%d"),
        "birth_date": "Born", "birth_country": "Country",
    }
    groups = {"Forwards": ["C", "LW", "RW", "L", "R"], "Defense": ["D"], "Goalies": ["G"]}
    tabs = st.tabs([f"{name} ({roster['position'].isin(pos).sum()})" for name, pos in groups.items()])
    for tab, positions in zip(tabs, groups.values()):
        with tab:
            st.dataframe(roster[roster["position"].isin(positions)], column_config=roster_config,
                         hide_index=True, use_container_width=True)


# =====================================================================
# PLAYER SEARCH
# =====================================================================
elif page == "Player Search":
    st.title("Player Search")

    players = run_query("""
        SELECT p.player_id, CONCAT(p.first_name, ' ', p.last_name) AS name, p.position,
               t.team_name, t.team_abbrev
        FROM players p LEFT JOIN teams t ON p.team_id = t.team_id
        ORDER BY p.last_name
    """)

    c1, c2 = st.columns([2, 1])
    search = c1.text_input("Search by name", placeholder="e.g. MacKinnon")
    team_filter = c2.selectbox("Team", ["All"] + sorted(players["team_name"].dropna().unique()))

    matches = players
    if search:
        matches = matches[matches["name"].str.contains(search, case=False, na=False)]
    if team_filter != "All":
        matches = matches[matches["team_name"] == team_filter]

    if matches.empty:
        st.info("No players match your search.")
        st.stop()

    labels = matches["name"] + " (" + matches["team_abbrev"].fillna("-") + ", " + matches["position"].fillna("-") + ")"
    choice = st.selectbox(f"{len(matches)} players found", labels)
    player_id = int(matches.loc[labels == choice, "player_id"].iloc[0])

    p = first_row("""
        SELECT p.*, t.team_name FROM players p LEFT JOIN teams t ON p.team_id = t.team_id
        WHERE p.player_id = %s
    """, (player_id,))

    photo, bio = st.columns([1, 4])
    if p["headshot_url"]:
        photo.image(p["headshot_url"], width=150)
    bio.markdown(f"## {p['first_name']} {p['last_name']}")
    number = f"#{int(p['jersey_number'])} · " if pd.notna(p["jersey_number"]) else ""
    bio.write(f"{number}{p['position']} · {p['team_name']}")
    details = []
    if pd.notna(p["height_cm"]):
        details.append(f"{int(p['height_cm'])} cm")
    if pd.notna(p["weight_kg"]):
        details.append(f"{int(p['weight_kg'])} kg")
    if p["birth_date"]:
        details.append(f"born {p['birth_date']}")
    if p["birth_country"]:
        details.append(p["birth_country"])
    if p["shoots_catches"]:
        details.append(("Catches " if p["position"] == "G" else "Shoots ") + p["shoots_catches"])
    bio.caption(" · ".join(details))

    if p["position"] == "G":
        stats = first_row("SELECT * FROM goalie_season_stats WHERE player_id = %s AND season = %s",
                          (player_id, CURRENT_SEASON))
        if stats is None or pd.isna(stats["games_played"]):
            st.info("No goalie stats for this season.")
        else:
            cols = st.columns(5)
            cols[0].metric("Games", int(stats["games_played"]))
            cols[1].metric("Wins", int(stats["wins"]))
            cols[2].metric("Losses", int(stats["losses"]))
            cols[3].metric("Save %", f"{stats['save_pct']:.3f}")
            cols[4].metric("Shutouts", int(stats["shutouts"]))
    else:
        stats = first_row("SELECT * FROM skater_season_stats WHERE player_id = %s AND season = %s",
                          (player_id, CURRENT_SEASON))
        if stats is None or pd.isna(stats["games_played"]):
            st.info("No skater stats for this season.")
        else:
            cols = st.columns(6)
            cols[0].metric("Games", int(stats["games_played"]))
            cols[1].metric("Goals", int(stats["goals"]))
            cols[2].metric("Assists", int(stats["assists"]))
            cols[3].metric("Points", int(stats["points"]))
            cols[4].metric("+/-", int(stats["plus_minus"]))
            cols[5].metric("PIM", int(stats["penalty_min"]))

            st.subheader("Compared with the league average")
            avg = first_row("""
                SELECT AVG(goals) AS goals, AVG(assists) AS assists, AVG(points) AS points
                FROM skater_season_stats WHERE season = %s AND games_played >= 20
            """, (CURRENT_SEASON,))
            compare = pd.DataFrame({
                "stat": ["Goals", "Assists", "Points"] * 2,
                "value": [stats["goals"], stats["assists"], stats["points"],
                          avg["goals"], avg["assists"], avg["points"]],
                "who": [p["last_name"]] * 3 + ["League avg (20+ GP)"] * 3,
            })
            compare["value"] = compare["value"].astype(float).round(1)
            st.bar_chart(compare, x="stat", y="value", color="who", stack=False)

        log = run_query("""
            SELECT g.game_date, gs.goals, gs.assists, gs.points, gs.toi, gs.plus_minus
            FROM game_stats gs JOIN games g ON gs.game_id = g.game_id
            WHERE gs.player_id = %s AND g.game_type = 2 ORDER BY g.game_date
        """, (player_id,))
        if not log.empty:
            st.subheader("Game log (regular season)")
            log["cumulative_points"] = log["points"].cumsum()
            st.line_chart(log, x="game_date", y="cumulative_points")
            st.dataframe(log.iloc[::-1], hide_index=True, use_container_width=True)


# =====================================================================
# GAME RESULTS
# =====================================================================
elif page == "Game Results":
    st.title("Game Results")

    games = run_query("""
        SELECT g.game_id, g.game_date, g.game_type, g.game_state,
               a.team_abbrev AS away, g.away_score, g.home_score, h.team_abbrev AS home,
               g.venue_name
        FROM games g
        LEFT JOIN teams h ON g.home_team_id = h.team_id
        LEFT JOIN teams a ON g.away_team_id = a.team_id
        ORDER BY g.game_date
    """)
    games["game_date"] = pd.to_datetime(games["game_date"])
    games["status"] = games["game_state"].map(STATE_LABELS).fillna(games["game_state"])
    games["type"] = games["game_type"].map({1: "Preseason", 2: "Regular", 3: "Playoffs"})

    c1, c2, c3, c4 = st.columns(4)
    min_d, max_d = games["game_date"].min().date(), games["game_date"].max().date()
    dates = c1.date_input("Dates", value=(min_d, max_d), min_value=min_d, max_value=max_d)
    team_list = sorted(set(games["home"].dropna()) | set(games["away"].dropna()))
    team = c2.selectbox("Team", ["All"] + team_list)
    status = c3.selectbox("Status", ["All"] + sorted(games["status"].dropna().unique()))
    game_type = c4.selectbox("Type", ["All"] + sorted(games["type"].dropna().unique()))

    df = games
    if isinstance(dates, tuple) and len(dates) == 2:
        df = df[(df["game_date"].dt.date >= dates[0]) & (df["game_date"].dt.date <= dates[1])]
    if team != "All":
        df = df[(df["home"] == team) | (df["away"] == team)]
    if status != "All":
        df = df[df["status"] == status]
    if game_type != "All":
        df = df[df["type"] == game_type]

    finals = df[df["status"] == "Final"]
    m1, m2, m3 = st.columns(3)
    m1.metric("Games shown", len(df))
    m2.metric("Completed", len(finals))
    m3.metric("Avg goals / game",
              f"{(finals['home_score'] + finals['away_score']).mean():.2f}" if len(finals) else "-")

    df = df.copy()
    df["score"] = df.apply(lambda r: f"{int(r['away_score'])} - {int(r['home_score'])}"
                           if pd.notna(r["away_score"]) and pd.notna(r["home_score"]) else "vs", axis=1)
    st.dataframe(
        df[["game_date", "away", "score", "home", "status", "type", "venue_name"]].iloc[::-1],
        column_config={"game_date": st.column_config.DateColumn("Date", format="MMM D, YYYY"),
                       "away": "Away", "score": "Score", "home": "Home", "status": "Status",
                       "type": "Type", "venue_name": "Venue"},
        hide_index=True, use_container_width=True, height=600,
    )


# =====================================================================
# LEADERBOARDS
# =====================================================================
elif page == "Leaderboards":
    st.title("Leaderboards")
    top_n = st.slider("Show top", 5, 25, 10)

    skater_sql = """
        SELECT CONCAT(p.first_name, ' ', p.last_name) AS player, t.team_abbrev AS team,
               s.games_played AS gp, s.{col} AS value
        FROM skater_season_stats s
        JOIN players p ON s.player_id = p.player_id
        JOIN teams t ON s.team_id = t.team_id
        WHERE s.season = %s AND s.{col} IS NOT NULL
        ORDER BY s.{col} {order} LIMIT %s
    """
    goalie_sql = """
        SELECT CONCAT(p.first_name, ' ', p.last_name) AS player, t.team_abbrev AS team,
               g.games_played AS gp, g.{col} AS value
        FROM goalie_season_stats g
        JOIN players p ON g.player_id = p.player_id
        JOIN teams t ON g.team_id = t.team_id
        WHERE g.season = %s AND g.{col} IS NOT NULL AND g.games_played >= {min_gp}
        ORDER BY g.{col} DESC LIMIT %s
    """
    boards = {
        "🎯 Points":          (skater_sql.format(col="points", order="DESC"), "Points", "%d"),
        "🥅 Goals":           (skater_sql.format(col="goals", order="DESC"), "Goals", "%d"),
        "🤝 Assists":         (skater_sql.format(col="assists", order="DESC"), "Assists", "%d"),
        "➕ Plus / Minus":    (skater_sql.format(col="plus_minus", order="DESC"), "+/-", "%d"),
        "🚨 Penalty Minutes": (skater_sql.format(col="penalty_min", order="DESC"), "PIM", "%d"),
        "🧤 Save %":          (goalie_sql.format(col="save_pct", min_gp=20), "SV% (min 20 GP)", "%.3f"),
        "🏆 Goalie Wins":     (goalie_sql.format(col="wins", min_gp=0), "Wins", "%d"),
        "🔒 Shutouts":        (goalie_sql.format(col="shutouts", min_gp=0), "Shutouts", "%d"),
    }

    tabs = st.tabs(list(boards.keys()))
    for tab, (sql, label, fmt) in zip(tabs, boards.values()):
        with tab:
            df = run_query(sql, (CURRENT_SEASON, top_n))
            df.insert(0, "rank", range(1, len(df) + 1))
            left, right = st.columns([3, 2])
            left.dataframe(df, column_config={
                "rank": st.column_config.NumberColumn("#", width="small"),
                "player": "Player", "team": "Team", "gp": "GP",
                "value": st.column_config.NumberColumn(label, format=fmt),
            }, hide_index=True, use_container_width=True)
            if not df.empty:
                right.bar_chart(df, x="player", y="value", sort="-value", horizontal=True,
                                y_label=label, x_label="")


# =====================================================================
# SQL QUERY
# =====================================================================
elif page == "SQL Query":
    st.title("SQL Query")
    st.caption("Run read-only queries (SELECT, SHOW, DESCRIBE) against the NHL database.")

    ready_queries = {
        "Write my own": "",
        "All teams": "SELECT * FROM teams ORDER BY team_name;",
        "Standings by points": """SELECT t.team_name, s.wins, s.losses, s.ot_losses, s.points
FROM standings s JOIN teams t ON s.team_id = t.team_id
ORDER BY s.points DESC;""",
        "Players per team": """SELECT t.team_name, COUNT(*) AS players
FROM players p JOIN teams t ON p.team_id = t.team_id
GROUP BY t.team_name ORDER BY players DESC;""",
        "Players by country": """SELECT birth_country, COUNT(*) AS players
FROM players GROUP BY birth_country ORDER BY players DESC;""",
        "Top 10 point scorers": f"""SELECT CONCAT(p.first_name, ' ', p.last_name) AS player, s.goals, s.assists, s.points
FROM skater_season_stats s JOIN players p ON s.player_id = p.player_id
WHERE s.season = '{CURRENT_SEASON}'
ORDER BY s.points DESC LIMIT 10;""",
        "Best save % (20+ games)": f"""SELECT CONCAT(p.first_name, ' ', p.last_name) AS goalie, g.games_played, g.wins, g.save_pct
FROM goalie_season_stats g JOIN players p ON g.player_id = p.player_id
WHERE g.season = '{CURRENT_SEASON}' AND g.games_played >= 20
ORDER BY g.save_pct DESC LIMIT 10;""",
        "Highest-scoring games": """SELECT g.game_date, a.team_abbrev AS away, g.away_score, g.home_score, h.team_abbrev AS home,
       g.away_score + g.home_score AS total_goals
FROM games g
JOIN teams h ON g.home_team_id = h.team_id
JOIN teams a ON g.away_team_id = a.team_id
WHERE g.home_score IS NOT NULL
ORDER BY total_goals DESC LIMIT 10;""",
        "Most points in a single game": """SELECT CONCAT(p.first_name, ' ', p.last_name) AS player, gs.game_id, gs.goals, gs.assists, gs.points
FROM game_stats gs JOIN players p ON gs.player_id = p.player_id
ORDER BY gs.points DESC, gs.goals DESC LIMIT 10;""",
        "Home vs away wins by team": """SELECT t.team_name, s.home_wins, s.away_wins
FROM standings s JOIN teams t ON s.team_id = t.team_id
ORDER BY s.home_wins DESC;""",
        "Show all tables": "SHOW TABLES;",
    }

    pick = st.selectbox("Ready-made queries", list(ready_queries.keys()))
    sql = st.text_area("SQL", value=ready_queries[pick], height=180,
                       placeholder="SELECT * FROM teams;")

    if st.button("Run query", type="primary"):
        first_word = sql.strip().split(None, 1)[0].upper() if sql.strip() else ""
        if not first_word:
            st.warning("Type a query or pick one from the list first.")
        elif first_word not in ("SELECT", "SHOW", "DESCRIBE", "DESC", "WITH", "EXPLAIN"):
            st.error("Only read-only queries (SELECT, SHOW, DESCRIBE, WITH, EXPLAIN) are allowed here.")
        else:
            try:
                result = run_query(sql.strip().rstrip(";"))
                st.success(f"{len(result)} rows returned")
                st.dataframe(result, hide_index=True, use_container_width=True)
                st.download_button("Download CSV", result.to_csv(index=False),
                                   file_name="query_result.csv", mime="text/csv")
            except mysql.connector.Error as err:
                st.error(f"MySQL error: {err}")
