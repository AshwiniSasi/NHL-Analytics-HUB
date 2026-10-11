# 🏒 NHL Analytics HUB

Fetches NHL data from the public NHL API, stores it in a MySQL database (7 tables), and explores it in a Streamlit app.
Pages: Home, Standings, Team Info, Player Search, Game Results, Leaderboards and SQL Query.
Setup: `pip install -r requirements.txt`, then run `addapidata_to_mysqldb.ipynb` to create the tables and load the data.
Run: set your MySQL details in `DB_CONFIG` in `app.py`, then `streamlit run app.py`.