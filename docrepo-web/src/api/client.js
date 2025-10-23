import axios from "axios";

const baseURL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const api = axios.create({ baseURL, withCredentials: false });

let accessToken = localStorage.getItem("access_token");
let refreshToken = localStorage.getItem("refresh_token");

export function setTokens(at, rt) {
  if (at) { accessToken = at; localStorage.setItem("access_token", at); }
  if (rt) { refreshToken = rt; localStorage.setItem("refresh_token", rt); }
}

export function clearTokens() {
  accessToken = null; refreshToken = null;
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
}

api.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

let refreshing = null;

api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const original = error.config || {};
    if (error.response?.status === 401 && !original._retry && refreshToken) {
      original._retry = true;
      try {
        if (!refreshing) {
          refreshing = axios
            .post(`${baseURL}/auth/refresh`, { refresh_token: refreshToken })
            .then((res) => {
              const { access_token, refresh_token } = res.data;
              setTokens(access_token, refresh_token);
            })
            .finally(() => { refreshing = null; });
        }
        await refreshing;
        return api(original); // retry original
      } catch (e) {
        clearTokens();
      }
    }
    return Promise.reject(error);
  }
);

export default api;
