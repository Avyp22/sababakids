import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export async function searchActivities(payload) {
  const { data } = await axios.post(`${API}/places/search`, payload);
  return data;
}

export async function getEvents(params = {}) {
  const { data } = await axios.get(`${API}/events`, { params });
  return data;
}

// "This place/event is wrong": {item_id, kind: "place"|"event", name, reason, comment}
export async function reportItem(payload) {
  const { data } = await axios.post(`${API}/report`, payload);
  return data;
}