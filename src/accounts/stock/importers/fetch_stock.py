from tkinter import messagebox

import pandas as pd
import requests
import yfinance as yf


def fetch_stock_data(db_stock, data: pd.DataFrame | list[str]) -> tuple[dict[str, list], list[dict[str, str]]]:
    """Télécharge et extrait les données requises pour alimenter les tables."""

    if isinstance(data, pd.DataFrame):
        data = data.copy()
        tickers_in_transactions = (
            data["symbol"].dropna()[data["symbol"].astype(str).str.strip() != ""].drop_duplicates().tolist()
        )
    else:
        tickers_in_transactions = data

    isin_ticker_add = []
    stocks_data = []
    prices_data = []
    splits_data = []
    dividends_data = []

    tickers = db_stock.get_tickers()

    for symbol in tickers_in_transactions:
        ticker = get_ticker_from_isin(symbol)

        if ticker is not None:
            temp = {}
            temp["isin"] = symbol
            temp["ticker"] = ticker
            isin_ticker_add.append(temp)
        else:
            continue

        # Si le ticker se trouve déjà dans la bdd
        if ticker in tickers:
            continue

        ticker_obj = yf.Ticker(ticker)
        info = {}

        try:
            info = ticker_obj.info or {}
        except Exception as e:
            messagebox.showinfo(f"Avertissement : Impossible de récupérer les informations pour {symbol} : {e}")
            continue

        company_name = (info.get("longName") or info.get("shortName") or "Unknown Company")[:100]
        currency = (info.get("currency") or "EUR")[:3].upper()
        country = info.get("country")

        if len(symbol) != 12:
            # Extraction sécurisée du code ISIN
            isin = None
            try:
                isin = info.get("isin")
                # Si non présent dans info, tentative isolée de récupération via la propriété .isin
                if not isin:
                    isin = ticker_obj.isin
            except Exception as e:
                messagebox.showinfo(
                    f"Avertissement : Timeout ou échec de récupération du code ISIN pour {symbol} : {e}"
                )
                continue

            if isin == "-" or not isin:
                isin = None
            else:
                isin = str(isin).strip()[:12]
        else:
            isin = symbol

        stocks_data.append((ticker, isin, company_name, currency, country))

        # Extraction des données historiques (Prix, Dividendes, Splits)
        try:
            history = ticker_obj.history(period="max", actions=True, auto_adjust=False)
        except Exception as e:
            messagebox.showinfo(f"Erreur lors du téléchargement de l'historique pour {isin} : {e}")
            continue

        if history.empty:
            continue

        for date_idx, row in history.iterrows():
            record_date = date_idx.strftime("%Y-%m-%d")

            close_price = round(float(row["Close"]), 2)
            prices_data.append((ticker, record_date, close_price))

            dividend_amount = float(row.get("Dividends", 0.0))
            if dividend_amount > 0:
                dividends_data.append((ticker, record_date, round(dividend_amount, 2)))

            split_ratio = float(row.get("Stock Splits", 0.0))
            if split_ratio > 0:
                split_records_ratio = float(split_ratio)
                splits_data.append((ticker, record_date, split_records_ratio))

    return {
        "stock": stocks_data,
        "price": prices_data,
        "stock_split": splits_data,
        "stock_dividend": dividends_data,
    }, isin_ticker_add


def get_ticker_from_isin(isin: str) -> str | None:
    """Recherche le ticker correspondant à un code ISIN via l'API Yahoo Finance."""
    url = f"https://query2.finance.yahoo.com/v1/finance/search?q={isin}"
    headers = {"User-Agent": "Mozilla/5.0"}

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        quotes = data.get("quotes", [])
        if quotes:
            # On retourne le premier ticker trouvé
            return quotes[0].get("symbol")
    return None
