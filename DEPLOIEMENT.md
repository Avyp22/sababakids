# Déploiement 100 % gratuit (sans Emergent)

| Pièce | Service gratuit | Rôle |
|---|---|---|
| Frontend React | **Render** Static Site (`sababakids`) — ou Netlify | Site statique |
| Backend FastAPI | **Render** — plan Free | API `/api/...` |
| Base de données | *Aucune* (optionnel : **MongoDB Atlas M0**) | Ne sert qu'à journaliser les recherches |
| Réveil du backend | **GitHub Actions** (`.github/workflows/keep-alive.yml`) | Ping toutes les 14 min |

## 1. Backend sur Render (≈ 5 min)
1. Créer un compte sur <https://render.com> avec GitHub (pas de carte bancaire requise).
2. **New → Blueprint** → choisir le repo `Avyp22/sababakids` → Render lit `render.yaml`.
3. Il demande les variables marquées `sync: false` :
   - `GOOGLE_MAPS_API_KEY` : ta clé Google (Places API (New) + Geocoding API). Vide = données « curated » seulement.
   - `MONGO_URL` : laisser **vide** (ou une URL Atlas, voir §4).
4. **Apply**. Au bout de 2–3 min l'URL ressemble à `https://sababakids-api.onrender.com`.
5. Tester : `https://sababakids-api.onrender.com/api/health` → `{"status":"ok"}`.

> Si tu changes l'URL du site Netlify (domaine perso…), mets à jour `CORS_ORIGINS`
> dans Render → service → Environment (liste séparée par des virgules, sans `/` final).

## 2. Frontend
Le Blueprint crée aussi le site statique `sababakids` → `https://sababakids.onrender.com`
(gratuit, sans crédits, `REACT_APP_BACKEND_URL` déjà renseignée dans `render.yaml`).

### Alternative : Netlify
Le plan gratuit Netlify fonctionne par crédits ; une fois épuisés, les déploiements sont bloqués
jusqu'au cycle suivant.
1. Netlify → site `chipper-gumdrop-477ddd` → **Site configuration → Environment variables**.
2. Ajouter `REACT_APP_BACKEND_URL` = `https://sababakids-api.onrender.com` (sans `/` final).
3. **Deploys → Trigger deploy → Clear cache and deploy site** (la variable est intégrée au build).
4. Le site est actuellement protégé par un login Netlify (réponse 401). Pour le rendre public :
   **Site configuration → Access & security → Visitor access** → désactiver la protection.

