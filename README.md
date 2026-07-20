# Electro-Dip Aluminium Procurement Online App

## Run on Windows
1. Install Python 3.11 or later.
2. Extract this ZIP.
3. Double-click RUN_APP_WINDOWS.bat.
4. The app opens in your browser.

## Manual start
Open Command Prompt in the app folder and run:

pip install -r requirements.txt
streamlit run app.py

## Publish online
1. Create a GitHub repository.
2. Upload app.py and requirements.txt.
3. Deploy through Streamlit Community Cloud.
4. Select app.py as the main file.

## Main functions
- NALCO base + IE-07 input
- Automatic five-week forecast
- BUY / HOLD / WAIT recommendation
- Stock cover and purchase quantity
- Rate revision history
- LME and USD/INR trend influence
- Supplier comparison
- Excel export

Replace the sample rate history with actual NALCO circular and IE-07 data.
