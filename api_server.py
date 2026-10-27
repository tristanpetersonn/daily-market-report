import os
import sys
import json
from datetime import datetime, timezone
import yfinance as yf
import google.generativeai as genai

api_key = os.environ.get("GOOGLE_API_KEY")
genai.configure(api_key=api_key)

def harvest_dynamic_market_data():
    sectors = {
        "Information Technology": "XLK", "Communication Services": "XLC",
        "Financials": "XLF", "Healthcare": "XLV",
        "Consumer Discretionary": "XLY", "Consumer Staples": "XLP",
        "Energy": "XLE", "Industrials": "XLI",
        "Materials": "XLB", "Utilities": "XLU",
        "Real Estate": "XLRE", "Digital Assets": "IBIT"
    }
    
    active_universe = [
        "NVDA", "AMD", "AAPL", "AVGO", "ORCL", "CRM", "PLTR", "SMCI", "ARM",
        "META", "GOOGL", "NFLX", "DIS", "TMUS", "TSLA", "HD", "NKE", "SBUX",
        "GS", "MS", "BAC", "V", "COIN", "HOOD", "MSTR", "MARA", "RIOT",
        "UNH", "ABBV", "ISRG", "VRTX", "XOM", "CVX", "SLB", "OXY", "COP",
        "GE", "CAT", "UBER", "BA", "LMT", "VST", "CEG", "NEE", "FCX", "NEM"
    ]
    
    # Dedicated institutional compounders so Long-Term sleeve always has high-quality picks
    compounder_pool = ["MSFT", "ASML", "AMZN", "LLY", "JPM", "COST"]
    
    all_tickers = ["^VIX"] + list(sectors.values()) + active_universe + compounder_pool
    
    # 1. Single batched download (prevents Yahoo Finance 429 rate limits)
    daily_data = yf.download(all_tickers, period="1mo", group_by="ticker", progress=False, threads=True)
    # 2. Pre-market aware download (captures 4:00 AM - 6:00 AM overnight gaps)
    premarket_data = yf.download(active_universe, period="2d", interval="5m", prepost=True, group_by="ticker", progress=False, threads=True)

    live_data = {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "vix": "Unavailable",
        "sectors": {},
        "todays_top_in_play_tickers": {},
        "core_compounders": {}
    }

    # Extract VIX
    try:
        vix_df = daily_data["^VIX"].dropna()
        if not vix_df.empty:
            live_data["vix"] = round(float(vix_df['Close'].iloc[-1]), 2)
    except Exception:
        pass

    # Extract Sectors
    for name, ticker in sectors.items():
        try:
            df = daily_data[ticker].dropna()
            if len(df) >= 2:
                latest = float(df['Close'].iloc[-1])
                prev = float(df['Close'].iloc[-2])
                five_day = float(df['Close'].iloc[-5]) if len(df) >= 5 else float(df['Close'].iloc[0])
                live_data["sectors"][name] = {
                    "ticker": ticker,
                    "price": round(latest, 2),
                    "1d_change_pct": round(((latest - prev) / prev) * 100, 2),
                    "5d_change_pct": round(((latest - five_day) / five_day) * 100, 2)
                }
        except Exception:
            continue

    # Score Active Universe (incorporating live pre-market price if available)
    scored_tickers = []
    for ticker in active_universe:
        try:
            df = daily_data[ticker].dropna()
            if len(df) >= 5:
                regular_close = float(df['Close'].iloc[-1])
                prev_close = float(df['Close'].iloc[-2])
                
                # Check for live 6:00 AM pre-market price
                current_price = regular_close
                try:
                    pm_df = premarket_data[ticker].dropna()
                    if not pm_df.empty:
                        current_price = float(pm_df['Close'].iloc[-1])
                except Exception:
                    pass

                overnight_gap_pct = ((current_price - regular_close) / regular_close) * 100
                day_change_pct = ((regular_close - prev_close) / prev_close) * 100
                
                avg_vol = float(df['Volume'].iloc[:-1].mean())
                latest_vol = float(df['Volume'].iloc[-1])
                rvol = round(latest_vol / avg_vol, 2) if avg_vol > 0 else 1.0
                
                # Weight both yesterday's momentum + this morning's pre-market gap
                activity_score = (abs(day_change_pct) + (abs(overnight_gap_pct) * 2)) * rvol
                
                scored_tickers.append((activity_score, ticker, {
                    "current_premarket_price": round(current_price, 2),
                    "last_regular_close": round(regular_close, 2),
                    "overnight_gap_pct": round(overnight_gap_pct, 2),
                    "prior_1d_change_pct": round(day_change_pct, 2),
                    "relative_volume_rvol": rvol,
                    "prior_day_high": round(float(df['High'].iloc[-1]), 2),
                    "prior_day_low": round(float(df['Low'].iloc[-1]), 2),
                    "30d_high": round(float(df['High'].max()), 2),
                    "30d_low": round(float(df['Low'].min()), 2)
                }))
        except Exception:
            continue

    scored_tickers.sort(key=lambda x: x[0], reverse=True)
    for _, ticker, metrics in scored_tickers[:12]:
        live_data["todays_top_in_play_tickers"][ticker] = metrics

    # Extract Core Compounders for Long-Term Sleeve
    for ticker in compounder_pool:
        try:
            df = daily_data[ticker].dropna()
            if len(df) >= 5:
                live_data["core_compounders"][ticker] = {
                    "current_price": round(float(df['Close'].iloc[-1]), 2),
                    "30d_high": round(float(df['High'].max()), 2),
                    "30d_low": round(float(df['Low'].min()), 2)
                }
        except Exception:
            continue

    return live_data

