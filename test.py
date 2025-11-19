import streamlit as st
import requests
import pandas as pd
import time

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="LoL Ultimate Scanner", page_icon="♾️", layout="wide")

# --- GESTION DE LA CLÉ API ---
try:
    API_KEY = st.secrets["RIOT_API_KEY"]
except:
    API_KEY = "RGAPI-6a35e62f-fe71-4584-a17c-db59549326f3" 

REGION_ROUTING = "europe"

# --- MOTEUR API (BURST MODE) ---
def make_request(url):
    while True:
        try:
            resp = requests.get(url, headers={"X-Riot-Token": API_KEY})
            if resp.status_code == 200: return resp.json()
            elif resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 10))
                with st.empty():
                    for i in range(wait, 0, -1):
                        st.warning(f"⚡ Optimisation des requêtes... Reprise dans {i}s...")
                        time.sleep(1)
                continue
            elif resp.status_code == 403:
                st.error("❌ Clé API expirée."); st.stop()
            else: return None
        except: return None

def get_puuid(name, tag):
    url = f"https://{REGION_ROUTING}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{name}/{tag}"
    data = make_request(url)
    return data['puuid'] if data else None

def get_matches(puuid):
    matches = []
    start = 0
    status = st.empty()
    while True:
        url = f"https://{REGION_ROUTING}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?queue=420&start={start}&count=100"
        ids = make_request(url)
        if not ids: break
        matches.extend(ids)
        status.write(f"📥 Récupération de l'historique... {len(matches)} matchs trouvés.")
        if len(ids) < 100: break
        start += 100
    status.empty()
    return matches

def style_winrate(val):
    if val >= 55: color = '#2ecc71' # Vert
    elif val <= 45: color = '#e74c3c' # Rouge
    else: color = '#f1c40f' # Jaune
    return f'color: {color}; font-weight: bold;'

# --- INTERFACE PRINCIPALE ---
st.title("♾️ LoL Full Season Scanner")

# 1. BARRE DE RECHERCHE (Scan du joueur)
if 'df' not in st.session_state:
    st.session_state.df = None

col1, col2 = st.columns([3, 1])
with col1:
    pseudo_input = st.text_input("Riot ID (ex: Caps#EUW)", placeholder="Pseudo#Tag")
with col2:
    st.write("")
    st.write("")
    start_btn = st.button("🚀 Lancer le Scan", type="primary", use_container_width=True)

# --- LOGIQUE DE SCAN ---
if start_btn and pseudo_input:
    if "#" not in pseudo_input:
        st.error("Format invalide. Utilise Pseudo#Tag")
        st.stop()
    
    name, tag = pseudo_input.split("#")
    stats = {}

    with st.status("Analyse en cours...", expanded=True) as status:
        puuid = get_puuid(name, tag)
        if not puuid: st.error("Joueur introuvable"); st.stop()

        match_ids = get_matches(puuid)
        total = len(match_ids)
        if total == 0: st.error("Aucune Ranked trouvée"); st.stop()

        # Estimation temps
        cycles = (total - 1) // 100
        est = "Moins d'une minute" if cycles == 0 else f"Env. {cycles*2} min"
        st.info(f"⏱️ Temps estimé : {est} ({total} matchs)")

        bar = st.progress(0)
        for i, m_id in enumerate(match_ids):
            details = make_request(f"https://{REGION_ROUTING}.api.riotgames.com/lol/match/v5/matches/{m_id}")
            time.sleep(0.05) # Burst
            bar.progress((i + 1) / total)
            
            if not details: continue
            parts = details['info']['participants']
            try: me = next(p for p in parts if p['puuid'] == puuid)
            except: continue
            
            for p in parts:
                if p['teamId'] == me['teamId'] and p['puuid'] != puuid:
                    role = p.get('teamPosition', 'UNKNOWN')
                    if role == "UTILITY": role = "SUPPORT"
                    
                    # On stocke proprement
                    k = f"{p['championName']}_{role}"
                    if k not in stats: 
                        stats[k] = {'champion': p['championName'], 'role': role, 'games': 0, 'wins': 0}
                    stats[k]['games'] += 1
                    if me['win']: stats[k]['wins'] += 1

        status.update(label="✅ Terminé !", state="complete")

    # Création du DataFrame
    data_list = []
    for v in stats.values():
        v['losses'] = v['games'] - v['wins']
        v['winrate'] = round((v['wins'] / v['games']) * 100, 1)
        data_list.append(v)
    
    st.session_state.df = pd.DataFrame(data_list)

# --- AFFICHAGE DES RÉSULTATS (Si le scan est fait) ---
if st.session_state.df is not None:
    df = st.session_state.df
    
    st.divider()
    st.markdown(f"### 📊 Résultats de l'analyse ({int(df['games'].sum()/4)} matchs)")

    # --- FILTRES DYNAMIQUES (Sidebar) ---
    st.sidebar.header("Filtres d'affichage")
    min_games = st.sidebar.slider("Minimum de games ensemble :", 1, 20, 2)
    roles = ["Tous"] + sorted(df['role'].unique().tolist())
    sel_role = st.sidebar.selectbox("Filtrer par Rôle :", roles)

    # Application filtres
    df_show = df[df['games'] >= min_games]
    if sel_role != "Tous":
        df_show = df_show[df_show['role'] == sel_role]

    # --- ONGLETS ---
    tab1, tab2, tab3 = st.tabs(["🏆 Tops & Flops", "🔍 Recherche Champion", "📂 Tableau Complet"])

    # ONGLET 1 : DASHBOARD
    with tab1:
        c1, c2 = st.columns(2)
        with c1:
            st.caption("🔥 Meilleures Synergies")
            top = df_show.sort_values(by=['winrate', 'games'], ascending=[False, False]).head(10)
            st.dataframe(top[['champion', 'role', 'games', 'winrate']], use_container_width=True, hide_index=True,
                         column_config={"winrate": st.column_config.ProgressColumn("Winrate", format="%.1f %%", min_value=0, max_value=100)})
        with c2:
            st.caption("💀 Pires Synergies")
            flop = df_show.sort_values(by=['winrate', 'games'], ascending=[True, False]).head(10)
            st.dataframe(flop[['champion', 'role', 'games', 'winrate']], use_container_width=True, hide_index=True,
                         column_config={"winrate": st.column_config.ProgressColumn("Winrate", format="%.1f %%", min_value=0, max_value=100)})

    # ONGLET 2 : RECHERCHE (C'est ici que tu peux chercher un champion !)
    with tab2:
        st.write("Tape le nom d'un champion pour voir vos stats ensemble.")
        all_champs = sorted(df['champion'].unique())
        search = st.selectbox("Champion :", all_champs)
        
        if search:
            res = df[df['champion'] == search]
            tot_g = res['games'].sum()
            tot_w = res['wins'].sum()
            wr = round(tot_w/tot_g*100, 1)
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Games", tot_g)
            m2.metric("Winrate Global", f"{wr}%")
            
            st.dataframe(res[['role', 'games', 'wins', 'losses', 'winrate']].style.applymap(style_winrate, subset=['winrate']), use_container_width=True)

    # ONGLET 3 : TABLEAU COMPLET
    with tab3:
        st.dataframe(
            df_show.sort_values(by='games', ascending=False),
            use_container_width=True,
            column_config={
                "champion": "Champion", "role": "Rôle", 
                "games": st.column_config.NumberColumn("Games"),
                "winrate": st.column_config.NumberColumn("WR %", format="%.1f %%")
            },
            hide_index=True
        )