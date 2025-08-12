import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# --- Google Sheets Setup ---
scopes = ["https://www.googleapis.com/auth/spreadsheets"]
skey = st.secrets["gcp_service_account"]
credentials = Credentials.from_service_account_info(skey, scopes=scopes)
client = gspread.authorize(credentials)
url = st.secrets["private_gsheets_url"]
sheet_name = "Books"
worksheet = client.open_by_url(url).worksheet(sheet_name)

# --- Load and Clean Data ---
def load_books():
    data = worksheet.get_all_records()

    if not data:
        df_books = pd.DataFrame(columns=["title", "authors", "elo"])
        df_books["elo"] = 1500
        worksheet.update([df_books.columns.values.tolist()] + df_books.values.tolist())
        return df_books

    df_books = pd.DataFrame(data)

    # ✅ Cast title and authors to string to avoid ArrowTypeError
    df_books["title"] = df_books["title"].astype(str).str.strip()
    df_books["authors"] = df_books["authors"].astype(str).str.strip()

    # ✅ Ensure elo is numeric
    df_books["elo"] = pd.to_numeric(df_books["elo"], errors="coerce").fillna(1500).astype(int)

    return df_books

df_books = load_books()

# --- App UI ---
st.title("📚 Book Rater")
st.write("Choose your favorite between two books. Elo scores will update based on your vote.")

# --- Random Book Pair ---
if "book_pair" not in st.session_state:
    st.session_state.book_pair = df_books.sample(2).reset_index(drop=True)

book1, book2 = st.session_state.book_pair.iloc[0], st.session_state.book_pair.iloc[1]

# --- Voting Buttons ---
if "vote" not in st.session_state:
    st.session_state.vote = None

col1, col2 = st.columns(2)
with col1:
    if st.button(f"{book1['title'].title()} by {book1['authors']}"):
        st.session_state.vote = (book1, book2)
with col2:
    if st.button(f"{book2['title'].title()} by {book2['authors']}"):
        st.session_state.vote = (book2, book1)

# --- Skip Button ---
if st.button("🔄 Skip this pair"):
    st.session_state.book_pair = df_books.sample(2).reset_index(drop=True)
    st.rerun()

# --- Elo Update Function ---
def update_elo(winner_elo, loser_elo, k=32):
    expected_win = 1 / (1 + 10 ** ((loser_elo - winner_elo) / 400))
    new_winner_elo = winner_elo + k * (1 - expected_win)
    new_loser_elo = loser_elo - k * (1 - expected_win)
    return round(new_winner_elo), round(new_loser_elo)

# --- Helper: Find Row Number by Title ---
def find_row_number(title_value, sheet_data, title_idx):
    for i, row in enumerate(sheet_data[1:], start=2):  # start=2 because row 1 is header
        row_title = row[title_idx].strip().lower()
        if row_title == title_value.strip().lower():
            return i
    return None

# --- Process Vote and Update Sheet ---
if st.session_state.vote:
    winner, loser = st.session_state.vote
    new_winner_elo, new_loser_elo = update_elo(winner["elo"], loser["elo"])

    df_books.loc[df_books["title"] == winner["title"], "elo"] = new_winner_elo
    df_books.loc[df_books["title"] == loser["title"], "elo"] = new_loser_elo

    sheet_data = worksheet.get_all_values()
    headers = [h.strip().lower() for h in sheet_data[0]]
    title_idx = headers.index("title")
    elo_idx = headers.index("elo")

    winner_row = find_row_number(winner["title"], sheet_data, title_idx)
    loser_row = find_row_number(loser["title"], sheet_data, title_idx)

    try:
        if winner_row:
            worksheet.update_cell(winner_row, elo_idx + 1, new_winner_elo)
        if loser_row:
            worksheet.update_cell(loser_row, elo_idx + 1, new_loser_elo)
        st.success(f"You voted for **{winner['title'].title()}**! Elo updated.")
    except Exception as e:
        st.error(f"❌ Update failed: {e}")

    # Reset and rerun
    st.session_state.vote = None
    st.session_state.book_pair = df_books.sample(2).reset_index(drop=True)
    st.rerun()

# --- Leaderboard ---
st.subheader("🏆 Leaderboard")
st.dataframe(df_books.sort_values("elo", ascending=False), use_container_width=True)