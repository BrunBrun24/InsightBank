# InsightBank - Dashboard 📊

**InsightBank** est un outil de gestion et d'analyse financière permettant de transformer des exports bancaires bruts en tableaux de bord interactifs. Le projet permet de centraliser vos flux financiers, de les catégoriser finement et d'obtenir une vision claire de votre santé budgétaire via des rendus HTML dynamiques ou des rapports Excel.

---

## 📸 Aperçu du projet

### Dashboard d'accueil
![Accueil](assets/accueil.png)

### Analyses et Graphiques
| Répartition (Donuts) | Flux (Sankey) |
| :---: | :---: |
| ![Distribution](assets/distribution.png) | ![Sankey](assets/sankey.png) |

---

## 🛠️ Configuration & Utilisation

Pour que l'analyse soit pertinente, vous disposez de plusieurs méthodes pour importer et structurer vos données :

### 1. Import des données
Il n'est pas strictement nécessaire de spécifier une source bancaire pour utiliser l'application. Vous avez trois options :
*   **Source Bancaire automatique** : Sélectionnez l'établissement correspondant à vos fichiers (BNP Paribas supporté nativement). Cela permet au moteur d'extraire automatiquement les données des exports Excel officiels.
*   **Import Excel Universel** : Vous pouvez importer vos données via un fichier Excel créé par vos soins en suivant une structure simple.
*   **Saisie Manuelle** : Ajoutez vos opérations directement au sein de l'application pour un contrôle total et immédiat.

### 2. Architecture des Catégories
Définissez vos propres catégories et sous-catégories (ex: *Alimentation > Boulangerie & Snacks*) pour obtenir des analyses personnalisées.
*   *Note : Le projet supporte une gestion complète des suppressions et ajouts pour coller à vos habitudes de vie.*

| Menu Configuration | Gestion des Catégories |
| :---: | :---: |
| ![Configuration](assets/configuration.png) | ![Categories](assets/configuration_categories.png) |

---

## 📉 Visualisation & Analyse

L'outil génère automatiquement des graphiques d'évolution pour suivre vos dépenses et revenus au fil des mois et des années.

*Évolution globale des flux financiers (Revenus vs Dépenses).*
<video src="https://github.com/user-attachments/assets/63da86e4-b6c0-46cc-a75c-7b29ef818b21" width="100%" controls></video>

*Zoom par catégories et sous-catégories.*
<video src="https://github.com/user-attachments/assets/4ad2a5dc-c363-45b0-8366-ac40f0ee8934" width="100%" controls></video>

---

## 📑 Rapports Excel

En plus de l'interface visuelle, le projet génère un fichier **Budget_2026.xlsx** parfaitement formaté pour ceux qui préfèrent manipuler les données brutes ou conserver une archive statique.

![Rapport Excel](assets/excel.png)

---

## 💡 Aide & Support

Pour toute question sur le fonctionnement de l'application, les formats de fichiers acceptés ou des conseils sur la configuration, n'hésitez pas à consulter le menu Informations directement intégré dans l'interface de l'application.

---

## 🚀 Road Map (Futur du projet)

Actuellement focalisé sur l'analyse des **opérations courantes**, le projet évolue pour devenir une solution de gestion de patrimoine complète :
* ➕ **Module Bourse** : Suivi des placements et investissements (actions, ETF).
* ➕ **Patrimoine Global** : Visualisation consolidée (Comptes courants + Épargne + Bourse).

## 🚀 Installation

```bash
# Cloner le dépôt
git clone [https://github.com/BrunBrun24/InsightBank.git](https://github.com/BrunBrun24/InsightBank.git)

# Installer les dépendances
pip install -r requirements.txt

# Lancer l'application
python src/main.py
