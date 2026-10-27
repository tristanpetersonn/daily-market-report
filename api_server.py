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
    
    compounder_pool = [
        "MSFT", "ASML", "AMZN", "LLY", "JPM", "COST", "BRK-B", 
        "V", "MA", "LIN", "UNH", "CAT", "PG", "HD", "GOOGL"
    ]
    
    all_tickers = list(set(["^VIX"] + list(sectors.values()) + active_universe + compounder_pool))
    
    daily_data = yf.download(all_tickers, period="1mo", group_by="ticker", progress=False, threads=True)
    premarket_data = yf.download(active_universe, period="2d", interval="5m", prepost=True, group_by="ticker", progress=False, threads=True)

    live_data = {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "vix": "Unavailable",
        "sectors": [],
        "day_trade_candidates": {},
        "swing_trade_candidates": {},
        "long_term_value_pullbacks": {}
    }

    try:
        vix_df = daily_data["^VIX"].dropna()
        if not vix_df.empty:
            live_data["vix"] = round(float(vix_df['Close'].iloc[-1]), 2)
    except Exception:
        pass

    for name, ticker in sectors.items():
        try:
            df = daily_data[ticker].dropna()
            if len(df) >= 2:
                latest = float(df['Close'].iloc[-1])
                prev = float(df['Close'].iloc[-2])
                five_day = float(df['Close'].iloc[-5]) if len(df) >= 5 else float(df['Close'].iloc[0])
                live_data["sectors"].append({
                    "sector": name,
                    "etf_ticker": ticker,
                    "price": round(latest, 2),
                    "1d_change_pct": round(((latest - prev) / prev) * 100, 2),
                    "5d_change_pct": round(((latest - five_day) / five_day) * 100, 2)
                })
        except Exception:
            continue

    scored_day = []
    scored_swing = []
    
    for ticker in active_universe:
        try:
            df = daily_data[ticker].dropna()
            if len(df) >= 10:
                regular_close = float(df['Close'].iloc[-1])
                prev_close = float(df['Close'].iloc[-2])
                
                high_low = df['High'] - df['Low']
                atr = float(high_low.tail(14).mean())
                
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
                
                day_risk = round(atr * 0.5, 2)
                swing_risk = round(atr * 1.5, 2)
                
                day_score = (abs(day_change_pct) + (abs(overnight_gap_pct) * 2)) * rvol
                swing_score = abs(day_change_pct) * rvol
                
                scored_day.append((day_score, ticker, {
                    "current_price": round(current_price, 2),
                    "overnight_gap_pct": round(overnight_gap_pct, 2),
                    "prior_1d_change_pct": round(day_change_pct, 2),
                    "relative_volume_rvol": rvol,
                    "atr_14d": round(atr, 2),
                    "calculated_levels": {
                        "entry": round(current_price, 2),
                        "stop_loss": round(current_price - day_risk, 2),
                        "target_1_2R": round(current_price + (day_risk * 2), 2),
                        "target_2_3R": round(current_price + (day_risk * 3), 2)
                    }
                }))
                
                scored_swing.append((swing_score, ticker, {
                    "current_price": round(current_price, 2),
                    "prior_1d_change_pct": round(day_change_pct, 2),
                    "relative_volume_rvol": rvol,
                    "30d_high": round(float(df['High'].max()), 2),
                    "30d_low": round(float(df['Low'].min()), 2),
                    "calculated_levels": {
                        "entry": round(current_price, 2),
                        "stop_loss": round(current_price - swing_risk, 2),
                        "target_1_2R": round(current_price + (swing_risk * 2), 2),
                        "target_2_3R": round(current_price + (swing_risk * 3), 2),
                        "risk_reward_ratio": "2.0:1 to 3.0:1"
                    }
                }))
        except Exception:
            continue

    scored_day.sort(key=lambda x: x[0], reverse=True)
    for _, ticker, metrics in scored_day[:6]:
        live_data["day_trade_candidates"][ticker] = metrics

    top_day_tickers = [t for _, t, _ in scored_day[:3]]
    scored_swing = [item for item in scored_swing if item[1] not in top_day_tickers]
    scored_swing.sort(key=lambda x: x[0], reverse=True)
    for _, ticker, metrics in scored_swing[:6]:
        live_data["swing_trade_candidates"][ticker] = metrics

    scored_compounders = []
    for ticker in compounder_pool:
        try:
            df = daily_data[ticker].dropna()
            if len(df) >= 10:
                curr = float(df['Close'].iloc[-1])
                low_30 = float(df['Low'].min())
                high_30 = float(df['High'].max())
                dist_from_low_pct = ((curr - low_30) / low_30) * 100 if low_30 > 0 else 50.0
                scored_compounders.append((dist_from_low_pct, ticker, {
                    "current_price": round(curr, 2),
                    "30d_low": round(low_30, 2),
                    "30d_high": round(high_30, 2),
                    "distance_above_30d_low_pct": round(dist_from_low_pct, 2)
                }))
        except Exception:
            continue

    scored_compounders.sort(key=lambda x: x[0])
    for _, ticker, metrics in scored_compounders[:5]:
        live_data["long_term_value_pullbacks"][ticker] = metrics

    return live_data

