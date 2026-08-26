import numpy as np
import pandas as pd

from accounts.stock.database.stock_db import StockDB
from config import load_config


class PortfolioTracker:
    def __init__(self, db_stock: StockDB, portfolio_id: int) -> None:
        self.__stock_db = db_stock
        self.__portfolio_id = portfolio_id
        self.__config = load_config()
        self.__benchmark = self.__config["benchmark"]

    def run(self) -> bool:
        self.__transactions = self.__stock_db.get_transactions_by_stock_account(self.__portfolio_id).sort_values(
            by="date"
        )
        if self.__transactions.empty:
            self.__stock_db.update_portfolio_amount(self.__portfolio_id, 0)
            return False

        self.__tickers = self.__transactions["ticker"].dropna().unique().tolist()
        if not self.__tickers:
            deposits = self.__transactions[self.__transactions["type"].isin(["deposit", "withdrawal"])]
            amount = float((deposits["amount"] - deposits["fee"]).sum()) if not deposits.empty else 0.0
            self.__stock_db.update_portfolio_amount(self.__portfolio_id, amount)
            return False
        else:
            self.__tickers.append(self.__benchmark)

        mask = self.__transactions["amount"] == 0
        self.__transactions.loc[mask, "amount"] = (
            self.__transactions.loc[mask, "amount"] + self.__transactions.loc[mask, "fee"]
        )

        self.__start_date = str(self.__transactions.iloc[0]["date"])

        self.__ticker_prices = self.__stock_db.get_tickers_prices(
            self.__portfolio_id, self.__tickers, self.__start_date
        )
        if self.__ticker_prices.empty:
            return False

        self.__end_date = str(self.__ticker_prices.index[-1])
        full_date_range = pd.date_range(start=self.__start_date, end=self.__end_date, freq="D")
        self.__ticker_prices = self.__ticker_prices.reindex(full_date_range).ffill().bfill()

        self.__ticker_splits = self.__stock_db.get_stock_splits(self.__tickers, self.__start_date)
        self.__ticker_shares = self.__calculate_daily_shares()
        self.__ticker_pru = self.__calculate_pru()
        self.__ticker_investments = self.__ticker_investments_evolution()
        self.__portfolio_cash = self.__compute_cash_evolution()["cash_cumulative"]

        # Valorisation boursière du portefeuille
        self.__ticker_values = self.__ticker_shares * self.__ticker_prices
        self.__portfolio_values = self.__ticker_values.sum(axis=1)

        # Dividendes
        self.__ticker_dividends = self.__calculate_cumulative_dividends()

        # Plus-value latente
        self.__ticker_latent_gains = self.__ticker_values - self.__ticker_investments
        self.__portfolio_latent_gain = self.__ticker_latent_gains.sum(axis=1)

        # Plus-value réalisée (ventes + dividendes)
        self.__portfolio_realized_gain = self.__compute_realized_gains()["realized_cumulative"]

        # Plus-value globale du portefeuille (Latente + Réalisée)
        self.__portfolio_total_gains = self.__portfolio_latent_gain + self.__portfolio_realized_gain

        # Valeur totale brute (Titres valorisés + Cash disponible)
        self.__portfolio_gross_value = (self.__portfolio_values + self.__portfolio_cash).ffill()

        # Performances en pourcentage
        self.__ticker_latent_gains_pct = (
            (self.__ticker_latent_gains / self.__ticker_investments.replace(0, np.nan)) * 100
        ).fillna(0)
        self.__portfolio_pct = self.__calculate_portfolio_percentage_change()
        self.__benchmark_pct = self.__calculate_benchmark_pct()
        self.__portfolio_daily_returns = self.__portfolio_percentage_per_day()
        self.__portfolio_monthly_returns = self.__monthly_simple_return()
        self.__portfolio_repartition = self.__compute_portfolio_repartition()

        # Métriques
        self.__correlation = self.__calculate_stocks_correlation_matrix()

        # Calcul des détails de chaque transaction
        tx = self.__transactions[self.__transactions["type"].isin(["buy", "sell"])].copy()
        self.__portfolio_tx_latent_gains, self.__portfolio_tx_pct = self.__transactions_details(tx, False)
        tx["ticker"] = self.__benchmark
        self.__benchmark_tx_latent_gains, self.__benchmark_tx_pct = self.__transactions_details(tx, True)

        return True

    @property
    def ticker_prices(self) -> pd.DataFrame:
        return self.__ticker_prices

    @property
    def ticker_pru(self) -> pd.DataFrame:
        return self.__ticker_pru.round(2)

    @property
    def ticker_shares(self) -> pd.DataFrame:
        return self.__ticker_shares.round(2)

    @property
    def ticker_investments(self) -> pd.DataFrame:
        return self.__ticker_investments.round(2)

    @property
    def portfolio_cash(self) -> pd.Series:
        return self.__portfolio_cash.round(2)

    @property
    def portfolio_deposit(self) -> pd.Series:
        return self.__compute_deposit_evolution().round(2)

    @property
    def ticker_values(self) -> pd.DataFrame:
        return self.__ticker_values.round(2)

    @property
    def portfolio_values(self) -> pd.Series:
        return self.__portfolio_values.round(2)

    @property
    def ticker_dividends(self) -> pd.DataFrame:
        return self.__ticker_dividends.round(2)

    @property
    def portfolio_dividends(self) -> pd.Series:
        return self.__ticker_dividends.sum(axis=1).round(2)

    @property
    def ticker_latent_gains(self) -> pd.DataFrame:
        return self.__ticker_latent_gains.round(2)

    @property
    def portfolio_latent_gain(self) -> pd.Series:
        return self.__portfolio_latent_gain.round(2)

    @property
    def portfolio_total_gains(self) -> pd.Series:
        return self.__portfolio_total_gains.round(2)

    @property
    def portfolio_gross_value(self) -> pd.Series:
        return self.__portfolio_gross_value.round(2)

    @property
    def ticker_latent_gains_pct(self) -> pd.DataFrame:
        return self.__ticker_latent_gains_pct.round(2)

    @property
    def portfolio_pct(self) -> pd.Series:
        return self.__portfolio_pct.round(2)

    @property
    def portfolio_daily_returns(self) -> pd.Series:
        return self.__portfolio_daily_returns.round(2)

    @property
    def portfolio_monthly_returns(self) -> pd.Series:
        return self.__portfolio_monthly_returns.round(2)

    @property
    def portfolio_repartition(self) -> dict[str, float]:
        return self.__portfolio_repartition

    @property
    def volatility_portfolio(self) -> float:
        return self.__calculate_volatility_portfolio()

    @property
    def sharpe_ratio(self) -> float:
        return self.__sharpe_ratio()

    @property
    def sortino_ratio(self) -> float:
        return self.__sortino_ratio()

    @property
    def correlation(self) -> pd.DataFrame:
        return self.__correlation

    @property
    def weighted_average_correlation(self) -> float:
        return self.__weighted_average_correlation()

    @property
    def compare_tx(
        self,
    ) -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame], dict[str, pd.DataFrame], dict[str, pd.DataFrame]]:
        return (
            self.__portfolio_tx_latent_gains,
            self.__portfolio_tx_pct,
            self.__benchmark_tx_latent_gains,
            self.__benchmark_tx_pct,
        )

    @property
    def benchmark_pct(self) -> pd.Series:
        return self.__benchmark_pct

    @property
    def transactions(self) -> pd.DataFrame:
        return self.__transactions

    def __calculate_daily_shares(self) -> pd.DataFrame:
        """Calcule le nombre d'actions quotidien en appliquant le ratio de split à l'historique des actions déjà accumulées."""
        trade_tx = self.__transactions[self.__transactions["type"].isin(["buy", "sell"])].copy()

        if trade_tx.empty:
            return pd.DataFrame(0.0, index=self.__ticker_prices.index, columns=self.__ticker_prices.columns)

        trade_tx["signed_shares"] = np.where(
            trade_tx["type"] == "sell",
            -trade_tx["shares"].abs(),
            trade_tx["shares"].abs(),
        )
        trade_tx["date"] = pd.to_datetime(trade_tx["date"])

        tx_deltas = (
            trade_tx.groupby(["date", "ticker"])["signed_shares"]
            .sum()
            .unstack(fill_value=0.0)
            .reindex(
                index=self.__ticker_prices.index,
                columns=self.__ticker_prices.columns,
                fill_value=0.0,
            )
        )

        split_factors = pd.DataFrame(1.0, index=self.__ticker_prices.index, columns=self.__ticker_prices.columns)
        if not self.__ticker_splits.empty:
            self.__ticker_splits["date"] = pd.to_datetime(self.__ticker_splits["date"])
            for _, row in self.__ticker_splits.iterrows():
                dt, tck, ratio = row["date"], row["ticker"], row["ratio"]
                if dt in split_factors.index and tck in split_factors.columns and ratio > 0:
                    split_factors.loc[dt, tck] = ratio

        daily_shares = pd.DataFrame(0.0, index=self.__ticker_prices.index, columns=self.__ticker_prices.columns)

        for i in range(len(self.__ticker_prices)):
            current_date = self.__ticker_prices.index[i]

            if i == 0:
                daily_shares.iloc[0] = tx_deltas.iloc[0]
            else:
                prev_date = self.__ticker_prices.index[i - 1]
                daily_shares.loc[current_date] = daily_shares.loc[prev_date] + tx_deltas.loc[current_date]

            for ticker in self.__ticker_prices.columns:
                ratio = split_factors.loc[current_date, ticker]
                if ratio != 1.0 and i > 0:
                    past_dates = self.__ticker_prices.index[: i + 1]
                    daily_shares.loc[past_dates, ticker] *= ratio

        return daily_shares.where(daily_shares.abs() >= 1e-3, 0.0)

    def __calculate_cumulative_dividends(self) -> pd.DataFrame:
        """Calcule le cumul des dividendes nets par jour et par ticker à partir des transactions."""
        div_tx = self.__transactions[self.__transactions["type"] == "dividend"].copy()

        if div_tx.empty:
            return pd.DataFrame(0.0, index=self.__ticker_prices.index, columns=self.__ticker_prices.columns)

        div_tx["date"] = pd.to_datetime(div_tx["date"])

        # Montant net du dividende (montant - frais)
        div_tx["net_amount"] = div_tx["amount"] - div_tx["fee"].fillna(0.0)

        daily_divs = (
            div_tx.groupby(["date", "ticker"])["net_amount"]
            .sum()
            .unstack(fill_value=0.0)
            .reindex(index=self.__ticker_prices.index, columns=self.__ticker_prices.columns, fill_value=0.0)
            .cumsum()
        )

        return daily_divs

    def __ticker_investments_evolution(self) -> pd.DataFrame:
        """Calcule l'évolution du montant net investi (au PRU) par ticker par jour."""
        trx = self.__transactions[self.__transactions["type"].isin(["buy", "sell"])].copy()
        if trx.empty:
            return pd.DataFrame(0.0, index=self.__ticker_prices.index, columns=self.__ticker_prices.columns)

        trx["date"] = pd.to_datetime(trx["date"])
        trx = trx.sort_values(by="date")

        invested_df = pd.DataFrame(0.0, index=self.__ticker_prices.index, columns=self.__ticker_prices.columns)

        for ticker in self.__ticker_prices.columns:
            ticker_tx = trx[trx["ticker"] == ticker]
            if ticker_tx.empty:
                continue

            current_invested = 0.0
            current_shares = 0.0
            daily_map = {}

            for current_date, group in ticker_tx.groupby("date"):
                for _, row in group.iterrows():
                    action = row["type"]
                    shares = abs(float(row["shares"]))
                    amount = abs(float(row["amount"]))
                    fee = abs(float(row["fee"])) if pd.notna(row["fee"]) else 0.0

                    if action == "buy":
                        # Ajout des frais au total investi lors d'un achat
                        current_invested += amount + fee
                        current_shares += shares
                    elif action == "sell":
                        if current_shares > 0:
                            pru = current_invested / current_shares
                        else:
                            pru = 0.0

                        current_invested -= shares * pru
                        current_shares -= shares

                        if current_shares < 1e-3:
                            current_shares = 0.0
                            current_invested = 0.0

                daily_map[current_date] = current_invested

            series_invested = pd.Series(daily_map).reindex(self.__ticker_prices.index).ffill().fillna(0.0)

            invested_df[ticker] = series_invested

        invested_df = invested_df.where(self.__ticker_shares > 0.0, 0.0)

        return invested_df

    def __calculate_pru(self) -> pd.DataFrame:
        pru_df = pd.DataFrame(0.0, index=self.__ticker_prices.index, columns=self.__ticker_prices.columns)

        trx = self.__transactions[self.__transactions["type"].isin(["buy", "sell"])].copy()
        if trx.empty:
            return pru_df

        trx["date"] = pd.to_datetime(trx["date"])
        trx = trx.sort_values(by="date")

        split_factors = pd.DataFrame(1.0, index=self.__ticker_prices.index, columns=self.__ticker_prices.columns)
        if not self.__ticker_splits.empty:
            self.__ticker_splits["date"] = pd.to_datetime(self.__ticker_splits["date"])
            for _, row in self.__ticker_splits.iterrows():
                dt, tck, ratio = row["date"], row["ticker"], row["ratio"]
                if dt in split_factors.index and tck in split_factors.columns and ratio > 0:
                    split_factors.loc[dt, tck] = ratio

        for ticker in self.__ticker_prices.columns:
            ticker_tx = trx[trx["ticker"] == ticker]
            current_shares = 0.0
            current_invested = 0.0

            for i, current_date in enumerate(self.__ticker_prices.index):
                split_ratio = split_factors.loc[current_date, ticker]
                if split_ratio != 1.0 and current_shares > 0:
                    current_shares *= split_ratio

                if current_date in ticker_tx["date"].values:
                    day_tx = ticker_tx[ticker_tx["date"] == current_date]

                    for _, row in day_tx.iterrows():
                        action = row["type"]
                        shares = float(row["shares"])
                        amount = float(row["amount"])
                        fee = float(row["fee"]) if pd.notna(row["fee"]) else 0.0

                        if action == "buy":
                            # Ajout des frais au montant investi pour le calcul du PRU
                            current_invested += amount + fee
                            current_shares += shares
                        elif action == "sell":
                            if current_shares > 0:
                                pru_current = current_invested / current_shares
                                current_invested -= shares * pru_current
                                current_shares -= shares

                            if current_shares < 1e-3:
                                current_shares = 0.0
                                current_invested = 0.0

                if current_shares > 0:
                    pru_df.loc[current_date, ticker] = current_invested / current_shares
                else:
                    pru_df.loc[current_date, ticker] = 0.0

        return pru_df.replace(0, np.nan)

    def __compute_realized_gains(self, include_dividends: bool = False) -> pd.DataFrame:
        """Calcule le cumul des plus-values réalisées lors des ventes et y intègre les dividendes."""
        trading_index = self.__ticker_prices.index
        realized_flow = pd.Series(0.0, index=trading_index)

        sells = self.__transactions[self.__transactions["type"] == "sell"].copy()

        if not sells.empty:
            sells["date"] = pd.to_datetime(sells["date"])
            for _, row in sells.iterrows():
                tx_date = row["date"]
                previous_date = tx_date - pd.Timedelta(days=1)
                ticker = row["ticker"]
                amount = float(row["amount"])
                fee = float(row["fee"]) if pd.notna(row["fee"]) else 0.0

                ticker_invested = self.__ticker_investments[ticker]
                valid_invested = ticker_invested.loc[:previous_date].dropna()

                invested_amount = valid_invested.iloc[-1] if not valid_invested.empty else 0.0
                # Plus-value nette de frais de vente
                gain = (amount - fee) - invested_amount

                valid_dates = trading_index[trading_index >= tx_date]
                if not valid_dates.empty:
                    realized_flow.loc[valid_dates[0]] += gain

        if include_dividends:
            div_tx = self.__transactions[self.__transactions["type"] == "dividend"].copy()
            if not div_tx.empty:
                div_tx["date"] = pd.to_datetime(div_tx["date"])
                for _, row in div_tx.iterrows():
                    tx_date = row["date"]
                    amount = float(row["amount"])
                    fee = float(row["fee"]) if pd.notna(row["fee"]) else 0.0
                    net_amount = amount - fee

                    valid_dates = trading_index[trading_index >= tx_date]
                    if not valid_dates.empty:
                        realized_flow.loc[valid_dates[0]] += net_amount

        realized_cumulative = realized_flow.cumsum()

        return pd.DataFrame(
            {
                "realized_flow": realized_flow,
                "realized_cumulative": realized_cumulative,
            },
            index=trading_index,
        )

    def __compute_cash_evolution(self) -> pd.DataFrame:
        tx = self.__transactions.copy()
        tx["date"] = pd.to_datetime(tx["date"])
        tx["fee"] = tx["fee"].fillna(0.0)

        # Application du flux net (frais inclus) selon la nature de la transaction
        def _get_net_cashflow(row: pd.Series) -> float:
            op = row["type"]
            amount = float(row["amount"]) if pd.notna(row["amount"]) else 0.0
            fee = float(row["fee"])

            if op == "buy":
                return -(amount - fee)
            elif op in ("sell", "dividend", "interest", "deposit"):
                return amount - fee
            elif op == "withdrawal":
                return -amount
            return 0.0

        tx["cash_flow"] = tx.apply(_get_net_cashflow, axis=1)
        cash_by_date = tx.groupby("date")["cash_flow"].sum()

        full_date_index = pd.date_range(start=self.__start_date, end=self.__end_date, freq="D")
        cash_by_date = cash_by_date.reindex(full_date_index, fill_value=0)

        result_df = pd.DataFrame(
            {
                "cash_flow": cash_by_date.values,
                "cash_cumulative": cash_by_date.cumsum().values,
            },
            index=full_date_index,
        )
        result_df.index.name = "date"

        return result_df

    def __compute_deposit_evolution(self) -> pd.Series:
        tx = self.__transactions[self.__transactions["type"] == "deposit"].copy()
        tx["date"] = pd.to_datetime(tx["date"])

        daily_deposits = tx.groupby("date")["amount"].sum().sort_index()

        start_date = pd.to_datetime(self.__start_date)
        end_date = pd.to_datetime(self.__end_date)
        full_date_range = pd.date_range(start=start_date, end=end_date, freq="D")

        deposit_evolution = daily_deposits.reindex(full_date_range).fillna(0).cumsum()

        return deposit_evolution

    def __calculate_portfolio_percentage_change(self) -> pd.Series:
        performance_pct = self.__portfolio_total_gains * 100 / self.__initial_invested_amount()
        return performance_pct.fillna(0.0).round(2)

    def __initial_invested_amount(self) -> float:
        tx = self.__transactions.copy()
        tx["date"] = pd.to_datetime(tx["date"])
        tx = tx.sort_values(by="date")

        available_cash = 0.0
        money_invest = 0.0
        invested_cash = 0.0

        shifted_investments = self.__ticker_investments.shift(1).fillna(0.0)

        for _, row in tx.iterrows():
            ticker = row["ticker"]
            amount = float(row["amount"]) if pd.notna(row["amount"]) else 0.0
            fee = float(row["fee"]) if pd.notna(row["fee"]) else 0.0
            op = row["type"]
            dt = row["date"]

            if op == "sell":
                net_sell_amount = amount - fee
                if ticker in shifted_investments.columns and dt in shifted_investments.index:
                    prev_invested = shifted_investments.at[dt, ticker]
                else:
                    prev_invested = 0.0

                if net_sell_amount > prev_invested:
                    money_invest += prev_invested

                available_cash += net_sell_amount

            elif op == "buy":
                total_cost = amount + fee
                if available_cash >= total_cost:
                    available_cash -= total_cost
                else:
                    invested_cash += total_cost - available_cash
                    available_cash = 0.0

                if money_invest >= total_cost:
                    money_invest -= total_cost

        return float(invested_cash + money_invest)

    def __calculate_stocks_correlation_matrix(self) -> pd.DataFrame:
        """Calcule la matrice de corrélation des rendements quotidiens des actions actuellement en portefeuille."""
        current_shares = self.__ticker_investments.iloc[-1]
        active_tickers = current_shares[current_shares > 0].index.tolist()

        if not active_tickers:
            return pd.DataFrame()

        active_prices = self.__ticker_prices[active_tickers]
        daily_returns = active_prices.pct_change()
        corr_matrix = daily_returns.corr(method="pearson")

        return corr_matrix.round(2).fillna(0.0)

    def __weighted_average_correlation(self) -> float:
        """Calcule la corrélation moyenne du portefeuille pondérée par la valeur de chaque position."""
        corr = self.__calculate_stocks_correlation_matrix()

        if corr.empty or len(corr.columns) < 2:
            return 0.0

        last_prices = self.__ticker_prices[corr.columns].iloc[-1]
        last_shares = self.__ticker_shares[corr.columns].iloc[-1]
        position_values = last_prices * last_shares

        total_value = position_values.sum()
        if total_value <= 0:
            return 0.0

        weights = (position_values / total_value).values
        weights_matrix = np.outer(weights, weights)
        mask = ~np.eye(corr.shape[0], dtype=bool)
        weighted_corr = np.sum(corr.values[mask] * weights_matrix[mask]) / np.sum(weights_matrix[mask])

        return round(float(weighted_corr), 2)

    def __portfolio_percentage_per_day(self) -> pd.Series:
        trade_tx = self.__transactions[self.__transactions["type"].isin(["buy", "sell"])].copy()

        if not trade_tx.empty:
            trade_tx["date"] = pd.to_datetime(trade_tx["date"])
            trade_tx["fee"] = trade_tx["fee"].fillna(0.0)
            trade_tx["net_cashflow"] = np.where(
                trade_tx["type"] == "buy",
                trade_tx["amount"].abs() + trade_tx["fee"].abs(),
                -(trade_tx["amount"].abs() - trade_tx["fee"].abs()),
            )
            daily_cashflows = (
                trade_tx.groupby("date")["net_cashflow"].sum().reindex(self.__portfolio_values.index, fill_value=0.0)
            )
        else:
            daily_cashflows = pd.Series(0.0, index=self.__portfolio_values.index)

        prev_values = self.__portfolio_values.shift(1)
        adjusted_value = self.__portfolio_values - daily_cashflows

        with np.errstate(divide="ignore", invalid="ignore"):
            daily_returns = np.where(
                (prev_values.isna()) | (prev_values == 0.0),
                0.0,
                (adjusted_value / prev_values) - 1.0,
            )

        daily_returns_series = pd.Series(daily_returns, index=self.__portfolio_values.index)
        return daily_returns_series.fillna(0.0)

    def __monthly_simple_return(self) -> pd.Series:
        """Calcule le pourcentage de gain/perte brut mensuel du portefeuille."""
        monthly_val = self.__portfolio_gross_value.resample("ME").last()
        monthly_start_val = monthly_val.shift(1).fillna(0.0)
        ext_tx = self.__transactions[self.__transactions["type"].isin(["deposit", "withdrawal"])].copy()

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

    def __compute_portfolio_repartition(self) -> dict[str, float]:
        total_money = self.__portfolio_values.iloc[-1]
        last_values = self.__ticker_values.iloc[-1]
        active_percentages = ((last_values[last_values > 0] / total_money) * 100).round(2)
        sorted_percentages = active_percentages.sort_values(ascending=False)

        return sorted_percentages.to_dict()

    def __calculate_volatility_portfolio(self) -> float:
        """Calcule la volatilité annualisée (%) des rendements quotidiens TWR du portefeuille."""
        daily_returns = self.__portfolio_daily_returns.replace([np.inf, -np.inf], np.nan).dropna()

        if daily_returns.empty or len(daily_returns) < 2:
            return 0.0

        daily_volatility = daily_returns.std()
        annualized_volatility = daily_volatility * np.sqrt(252)

        return round(float(annualized_volatility * 100.0), 2)

    def __sharpe_ratio(self, risk_free_rate: float = 0.02) -> float:
        """Calcule le ratio de Sharpe annualisé du portefeuille basé sur le TWR."""
        daily_returns = self.__portfolio_daily_returns.replace([np.inf, -np.inf], np.nan).dropna()

        if daily_returns.empty or len(daily_returns) < 2:
            return 0.0

        rf_daily = (1.0 + risk_free_rate) ** (1 / 252) - 1.0
        excess_returns = daily_returns - rf_daily

        std_dev = daily_returns.std(ddof=1)
        if np.isnan(std_dev) or std_dev == 0.0:
            return 0.0

        sharpe = (excess_returns.mean() / std_dev) * np.sqrt(252)
        return round(float(sharpe), 2)

    def __sortino_ratio(self, risk_free_rate: float = 0.02) -> float:
        """Calcule le ratio de Sortino annualisé du portefeuille basé sur le TWR."""
        daily_returns = self.__portfolio_daily_returns.replace([np.inf, -np.inf], np.nan).dropna()

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

    def __apply_splits_to_transactions(self, transactions: pd.DataFrame) -> pd.DataFrame:
        """Ajuste les prix d'achat et le nombre d'actions des transactions en fonction des splits survenus après la date de chaque transaction."""
        if transactions.empty or self.__ticker_splits.empty:
            return transactions.copy()

        tx_adjusted = transactions.copy()
        tx_adjusted["date"] = pd.to_datetime(tx_adjusted["date"])
        splits = self.__ticker_splits.copy()
        splits["date"] = pd.to_datetime(splits["date"])

        for idx, row in tx_adjusted.iterrows():
            ticker = row["ticker"]
            tx_date = row["date"]

            ticker_splits = splits[(splits["ticker"] == ticker) & (splits["date"] > tx_date)]

            if not ticker_splits.empty:
                split_factor = ticker_splits["ratio"].prod()

                tx_adjusted.at[idx, "price"] = row["price"] / split_factor
                tx_adjusted.at[idx, "shares"] = row["shares"] * split_factor

        return tx_adjusted

    def __transactions_details(
        self, transactions: pd.DataFrame, is_benchmark: bool
    ) -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame]]:
        """On calcule la performance détaillée pour chaque transaction"""

        transactions = self.__apply_splits_to_transactions(transactions)
        tickers_prices = self.__ticker_prices
        transactions_pct = {}
        transactions_latent_gains = {}
        for ticker in self.__tickers:
            tx_buy_sell = transactions[transactions["ticker"] == ticker]

            if tx_buy_sell.empty:
                continue

            dates = tx_buy_sell["date"].to_list()
            ticker_prices = tickers_prices[ticker]

            ticker_latent_gains_pct = pd.DataFrame(
                index=tickers_prices.index,
                data={date: ticker_prices for date in dates},
            )

            # Calcul du pourcentage
            for date in dates:
                if is_benchmark:
                    buy_price = tickers_prices.loc[date, ticker]
                else:
                    buy_price = tx_buy_sell.loc[tx_buy_sell["date"] == date, "price"].values[0]

                ticker_prices_sub = tickers_prices.loc[tickers_prices.index >= pd.to_datetime(date), ticker]
                ticker_latent_gains_pct[date] = ticker_prices_sub / buy_price

            # Calcul des plus values latentes
            ticker_latent_gains = ticker_latent_gains_pct.copy()
            for date in dates:
                buy_amount = tx_buy_sell.loc[tx_buy_sell["date"] == date, "amount"].values[0]
                ticker_prices_sub = tickers_prices.loc[tickers_prices.index >= pd.to_datetime(date), ticker]
                ticker_latent_gains[date] = buy_amount * ticker_latent_gains[date]

            transactions_pct[ticker] = (ticker_latent_gains_pct * 100) - 100
            transactions_latent_gains[ticker] = ticker_latent_gains

        return transactions_latent_gains, transactions_pct

    def __calculate_benchmark_pct(self) -> pd.Series:
        """Simule l'évolution globale du portefeuille si tous les flux avaient été investis dans le benchmark."""
        trade_tx = self.__transactions[self.__transactions["type"].isin(["buy", "sell"])].copy()
        if trade_tx.empty:
            return pd.Series(0.0, index=self.__ticker_prices.index)

        trade_tx["date"] = pd.to_datetime(trade_tx["date"])
        trade_tx = trade_tx.sort_values(by="date")

        bench_prices = self.__ticker_prices[self.__benchmark]

        current_shares = 0.0
        current_invested = 0.0
        realized_gains = 0.0

        daily_shares = pd.Series(0.0, index=self.__ticker_prices.index)
        daily_invested = pd.Series(0.0, index=self.__ticker_prices.index)
        daily_realized = pd.Series(0.0, index=self.__ticker_prices.index)

        for current_date in self.__ticker_prices.index:
            if current_date in trade_tx["date"].values:
                day_tx = trade_tx[trade_tx["date"] == current_date]

                for _, row in day_tx.iterrows():
                    op = row["type"]
                    amount = float(row["amount"])
                    fee = float(row["fee"]) if pd.notna(row["fee"]) else 0.0
                    b_price = bench_prices.loc[current_date]

                    if op == "buy":
                        total_cost = amount + fee
                        if b_price > 0:
                            shares_bought = total_cost / b_price
                            current_shares += shares_bought
                            current_invested += total_cost

                    elif op == "sell":
                        net_proceeds = amount - fee
                        if b_price > 0:
                            shares_sold = net_proceeds / b_price

                            # Sécurité : Si le benchmark a fortement sous-performé par rapport au portefeuille réel,
                            # le retrait de cash pourrait excéder la valeur totale du portefeuille fantôme.
                            if shares_sold > current_shares:
                                shares_sold = current_shares
                                net_proceeds = shares_sold * b_price

                            if current_shares > 0:
                                pru = current_invested / current_shares
                                gain = net_proceeds - (shares_sold * pru)
                                realized_gains += gain

                                current_invested -= shares_sold * pru
                                current_shares -= shares_sold

                            if current_shares < 1e-3:
                                current_shares = 0.0
                                current_invested = 0.0

            daily_shares.loc[current_date] = current_shares
            daily_invested.loc[current_date] = current_invested
            daily_realized.loc[current_date] = realized_gains

        # Valorisation et calcul de la plus-value totale (Latente + Réalisée)
        benchmark_values = daily_shares * bench_prices
        latent_gains = benchmark_values - daily_invested
        total_gains = latent_gains + daily_realized

        invested_amount = self.__initial_invested_amount()

        if invested_amount > 0:
            benchmark_pct = (total_gains * 100) / invested_amount
        else:
            benchmark_pct = pd.Series(0.0, index=self.__ticker_prices.index)

        return benchmark_pct.fillna(0.0).round(2)
