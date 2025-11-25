import streamlit as st
import requests
import pandas as pd
import time
import json
from github import Github, GithubException # Nécessite PyGithub dans requirements.txt

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="LoL Infinite Tracker", page_icon="♾️", layout="wide")

# Récupération des secrets
try:
    API_KEY = st.secrets["RIOT_API_KEY"]
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
except:
    st.error("❌ Les clés API (Riot ou GitHub) sont manquantes dans les Secrets.")
    st.stop()

REGION_ROUTING = "europe"

# Configuration GitHub pour le stockage
REPO_NAME = "valoupipop/LOL-SYNERGIES" # ⚠️ REMPLACE PAR TON "PSEUDO/NOM-DU-REPO"
CACHE_FILE_PATH = "match_database.json" # Le nom du fichier qui sera créé sur GitHub

# --- 2. FONCTIONS GITHUB (SAUVEGARDE & CHARGEMENT) ---

def load_data_from_github():
    """Télécharge la base de données JSON depuis GitHub"""
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        contents = repo.get_contents(CACHE_FILE_PATH)
        json_data = json.loads(contents.decoded_content.decode())
        return json_data
    except:
        # Si le fichier n'existe pas encore (premier lancement), on retourne un dico vide
        return {}

def save_data_to_github(new_data):
    """Met à jour le fichier sur GitHub"""
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(REPO_NAME)
    
    # On convertit les données en texte JSON joli
    json_str = json.dumps(new_data, indent=4)
    
    try:
        # On essaie de récupérer le fichier pour avoir son ID (sha) et le mettre à jour
        contents = repo.get_contents(CACHE_FILE_PATH)
        repo.update_file(CACHE_FILE_PATH, "Auto-update matches (Bot)", json_str, contents.sha)
    except:
        # Si le fichier n'existe pas, on le crée
        repo.create_file(CACHE_FILE_PATH, "Initial create (Bot)", json_str)

# --- 3. FONCTIONS RIOT API ---

def make_request(url):
    while True:
        try:
            resp = requests.get(url, headers={"X-Riot-Token": API_KEY})
            if resp.status_code == 200: return resp.json()
            elif resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 10))
                placeholder = st.empty()
                for i in range(wait, 0, -1):
                    placeholder.warning(f"⚡ Pause forcée Riot (Rate Limit)... {i}s")
                    time.sleep(1)
                placeholder.empty()
                continue
            elif resp.status_code == 403:
                st.error("❌ Clé API expirée."); st.stop()
            else: return None
        except: return None

def get_puuid(name, tag):
    url = f"https://{REGION_ROUTING}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{name}/{tag}"
    data = make_request(url)
    return data['puuid'] if data else None

def get_all_match_ids(puuid):
    """Récupère TOUS les IDs de l'historique Ranked"""
    matches = []
    start = 0
    status = st.empty()
    while True:
        url = f"https://{REGION_ROUTING}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?queue=420&start={start}&count=100"
        ids = make_request(url)
        if not ids: break
        matches.extend(ids)
        status.write(f"📥 Vérification de l'historique... {len(matches)} matchs identifiés.")
        if len(ids) < 100: break
        start += 100
    status.empty()
    return matches

def style_winrate(val):
    if val >= 55: color = '#2ecc71'
    elif val <= 45: color = '#e74c3c'
    else: color = '#f1c40f'
    return f'color: {color}; font-weight: bold;'

# --- 4. INTERFACE & LOGIQUE PRINCIPALE ---

st.title("♾️ LoL Persistent Tracker")
st.markdown("Ce scanner sauvegarde tes matchs sur GitHub. Plus tu l'utilises, plus il devient précis.")

# Initialisation de la session
if 'df' not in st.session_state: st.session_state.df = None

col1, col2 = st.columns([3, 1])
with col1:
    pseudo_input = st.text_input("Riot ID (ex: Caps#EUW)", placeholder="Pseudo#Tag")
with col2:
    st.write("")
    st.write("")
    start_btn = st.button("🚀 Mettre à jour / Scanner", type="primary", use_container_width=True)