## 3. Éviter la mise en veille (optionnel)
Le plan gratuit Render s'endort après 15 min sans trafic (1re requête ≈ 50 s).
Le workflow `keep-alive.yml` le garde éveillé de 8h à 1h (heure d'Israël) :
GitHub → repo → **Settings → Secrets and variables → Actions → Variables → New variable**
`BACKEND_URL` = `https://sababakids-api.onrender.com`.
Budget Render : 750 h/mois gratuites, largement suffisant pour un seul service.

## 4. MongoDB (optionnel)
Le backend fonctionne sans base. Pour garder l'historique des recherches :
<https://www.mongodb.com/cloud/atlas> → cluster **M0 Free** → Network Access `0.0.0.0/0`
→ copier l'URL `mongodb+srv://...` dans `MONGO_URL` sur Render.

## 5. Couper Emergent
Une fois le site Netlify fonctionnel avec le backend Render, tu peux arrêter le déploiement
Emergent. Le dossier `.emergent/` et les scripts Emergent (analytics PostHog, éditeur visuel)
ont été retirés du code.

## Dev local
```bash
cd backend && pip install -r requirements-dev.txt && cp .env.example .env
uvicorn server:app --reload --port 8001
cd frontend && yarn install && yarn start   # frontend/.env : REACT_APP_BACKEND_URL=http://localhost:8001
```

## Consommation Google
- Recherche « Tout » : 4 appels Google lancés en parallèle (au lieu de 9 en série).
- Une recherche identique dans l'heure est servie depuis le cache, sans appel Google.
- Photos servies par le backend (`/api/photo/...`) : la clé Google n'est plus visible dans le navigateur, et chaque photo est mise en cache 24 h.
- `GOOGLE_PLACES_DETAIL=basic` (variable Render) supprime notes et horaires → gamme Google moins chère, quota gratuit plus large.

## Sources d'événements
| Source | Méthode | Filtre « famille » |
|---|---|---|
| Mairie de Modi'in | page EventBoard | âges / mots-clés |
| Mairie de Holon | liste « Havingfun » | champ « public cible » de la mairie |
| Mairie de Haïfa | page city-events | catégorie « family » de la mairie |
| Leaan (national) | JSON de la page d'accueil | catégorie « ילדים » du site |

- Non connectables aujourd'hui : Jérusalem (403), Kfar Saba, Herzliya, Bat Yam, Givatayim, Hod Hasharon (anti-bot), Netanya (Cloudflare), Tel Aviv (chargement JavaScript).
- Ajouter une ville : écrire un `fetch_<ville>()` dans `backend/events_source.py`, l'ajouter à `EVENT_SOURCES` et `FETCHERS`.
- Santé des sources : `GET /api/sources?refresh=true`. Le workflow `check-event-sources` l'appelle chaque matin et échoue (→ e-mail GitHub) si une source ne renvoie plus rien.

## Fonctions à activer (comptes gratuits à créer par toi)

### Statistiques de visite — GoatCounter (sans cookies, sans bannière)
1. <https://www.goatcounter.com/signup> → code du site : par ex. `sababakids`.
2. Render → service **sababakids** (static) → Environment → `REACT_APP_GOATCOUNTER` = `sababakids` → redéployer.
3. Tableau de bord : `https://sababakids.goatcounter.com` (pages vues, villes ouvertes via /haifa…, événements « search/park », « tab/events », « events-date/weekend », « weather/rain-indoor », « report/... »).

### Base de données — MongoDB Atlas M0 (cache Google persistant + signalements)
1. <https://www.mongodb.com/cloud/atlas/register> → cluster **M0 Free** (région Francfort).
2. Database Access → un utilisateur ; Network Access → `0.0.0.0/0`.
3. Connect → Drivers → copier `mongodb+srv://...` → Render → **sababakids-api** → `MONGO_URL`.
Sans MongoDB tout marche, mais le cache Google repart de zéro à chaque redémarrage et les signalements ne sont gardés qu'en mémoire.

### Signalements
- Bouton « Signaler un problème » sur chaque lieu et événement.
- 3 signalements de personnes différentes → l'élément passe dans la liste `flagged` **à vérifier** (nécessite MongoDB). Rien n'est masqué automatiquement : une seule personne pourrait se faire passer pour plusieurs.
- La clé admin (ADMIN_KEY, générée par Render → sababakids-api → Environment) passe de préférence dans l'en-tête `X-Admin-Key`, pour ne pas apparaître dans les journaux du serveur. `?key=` marche encore, mais à éviter.
- Consulter (regarder d'abord `flagged`) :
  `curl -H "X-Admin-Key: <ADMIN_KEY>" https://sababakids-api.onrender.com/api/reports`
- Masquer :
  `curl -X POST -H "X-Admin-Key: <ADMIN_KEY>" "https://sababakids-api.onrender.com/api/hide?item_id=<id>"`
  Réafficher, ou écarter un signalement injustifié : ajouter `&unhide=true`. Dans les deux cas l'élément sort de `flagged`.
- Limite : 10 signalements par heure et par visiteur.

### Protection du quota Google
- 30 recherches par minute et par visiteur (au-delà : message « trop de recherches »).
- Plafond global d'appels Google payants par jour : variable `GOOGLE_DAILY_LIMIT` (défaut 1000) sur **sababakids-api**. Une fois atteint, le site affiche seulement la sélection SababaKids jusqu'à minuit (heure d'Israël). Les résultats déjà en cache ne comptent pas.
- En plus, fixer un plafond dans Google Cloud Console → APIs & Services → Places API (New) → Quotas : c'est la seule vraie garantie sur la facture.

### Référencement
- Pages par ville : `/tel-aviv`, `/haifa`, `/holon`, `/jerusalem`… (liste : `frontend/src/lib/cities.json`), générées au build. Le build interroge l'API : chaque page liste les lieux de la sélection SababaKids proches et les prochains événements familiaux, avec les données `Event` de schema.org pour que Google puisse les afficher dans ses résultats. Si l'API ne répond pas, la page est construite quand même, avec le texte générique.
- Événements à jour sur ces pages : la tâche GitHub `refresh-city-pages` relance le build chaque matin. À activer une fois : Render → **sababakids** (site statique) → Settings → Deploy Hook → copier l'URL → GitHub → Settings → Secrets and variables → Actions → **New repository secret** `RENDER_STATIC_DEPLOY_HOOK`.
- Nom de domaine personnalisé (ex. sababakids.co.il) : l'ajouter dans Render → sababakids → Settings → Custom Domains, puis mettre la variable `PUBLIC_SITE_URL=https://sababakids.co.il` sur le site statique (URLs canoniques et sitemap), remplacer `og:url`, `canonical` et `og:image` dans `frontend/index.html`, ajouter le domaine à `CORS_ORIGINS` du backend, et redéclarer le site dans Search Console. Le faire tôt : changer de domaine plus tard fait perdre le référencement acquis.
- Google Search Console : <https://search.google.com/search-console> → ajouter le site → soumettre `https://sababakids.onrender.com/sitemap.xml`.
