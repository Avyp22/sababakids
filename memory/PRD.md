# SababaKids — Product Requirements Document

## Original Problem Statement
User lives in Israel and frequently wonders what activities to do with their kids. They want an app connected to relevant APIs that shows activities within a defined perimeter.

## User Choices
- Show both **places** (parks, museums, playgrounds, zoos, beaches, etc.) and **one-off events**
- Perimeter defined by **both** GPS current location (adjustable radius) and typing a city/address
- Data source: **Google Places API** (with curated Israeli fallback dataset)
- Filters by **children's age** and **category** (indoor/outdoor, free/paid)
- Interface language: **English**

## Architecture
- **Frontend**: React (CRA + craco), Tailwind, shadcn/ui, Leaflet maps, lucide-react icons, sonner toasts. Theme: warm Mediterranean "Organic Earthy Playful" (terracotta/sage/amber), light + dark mode.
- **Backend**: FastAPI, `/api` prefix, httpx for Google Places (New) + Geocoding, MongoDB (search history log).
- **Data**: `mock_data.py` holds CITY_COORDS, 22 curated Israeli activities, 6 curated events used as rich fallback when `GOOGLE_MAPS_API_KEY` is empty.

## Core Requirements (static)
- Location search by city/address + GPS, adjustable radius 1–50 km.
- Category, age, indoor/outdoor, free/paid filtering.
- List, Map, Events, and Saved views. Favorites persisted in localStorage.
- Activity detail drawer with hours, ages, features, Waze/Google Maps directions.

## Implemented (2026-06)
- ✅ Backend `/api/places/search` — geocode + Google Places (New) nearby/text + haversine filtering + all filters + curated fallback. **LIVE Google key active** (open_now, photos, ratings).
- ✅ Backend `/api/events` — combines **live scraped municipal events** (Modi'in board via `events_source.py`, cached 30min) with curated events; parses date/time/GPS/price/age/ticket/.ics; `family_only` filter.
- ✅ Frontend: Header, FiltersBar, ActivityCard grid, ActivityDetail drawer, Leaflet MapView, EventsView (tickets + add-to-calendar + live source badge + RTL Hebrew), Saved/favorites + WhatsApp share, Open Now badges, dark mode, mobile bottom nav.

## Live Event Sources
- `events_source.py` — pluggable event connectors:
  - **Modi'in Municipality** board (`_parse_modiin`) — municipal, proximity-gated, respects user radius.
  - **Leaan (national aggregator)** (`fetch_leaan`) — parses leaan.co.il embedded Next.js JSON (~340 future ticketed events) covering ALL major cities incl. Jerusalem/Tel Aviv/Haifa; Hebrew city→coords via `HEB_CITY_COORDS`; distance-filtered by user radius.
  - Curated SababaKids picks as fallback. `family_only` filter (default OFF = show all). 30-min in-process cache.
- Add more municipalities by extending `EVENT_SOURCES` + a parser.
- Tested iteration 2: 100% backend (18/18) + frontend. Fixed: municipal events now respect user radius_km.

## Integrations / Keys
- **Google Maps API key** (`GOOGLE_MAPS_API_KEY` in `/app/backend/.env`) — currently EMPTY. App runs on curated data until the user provides a key (needs Places API New + Geocoding API enabled). When set, live nearby places are merged with curated data.

## Backlog / Remaining
- P1: Wire real Google key for live places (waiting on user's key).
- P1: Real Israeli events feed (currently curated/mock).
- P2: WhatsApp share of saved family trip list.
- P2: Hebrew + French UI localization.
- P2: Weather-aware recommendations, opening-hours "open now" badge.

## No Authentication
Open app, no user accounts.
