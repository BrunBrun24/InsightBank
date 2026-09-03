# InsightBank - Dashboard 📊

**InsightBank** est un outil complet de gestion financière et boursière permettant de transformer vos données brutes en tableaux de bord interactifs. Le projet permet de centraliser vos flux bancaires et vos investissements, de catégoriser vos opérations et d'obtenir une vision claire de votre santé financière ainsi que de la performance de vos portefeuilles.

---

![Accueil](https://github.com/user-attachments/assets/d358f64e-6105-477b-abf8-98a8883c057b)

| Configuration | Informations |
| :---: | :---: |
| ![Configuration](https://github.com/user-attachments/assets/f3544fd0-1957-4285-9b4d-e2166d5b5219) | ![Informations](https://github.com/user-attachments/assets/48daf418-0b16-4ab6-bd29-8497f86e246c) |

---

## 🏦 Module Banque

Le module Banque permet de centraliser vos comptes courants, de catégoriser vos opérations et d'analyser vos flux financiers.

* **Importation des données** : Importez facilement vos relevés. Pour une prise en charge automatique, l'établissement **BNP Paribas** est nativement intégré. Il est également possible d'importer vos propres données bancaires venant d'autres établissements via un format générique.
* **Rapports HTML interactifs** : Génération d'un tableau de bord dynamique complet (graphiques de répartition, flux Sankey, suivi mensuel) téléchargeable pour une consultation hors-ligne.
* **Bilans Excel complets** : Exportation d'un rapport complet récapitulant l'ensemble de vos revenus et dépenses par catégories et sous-catégories.

### Rendu interactif HTML
<video src="https://github.com/user-attachments/assets/70e50e79-b0e9-49a9-9c76-91c67dc167f8" width="100%" controls></video>

### Rapport Excel
![Rapport Excel Banque](https://github.com/user-attachments/assets/98bee0d9-e78a-4e7b-9c6f-59d5931f1ddf)

---

## 📈 Module Bourse

Le module Bourse permet de suivre la performance globale de vos placements, d'analyser la répartition de vos actifs et de comparer vos rendements à un indice de référence (Benchmark).

* **Importation des données** : Le courtier **Trade Republic** est pris en charge automatiquement à partir de vos exports de transactions. Vous pouvez aussi importer les données d'autres courtiers via un fichier personnalisé.
* **Rapports HTML interactifs** : Analyse visuelle et dynamique de votre portefeuille, avec graphiques de performances cumulées et comparaison au benchmark, directement téléchargeables.
* **Bilans Excel complets** : Génération d'un fichier Excel détaillé comprenant le tableau de bord, l'état des positions ouvertes, l'historique complet des transactions et la matrice de corrélation des rendements.

### Rendu interactif HTML
<video src="https://github.com/user-attachments/assets/4a04e7a4-1d64-4f33-a661-ef441625efb8" width="100%" controls></video>

### Rapport Excel
| Tableau de Bord Portefeuille | Détail des Positions Ouvertes |
| :---: | :---: |
| ![Dashboard Bourse Excel](https://github.com/user-attachments/assets/c985e596-e0b2-445c-85e0-92dcb15da374) | ![Positions Bourse Excel](https://github.com/user-attachments/assets/a2239475-88b6-447b-a14b-a186cf203874) |
| Transactions du Portefeuille | Matrice de Corrélation  |
| ![Transactions Bourse Excel](https://github.com/user-attachments/assets/131d9100-04fd-49b0-9cc2-6e2eb56daff4) | ![Corrélation Bourse Excel](https://github.com/user-attachments/assets/12e96d19-ab56-494c-9c88-75df709868aa) |

---

## 💰 Module Patrimoine Global

Le module Patrimoine Global permet de consolider l'ensemble de vos avoirs financiers en un seul et unique endroit pour obtenir une vision macroéconomique de votre patrimoine.

* **Vue consolidée** : Regroupe automatiquement l'ensemble de vos comptes bancaires et de vos portefeuilles d'investissement.
* **Bilans détaillés et globaux** : Visualisez un bilan séparé pour vos liquidités bancaires, un bilan pour vos portefeuilles boursiers, ainsi qu'un bilan global combinant l'intégralité de votre patrimoine net.
* **Support Multidevise** : Choisissez librement la devise de votre choix pour afficher et convertir l'ensemble des valorisations de votre patrimoine.
* **Rapports HTML interactifs & Bilans Excel** : Retrouvez le même niveau d'interactivité graphique et d'exportation de données détaillées pour suivre l'évolution de vos actifs dans le temps.

### Rendu interactif HTML
<video src="https://github.com/user-attachments/assets/f106d3e3-7a7f-40dc-aa9f-5abf831fbd93" width="100%" controls></video>

### Rapport Excel
![Rapport Excel Patrimoine](https://github.com/user-attachments/assets/89199ca2-e6b0-45d9-b4e2-2630f560381c)

---

## 💡 Aide & Guide d'importation

Pour savoir exactement comment exporter et importer vos données (formats attendus, structures des colonnes pour BNP Paribas, Trade Republic ou fichiers personnalisés) ou pour configurer vos règles d'automatisation, consultez directement la page **Informations** accessible dans le menu latéral de l'application.

---

## 🔒 Confidentialité & Sécurité

**InsightBank** a été entièrement conçue pour garantir une confidentialité absolue :
* **Stockage 100% Local** : Toutes vos données financières, transactions et configurations restent stockées uniquement sur votre propre ordinateur.
* **Aucun tiers ni serveur distant** : Aucune donnée n'est transmise ou enregistrée sur un serveur externe. Vous êtes la seule personne à y avoir accès.

---

## 📄 Licence & Avertissement

Ce projet est distribué sous licence **MIT**. Vous êtes libre de l'utiliser, de le modifier et de le redistribuer.

> ⚠️ **Avertissement concernant Highcharts :**  
> Ce projet intègre la bibliothèque **Highcharts** pour le rendu des graphiques interactifs HTML. Highcharts n'est pas sous licence MIT et reste la propriété de son éditeur. Si vous souhaitez réutiliser, modifier ou redistribuer ce projet, il vous appartient de vous conformer aux termes de la [licence Highcharts](https://www.highcharts.com/license) (usage strictement personnel/non-commercial ou acquisition d'une licence commerciale selon votre cas).

---

## 💻 Prérequis techniques

* **Python** : Version **3.10** ou supérieure recommandée.
* Un environnement virtuel (`venv`) est fortement conseillé pour isoler les dépendances du projet.

---

## 🚀 Installation

```bash
# Cloner le dépôt
git clone [https://github.com/BrunBrun24/InsightBank.git](https://github.com/BrunBrun24/InsightBank.git)

# Installer les dépendances
pip install -r requirements.txt

# Lancer l'application
python src/main.py
