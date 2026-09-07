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
- ✅ Backend `/api/places/search` — geocode (city lookup + Google fallback) + Google Places nearby/text search + haversine distance filtering + all filters. Curated Israeli activities always merged as fallback.
- ✅ Backend `/api/events` — curated events with dynamically computed upcoming dates + distance.
- ✅ Frontend: Header, FiltersBar (search/GPS/radius/category/age/setting/price), ActivityCard grid, ActivityDetail drawer, Leaflet MapView with category pins, EventsView, Saved/favorites, dark mode, mobile bottom nav.
- ✅ Tested: 100% backend (12/12 pytest) and 100% frontend (Playwright) on iteration 1.

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
