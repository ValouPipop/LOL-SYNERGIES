import streamlit as st
import requests
import pandas as pd
import time
import json
import plotly.express as px # NOUVEAU POUR LES GRAPHIQUES
from github import Github, GithubException

# --- 1. CONFIGURATION ---
st.set_page_config(
    page_title="LoL Synergy Pro",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. CSS ULTRA MODERNE (Gaming UI) ---
st.markdown("""
<style>
    /* FOND ET TEXTE */
    .stApp {
        background-color: #09090b;
        color: #ffffff;
    }
    
    /* TITRE GRADIENT */
    h1 {
        background: linear-gradient(to right, #00f260, #0575e6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-family: 'Helvetica Neue', sans-serif;
        font-weight: 900;
        letter-spacing: -1px;
    }

    /* CARTES DE STATS (GLASSMORPHISM) */
    .stat-card {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 15px;
        padding: 20px;
        text-align: center;
        backdrop-filter: blur(10px);
        transition: transform 0.3s ease, border-color 0.3s ease;
    }
    .stat-card:hover {
        transform: translateY(-5px);
        border-color: #00f260;
        box-shadow: 0 10px 30px -10px rgba(0, 242, 96, 0.3);
    }
    .stat-value {
        font-size: 36px;
        font-weight: 800;
        color: #fff;
        margin: 0;
    }
    .stat-label {
        font-size: 14px;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: #a1a1aa;
        margin-bottom: 5px;
    }

    /* BOUTON SCAN */
    div.stButton > button {
        background: linear-gradient(135deg, #00f260 0%, #0575e6 100%);
        color: white;
        border: none;
        padding: 0.7rem 2rem;
        border-radius: 50px;
        font-weight: bold;
        font-size: 16px;
        box-shadow: 0 4px 15px rgba(5, 117, 230, 0.4);
        transition: all 0.3s ease;
        width: 100%;
    }
    div.stButton > button:hover {
        transform: scale(1.02);
        box-shadow: 0 6px 25px rgba(0, 242, 96, 0.5);
    }

    /* INPUT TEXT */
    .stTextInput input {
        background-color: #18181b !important;
        border: 1px solid #27272a !important;
        color: white !important;
        border-radius: 12px !important;
        padding: 10px 15px !important;
    }
    .stTextInput input:focus {
        border-color: #00f260 !important;
        box-shadow: 0 0 0 2px rgba(0, 242, 96, 0.2) !important;
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
REPO_NAME = "valoupipop/LOL-SYNERGIES"
CACHE_FILE_PATH = "match_database.json"

# --- 4. FONCTIONS BACKEND (IDENTIQUE AVANT) ---
def load_data_from_github():
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        contents = repo.get_contents(CACHE_FILE_PATH)
        return json.loads(contents.decoded_content.decode())
    except: return {}

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

# --- 5. UI PRINCIPALE ---

st.title("⚡ LoL Synergy Pro")
st.caption("ANALYSEUR DE DONNÉES RANKED & SYNERGIES")

if 'df' not in st.session_state: st.session_state.df = None

# Barre de recherche (Design compact)
col1, col2 = st.columns([3, 1])
with col1:
    pseudo_input = st.text_input("Riot ID", placeholder="Ex: Faker#T1", label_visibility="collapsed")
with col2:
    start_btn = st.button("LANCER LE SCAN")

# LOGIQUE DE TRAITEMENT (Scan...)
if start_btn and pseudo_input:
    if "#" not in pseudo_input:
        st.error("Format requis : Pseudo#Tag")
        st.stop()
    name, tag = pseudo_input.split("#")
    
    with st.status("🔮 Synchronisation des données...", expanded=True) as status:
        db = load_data_from_github()
        player_key = f"{name}#{tag}".lower()
        if player_key not in db: db[player_key] = {}
        player_matches_db = db[player_key]
        
        puuid = get_puuid(name, tag)
        if not puuid: status.update(label="❌ Joueur introuvable", state="error"); st.stop()
        
        all_ids = get_all_match_ids(puuid)
        new_ids = [mid for mid in all_ids if mid not in player_matches_db]
        
        if new_ids:
            st.info(f"🆕 {len(new_ids)} nouvelles parties trouvées.")
            bar = st.progress(0)
            for i, m_id in enumerate(new_ids):
                details = make_request(f"https://{REGION_ROUTING}.api.riotgames.com/lol/match/v5/matches/{m_id}")
                time.sleep(0.05)
                bar.progress((i + 1) / len(new_ids))
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
            
            db[player_key] = player_matches_db
            save_data_to_github(db)

        status.update(label="✅ Données à jour !", state="complete")

    # Calcul Stats
    final_stats = {}
    for m_id, data in db[player_key].items():
        win = data['win']
        for ally in data['allies']:
            k = f"{ally['champion']}_{ally['role']}"
            if k not in final_stats: final_stats[k] = {'champion': ally['champion'], 'role': ally['role'], 'games': 0, 'wins': 0}
            final_stats[k]['games'] += 1
            if win: final_stats[k]['wins'] += 1

    data_list = []
    for v in final_stats.values():
        v['losses'] = v['games'] - v['wins']
        v['winrate'] = round((v['wins'] / v['games']) * 100, 1)
        data_list.append(v)
    
    st.session_state.df = pd.DataFrame(data_list)

# --- 6. AFFICHAGE DES RÉSULTATS (C'est ici que ça change !) ---
if st.session_state.df is not None:
    df = st.session_state.df
    total_games = int(df['games'].sum() / 4)
    avg_wr = df[df['games'] > 2]['winrate'].mean() if not df[df['games'] > 2].empty else 0
    unique_allies = len(df)
    
    st.write("") # Spacer

    # --- A. CARTES DE STATS PERSONNALISÉES (HTML/CSS) ---
    colA, colB, colC = st.columns(3)
    
    def stat_card(label, value, color="#ffffff"):
        return f"""
        <div class="stat-card">
            <div class="stat-label">{label}</div>
            <div class="stat-value" style="color: {color}">{value}</div>
        </div>
        """
    
    with colA: st.markdown(stat_card("Matchs Analysés", total_games, "#00f260"), unsafe_allow_html=True)
    with colB: st.markdown(stat_card("Champions Alliés", unique_allies, "#0575e6"), unsafe_allow_html=True)
    with colC: 
        color_wr = "#00f260" if avg_wr >= 50 else "#ff4b4b"
        st.markdown(stat_card("Winrate Moyen (Duo)", f"{avg_wr:.1f}%", color_wr), unsafe_allow_html=True)

    st.write("") # Spacer

    # --- B. GRAPHIQUES (PLOTLY) ---
    # Préparation des données pour le graph
    role_dist = df.groupby('role')['games'].sum().reset_index()
    
    # Graphique en camembert (Roles)
    fig = px.pie(role_dist, values='games', names='role', title='Répartition des Rôles Alliés',
                 color_discrete_sequence=px.colors.qualitative.Pastel)
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="white")
    
    # On affiche le graph dans un expander pour pas prendre toute la place
    with st.expander("📊 Voir la distribution des rôles (Graphique)", expanded=False):
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # --- C. TABLEAUX ---
    # Filtres
    c_filter1, c_filter2 = st.columns(2)
    with c_filter1:
        min_games = st.slider("Filtrer par nombre de games (Min)", 1, 20, 2)
    with c_filter2:
        roles = ["Tous"] + sorted(df['role'].unique().tolist())
        sel_role = st.selectbox("Filtrer par Rôle", roles)

    df_show = df[df['games'] >= min_games]
    if sel_role != "Tous": df_show = df_show[df_show['role'] == sel_role]

    tab1, tab2, tab3 = st.tabs(["🏆 TOPS & FLOPS", "🔍 DÉTAIL CHAMPION", "📂 DATA"])

    with tab1:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("##### 🟢 Synergies Divines")
            top = df_show.sort_values(by=['winrate', 'games'], ascending=[False, False]).head(10)
            st.dataframe(
                top,
                column_order=("champion", "role", "games", "winrate"),
                column_config={
                    "winrate": st.column_config.ProgressColumn("WR", format="%.0f%%", min_value=0, max_value=100),
                    "champion": "Champion", "role": "Poste", "games": "Games"
                },
                use_container_width=True, hide_index=True
            )
        with c2:
            st.markdown("##### 🔴 Synergies Maudites")
            flop = df_show.sort_values(by=['winrate', 'games'], ascending=[True, False]).head(10)
            st.dataframe(
                flop,
                column_order=("champion", "role", "games", "winrate"),
                column_config={
                    "winrate": st.column_config.ProgressColumn("WR", format="%.0f%%", min_value=0, max_value=100),
                    "champion": "Champion", "role": "Poste", "games": "Games"
                },
                use_container_width=True, hide_index=True
            )

    with tab2:
        col_search, col_stats = st.columns([1, 2])
        with col_search:
            search = st.selectbox("Chercher un champion", sorted(df['champion'].unique()))
        
        if search:
            res = df[df['champion'] == search]
            tot_g = res['games'].sum()
            wr = round(res['wins'].sum()/tot_g*100, 1) if tot_g > 0 else 0
            
            with col_stats:
                m1, m2 = st.columns(2)
                st.markdown(f"**Games:** {tot_g} | **Winrate:** <span style='color:{'#00f260' if wr>50 else '#ff4b4b'}'>{wr}%</span>", unsafe_allow_html=True)
            
            st.dataframe(res.style.applymap(style_winrate, subset=['winrate']), use_container_width=True, hide_index=True)

    with tab3:
        st.dataframe(
            df_show.sort_values(by='games', ascending=False),
            column_config={"winrate": st.column_config.NumberColumn("WR %", format="%.1f %%")},
            use_container_width=True, hide_index=True
        )

# Footer
st.markdown("<br><center><small style='color: #444;'>LoL Synergy Pro isn't endorsed by Riot Games.</small></center>", unsafe_allow_html=True)
