from datetime import datetime

import numpy as np
import pandas as pd

from accounts.bank.database.bank_db import BankDB
from accounts.heritage.reporting.reporting import export_heritage_to_excel
from accounts.heritage.visualization.visualization import generate_standalone_heritage_report
from accounts.stock.database.stock_db import StockDB
from accounts.stock.processing.portfolio_tracker import PortfolioTracker
from config import load_config


def calculate_heritage(bank_db: BankDB, stock_db: StockDB) -> None:
    target_currency = load_config()["currency"]

    account_df = bank_account(bank_db, stock_db, target_currency)
    portfolios_df = stock_account(stock_db, target_currency)
    if account_df.empty and portfolios_df.empty:
        return

    data = {}
    all_accounts_df = pd.concat([account_df, portfolios_df], axis=1).sort_index().ffill().replace(0, np.nan)
    heritage_series = all_accounts_df.sum(axis=1).replace(0, np.nan)
    account_distribution = calculate_account_distribution(all_accounts_df)
    yearly_growth = calculate_yearly_growth(heritage_series)

    data = {
        "all_accounts_df": all_accounts_df,
        "heritage_series": heritage_series,
        "account_distribution": account_distribution,
        "yearly_growth": yearly_growth,
    }

    if target_currency == "EUR":
        currency_symbol = "€"
    elif target_currency == "USD":
        currency_symbol = "$"

    generate_standalone_heritage_report(data, currency_symbol)
    export_heritage_to_excel(data, currency_symbol)


def bank_account(bank_db: BankDB, stock_db: StockDB, target_currency: str) -> pd.DataFrame:
    bank_accounts = bank_db.get_all_bank_account_currencies()
    account_dfs = []

    for account in bank_accounts:
        operations_df = bank_db.get_account_operations(account["id"])
        if not operations_df.empty:
            operations_df["operation_date"] = pd.to_datetime(operations_df["operation_date"])
            operations_df["account_name"] = account["name"]
            account_dfs.append(operations_df[["operation_date", "account_name", "amount"]])

    if not account_dfs:
        return pd.DataFrame()

    operations_all_df = pd.concat(account_dfs, ignore_index=True)

    start_date = operations_all_df["operation_date"].min()
    end_date = pd.Timestamp.now().normalize()
    full_dates = pd.date_range(start=start_date, end=end_date, freq="D", name="date")

    # Groupby par jour et par compte (pour gérer plusieurs opérations le même jour sur un compte)
    daily_by_account = (
        operations_all_df.groupby(["operation_date", "account_name"])["amount"].sum().unstack(level="account_name")
    )

    # Reindexation sur la grille complète des dates, remplissage et cumul par compte
    account_df = daily_by_account.reindex(full_dates).fillna(0.0).cumsum(axis=0)

    # On convertit les montants avec le taux de change actuel
    for data in bank_accounts:
        source_currency = data["currency"]
        if source_currency != target_currency:
            today_str = datetime.now().strftime("%Y-%m-%d")

            # Tentative avec le ticker direct (ex: EURUSD=X)
            ticker_direct = f"{source_currency}{target_currency}=X"
            rate = stock_db.get_rate(date=today_str, ticker=ticker_direct)

            # Si non trouvé, tentative avec le ticker inverse (ex: USDEUR=X)
            if rate is None:
                ticker_inverse = f"{target_currency}{source_currency}=X"
                inverse_rate = stock_db.get_rate(date=today_str, ticker=ticker_inverse)
                if inverse_rate and inverse_rate != 0:
                    rate = 1.0 / inverse_rate

            # Fallback à 1.0 si aucun taux n'est disponible
            rate = rate or 1.0

            account_df[data["name"]] = (account_df[data["name"]] * rate).round(2)

    return account_df


def stock_account(stock_db: str, target_currency: str) -> pd.DataFrame:
    portfolios = stock_db.get_all_portfolios()

    portfolios_data = {}
    for _, data in portfolios.iterrows():
        portfolio_tracker = PortfolioTracker(stock_db, data["id"])
        portfolio_values = portfolio_tracker.heritage_portfolio_values(target_currency)
        if not portfolio_values.empty:
            portfolios_data[data["name"]] = portfolio_values

    portfolios_df = pd.DataFrame(portfolios_data).sort_index()

    # On convertit les montants avec le taux de change actuel
    for _, data in portfolios.iterrows():
        source_currency = data["currency"]
        if source_currency != target_currency:
            today_str = datetime.now().strftime("%Y-%m-%d")

            # Tentative avec le ticker direct (ex: EURUSD=X)
            ticker_direct = f"{source_currency}{target_currency}=X"
            rate = stock_db.get_rate(date=today_str, ticker=ticker_direct)

            # Si non trouvé, tentative avec le ticker inverse (ex: USDEUR=X)
            if rate is None:
                ticker_inverse = f"{target_currency}{source_currency}=X"
                inverse_rate = stock_db.get_rate(date=today_str, ticker=ticker_inverse)
                if inverse_rate and inverse_rate != 0:
                    rate = 1.0 / inverse_rate

            # Fallback à 1.0 si aucun taux n'est disponible
            rate = rate or 1.0

            portfolios_df[data["name"]] = (portfolios_df[data["name"]] * rate).round(2)

    return portfolios_df


def calculate_account_distribution(all_accounts_df: pd.DataFrame) -> dict[str, dict[str, float]]:
    """Calcule le montant et le pourcentage de chaque compte sur la dernière date disponible."""
    if all_accounts_df.empty:
        return {}

    latest_balances = all_accounts_df.iloc[-1]
    total_amount = latest_balances.sum()

    if total_amount == 0.0:
        return {account: {"amount": 0.0, "percentage": 0.0} for account in latest_balances.index}

    distribution = {}

    for account, amount in latest_balances.items():
        percentage = (amount / total_amount) * 100
        distribution[str(account)] = {
            "amount": round(float(amount), 2),
            "percentage": round(float(percentage), 2),
        }

    return distribution


def calculate_yearly_growth(heritage_series: pd.Series) -> pd.DataFrame:
    """Calcule la valeur en fin d'année, le gain/perte en € et la variation en % par an."""
    if heritage_series.empty:
        return pd.DataFrame(columns=["end_balance", "gain_loss", "percentage_change"])

    # Réchantillonnage annuel (dernière valeur connue de chaque année)
    yearly_df = heritage_series.resample("YE").last().to_frame(name="end_balance")

    # Si le patrimoine commence en cours de première année, on peut inclure la valeur initiale
    first_val = heritage_series.iloc[0]

    # Décalage pour obtenir la valeur de départ de chaque année
    previous_balances = yearly_df["end_balance"].shift(1)
    previous_balances.iloc[0] = first_val  # Pour la première année

    yearly_df["gain_loss"] = (yearly_df["end_balance"] - previous_balances).round(2)

    # Calcul du pourcentage
    safe_base = previous_balances.replace(0, pd.NA)
    percentage_change = ((yearly_df["gain_loss"] / safe_base) * 100).round(2)

    # on met à None partout où la base de départ est négative ou nulle
    percentage_change[previous_balances <= 0] = None

    yearly_df["percentage_change"] = percentage_change
    yearly_df.index = yearly_df.index.year.astype(str)

    return yearly_df
