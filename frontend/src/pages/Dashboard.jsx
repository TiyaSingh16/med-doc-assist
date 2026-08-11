import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { uploadDocument, getDocuments } from "../api/documents";
import { logoutUser } from "../api/auth";
import { compareDocuments } from "../api/documents";

const STATUS_STYLES = {
  completed: "bg-green-100 text-green-700",
  processing: "bg-amber-100 text-amber-700",
  pending: "bg-slate-100 text-slate-700",
  failed: "bg-red-100 text-red-700",
};

export default function Dashboard() {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [compareMode, setCompareMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState([]);
  const navigate = useNavigate();

  const fetchDocuments = useCallback(async () => {
    try {
      const res = await getDocuments();
      setDocuments(res.data.documents);
    } catch (err) {
      setError("Failed to load documents");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  // Poll every 4s while any document is still processing, so status badges update live
  useEffect(() => {
    const hasProcessing = documents.some(
      (d) => d.processing_status === "processing" || d.processing_status === "pending"
    );
    if (!hasProcessing) return;

    const interval = setInterval(fetchDocuments, 4000);
    return () => clearInterval(interval);
  }, [documents, fetchDocuments]);

  const handleFileChange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    if (!file.name.endsWith(".pdf")) {
      setError("Only PDF files are allowed");
      return;
    }

    setError("");
    setUploading(true);
    try {
      await uploadDocument(file);
      await fetchDocuments();
    } catch (err) {
      setError(err.response?.data?.detail || "Upload failed");
    } finally {
      setUploading(false);
      e.target.value = ""; // reset file input so the same file can be re-selected later
    }
  };

  const toggleSelect = (docId) => {
    setSelectedIds((prev) => {
      if (prev.includes(docId)) {
        return prev.filter((id) => id !== docId);
      }
      if (prev.length >= 2) {
        return [prev[1], docId]; // keep only the most recent 2 selections
      }
      return [...prev, docId];
    });
  };

  const handleCompare = () => {
    if (selectedIds.length !== 2) return;
    navigate(`/compare/${selectedIds[0]}/${selectedIds[1]}`);
  };

  const handleLogout = () => {
    logoutUser();
    navigate("/login");
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-white border-b border-slate-200 px-8 py-4 flex justify-between items-center">
        <h1 className="text-lg font-semibold text-slate-800">Medical Document Assistant</h1>
        <div className="flex items-center gap-4">
          <button
            onClick={() => {
              setCompareMode((prev) => !prev);
              setSelectedIds([]);
            }}
            className={`text-sm font-medium px-3 py-1.5 rounded-full transition ${
              compareMode
                ? "bg-blue-600 text-white"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            {compareMode ? "Cancel compare" : "Compare documents"}
          </button>
          <button
            onClick={handleLogout}
            className="text-sm text-slate-500 hover:text-slate-800 transition"
          >
            Log out
          </button>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-8">
        <div className="bg-white rounded-2xl border border-slate-200 p-6 mb-6">
          <h2 className="font-medium text-slate-800 mb-3">Upload a document</h2>
          <label className="flex flex-col items-center justify-center border-2 border-dashed border-slate-300 rounded-xl py-8 cursor-pointer hover:border-blue-400 transition">
            <span className="text-sm text-slate-500">
              {uploading ? "Uploading..." : "Click to select a PDF"}
            </span>
            <input
              type="file"
              accept=".pdf"
              onChange={handleFileChange}
              disabled={uploading}
              className="hidden"
            />
          </label>
          {error && <p className="text-sm text-red-600 mt-3">{error}</p>}
        </div>

        <div className="bg-white rounded-2xl border border-slate-200 p-6">
          <h2 className="font-medium text-slate-800 mb-4">Your documents</h2>

          {loading ? (
            <p className="text-sm text-slate-500">Loading...</p>
          ) : documents.length === 0 ? (
            <p className="text-sm text-slate-500">No documents yet — upload one to get started.</p>
          ) : (
            <ul className="space-y-2">
              {documents.map((doc) => (
                <li
                  key={doc.id}
                  className={`flex items-center justify-between px-4 py-3 rounded-xl border transition ${
                    selectedIds.includes(doc.id)
                      ? "border-blue-400 bg-blue-50"
                      : "border-slate-100 hover:border-slate-200"
                  }`}
                >
                  <div className="flex items-center gap-3">
                    {compareMode && (
                      <input
                        type="checkbox"
                        checked={selectedIds.includes(doc.id)}
                        onChange={() => toggleSelect(doc.id)}
                        disabled={doc.processing_status !== "completed"}
                        className="w-4 h-4 accent-blue-600"
                      />
                    )}
                    <div>
                      <p className="text-sm font-medium text-slate-800">{doc.filename}</p>
                      <span
                        className={`inline-block text-xs px-2 py-0.5 rounded-full mt-1 ${
                          STATUS_STYLES[doc.processing_status] || "bg-slate-100 text-slate-600"
                        }`}
                      >
                        {doc.processing_status}
                      </span>
                    </div>
                  </div>
                  {!compareMode && (
                    <button
                      disabled={doc.processing_status !== "completed"}
                      onClick={() => navigate(`/chat/${doc.id}`)}
                      className="text-sm font-medium text-blue-600 hover:underline disabled:text-slate-300 disabled:no-underline"
                    >
                      Chat →
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
          {compareMode && selectedIds.length === 2 && (
            <div className="fixed bottom-6 left-1/2 -translate-x-1/2 bg-slate-800 text-white px-6 py-3 rounded-full shadow-lg flex items-center gap-4">
              <span className="text-sm">2 documents selected</span>
              <button
                onClick={handleCompare}
                className="bg-blue-600 hover:bg-blue-700 transition px-4 py-1.5 rounded-full text-sm font-medium"
              >
                Compare →
              </button>
            </div>
          )}
      </main>
    </div>
  );
}