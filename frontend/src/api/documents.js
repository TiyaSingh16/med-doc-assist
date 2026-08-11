import apiClient from "./client";

export const uploadDocument = (file) => {
  const formData = new FormData();
  formData.append("file", file);
  return apiClient.post("/documents/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
};

export const getDocuments = () => apiClient.get("/documents/");

export const getDocument = (documentId) =>
  apiClient.get(`/documents/${documentId}`);

export const extractDocumentData = (documentId, forceRefresh = false) =>
  apiClient.post(`/documents/${documentId}/extract?force_refresh=${forceRefresh}`);

export const compareDocuments = (documentIdA, documentIdB) =>
  apiClient.post("/documents/compare", {
    document_id_a: documentIdA,
    document_id_b: documentIdB,
  });