try:
    market_reality = harvest_dynamic_market_data()
    
    # Safety check: if Yahoo Finance returned zero tickers, abort before overwriting good file
    if not market_reality["todays_top_in_play_tickers"]:
        raise RuntimeError("Yahoo Finance returned empty dataset. Aborting to protect existing JSON.")

    model = genai.GenerativeModel(
        model_name="gemini-3.8-flash",
        system_instruction="""You are an elite quantitative trading and cognitive performance co-pilot. 
        CRITICAL RULE: Use ONLY the exact prices, dates, and metrics provided in LIVE MARKET DATA. 
        Never invent prices. Output strictly valid JSON.""",
        generation_config={"response_mime_type": "application/json"} 
    )

    prompt = f"""
    Here is today's verified LIVE MARKET DATA (including pre-market action):
    {json.dumps(market_reality, indent=2)}

    Generate today's market intelligence JSON report using ONLY the numbers above:
    - "timestamp": Exact timestamp_utc from data.
    - "macro_context": "market_regime", "volatility_index_vix", "liquidity_condition", "cognitive_bias_alert".
    - "sector_health_scan": All 12 sectors using their real 1d and 5d change.
    - "recommendations": 
        - "day_trading": Pick 3 top movers from 'todays_top_in_play_tickers'. Base entry, stop_loss, target_1, and target_2 strictly around their current_premarket_price, prior_day_high, and prior_day_low.
        - "swing_trading": Pick 3 distinct setups from 'todays_top_in_play_tickers' using their 30d_high and 30d_low.
        - "long_term_investing": Pick 3 compounders from 'core_compounders' using their real current_price.
    """

    response = model.generate_content(prompt)
    
    # Validate that the AI actually returned parseable JSON before overwriting daily_report.json
    parsed_json = json.loads(response.text)
    
    with open("daily_report.json", "w") as f:
        json.dump(parsed_json, f, indent=2)
        
    print("Successfully generated and verified daily_report.json")
    
except Exception as e:
    print(f"CRITICAL PIPELINE FAILURE: {e}", file=sys.stderr)
    sys.exit(1) # Stops GitHub from overwriting your working daily_report.json with an error message
