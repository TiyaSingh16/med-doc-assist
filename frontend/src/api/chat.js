import apiClient from "./client";

export const askQuestion = (documentId, question) =>
  apiClient.post("/chat/query", { document_id: documentId, question });

export const getChatHistory = (documentId) =>
  apiClient.get(`/chat/${documentId}/history`);