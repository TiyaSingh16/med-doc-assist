import apiClient from "./client";

export const registerUser = (email, password) =>
  apiClient.post("/auth/register", { email, password });

export const loginUser = async (email, password) => {
  const response = await apiClient.post("/auth/login", { email, password });
  const { access_token } = response.data;
  localStorage.setItem("token", access_token);
  return response.data;
};

export const logoutUser = () => {
  localStorage.removeItem("token");
};

export const getCurrentUser = () => apiClient.get("/auth/me");