import streamlit as st
import requests
import pandas as pd
import time
import json
from github import Github, GithubException

# --- 1. CONFIGURATION DE LA PAGE & THÈME ---
st.set_page_config(
    page_title="LoL Synergy Pro",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. CSS PERSONNALISÉ (LE DESIGN) ---
st.markdown("""
<style>
    /* Fond global */
    .stApp {
        background-color: #0e1117;
        color: #e0e0e0;
    }
    
    /* Titre Principal avec effet Gradient */
    h1 {
        background: -webkit-linear-gradient(45deg, #0AC8B9, #1E90FF);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        font-family: 'Segoe UI', sans-serif;
    }

    /* Style des Boutons */
    div.stButton > button {
        background: linear-gradient(90deg, #0AC8B9 0%, #1E90FF 100%);
        color: white;
        border: none;
        padding: 0.6rem 1.5rem;
        border-radius: 10px;
        font-weight: bold;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(30, 144, 255, 0.4);
    }
    div.stButton > button:hover {
        transform: scale(1.05);
        box-shadow: 0 6px 20px rgba(10, 200, 185, 0.6);
        color: white;
    }

    /* Style des Metrics (Cartes de stats) */
    div[data-testid="stMetric"] {
        background-color: #1a1c24;
        border: 1px solid #2d303e;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
    }
    div[data-testid="stMetricLabel"] {
        color: #0AC8B9;
        font-weight: bold;
    }

    /* Tabs (Onglets) */
    button[data-baseweb="tab"] {
        font-size: 16px;
        font-weight: 600;
    }
    
    /* Input field */
    .stTextInput input {
        background-color: #1a1c24;
        color: white;
        border: 1px solid #444;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. GESTION DES CLÉS ---
if "riot" in st.query_params:
    st.markdown("e7c9e2f7-71b1-4805-b9e6-fb8fe60ef993")
    st.stop()

try:
    API_KEY = st.secrets["RIOT_API_KEY"]
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
except:
    st.error("❌ Les clés API sont manquantes.")
    st.stop()

REGION_ROUTING = "europe"
REPO_NAME = "valoupipop/LOL-SYNERGIES" # ⚠️ VERIFIE BIEN CE NOM
CACHE_FILE_PATH = "match_database.json"

# --- 4. FONCTIONS BACKEND ---

def load_data_from_github():
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        contents = repo.get_contents(CACHE_FILE_PATH)
        return json.loads(contents.decoded_content.decode())
    except:
        return {}

def save_data_to_github(new_data):
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(REPO_NAME)
    json_str = json.dumps(new_data, indent=4)
    try:
        contents = repo.get_contents(CACHE_FILE_PATH)
        repo.update_file(CACHE_FILE_PATH, "Auto-update (Bot)", json_str, contents.sha)
    except:
        repo.create_file(CACHE_FILE_PATH, "Init (Bot)", json_str)

def make_request(url):
    while True:
        try:
            resp = requests.get(url, headers={"X-Riot-Token": API_KEY})
            if resp.status_code == 200: return resp.json()
            elif resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 10))
                placeholder = st.empty()
                for i in range(wait, 0, -1):
                    placeholder.warning(f"⚡ Surcharge Hextech... Refroidissement dans {i}s")
                    time.sleep(1)
                placeholder.empty()
                continue
            elif resp.status_code == 403: st.error("❌ Clé API Expirée"); st.stop()
            else: return None
        except: return None

def get_puuid(name, tag):
    url = f"https://{REGION_ROUTING}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{name}/{tag}"
    data = make_request(url)
    return data['puuid'] if data else None

def get_all_match_ids(puuid):
    matches = []
    start = 0
    status = st.empty()
    while True:
        url = f"https://{REGION_ROUTING}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?queue=420&start={start}&count=100"
        ids = make_request(url)
        if not ids: break
        matches.extend(ids)
        status.caption(f"📥 Scan des archives... {len(matches)} matchs détectés.")
        if len(ids) < 100: break
        start += 100
    status.empty()
    return matches

def style_winrate(val):
    if val >= 55: color = '#2ecc71'
    elif val <= 45: color = '#e74c3c'
    else: color = '#f1c40f'
    return f'color: {color}; font-weight: bold;'

# --- 5. INTERFACE UTILISATEUR ---

st.title("⚡ LoL Synergy Pro")
st.markdown("**Optimise tes Ranked grâce à la Data.** Analyse tes synergies et trouve tes meilleurs duos.")

if 'df' not in st.session_state: st.session_state.df = None

# Zone de recherche stylisée
with st.container():
    col1, col2 = st.columns([3, 1])
    with col1:
        pseudo_input = st.text_input("Riot ID", placeholder="Ex: Caps#EUW", label_visibility="collapsed")
    with col2:
        start_btn = st.button("LANCER L'ANALYSE", use_container_width=True)

# LOGIQUE DE TRAITEMENT
if start_btn and pseudo_input:
    if "#" not in pseudo_input:
        st.error("Format requis : Pseudo#Tag")
        st.stop()

    name, tag = pseudo_input.split("#")
    
    with st.status("🔮 Connexion au Néant...", expanded=True) as status:
        # 1. GitHub Load
        db = load_data_from_github()
        player_key = f"{name}#{tag}".lower()
        if player_key not in db: db[player_key] = {}
        player_matches_db = db[player_key]
        
        # 2. Riot Load
        puuid = get_puuid(name, tag)
        if not puuid: status.update(label="❌ Joueur introuvable", state="error"); st.stop()
        
        all_online_ids = get_all_match_ids(puuid)
        new_match_ids = [mid for mid in all_online_ids if mid not in player_matches_db]
        
        if not new_match_ids:
            status.update(label="✅ Base de données déjà à jour !", state="complete")
        else:
            st.info(f"🆕 {len(new_match_ids)} nouveaux matchs détectés. Analyse en cours...")
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
                
                match_data = {"win": me['win'], "allies": []}
                for p in parts:
                    if p['teamId'] == me['teamId'] and p['puuid'] != puuid:
                        role = p.get('teamPosition', 'UNKNOWN')
                        if role == "UTILITY": role = "SUPPORT"
                        match_data["allies"].append({"champion": p['championName'], "role": role})
                
                player_matches_db[m_id] = match_data

            # Save to GitHub
            status.write("💾 Sauvegarde Cloud...")
            db[player_key] = player_matches_db
            save_data_to_github(db)
            status.update(label="✅ Synchronisation terminée !", state="complete")

    # Calcul Stats
    final_stats = {}
    current_matches = db[player_key]
    for m_id, data in current_matches.items():
        win = data['win']
        for ally in data['allies']:
            k = f"{ally['champion']}_{ally['role']}"
            if k not in final_stats:
                final_stats[k] = {'champion': ally['champion'], 'role': ally['role'], 'games': 0, 'wins': 0}
            final_stats[k]['games'] += 1
            if win: final_stats[k]['wins'] += 1

    data_list = []
    for v in final_stats.values():
        v['losses'] = v['games'] - v['wins']
        v['winrate'] = round((v['wins'] / v['games']) * 100, 1)
        data_list.append(v)
    
    st.session_state.df = pd.DataFrame(data_list)

# --- AFFICHAGE DASHBOARD ---
if st.session_state.df is not None:
    df = st.session_state.df
    total_games = int(df['games'].sum() / 4) # Approx
    
    st.divider()
    
    # 3 CHIFFRES CLÉS EN HAUT
    colA, colB, colC = st.columns(3)
    colA.metric("Matchs Analysés", total_games)
    colB.metric("Champions Alliés Uniques", len(df))
    # Winrate moyen (simple moyenne des winrates pour l'exemple)
    avg_wr = round(df[df['games'] > 2]['winrate'].mean(), 1)
    colC.metric("Winrate Moyen (Duo)", f"{avg_wr}%")

    st.markdown("---")

    # SIDEBAR FILTRES
    st.sidebar.markdown("### 🎛️ Filtres")
    min_games = st.sidebar.slider("Minimum Games", 1, 20, 2)
    roles = ["Tous"] + sorted(df['role'].unique().tolist())
    sel_role = st.sidebar.selectbox("Rôle Allié", roles)

    df_show = df[df['games'] >= min_games]
    if sel_role != "Tous": df_show = df_show[df_show['role'] == sel_role]

    # ONGLETS STYLISÉS
    tab1, tab2, tab3 = st.tabs(["🏆 TOPS & FLOPS", "🔎 DÉTAIL CHAMPION", "📂 DATA EXPLORER"])
    
    with tab1:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### 🔥 Synergies Divines")
            top = df_show.sort_values(by=['winrate', 'games'], ascending=[False, False]).head(10)
            st.dataframe(
                top,
                column_order=("champion", "role", "games", "winrate"),
                column_config={
                    "winrate": st.column_config.ProgressColumn("Winrate", format="%.1f %%", min_value=0, max_value=100, help="Vert = Super Synergie"),
                    "champion": "Champion",
                    "role": "Poste",
                    "games": st.column_config.NumberColumn("Parties")
                },
                use_container_width=True, hide_index=True
            )
        with c2:
            st.markdown("#### 💀 Synergies Maudites")
            flop = df_show.sort_values(by=['winrate', 'games'], ascending=[True, False]).head(10)
            st.dataframe(
                flop,
                column_order=("champion", "role", "games", "winrate"),
                column_config={
                    "winrate": st.column_config.ProgressColumn("Winrate", format="%.1f %%", min_value=0, max_value=100),
                    "champion": "Champion",
                    "role": "Poste",
                    "games": st.column_config.NumberColumn("Parties")
                },
                use_container_width=True, hide_index=True
            )

    with tab2:
        col_search, col_stats = st.columns([1, 2])
        with col_search:
            all_champs = sorted(df['champion'].unique())
            search = st.selectbox("Sélectionner un champion :", all_champs)
        
        if search:
            res = df[df['champion'] == search]
            tot_g = res['games'].sum()
            tot_w = res['wins'].sum()
            wr = round(tot_w/tot_g*100, 1) if tot_g > 0 else 0
            
            with col_stats:
                m1, m2 = st.columns(2)
                m1.metric(f"Games avec {search}", tot_g)
                m2.metric("Winrate Global", f"{wr}%", delta=f"{wr-50}% vs Moyenne" if wr != 50 else None)
            
            st.dataframe(
                res.style.format({"winrate": "{:.1f} %"}).applymap(style_winrate, subset=['winrate']),
                column_order=("role", "games", "wins", "losses", "winrate"),
                use_container_width=True, hide_index=True
            )

    with tab3:
        st.dataframe(
            df_show.sort_values(by='games', ascending=False),
            column_config={
                "champion": "Champion", "role": "Rôle", 
                "games": st.column_config.NumberColumn("Games"),
                "wins": st.column_config.NumberColumn("W"),
                "losses": st.column_config.NumberColumn("L"),
                "winrate": st.column_config.NumberColumn("WR %", format="%.1f %%")
            },
            use_container_width=True, hide_index=True
        )

# FOOTER
st.divider()
st.markdown("<center><small style='color: #555;'>LoL Synergy Pro isn't endorsed by Riot Games...</small></center>", unsafe_allow_html=True)
