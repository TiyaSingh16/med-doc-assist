import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { compareDocuments, getDocument } from "../api/documents";

const TREND_STYLES = {
  improved: "bg-green-100 text-green-700",
  worsened: "bg-red-100 text-red-700",
  unchanged: "bg-slate-100 text-slate-600",
  new: "bg-blue-100 text-blue-700",
  resolved: "bg-purple-100 text-purple-700",
};

const CHANGE_STYLES = {
  added: "bg-blue-100 text-blue-700",
  removed: "bg-red-100 text-red-700",
  dosage_changed: "bg-amber-100 text-amber-700",
  unchanged: "bg-slate-100 text-slate-600",
  new: "bg-blue-100 text-blue-700",
  resolved: "bg-purple-100 text-purple-700",
  ongoing: "bg-slate-100 text-slate-600",
};

function Badge({ text, styleMap }) {
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${styleMap[text] || "bg-slate-100 text-slate-600"}`}>
      {text.replace("_", " ")}
    </span>
  );
}

export default function Compare() {
  const { idA, idB } = useParams();
  const navigate = useNavigate();
  const [docA, setDocA] = useState(null);
  const [docB, setDocB] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        const [resA, resB, resCompare] = await Promise.all([
          getDocument(idA),
          getDocument(idB),
          compareDocuments(idA, idB),
        ]);
        setDocA(resA.data);
        setDocB(resB.data);
        setResult(resCompare.data);
      } catch (err) {
        setError(err.response?.data?.detail || "Failed to compare documents");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [idA, idB]);

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-white border-b border-slate-200 px-8 py-4 flex items-center gap-4">
        <button
          onClick={() => navigate("/dashboard")}
          className="text-sm text-slate-500 hover:text-slate-800 transition"
        >
          ← Back
        </button>
        <h1 className="text-sm font-medium text-slate-800">Document comparison</h1>
      </header>

      <main className="max-w-2xl mx-auto px-6 py-8">
        {loading && (
          <p className="text-sm text-slate-500 text-center mt-12">
            Comparing documents... this may take a moment.
          </p>
        )}

        {error && (
          <p className="text-sm text-red-600 bg-red-50 px-4 py-3 rounded-xl">{error}</p>
        )}

        {result && (
          <div className="space-y-6">
            <div className="bg-white rounded-2xl border border-slate-200 p-4 flex items-center justify-between text-sm">
              <span className="font-medium text-slate-700">{docA?.filename}</span>
              <span className="text-slate-400">→</span>
              <span className="font-medium text-slate-700">{docB?.filename}</span>
            </div>

            <div className="bg-white rounded-2xl border border-slate-200 p-6">
              <h2 className="font-medium text-slate-800 mb-2">Summary</h2>
              <p className="text-sm text-slate-600 leading-relaxed">{result.summary}</p>
            </div>

            {result.lab_value_changes.length > 0 && (
              <div className="bg-white rounded-2xl border border-slate-200 p-6">
                <h2 className="font-medium text-slate-800 mb-4">Lab values</h2>
                <div className="space-y-3">
                  {result.lab_value_changes.map((lv, i) => (
                    <div key={i} className="flex items-center justify-between text-sm">
                      <span className="text-slate-700">{lv.test_name}</span>
                      <div className="flex items-center gap-2">
                        <span className="text-slate-500">
                          {lv.old_value ?? "—"} → {lv.new_value ?? "—"} {lv.unit || ""}
                        </span>
                        <Badge text={lv.trend} styleMap={TREND_STYLES} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {result.medication_changes.length > 0 && (
              <div className="bg-white rounded-2xl border border-slate-200 p-6">
                <h2 className="font-medium text-slate-800 mb-4">Medications</h2>
                <div className="space-y-3">
                  {result.medication_changes.map((med, i) => (
                    <div key={i} className="flex items-center justify-between text-sm">
                      <span className="text-slate-700">{med.name}</span>
                      <div className="flex items-center gap-2">
                        {(med.old_dosage || med.new_dosage) && (
                          <span className="text-slate-500">
                            {med.old_dosage ?? "—"} → {med.new_dosage ?? "—"}
                          </span>
                        )}
                        <Badge text={med.change_type} styleMap={CHANGE_STYLES} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {result.diagnosis_changes.length > 0 && (
              <div className="bg-white rounded-2xl border border-slate-200 p-6">
                <h2 className="font-medium text-slate-800 mb-4">Diagnoses</h2>
                <div className="space-y-3">
                  {result.diagnosis_changes.map((dx, i) => (
                    <div key={i} className="flex items-center justify-between text-sm">
                      <span className="text-slate-700">{dx.condition}</span>
                      <Badge text={dx.change_type} styleMap={CHANGE_STYLES} />
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}