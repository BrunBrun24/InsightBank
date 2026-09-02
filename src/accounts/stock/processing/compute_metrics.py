import numpy as np
import pandas as pd


def monthly_simple_returns(portfolio_gross_value: pd.DataFrame, transactions: pd.DataFrame) -> pd.Series:
    """Calcule le pourcentage de gain/perte brut mensuel du portefeuille."""
    monthly_val = portfolio_gross_value.resample("ME").last()
    monthly_start_val = monthly_val.shift(1).fillna(0.0)
    ext_tx = transactions[transactions["type"].isin(["deposit", "withdrawal"])].copy()

    if not ext_tx.empty:
        ext_tx["date"] = pd.to_datetime(ext_tx["date"])
        ext_tx["net_flow"] = np.where(ext_tx["type"] == "deposit", ext_tx["amount"].abs(), -ext_tx["amount"].abs())
        monthly_flows = (
            ext_tx.groupby("date")["net_flow"].sum().resample("ME").sum().reindex(monthly_val.index, fill_value=0.0)
        )
    else:
        monthly_flows = pd.Series(0.0, index=monthly_val.index)

    monthly_gain_euro = monthly_val - monthly_start_val - monthly_flows
    capital_engaged = monthly_start_val + np.maximum(0.0, monthly_flows)

    with np.errstate(divide="ignore", invalid="ignore"):
        monthly_pct = np.where(capital_engaged > 0.0, (monthly_gain_euro / capital_engaged) * 100, 0.0)

    return pd.Series(monthly_pct, index=monthly_val.index).round(2)


def compute_portfolio_repartition(portfolio_values: pd.DataFrame, ticker_values: pd.DataFrame) -> dict[str, float]:
    total_money = portfolio_values.iloc[-1]
    last_values = ticker_values.iloc[-1]
    active_percentages = ((last_values[last_values > 0] / total_money) * 100).round(2)
    sorted_percentages = active_percentages.sort_values(ascending=False)

    return sorted_percentages.to_dict()


def sharpe_ratio(portfolio_daily_returns: pd.DataFrame, risk_free_rate: float = 0.02) -> float:
    """Calcule le ratio de Sharpe annualisé du portefeuille basé sur le TWR."""
    daily_returns = portfolio_daily_returns.replace([np.inf, -np.inf], np.nan).dropna()

    if daily_returns.empty or len(daily_returns) < 2:
        return 0.0

    rf_daily = (1.0 + risk_free_rate) ** (1 / 252) - 1.0
    excess_returns = daily_returns - rf_daily

    std_dev = daily_returns.std(ddof=1)
    if np.isnan(std_dev) or std_dev == 0.0:
        return 0.0

    sharpe = (excess_returns.mean() / std_dev) * np.sqrt(252)
    return round(float(sharpe), 2)


def sortino_ratio(portfolio_daily_returns: pd.DataFrame, risk_free_rate: float = 0.02) -> float:
    """Calcule le ratio de Sortino annualisé du portefeuille basé sur le TWR."""
    daily_returns = portfolio_daily_returns.replace([np.inf, -np.inf], np.nan).dropna()

    if daily_returns.empty or len(daily_returns) < 2:
        return 0.0

    rf_daily = (1.0 + risk_free_rate) ** (1 / 252) - 1.0
    excess_returns = daily_returns - rf_daily

    # Seuls les rendements sous le taux sans risque comptent comme risque
    downside_diff = np.minimum(excess_returns, 0.0)
    downside_std = np.sqrt(np.mean(downside_diff**2))

    if np.isnan(downside_std) or downside_std == 0.0:
        return 0.0

    sortino = (excess_returns.mean() / downside_std) * np.sqrt(252)
    return round(float(sortino), 2)