if start_btn and pseudo_input:
    name, tag = pseudo_input.split("#")
    
    with st.status("Connexion à la base de données...", expanded=True) as status:
        
        # 1. Charger la base de données existante depuis GitHub
        db = load_data_from_github()
        
        # Si le joueur n'est pas encore dans la base, on lui crée une entrée
        player_key = f"{name}#{tag}".lower() # On utilise le pseudo comme clé principale
        if player_key not in db:
            db[player_key] = {} # Dictionnaire vide pour stocker ses matchs

        player_matches_db = db[player_key]
        st.write(f"📂 Matchs déjà sauvegardés : {len(player_matches_db)}")

        # 2. Récupérer le PUUID et la liste des matchs actuels
        puuid = get_puuid(name, tag)
        if not puuid: st.error("Joueur introuvable"); st.stop()
        
        all_online_ids = get_all_match_ids(puuid)
        
        # 3. FILTRAGE : Quels sont les matchs qu'on n'a PAS encore ?
        new_match_ids = [mid for mid in all_online_ids if mid not in player_matches_db]
        
        if not new_match_ids:
            status.update(label="✅ Aucune nouvelle partie à analyser. Tout est à jour !", state="complete")
        else:
            st.info(f"🆕 {len(new_match_ids)} nouveaux matchs trouvés. Analyse en cours...")
            
            # 4. Boucle d'analyse (seulement sur les nouveaux)
            bar = st.progress(0)
            total_new = len(new_match_ids)
            
            for i, m_id in enumerate(new_match_ids):
                details = make_request(f"https://{REGION_ROUTING}.api.riotgames.com/lol/match/v5/matches/{m_id}")
                time.sleep(0.05)
                bar.progress((i + 1) / total_new)
                
                if not details: continue
                
                parts = details['info']['participants']
                try: me = next(p for p in parts if p['puuid'] == puuid)
                except: continue
                
                # On prépare les données de ce match
                match_data = {
                    "win": me['win'],
                    "allies": []
                }
                
                for p in parts:
                    if p['teamId'] == me['teamId'] and p['puuid'] != puuid:
                        role = p.get('teamPosition', 'UNKNOWN')
                        if role == "UTILITY": role = "SUPPORT"
                        match_data["allies"].append({
                            "champion": p['championName'],
                            "role": role
                        })
                
                # Sauvegarde dans la mémoire locale
                player_matches_db[m_id] = match_data

            # 5. Sauvegarde finale vers GitHub
            status.write("💾 Sauvegarde des nouvelles données sur GitHub...")
            db[player_key] = player_matches_db # On met à jour l'entrée du joueur
            save_data_to_github(db)
            status.update(label="✅ Base de données mise à jour avec succès !", state="complete")

    # --- CALCUL DES STATS (Sur TOUT l'historique : Ancien + Nouveau) ---
    final_stats = {}
    # On relit les données (qui sont maintenant à jour)
    current_matches = db[player_key]
    
    for m_id, data in current_matches.items():
        win = data['win']
        for ally in data['allies']:
            k = f"{ally['champion']}_{ally['role']}"
            if k not in final_stats:
                final_stats[k] = {'champion': ally['champion'], 'role': ally['role'], 'games': 0, 'wins': 0}
            
            final_stats[k]['games'] += 1
            if win: final_stats[k]['wins'] += 1

    # Création DataFrame
    data_list = []
    for v in final_stats.values():
        v['losses'] = v['games'] - v['wins']
        v['winrate'] = round((v['wins'] / v['games']) * 100, 1)
        data_list.append(v)
    
    st.session_state.df = pd.DataFrame(data_list)

# --- AFFICHAGE (Reste identique à la V2) ---
if st.session_state.df is not None:
    df = st.session_state.df
    st.divider()
    st.markdown(f"### 📊 Résultats Consolidés ({int(df['games'].sum()/4)} matchs analysés)")
    
    # ... (Copie ici la partie affichage Onglets/Filtres de la version précédente) ...
    # Je te remets l'affichage basique pour que le code soit complet :
    
    st.sidebar.header("Filtres")
    min_games = st.sidebar.slider("Minimum games :", 1, 20, 2)
    roles = ["Tous"] + sorted(df['role'].unique().tolist())
    sel_role = st.sidebar.selectbox("Rôle Allié :", roles)

    df_show = df[df['games'] >= min_games]
    if sel_role != "Tous": df_show = df_show[df_show['role'] == sel_role]

    tab1, tab2 = st.tabs(["🏆 Tops & Flops", "📂 Tableau Complet"])
    
    with tab1:
        c1, c2 = st.columns(2)
        with c1:
            st.caption("🔥 Meilleures Synergies")
            st.dataframe(df_show.sort_values(by=['winrate', 'games'], ascending=[False, False]).head(10), use_container_width=True)
        with c2:
            st.caption("💀 Pires Synergies")
            st.dataframe(df_show.sort_values(by=['winrate', 'games'], ascending=[True, False]).head(10), use_container_width=True)

    with tab2:
        st.dataframe(df_show.sort_values(by='games', ascending=False), use_container_width=True)

# Disclaimer Riot
st.divider()
st.markdown("<small style='color: gray;'>LoL Infinite Scanner isn't endorsed by Riot Games...</small>", unsafe_allow_html=True)
