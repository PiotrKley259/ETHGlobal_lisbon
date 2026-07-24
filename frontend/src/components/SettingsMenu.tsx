import { useEffect, useState } from "react";
import { getSettings, postSettings } from "../api";

interface SettingsMenuProps {
  onSaved: () => void; // parent re-hydrates the panel (regime is recomputed)
  onClose: () => void;
}

// B2.2b — regime-band settings behind the gear icon. Two threshold inputs,
// validated 0 < calm < elevated < 1 both here and by the backend (422).
export function SettingsMenu({ onSaved, onClose }: SettingsMenuProps) {
  const [calm, setCalm] = useState("0.33");
  const [elevated, setElevated] = useState("0.66");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    getSettings()
      .then((s) => {
        setCalm(String(s.regime_bands.calm));
        setElevated(String(s.regime_bands.elevated));
      })
      .catch(() => setError("could not load settings (backend down?)"));
  }, []);

  const save = async () => {
    const c = Number(calm);
    const e = Number(elevated);
    if (!(c > 0 && c < e && e < 1)) {
      setError("need 0 < calm < elevated < 1");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await postSettings({ regime_bands: { calm: c, elevated: e } });
      onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="settings-menu">
      <div className="settings-row">
        <label>
          calm boundary
          <input value={calm} onChange={(e) => setCalm(e.target.value)} inputMode="decimal" />
        </label>
        <label>
          stressed boundary
          <input value={elevated} onChange={(e) => setElevated(e.target.value)} inputMode="decimal" />
        </label>
      </div>
      <p className="settings-hint">
        7d-vol percentile thresholds: below calm → calm, below stressed boundary →
        elevated, else stressed.
      </p>
      {error && <p className="settings-error">⚠ {error}</p>}
      <div className="settings-actions">
        <button onClick={onClose} disabled={saving}>cancel</button>
        <button onClick={save} disabled={saving} className="primary">
          {saving ? "saving…" : "save"}
        </button>
      </div>
    </div>
  );
}
