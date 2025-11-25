# LoL Synergy Pro ⚡

**LoL Synergy Pro** est une application web d'analyse de données pour **League of Legends**, développée en **Python** utilisant le framework **Streamlit**. Le but du projet est de scanner l'intégralité de l'historique de matchs classés (SoloQ) d'un joueur pour identifier les meilleures synergies (Champions & Rôles alliés) avec lesquelles il obtient le meilleur taux de victoire.

## Fonctionnalités principales

* **Scan Intelligent (Burst Mode) :** Un algorithme optimisé qui respecte les limitations de l'API Riot (Rate Limits) tout en récupérant les matchs le plus rapidement possible.
* **Base de Données Persistante (GitHub Storage) :** Utilisation de l'API GitHub pour stocker l'historique des matchs dans un fichier JSON distant. Cela permet de ne pas re-télécharger les anciens matchs à chaque lancement (Scan Incrémental).
* **Interface UI/UX Moderne :** Design "Gaming" avec effet Glassmorphism, CSS personnalisé, mode sombre et animations.
* **Visualisation Avancée :**
    * Cartes de statistiques globales (Winrate moyen, total games).
    * Graphiques interactifs (Donut Chart via Plotly) pour la répartition des rôles.
    * Tableaux dynamiques avec barres de progression colorées.

## Fonctionnement du Système

Le projet repose sur trois piliers techniques :

1.  **Riot Games API (Extraction) :**
    * Récupération du PUUID via le Riot ID.
    * Récupération des IDs de matchs et des détails de chaque partie.
    * Filtrage exclusif des parties **Ranked Solo/Duo**.
2.  **GitHub API (Stockage) :**
    * Le script agit comme une base de données.
    * Il télécharge le JSON existant au démarrage.
    * Il compare les matchs locaux vs les matchs en ligne pour ne traiter que les nouveaux.
    * Il sauvegarde les nouvelles données automatiquement sur le dépôt.
3.  **Streamlit (Affichage) :**
    * Traitement des données avec Pandas.
    * Génération de l'interface utilisateur interactive en temps réel.

## Installation et Configuration

### Pré-requis

* **Langage :** Python 3.9+
* **Comptes :** Compte Riot Developer (pour la clé API) et Compte GitHub (pour le Token d'accès).

### Étapes d'installation

1.  **Cloner le projet :**
    ```bash
    git clone [https://github.com/ton-pseudo/LOL-SYNERGIES.git](https://github.com/ton-pseudo/LOL-SYNERGIES.git)
    cd LOL-SYNERGIES
    ```

2.  **Installation des dépendances :**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configuration des Secrets :**
    Créez un fichier `.streamlit/secrets.toml` (ou configurez les "Secrets" sur Streamlit Cloud) avec vos clés :
    ```toml
    RIOT_API_KEY = "RGAPI-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    GITHUB_TOKEN = "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    ```

## Utilisation

### 1. Lancement de l'application
En local, lancez la commande suivante dans votre terminal :
```bash
streamlit run app.py
