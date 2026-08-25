import axios from "axios";

const baseURL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export const api = axios.create({ baseURL });

export const Applications = {
  list: (params) => api.get("/api/v1/applications", { params }).then((r) => r.data),
  get: (id) => api.get(`/api/v1/applications/${id}`).then((r) => r.data),
  create: (payload) => api.post("/api/v1/applications", payload).then((r) => r.data),
  process: (id) => api.post(`/api/v1/applications/${id}/process`).then((r) => r.data),
  remove: (id) => api.delete(`/api/v1/applications/${id}`),
  uploadDocument: (id, docType, file) => {
    const form = new FormData();
    form.append("doc_type", docType);
    form.append("file", file);
    return api
      .post(`/api/v1/applications/${id}/documents`, form, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((r) => r.data);
  },
  audit: (id) => api.get(`/api/v1/applications/${id}/audit`).then((r) => r.data),
};

export const Documents = {
  downloadUrl: (documentId) => `${baseURL}/api/v1/documents/${documentId}/download`,
};

export const Review = {
  reviewers: () => api.get("/api/v1/reviewers").then((r) => r.data),
  addReviewer: (payload) => api.post("/api/v1/reviewers", payload).then((r) => r.data),
  assign: (appId, reviewerName) =>
    api
      .post(`/api/v1/applications/${appId}/assign`, null, { params: { reviewer_name: reviewerName } })
      .then((r) => r.data),
  decide: (appId, payload) =>
    api.post(`/api/v1/applications/${appId}/decisions`, payload).then((r) => r.data),
  decisions: (appId) => api.get(`/api/v1/applications/${appId}/decisions`).then((r) => r.data),
};

export const Analytics = {
  summary: () => api.get("/api/v1/analytics/summary").then((r) => r.data),
  timeline: () => api.get("/api/v1/analytics/timeline").then((r) => r.data),
};

export const Reports = {
  applicationsCSVUrl: (params = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v))
    ).toString();
    return `${baseURL}/api/v1/reports/applications.csv${qs ? "?" + qs : ""}`;
  },
  applicationPDFUrl: (applicationId) =>
    `${baseURL}/api/v1/reports/applications/${applicationId}/pdf`,
};

export const Assistant = {
  ask: (question, applicationId) =>
    api
      .post("/api/v1/assistant/ask", { question, application_id: applicationId || null })
      .then((r) => r.data),
  summarize: (applicationId) =>
    api.get(`/api/v1/assistant/applications/${applicationId}/summary`).then((r) => r.data),
};

export default api;
