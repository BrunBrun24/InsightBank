from pathlib import Path

import pandas as pd
from jinja2 import Template

from accounts.stock.database.stock_db import StockDB
from accounts.stock.processing.portfolio_tracker import PortfolioTracker
from config import load_config


def to_unix_ms(index: pd.Index) -> list[int]:
    """Convertit l'index temporel Pandas en millisecondes Unix (13 chiffres)."""
    dt_index = pd.to_datetime(index)
    return (dt_index.astype("int64") // 10**6).tolist()


def series_to_highcharts(series: pd.Series) -> list[list[int | float]]:
    if series.empty:
        return []
    clean_series = series.fillna(0.0)
    timestamps = to_unix_ms(clean_series.index)
    return list(zip(timestamps, clean_series.values.tolist()))


def dataframe_to_highcharts(df: pd.DataFrame) -> list[dict]:
    series_list = []
    if df.empty:
        return series_list

    timestamps = to_unix_ms(df.index)

    for col in df.columns:
        clean_col = df[col].fillna(0.0)
        data_points = list(zip(timestamps, clean_col.values.tolist()))
        series_list.append({"name": str(col), "data": data_points})

    return series_list


def dict_df_to_highcharts(dict_df: dict[str, pd.DataFrame]) -> dict[str, dict[str, list]]:
    """Convertit un dict de DataFrames (Ticker -> DataFrame(index=dates_historique, columns=dates_tx))
    en dictionnaire JSON réutilisable par Highcharts.
    """
    result = {}
    for ticker, df in dict_df.items():
        if df.empty:
            continue
        timestamps = to_unix_ms(df.index)
        result[ticker] = {}
        for date_col in df.columns:
            # Transformation de la date de transaction en string ISO
            date_str = str(date_col)[:10]
            clean_col = df[date_col].fillna(0.0)
            # Ne conserver que les points non-nuls (à partir de la date d'achat)
            data_points = [
                [ts, val] for ts, val in zip(timestamps, clean_col.values.tolist()) if pd.notna(val) and val != 0.0
            ]
            result[ticker][date_str] = data_points

    return result


def correlation_to_heatmap(df_corr: pd.DataFrame) -> dict:
    if df_corr.empty:
        return {"categories": [], "data": []}

    categories = df_corr.columns.tolist()
    heatmap_data = []

    for i, row_name in enumerate(categories):
        for j, col_name in enumerate(categories):
            val = float(df_corr.loc[row_name, col_name])
            heatmap_data.append([j, i, val])

    return {"categories": categories, "data": heatmap_data}


def generate_rapport(
    stock_db: StockDB, portfolio_id: int, portfolio_tracker: PortfolioTracker, output_path: str | Path
) -> None:
    # Enregistre le montant du portefeuille
    stock_db.update_portfolio_amount(portfolio_id, portfolio_tracker.portfolio_gross_value.iloc[-1])

    currency = stock_db.get_portfolio_currency(portfolio_id)
    currency_symbol = None
    if currency == "EUR":
        currency_symbol = "€"
    elif currency == "USD":
        currency_symbol = "$"

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "name": stock_db.get_portfolio_name(portfolio_id),
        "currency": currency_symbol,
        "kpis": {
            "sharpe_ratio": portfolio_tracker.sharpe_ratio,
            "sortino_ratio": portfolio_tracker.sortino_ratio,
            "volatility": portfolio_tracker.volatility_portfolio,
            "weighted_average_correlation": portfolio_tracker.weighted_average_correlation,
        },
        "repartition": [
            {"name": ticker, "y": pct, "amount": float(portfolio_tracker.ticker_values[ticker].iloc[-1])}
            for ticker, pct in portfolio_tracker.portfolio_repartition.items()
        ],
        "correlation": correlation_to_heatmap(portfolio_tracker.correlation),
        "timeseries": {
            "portfolio_gross_value": series_to_highcharts(portfolio_tracker.portfolio_gross_value),
            "portfolio_values": series_to_highcharts(portfolio_tracker.portfolio_values),
            "portfolio_cash": series_to_highcharts(portfolio_tracker.portfolio_cash),
            "portfolio_deposit": series_to_highcharts(portfolio_tracker.portfolio_deposit),
            "portfolio_pct": series_to_highcharts(portfolio_tracker.portfolio_pct),
            "portfolio_daily_returns": series_to_highcharts(portfolio_tracker.portfolio_daily_returns),
            "portfolio_monthly_returns": series_to_highcharts(portfolio_tracker.portfolio_monthly_returns),
            "portfolio_total_gains": series_to_highcharts(portfolio_tracker.portfolio_total_gains),
            "portfolio_latent_gain": series_to_highcharts(portfolio_tracker.portfolio_latent_gain),
            "portfolio_dividends": series_to_highcharts(portfolio_tracker.portfolio_dividends),
            "benchmark_pct": series_to_highcharts(portfolio_tracker.benchmark_pct),
        },
        "multiseries": {
            "ticker_investments": dataframe_to_highcharts(portfolio_tracker.ticker_investments),
            "ticker_values": dataframe_to_highcharts(portfolio_tracker.ticker_values),
            "ticker_dividends": dataframe_to_highcharts(portfolio_tracker.ticker_dividends),
            "ticker_latent_gains": dataframe_to_highcharts(portfolio_tracker.ticker_latent_gains),
            "ticker_latent_gains_pct": dataframe_to_highcharts(portfolio_tracker.ticker_latent_gains_pct),
        },
    }

    portfolio_tx_gains, portfolio_tx_pct, benchmark_tx_gains, benchmark_tx_pct = portfolio_tracker.compare_tx

    # Formatage des transactions (Buy & Sell) pour positionner les marqueurs (triangles)
    tx_list = []
    tx = portfolio_tracker.transactions
    if not tx.empty:
        raw_tx = tx.copy()
        trade_tx = raw_tx[raw_tx["type"].isin(["buy", "sell"])]
        for _, row in trade_tx.iterrows():
            tx_list.append(
                {
                    "ticker": row["ticker"],
                    "type": row["type"],
                    "date": str(row["date"])[:10],
                    "timestamp": int(pd.to_datetime(row["date"]).timestamp() * 1000),
                    "amount": float(row["amount"]) if pd.notna(row["amount"]) else 0.0,
                    "shares": float(row["shares"]) if pd.notna(row["shares"]) else 0.0,
                    "price": float(row["price"]) if pd.notna(row["price"]) else 0.0,
                }
            )

    data["benchmark_ticker"] = load_config()["benchmark"]
    data["compare_tx_pct"] = dict_df_to_highcharts(portfolio_tx_pct)
    data["benchmark_tx_pct"] = dict_df_to_highcharts(benchmark_tx_pct)
    data["all_transactions"] = tx_list

    # Lecture du contenu des fichiers JavaScript
    js_dir = Path("src/static/js")
    highcharts_js = (js_dir / "highcharts.js").read_text(encoding="utf-8")
    highcharts_more_js = (js_dir / "highcharts-more.js").read_text(encoding="utf-8")
    heatmap_js = (js_dir / "heatmap.js").read_text(encoding="utf-8")
    treemap_js = (js_dir / "treemap.js").read_text(encoding="utf-8")
    exporting_js = (js_dir / "exporting.js").read_text(encoding="utf-8")

    # Chargement et compilation du template
    template_path = Path("src/static/template/stock.html")
    template = Template(template_path.read_text(encoding="utf-8"))

    # Injection des données ET du code JS dans le HTML
    html_rendu = template.render(
        highcharts_js=highcharts_js,
        highcharts_more_js=highcharts_more_js,
        heatmap_js=heatmap_js,
        treemap_js=treemap_js,
        exporting_js=exporting_js,
        portfolio_data=data,
    )

    output_file.write_text(html_rendu, encoding="utf-8")
