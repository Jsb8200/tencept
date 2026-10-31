# TENCEPT — Options Flow Intelligence

## Run locally
1. Install Python 3.10 or newer.
2. Open a terminal in this folder.
3. Run:
   ```bash
   pip install -r requirements.txt
   streamlit run app.py
   ```
4. Open the local URL shown in the terminal (usually http://localhost:8501).
5. Upload one or more QuantData Options Order Flow CSV exports in the sidebar.

## Notes
- Dark theme is built into the app.
- Supports multiple CSV sessions and filters by ticker, date range, DTE and spread legs.
- Duplicate Trade IDs are removed when files are combined.
- AA/A are treated as buyer-initiated; B/BB as seller-initiated; M as neutral.
- Signed delta = Size × 100 × option delta × aggressor sign.
- This estimates aggressor-side option delta, not dealer inventory or actual hedge direction.
- Strategy Type is not inferred.