def portfolio_percentage_per_day(portfolio_values: pd.DataFrame, transactions: pd.DataFrame) -> pd.Series:
    trade_tx = transactions[transactions["type"].isin(["buy", "sell"])].copy()

    if not trade_tx.empty:
        trade_tx["date"] = pd.to_datetime(trade_tx["date"])
        trade_tx["fee"] = trade_tx["fee"].fillna(0.0)
        trade_tx["net_cashflow"] = np.where(
            trade_tx["type"] == "buy",
            trade_tx["amount"].abs() + trade_tx["fee"].abs(),
            -(trade_tx["amount"].abs() - trade_tx["fee"].abs()),
        )
        daily_cashflows = trade_tx.groupby("date")["net_cashflow"].sum().reindex(portfolio_values.index, fill_value=0.0)
    else:
        daily_cashflows = pd.Series(0.0, index=portfolio_values.index)

    prev_values = portfolio_values.shift(1)
    adjusted_value = portfolio_values - daily_cashflows

    with np.errstate(divide="ignore", invalid="ignore"):
        daily_returns = np.where(
            (prev_values.isna()) | (prev_values == 0.0),
            0.0,
            (adjusted_value / prev_values) - 1.0,
        )

    daily_returns_series = pd.Series(daily_returns, index=portfolio_values.index)
    return daily_returns_series.fillna(0.0)


def calculate_volatility_portfolio(portfolio_daily_returns: pd.DataFrame) -> float:
    """Calcule la volatilité annualisée (%) des rendements quotidiens TWR du portefeuille."""
    daily_returns = portfolio_daily_returns.replace([np.inf, -np.inf], np.nan).dropna()

    if daily_returns.empty or len(daily_returns) < 2:
        return 0.0

    daily_volatility = daily_returns.std()
    annualized_volatility = daily_volatility * np.sqrt(252)

    return round(float(annualized_volatility * 100.0), 2)


def calculate_stocks_correlation_matrix(ticker_investments: pd.DataFrame, ticker_prices: pd.DataFrame) -> pd.DataFrame:
    """Calcule la matrice de corrélation des rendements quotidiens des actions actuellement en portefeuille."""
    current_shares = ticker_investments.iloc[-1]
    active_tickers = current_shares[current_shares > 0].index.tolist()

    if not active_tickers:
        return pd.DataFrame()

    active_prices = ticker_prices[active_tickers]
    daily_returns = active_prices.pct_change()
    corr_matrix = daily_returns.corr(method="pearson")

    return corr_matrix.round(2).fillna(0.0)


def weighted_average_correlation(
    ticker_investments: pd.DataFrame, ticker_prices: pd.DataFrame, ticker_shares: pd.DataFrame
) -> float:
    """Calcule la corrélation moyenne du portefeuille pondérée par la valeur de chaque position."""
    corr = calculate_stocks_correlation_matrix(ticker_investments, ticker_prices)

    if corr.empty or len(corr.columns) < 2:
        return 0.0

    last_prices = ticker_prices[corr.columns].iloc[-1]
    last_shares = ticker_shares[corr.columns].iloc[-1]
    position_values = last_prices * last_shares

    total_value = position_values.sum()
    if total_value <= 0:
        return 0.0

    weights = (position_values / total_value).values
    weights_matrix = np.outer(weights, weights)
    mask = ~np.eye(corr.shape[0], dtype=bool)
    weighted_corr = np.sum(corr.values[mask] * weights_matrix[mask]) / np.sum(weights_matrix[mask])

    return round(float(weighted_corr), 2)


def compute_deposit_evolution(transactions: pd.DataFrame, start_date: str, end_date: str) -> pd.Series:
    tx = transactions[transactions["type"] == "deposit"].copy()
    tx["date"] = pd.to_datetime(tx["date"])

    daily_deposits = tx.groupby("date")["amount"].sum().sort_index()

    start_date = pd.to_datetime(start_date)
    end_date = pd.to_datetime(end_date)
    full_date_range = pd.date_range(start=start_date, end=end_date, freq="D")

    deposit_evolution = daily_deposits.reindex(full_date_range).fillna(0).cumsum()

    return deposit_evolution
