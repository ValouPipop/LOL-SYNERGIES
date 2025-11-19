import streamlit as st
import requests
import pandas as pd
import time

# Si l'URL contient ?riot=true, on affiche juste le code et on s'arrête.
query_params = st.query_params
if "riot" in query_params:
    st.write("e7c9e2f7-71b1-4805-b9e6-fb8fe60ef993") # <--- TON CODE RIOT ICI
    st.stop()
# ---------------------------------
# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="LoL Ultimate Scanner",
    page_icon="♾️",
    layout="wide"
)

# --- GESTION DE LA CLÉ API ---
# Essaie de charger depuis les secrets Streamlit, sinon utilise une clé locale
try:
    API_KEY = st.secrets["RIOT_API_KEY"]
except:
    # Remplace ceci par ta clé temporaire si tu testes en local sur ton PC
    API_KEY = "RGAPI-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"

REGION_ROUTING = "europe"

# --- MOTEUR API INTELLIGENT (BURST MODE) ---
def make_request(url):
    """
    Effectue une requête API.
    Gère automatiquement les limites de taux (Rate Limits) de Riot.
    """
    while True:
        try:
            resp = requests.get(url, headers={"X-Riot-Token": API_KEY})
            
            # Cas 1 : Succès
            if resp.status_code == 200:
                return resp.json()
            
            # Cas 2 : Trop de requêtes (Rate Limit)
            elif resp.status_code == 429:
                wait_time = int(resp.headers.get("Retry-After", 10))
                
                # On crée un conteneur vide pour le message d'avertissement
                placeholder = st.empty()
                
                # Compte à rebours visuel
                for i in range(wait_time, 0, -1):
                    placeholder.warning(f"⚡ Vitesse max atteinte ! Optimisation des requêtes... Reprise dans {i}s...")
                    time.sleep(1)
                
                # IMPORTANT : On efface le message une fois l'attente finie
                placeholder.empty()
                continue # On réessaie la requête
            
            # Cas 3 : Clé expirée ou invalide
            elif resp.status_code == 403:
                st.error("❌ La clé API Riot est invalide ou a expiré. Veuillez mettre à jour les 'Secrets'.")
                st.stop()
            
            # Autres erreurs (404, 500...)
            else:
                return None
        except Exception as e:
            st.error(f"Erreur de connexion : {e}")
            return None

def get_puuid(name, tag):
    """Récupère le PUUID via Riot ID"""
    url = f"https://{REGION_ROUTING}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{name}/{tag}"
    data = make_request(url)
    return data['puuid'] if data else None

def get_matches(puuid):
    """Récupère TOUS les IDs de matchs Ranked Solo (Queue 420) via pagination"""
    matches = []
    start = 0
    status = st.empty()
    
    while True:
        # On demande par paquets de 100
        url = f"https://{REGION_ROUTING}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?queue=420&start={start}&count=100"
        ids = make_request(url)
        
        if not ids:
            break
            
        matches.extend(ids)
        status.write(f"📥 Récupération de l'historique... {len(matches)} matchs trouvés.")
        
        # Si on reçoit moins de 100 matchs, c'est qu'on est à la fin
        if len(ids) < 100:
            break
        
        start += 100
    
    status.empty()
    return matches

def style_winrate(val):
    """Colore les cellules du tableau selon le winrate"""
    if val >= 55:
        color = '#2ecc71' # Vert
    elif val <= 45:
        color = '#e74c3c' # Rouge
    else:
        color = '#f1c40f' # Jaune
    return f'color: {color}; font-weight: bold;'

# --- INTERFACE PRINCIPALE ---

st.title("♾️ LoL Full Season Scanner")
st.markdown("Ce scanner analyse **l'intégralité** de tes matchs classés (SoloQ) pour trouver tes meilleures synergies.")

# Initialisation de la mémoire (Session State) pour ne pas perdre les données quand on filtre
if 'df' not in st.session_state:
    st.session_state.df = None

# --- ZONE DE RECHERCHE ---
col1, col2 = st.columns([3, 1])
with col1:
    pseudo_input = st.text_input("Riot ID (ex: Caps#EUW)", placeholder="Pseudo#Tag")
with col2:
    st.write("") # Espace pour aligner
    st.write("") 
    start_btn = st.button("🚀 Lancer le Scan", type="primary", use_container_width=True)

