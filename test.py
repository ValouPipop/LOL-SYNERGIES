import streamlit as st
import requests
import pandas as pd
import time
import json
import plotly.express as px
from github import Github, GithubException

# --- 1. CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="LoL Synergy Pro",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. CSS STYLE "GAMING" ---
st.markdown("""
<style>
    .stApp { background-color: #09090b; color: #ffffff; }
    h1 {
        background: linear-gradient(to right, #00f260, #0575e6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-family: 'Helvetica Neue', sans-serif;
        font-weight: 900;
    }
    .stat-card {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 15px; padding: 20px; text-align: center;
        backdrop-filter: blur(10px);
    }
    .stat-value { font-size: 32px; font-weight: 800; color: #fff; margin: 0; }
    .stat-label { font-size: 12px; text-transform: uppercase; letter-spacing: 1px; color: #a1a1aa; }
    div.stButton > button {
        background: linear-gradient(135deg, #00f260 0%, #0575e6 100%);
        color: white; border: none; padding: 0.7rem 2rem;
        border-radius: 50px; font-weight: bold; width: 100%;
        transition: transform 0.2s;
    }
    div.stButton > button:hover { transform: scale(1.02); }
    .stTextInput input {
        background-color: #18181b !important; border: 1px solid #27272a !important; color: white !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. VALIDATION RIOT & SECRETS ---
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
REPO_NAME = "valoupipop/LOL-SYNERGIES" # ⚠️ TON REPO GITHUB
CACHE_FILE_PATH = "match_database.json"

# --- 4. FONCTIONS GITHUB (Backend Persistant) ---
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
        repo.update_file(CACHE_FILE_PATH, "Auto-update Stats (Bot)", json_str, contents.sha)
    except:
        repo.create_file(CACHE_FILE_PATH, "Init Stats (Bot)", json_str)

# --- 5. FONCTIONS RIOT (Rate Limit + Logique) ---
def make_request(url):
    while True:
        try:
            resp = requests.get(url, headers={"X-Riot-Token": API_KEY})
            if resp.status_code == 200: return resp.json()
            elif resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 10))
                placeholder = st.empty()
                for i in range(wait, 0, -1):
                    placeholder.warning(f"⚡ Refroidissement API... {i}s")
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

def get_new_matches(puuid, last_known_id):
    """
    Récupère uniquement les IDs de matchs plus récents que last_known_id.
    """
    new_matches = []
    start = 0
    found_last = False
    status = st.empty()
    
    while not found_last:
        url = f"https://{REGION_ROUTING}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?queue=420&start={start}&count=100"
        ids = make_request(url)
        
        if not ids: break
        
        for m_id in ids:
            if m_id == last_known_id:
                found_last = True
                break
            new_matches.append(m_id)
        
        status.caption(f"📥 Scan chronologique... {len(new_matches)} nouveaux matchs trouvés.")
        
        if len(ids) < 100 or found_last: break
        start += 100
    
    status.empty()
    # L'API donne du plus récent au plus vieux. On inverse pour traiter chronologiquement.
    new_matches.reverse() 
    return new_matches

def style_winrate(val):
    if val >= 55: color = '#2ecc71'
    elif val <= 45: color = '#e74c3c'
    else: color = '#f1c40f'
    return f'color: {color}; font-weight: bold;'

# --- 6. INTERFACE & SCAN ---
st.title("⚡ LoL Synergy Pro")
st.caption("SCANNER DE SYNERGIES RANKED • STOCKAGE CLOUD • MODE BURST")

if 'df' not in st.session_state: st.session_state.df = None

# Input
col1, col2 = st.columns([3, 1])
with col1:
    pseudo_input = st.text_input("Riot ID", placeholder="Ex: Caps#EUW", label_visibility="collapsed")
with col2:
    start_btn = st.button("LANCER LE SCAN")

# LOGIQUE DE TRAITEMENT (Le Cœur du programme)
if start_btn and pseudo_input:
    if "#" not in pseudo_input: st.error("Format requis: Pseudo#Tag"); st.stop()
    name, tag = pseudo_input.split("#")
    
    with st.status("🔮 Synchronisation des données...", expanded=True) as status:
        # 1. Charger la DB
        db = load_data_from_github()
        player_key = f"{name}#{tag}".lower()
        
        # Init si nouveau joueur
        if player_key not in db:
            db[player_key] = {"last_match_id": None, "stats": {}}
        
        player_data = db[player_key]
        last_id = player_data.get("last_match_id")
        current_stats = player_data.get("stats", {})
        
        # 2. Riot
        puuid = get_puuid(name, tag)
        if not puuid: status.update(label="❌ Joueur introuvable", state="error"); st.stop()
        
        # 3. Récupérer SEULEMENT les nouveaux matchs
        new_ids = get_new_matches(puuid, last_id)
        
        if not new_ids:
            status.update(label="✅ Tout est déjà à jour !", state="complete")
        else:
            st.info(f"🆕 {len(new_ids)} nouvelles parties à analyser.")
            bar = st.progress(0)
            
            for i, m_id in enumerate(new_ids):
                details = make_request(f"https://{REGION_ROUTING}.api.riotgames.com/lol/match/v5/matches/{m_id}")
                time.sleep(0.05)
                bar.progress((i + 1) / len(new_ids))
                
                if not details: continue
                parts = details['info']['participants']
                try: me = next(p for p in parts if p['puuid'] == puuid)
                except: continue
                
                win = me['win']
                
                for p in parts:
                    if p['teamId'] == me['teamId'] and p['puuid'] != puuid:
                        role = p.get('teamPosition', 'UNKNOWN')
                        if role == "UTILITY": role = "SUPPORT"
                        
                        k = f"{p['championName']}_{role}"
                        
                        # Création ou Mise à jour (Incrémentation)
                        if k not in current_stats:
                            current_stats[k] = {'champion': p['championName'], 'role': role, 'games': 0, 'wins': 0}
                        
                        current_stats[k]['games'] += 1
                        if win: current_stats[k]['wins'] += 1
                
                # Mise à jour du dernier ID traité
                player_data["last_match_id"] = m_id

            # Sauvegarde
            player_data["stats"] = current_stats
            db[player_key] = player_data
            
            status.write("💾 Sauvegarde de la base optimisée sur GitHub...")
            save_data_to_github(db)
            status.update(label="✅ Synchronisation terminée !", state="complete")

    # Préparation DataFrame
    data_list = []
    stats_source = db[player_key]["stats"]
    for v in stats_source.values():
        v['losses'] = v['games'] - v['wins']
        v['winrate'] = round((v['wins'] / v['games']) * 100, 1)
        data_list.append(v)
    
    st.session_state.df = pd.DataFrame(data_list)

# --- 7. DASHBOARD VISUEL ---
if st.session_state.df is not None:
    df = st.session_state.df
    total_games = int(df['games'].sum() / 4)
    avg_wr = df[df['games'] > 2]['winrate'].mean() if not df[df['games'] > 2].empty else 0
    
    st.divider()

    # CARTES HTML
    def card(label, value, color="#fff"):
        return f"""<div class="stat-card"><div class="stat-label">{label}</div><div class="stat-value" style="color:{color}">{value}</div></div>"""
    
    c1, c2, c3 = st.columns(3)
    c1.markdown(card("Matchs Analysés", total_games, "#00f260"), unsafe_allow_html=True)
    c2.markdown(card("Alliés Uniques", len(df), "#0575e6"), unsafe_allow_html=True)
    c3.markdown(card("Winrate Moyen", f"{avg_wr:.1f}%", "#00f260" if avg_wr>=50 else "#ff4b4b"), unsafe_allow_html=True)

    st.write("")

    # GRAPHIQUE
    col_graph, col_dummy = st.columns([1, 2])
    with col_graph:
        role_dist = df.groupby('role')['games'].sum().reset_index()
        fig = px.pie(role_dist, values='games', names='role', title='Distribution des Rôles Alliés', hole=0.4,
                     color_discrete_sequence=px.colors.qualitative.Pastel)
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="white", showlegend=False)
        with st.expander("📊 Voir le Graphique", expanded=False):
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # TABLEAUX
    c_filt1, c_filt2 = st.columns(2)
    min_g = c_filt1.slider("Minimum Games", 1, 20, 2)
    roles = ["Tous"] + sorted(df['role'].unique().tolist())
    s_role = c_filt2.selectbox("Rôle", roles)
    
    df_s = df[df['games'] >= min_g]
    if s_role != "Tous": df_s = df_s[df_s['role'] == s_role]

    tab1, tab2, tab3 = st.tabs(["🏆 TOPS & FLOPS", "🔍 DÉTAIL", "📂 DATA"])
    
    with tab1:
        cc1, cc2 = st.columns(2)
        cc1.markdown("##### 🟢 Top Synergies")
        cc1.dataframe(df_s.sort_values(by=['winrate', 'games'], ascending=[False, False]).head(10), 
                     column_order=("champion", "role", "games", "winrate"), hide_index=True, use_container_width=True,
                     column_config={"winrate": st.column_config.ProgressColumn("WR", format="%.0f%%", min_value=0, max_value=100)})
        
        cc2.markdown("##### 🔴 Pires Synergies")
        cc2.dataframe(df_s.sort_values(by=['winrate', 'games'], ascending=[True, False]).head(10), 
                     column_order=("champion", "role", "games", "winrate"), hide_index=True, use_container_width=True,
                     column_config={"winrate": st.column_config.ProgressColumn("WR", format="%.0f%%", min_value=0, max_value=100)})

    with tab2:
        champ = st.selectbox("Champion", sorted(df['champion'].unique()))
        if champ:
            r = df[df['champion'] == champ]
            tg = r['games'].sum()
            wr = round(r['wins'].sum()/tg*100, 1) if tg > 0 else 0
            st.markdown(f"**Games:** {tg} | **Winrate:** {wr}%")
            st.dataframe(r.style.applymap(style_winrate, subset=['winrate']), use_container_width=True, hide_index=True)

    with tab3:
        st.dataframe(df_s.sort_values('games', ascending=False), use_container_width=True, hide_index=True,
                     column_config={"winrate": st.column_config.NumberColumn("WR %", format="%.1f %%")})

st.markdown("<br><center><small style='color:#555'>LoL Synergy Pro isn't endorsed by Riot Games.</small></center>", unsafe_allow_html=True)