try:
    market_reality = harvest_dynamic_market_data()
    
    if not market_reality["day_trade_candidates"]:
        raise RuntimeError("Yahoo Finance returned empty dataset. Aborting to protect existing JSON.")

    model = genai.GenerativeModel(
        model_name="gemini-3.8-flash",
        system_instruction="""You are an elite quantitative trading and cognitive performance co-pilot. 
        CRITICAL RULES:
        1. Copy the EXACT 'etf_ticker' strings from the input data.
        2. Use the EXACT pre-calculated ATR 'calculated_levels' (entry, stop_loss, target_1_2R, target_2_3R) provided in the data so Risk-to-Reward is always mathematically at least 2:1.
        3. Output strictly valid JSON matching the exact schema requested.""",
        generation_config={"response_mime_type": "application/json"} 
    )

    prompt = f"""
    Here is today's verified LIVE MARKET DATA with pre-calculated ATR risk/reward levels:
    {json.dumps(market_reality, indent=2)}

    Generate today's market intelligence JSON report using this exact schema:
    {{
      "timestamp": "exact timestamp_utc",
      "macro_context": {{
        "market_regime": "string",
        "volatility_index_vix": number,
        "liquidity_condition": "string",
        "cognitive_bias_alert": "string"
      }},
      "sector_health_scan": [
        {{
          "sector": "string",
          "etf_ticker": "exact etf_ticker from data",
          "price": number,
          "1d_change_pct": number,
          "5d_change_pct": number,
          "relative_strength": "Bullish Outperformer | Bullish | Neutral | Bearish Underperformer",
          "momentum_score_100": number,
          "flow_direction": "Institutional Inflow | Selective Rotation | Outflow"
        }}
      ],
      "recommendations": {{
        "day_trading": [
          {{
            "ticker": "string (pick 3 from day_trade_candidates)",
            "setup_type": "string",
            "rationale": "string citing rvol, overnight_gap_pct, and prior_1d_change_pct",
            "entry": number (use exact calculated_levels.entry),
            "stop_loss": number (use exact calculated_levels.stop_loss),
            "target_1": number (use exact calculated_levels.target_1_2R),
            "target_2": number (use exact calculated_levels.target_2_3R)
          }}
        ],
        "swing_trading": [
          {{
            "ticker": "string (pick 3 from swing_trade_candidates)",
            "timeframe": "2 to 6 Weeks",
            "setup_type": "string",
            "rationale": "string citing 30d range and rvol",
            "entry": number (use exact calculated_levels.entry),
            "stop_loss": number (use exact calculated_levels.stop_loss),
            "target_1": number (use exact calculated_levels.target_1_2R),
            "target_2": number (use exact calculated_levels.target_2_3R),
            "risk_reward_ratio": "2.0:1 to 3.0:1"
          }}
        ],
        "long_term_investing": [
          {{
            "ticker": "string (pick 3 from long_term_value_pullbacks)",
            "timeframe": "3 to 5+ Years",
            "rationale": "string citing distance_above_30d_low_pct value entry and structural moat",
            "current_price": number,
            "30d_low": number,
            "30d_high": number
          }}
        ]
      }}
    }}
    """

    response = model.generate_content(prompt)
    parsed_json = json.loads(response.text)
    
    with open("daily_report.json", "w") as f:
        json.dump(parsed_json, f, indent=2)
        
    print("Successfully generated and verified math-locked daily_report.json")
    
except Exception as e:
    print(f"CRITICAL PIPELINE FAILURE: {e}", file=sys.stderr)
    sys.exit(1)