# --- LOGIQUE DE SCAN ---
if start_btn and pseudo_input:
    if "#" not in pseudo_input:
        st.error("Format invalide. Utilise le format Pseudo#Tag")
        st.stop()
    
    name, tag = pseudo_input.split("#")
    stats = {}

    # Conteneur de statut animé
    with st.status("Initialisation du scanner...", expanded=True) as status:
        
        # 1. Trouver le joueur
        puuid = get_puuid(name, tag)
        if not puuid:
            status.update(label="❌ Joueur introuvable", state="error")
            st.stop()

        # 2. Récupérer les matchs
        match_ids = get_matches(puuid)
        total = len(match_ids)
        
        if total == 0:
            status.update(label="❌ Aucune Ranked trouvée sur ce compte.", state="error")
            st.stop()

        # Estimation du temps pour l'utilisateur
        cycles = (total - 1) // 100
        est = "Moins d'une minute" if cycles == 0 else f"Environ {cycles*2} minutes"
        st.info(f"⏱️ Temps estimé : {est} ({total} matchs à analyser)")

        # 3. Analyse match par match
        bar = st.progress(0)
        
        for i, m_id in enumerate(match_ids):
            details = make_request(f"https://{REGION_ROUTING}.api.riotgames.com/lol/match/v5/matches/{m_id}")
            
            # Micro-pause BURST (0.05s) pour respecter la limite 20 req/sec
            time.sleep(0.05) 
            bar.progress((i + 1) / total)
            
            if not details: continue
            
            parts = details['info']['participants']
            
            # Identifier "Moi"
            try:
                me = next(p for p in parts if p['puuid'] == puuid)
            except: continue
            
            # Analyser les alliés
            for p in parts:
                if p['teamId'] == me['teamId'] and p['puuid'] != puuid:
                    role = p.get('teamPosition', 'UNKNOWN')
                    if role == "UTILITY": role = "SUPPORT"
                    
                    # Clé unique : Nom_Role
                    k = f"{p['championName']}_{role}"
                    
                    if k not in stats: 
                        stats[k] = {'champion': p['championName'], 'role': role, 'games': 0, 'wins': 0}
                    
                    stats[k]['games'] += 1
                    if me['win']:
                        stats[k]['wins'] += 1

        status.update(label="✅ Analyse terminée avec succès !", state="complete")

    # Transformation en DataFrame
    data_list = []
    for v in stats.values():
        v['losses'] = v['games'] - v['wins']
        v['winrate'] = round((v['wins'] / v['games']) * 100, 1)
        data_list.append(v)
    
    # Sauvegarde dans la mémoire du navigateur
    st.session_state.df = pd.DataFrame(data_list)

# --- AFFICHAGE DES RÉSULTATS ---
if st.session_state.df is not None:
    df = st.session_state.df
    
    st.divider()
    st.markdown(f"### 📊 Résultats de l'analyse ({int(df['games'].sum()/4)} matchs)")

    # --- BARRE LATÉRALE (FILTRES) ---
    st.sidebar.header("Filtres d'affichage")
    
    # Slider dynamique
    min_games = st.sidebar.slider("Minimum de games ensemble :", 1, 20, 2)
    
    # Filtre rôle
    roles = ["Tous"] + sorted(df['role'].unique().tolist())
    sel_role = st.sidebar.selectbox("Filtrer par Rôle Allié :", roles)

    # Application des filtres
    df_show = df[df['games'] >= min_games]
    if sel_role != "Tous":
        df_show = df_show[df_show['role'] == sel_role]

    # --- ONGLETS ---
    tab1, tab2, tab3 = st.tabs(["🏆 Tops & Flops", "🔍 Recherche Champion", "📂 Tableau Complet"])

    # ONGLET 1 : DASHBOARD
    with tab1:
        if df_show.empty:
            st.info("Aucune donnée avec ces filtres.")
        else:
            c1, c2 = st.columns(2)
            with c1:
                st.caption("🔥 Meilleures Synergies")
                top = df_show.sort_values(by=['winrate', 'games'], ascending=[False, False]).head(10)
                st.dataframe(
                    top[['champion', 'role', 'games', 'winrate']], 
                    use_container_width=True, 
                    hide_index=True,
                    column_config={"winrate": st.column_config.ProgressColumn("Winrate", format="%.1f %%", min_value=0, max_value=100)}
                )
            with c2:
                st.caption("💀 Pires Synergies")
                flop = df_show.sort_values(by=['winrate', 'games'], ascending=[True, False]).head(10)
                st.dataframe(
                    flop[['champion', 'role', 'games', 'winrate']], 
                    use_container_width=True, 
                    hide_index=True,
                    column_config={"winrate": st.column_config.ProgressColumn("Winrate", format="%.1f %%", min_value=0, max_value=100)}
                )

    # ONGLET 2 : RECHERCHE PRÉCISE
    with tab2:
        st.write("Tape le nom d'un champion pour voir vos stats ensemble.")
        all_champs = sorted(df['champion'].unique())
        search = st.selectbox("Champion :", all_champs)
        
        if search:
            res = df[df['champion'] == search]
            tot_g = res['games'].sum()
            tot_w = res['wins'].sum()
            wr = round(tot_w/tot_g*100, 1) if tot_g > 0 else 0
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Games Totales", tot_g)
            m2.metric("Winrate Global", f"{wr}%")
            
            st.dataframe(
                res[['role', 'games', 'wins', 'losses', 'winrate']].style.applymap(style_winrate, subset=['winrate']), 
                use_container_width=True
            )

    # ONGLET 3 : TABLEAU COMPLET
    with tab3:
        st.dataframe(
            df_show.sort_values(by='games', ascending=False),
            use_container_width=True,
            column_config={
                "champion": "Champion", 
                "role": "Rôle", 
                "games": st.column_config.NumberColumn("Games"),
                "winrate": st.column_config.NumberColumn("WR %", format="%.1f %%")
            },
            hide_index=True
        )

# --- DISCLAIMER OBLIGATOIRE POUR RIOT ---
st.divider()
st.markdown("""
<small style='color: gray;'>
LoL Ultimate Scanner isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot Games 
or anyone officially involved in producing or managing Riot Games properties. Riot Games, and all associated properties 
are trademarks or registered trademarks of Riot Games, Inc.
</small>
""", unsafe_allow_html=True)

