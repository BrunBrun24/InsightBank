import json
import os
from datetime import datetime

CONFIG_PATH = os.path.join("config.json")


def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        default_config = {
            "destination_path": "exports",
            "smart_categorization_enabled": "true",
            "benchmark": "^GSPC",
            "currency": "EUR",
            "database": {
                "db_banking_path": "data/bank_accounts.db",
                "db_stock_path": "data/stock.db",
                "incomes": {
                    "short_label_and_operation_type": {
                        "Remise Chèques": ["Remise Chèques"],
                        "Virement Instantane Reçus": ["Vir Sepa Inst Reçu"],
                    },
                    "categories_subcategories": {
                        "Revenus Professionnels": ["Salaires", "Revenus d'activité", "Primes et Bonus"],
                        "Allocations et Retraites": ["Aides - Allocations", "Pensions"],
                        "Patrimoine et Placements": ["Revenus de placement", "Intérêts", "Loyers"],
                        "Remboursements et Transferts": [
                            "Remboursement",
                            "Remboursement amis",
                            "Cashback",
                            "Virements internes",
                        ],
                        "Autres Revenus": ["Chèques reçus", "Déblocage emprunt", "Virements reçus"],
                    },
                },
                "expenses": {
                    "short_label_and_operation_type": {
                        "Commissions": ["Commissions"],
                        "Paiment CB": ["Facture Carte"],
                        "Virement": ["Vir Cpte a Cpte Reçu", "Virement faveur Tiers"],
                        "Virement Instantane Emis": ["Vir Sepa Inst Emis"],
                        "Virement Interne": ["Vir Cpte a Cpte Emis"],
                    },
                    "categories_subcategories": {
                        "Logement & Factures": [
                            "Loyer / Prêt immo",
                            "Énergie (Eau/Elec/Gaz)",
                            "Assurances / Mutuelle",
                            "Services (Internet/Mobile)",
                        ],
                        "Alimentation": ["Courses / Supermarché", "Restaurants & Fast-food", "Boulangerie & Snacks"],
                        "Transport": ["Carburant & Péage", "Transports en commun / Train", "Entretien & Parking"],
                        "Vie Quotidienne": [
                            "Shopping & Mode",
                            "Santé & Pharmacie",
                            "Hygiène & Beauté",
                            "Cadeaux & Dons",
                        ],
                        "Loisirs & Sorties": [
                            "Sorties (Bars/Cinéma)",
                            "Abonnements (Netflix/Sport)",
                            "Vacances & Week-ends",
                            "Culture & Tech",
                        ],
                        "Famille & Proches": [
                            "Enfants (Scolarité/Garde)",
                            "Aides & Argent prêté",
                            "Dépenses de couple",
                        ],
                        "Épargne & Taxes": ["Investissements", "Impôts & Taxes", "Imprévus & Amendes"],
                    },
                },
            },
            "custom_rules": [],
            "theme": {
                "red": {"fg_color": "#F04949", "hover_color": "#a71d2a"},
                "green": {"fg_color": "#29B68E", "hover_color": "#1A9774"},
                "blue_01": {"fg_color": "#5C5CFF", "hover_color": "#3F3FBF"},
                "blue_02": {"fg_color": "#7E4AF7", "hover_color": "#673ACF"},
                "blue_03": {"fg_color": "#7F6CEB", "hover_color": "#6D5CCC"},
                "magenta": {"fg_color": "#A94AF7", "hover_color": "#933ED8"},
            },
        }
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=4)
        return default_config

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(data):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def update_config_benchmark(benchmark: str):
    if benchmark == "S&P 500":
        benchmark = "^GSPC"
    elif benchmark == "NASDAQ":
        benchmark = "^IXIC"
    elif benchmark == "MSCI World":
        benchmark = "URTH"
    elif benchmark == "CAC 40":
        benchmark = "^FCHI"

    full_config = load_config()
    full_config["benchmark"] = benchmark
    save_config(full_config)


def update_config_currency(currency: str):
    full_config = load_config()
    full_config["currency"] = currency
    save_config(full_config)


def update_config_last_login():
    full_config = load_config()
    full_config["last_login_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_config(full_config)
