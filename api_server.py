import os
import json
from datetime import datetime, timezone
import yfinance as yf
import google.generativeai as genai

api_key = os.environ.get("GOOGLE_API_KEY")
genai.configure(api_key=api_key)

def harvest_live_market_data():
    """Pulls real-time prices, 5-day momentum, and key levels from Yahoo Finance."""
    sectors = {
        "Information Technology": "XLK",
        "Communication Services": "XLC",
        "Financials": "XLF",
        "Healthcare": "XLV",
        "Consumer Discretionary": "XLY",
        "Consumer Staples": "XLP",
        "Energy": "XLE",
        "Industrials": "XLI",
        "Materials": "XLB",
        "Utilities": "XLU",
        "Real Estate": "XLRE",
        "Digital Assets": "IBIT"
    }
    
    # Core liquid tickers across Day, Swing, and Long-Term sleeves
    watchlist = ["NVDA", "TSLA", "COIN", "AMD", "META", "VST", "GE", "PLTR", "MSFT", "ASML", "AMZN", "AAPL"]
    
    live_data = {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "vix": None,
        "sectors": {},
        "watchlist_metrics": {}
    }
    
    # 1. Get real VIX
    try:
        vix_hist = yf.Ticker("^VIX").history(period="5d")
        if not vix_hist.empty:
            live_data["vix"] = round(float(vix_hist['Close'].iloc[-1]), 2)
    except Exception:
        live_data["vix"] = "Unavailable"

    # 2. Get real Sector ETF performance
    for name, ticker in sectors.items():
        try:
            hist = yf.Ticker(ticker).history(period="5d")
            if len(hist) >= 2:
                latest = float(hist['Close'].iloc[-1])
                prev = float(hist['Close'].iloc[-2])
                five_day_start = float(hist['Close'].iloc[0])
                live_data["sectors"][name] = {
                    "ticker": ticker,
                    "price": round(latest, 2),
                    "1d_change_pct": round(((latest - prev) / prev) * 100, 2),
                    "5d_change_pct": round(((latest - five_day_start) / five_day_start) * 100, 2)
                }
        except Exception:
            continue

    # 3. Get real Watchlist levels (Prior Day High/Low/Close for real trading setups)
    for ticker in watchlist:
        try:
            hist = yf.Ticker(ticker).history(period="1mo")
            if len(hist) >= 2:
                latest_close = float(hist['Close'].iloc[-1])
                prev_high = float(hist['High'].iloc[-1])
                prev_low = float(hist['Low'].iloc[-1])
                month_high = float(hist['High'].max())
                month_low = float(hist['Low'].min())
                live_data["watchlist_metrics"][ticker] = {
                    "last_close": round(latest_close, 2),
                    "prior_day_high": round(prev_high, 2),
                    "prior_day_low": round(prev_low, 2),
                    "30d_high": round(month_high, 2),
                    "30d_low": round(month_low, 2)
                }
        except Exception:
            continue

    return live_data

try:
    # Step 1: Harvest actual market reality
    market_reality = harvest_live_market_data()
    
    # Step 2: Configure Gemini 3.8 Flash
    model = genai.GenerativeModel(
        model_name="gemini-3.8-flash",
        system_instruction="""You are an elite quantitative trading and cognitive performance co-pilot. 
        CRITICAL RULE: You MUST strictly use the exact prices, dates, and percentages provided in the LIVE MARKET DATA. 
        NEVER hallucinate or invent prices. Because this runs at 6:00 AM pre-market, base all Day Trading levels on the provided Prior Day High (PDH), Prior Day Low (PDL), and last close—do not invent fake post-open prices.
        Your output must strictly be a valid JSON data structure.""",
        generation_config={"response_mime_type": "application/json"} 
    )

    # Step 3: Inject reality into the prompt
    prompt = f"""
    Here is today's verified LIVE MARKET DATA pulled directly from the exchange:
    {json.dumps(market_reality, indent=2)}

    Using ONLY the real data above for prices, timestamps, and VIX, generate today's market intelligence JSON report.
    
    Strictly follow this exact JSON structure:
    - "timestamp": Use the exact timestamp_utc from the live data.
    - "macro_context": Include "market_regime", "volatility_index_vix" (use exact VIX from data), "liquidity_condition", and "cognitive_bias_alert".
    - "sector_health_scan": Array of all 12 sectors using their real price, 1d_change_pct, and 5d_change_pct to determine "relative_strength", "momentum_score_100", and "flow_direction".
    - "recommendations": 
        - "day_trading": Pick 3 stocks from the watchlist_metrics. Use their REAL last_close, prior_day_high, and prior_day_low to map out pre-market breakout or bounce levels (entry, stop_loss, target_1, target_2).
        - "swing_trading": Pick 3 stocks from the watchlist_metrics using their 30d_high and 30d_low to build realistic entry zones, stops, and targets.
        - "long_term_investing": Pick 3 core compounders from the watchlist with real price context and thesis.
    """

    response = model.generate_content(prompt)
    print(response.text)
    
except Exception as e:
    safe_error = str(e).replace('"', "'")
    print(f'{{"error": "Could not generate todays report. Reason: {safe_error}"}}')
