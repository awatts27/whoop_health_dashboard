import React, { useEffect, useState, useCallback } from "react";
import {
  LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, ReferenceLine, ComposedChart, Area,
} from "recharts";
import {
  fetchSummary, fetchSleep, fetchRecovery,
  fetchWorkouts, fetchCycles, postJournal,
} from "../api.js";

// ---------------------------------------------------------------------------
// Utility helpers
// ---------------------------------------------------------------------------
const ms2hrs = (ms) => ms != null ? (ms / 3_600_000).toFixed(1) : "—";
const round1 = (v) => v != null ? Number(v).toFixed(1) : "—";
const round0 = (v) => v != null ? Math.round(Number(v)) : "—";
const fmtDate = (iso) => {
  if (!iso) return "";
  const [, m, d] = iso.split("-");
  return `${m}/${d}`;
};
const today = () => new Date().toISOString().split("T")[0];

// ---------------------------------------------------------------------------
// Stat card
// ---------------------------------------------------------------------------
function StatCard({ label, value, unit = "", delta = null, flag = false, highlight = false }) {
  const flagStyle = flag
    ? { color: "var(--red)", fontWeight: 700 }
    : highlight
    ? { color: "var(--green)" }
    : {};

  return (
    <div style={styles.card}>
      <div style={styles.cardLabel}>{label}</div>
      <div style={{ ...styles.cardValue, ...flagStyle }}>
        {value}
        {unit && <span style={styles.cardUnit}> {unit}</span>}
      </div>
      {delta != null && (
        <div style={{ color: delta >= 0 ? "var(--green)" : "var(--red)", fontSize: 12, marginTop: 2 }}>
          {delta >= 0 ? "+" : ""}{round1(delta)} vs 30d
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section header
// ---------------------------------------------------------------------------
function SectionHeader({ children }) {
  return <h2 style={styles.sectionHeader}>{children}</h2>;
}

// ---------------------------------------------------------------------------
// Custom tooltip for charts
// ---------------------------------------------------------------------------
function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={styles.tooltip}>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>{label}</div>
      {payload.map((p) => (
        <div key={p.dataKey} style={{ color: p.color, fontSize: 12 }}>
          {p.name}: {round1(p.value)}
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Journal form
// ---------------------------------------------------------------------------
function JournalPanel({ onSaved }) {
  const [form, setForm] = useState({
    notes: "",
    alcohol: false,
    travel: false,
    sauna: false,
    cold_plunge: false,
    fasted_training: false,
  });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState(null);

  const toggle = (key) => setForm((f) => ({ ...f, [key]: !f[key] }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await postJournal(today(), form);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
      onSaved?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const boolFields = [
    { key: "alcohol", label: "Alcohol" },
    { key: "travel", label: "Travel" },
    { key: "sauna", label: "Sauna" },
    { key: "cold_plunge", label: "Cold Plunge" },
    { key: "fasted_training", label: "Fasted Training" },
  ];

  return (
    <form onSubmit={handleSubmit} style={styles.journalForm}>
      <div style={styles.journalToggles}>
        {boolFields.map(({ key, label }) => (
          <label key={key} style={styles.toggleLabel}>
            <input
              type="checkbox"
              checked={form[key]}
              onChange={() => toggle(key)}
              style={{ marginRight: 6 }}
            />
            {label}
          </label>
        ))}
      </div>
      <textarea
        placeholder="Notes (optional)…"
        value={form.notes}
        onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
        style={styles.textarea}
        rows={3}
      />
      {error && <div style={{ color: "var(--red)", fontSize: 12 }}>{error}</div>}
      <button type="submit" disabled={saving} style={styles.submitBtn}>
        {saving ? "Saving…" : saved ? "Saved ✓" : `Log for ${today()}`}
      </button>
    </form>
  );
}

// ---------------------------------------------------------------------------
// Main Dashboard
// ---------------------------------------------------------------------------
export default function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [sleep, setSleep] = useState([]);
  const [recovery, setRecovery] = useState([]);
  const [workouts, setWorkouts] = useState([]);
  const [cycles, setCycles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, sl, rec, wkt, cyc] = await Promise.all([
        fetchSummary(),
        fetchSleep(30),
        fetchRecovery(30),
        fetchWorkouts(30),
        fetchCycles(30),
      ]);
      setSummary(s);
      setSleep([...sl].reverse());
      setRecovery([...rec].reverse());
      setWorkouts(wkt);
      setCycles([...cyc].reverse());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // ---- Merge chart data (recovery + HRV by date) ----
  const recoveryChartData = recovery.map((r) => ({
    date: fmtDate(r.date),
    recovery_score: r.recovery_score != null ? Number(r.recovery_score) : null,
    hrv_rmssd: r.hrv_rmssd != null ? Number(r.hrv_rmssd) : null,
  }));

  // ---- Sleep breakdown chart ----
  const sleepChartData = sleep.map((s) => ({
    date: fmtDate(s.date),
    sws: s.slow_wave_sleep_ms != null ? +(s.slow_wave_sleep_ms / 3_600_000).toFixed(2) : null,
    rem: s.rem_sleep_ms != null ? +(s.rem_sleep_ms / 3_600_000).toFixed(2) : null,
    light: s.light_sleep_ms != null ? +(s.light_sleep_ms / 3_600_000).toFixed(2) : null,
  }));

  // ---- Strain vs recovery chart ----
  const strainRecoveryData = cycles.map((c) => {
    const rec = recovery.find((r) => r.date === c.date);
    return {
      date: fmtDate(c.date),
      day_strain: c.day_strain != null ? Number(c.day_strain) : null,
      recovery_score: rec?.recovery_score != null ? Number(rec.recovery_score) : null,
    };
  });

  // ---- Strain:Recovery ratio chart ----
  const ratioData = cycles.map((c) => {
    const rec = recovery.find((r) => r.date === c.date);
    const ratio =
      c.day_strain != null && rec?.recovery_score && Number(rec.recovery_score) !== 0
        ? +(Number(c.day_strain) / Number(rec.recovery_score)).toFixed(3)
        : null;
    return { date: fmtDate(c.date), ratio };
  });

  // ---- Recent workouts table (last 10) ----
  const recentWorkouts = workouts.slice(0, 10);

  if (loading) {
    return (
      <div style={styles.loading}>
        <div>Loading health data…</div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={styles.loading}>
        <div style={{ color: "var(--red)" }}>Error: {error}</div>
        <button onClick={load} style={{ ...styles.submitBtn, marginTop: 12 }}>
          Retry
        </button>
      </div>
    );
  }

  const strainFlag = summary?.strain_recovery_flag;

  return (
    <div style={styles.page}>
      {/* ---- Header ---- */}
      <header style={styles.header}>
        <h1 style={styles.title}>WHOOP Health Dashboard</h1>
        {summary?.strain_recovery_flag && (
          <div style={styles.flagBanner}>
            ⚠ Strain:Recovery ratio &gt; 1.0 for 3+ of the last 7 days — consider a deload.
          </div>
        )}
      </header>

      {/* ---- 7-day Summary Stats ---- */}
      <section style={styles.section}>
        <SectionHeader>7-Day Averages</SectionHeader>
        <div style={styles.statsGrid}>
          <StatCard
            label="HRV (rMSSD)"
            value={round1(summary?.hrv_rmssd_7d_avg)}
            unit="ms"
            delta={summary?.hrv_vs_30d_baseline}
          />
          <StatCard
            label="Resting HR"
            value={round1(summary?.resting_hr_7d_avg)}
            unit="bpm"
          />
          <StatCard
            label="Sleep Duration"
            value={round1(summary?.sleep_duration_7d_avg_hrs)}
            unit="hrs"
          />
          <StatCard
            label="Slow-Wave Sleep"
            value={round1(summary?.sws_7d_avg_hrs)}
            unit="hrs"
          />
          <StatCard
            label="Recovery Score"
            value={round0(summary?.recovery_score_7d_avg)}
            unit="%"
          />
          <StatCard
            label="Day Strain"
            value={round1(summary?.day_strain_7d_avg)}
          />
          <StatCard
            label="Strain:Recovery"
            value={round1(summary?.strain_to_recovery_ratio_7d)}
            flag={strainFlag}
          />
          <StatCard
            label="Sleep Debt"
            value={round1(summary?.sleep_debt_7d_hrs)}
            unit="hrs"
          />
        </div>

        {/* HRV trend badge */}
        {summary?.hrv_trend_7d && (
          <div style={styles.trendBadge(summary.hrv_trend_7d)}>
            HRV trend (7d): {summary.hrv_trend_7d.toUpperCase()}
          </div>
        )}

        {/* Notable outliers */}
        {summary?.notable_outliers?.length > 0 && (
          <div style={styles.outliers}>
            <strong>Notable outliers:</strong>
            <ul style={{ marginTop: 4, paddingLeft: 18 }}>
              {summary.notable_outliers.map((o, i) => (
                <li key={i} style={{ color: "var(--orange)", fontSize: 13 }}>{o}</li>
              ))}
            </ul>
          </div>
        )}
      </section>

      {/* ---- Recovery + HRV Chart ---- */}
      <section style={styles.section}>
        <SectionHeader>Recovery Score &amp; HRV — 30 days</SectionHeader>
        <div style={styles.chartWrap}>
          <ResponsiveContainer width="100%" height={260}>
            <ComposedChart data={recoveryChartData} margin={{ top: 8, right: 24, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="date" tick={{ fill: "var(--muted)", fontSize: 11 }} interval={4} />
              <YAxis yAxisId="left" domain={[0, 100]} tick={{ fill: "var(--muted)", fontSize: 11 }} />
              <YAxis yAxisId="right" orientation="right" domain={["auto", "auto"]} tick={{ fill: "var(--muted)", fontSize: 11 }} />
              <Tooltip content={<ChartTooltip />} />
              <Legend wrapperStyle={{ color: "var(--muted)", fontSize: 12 }} />
              <Area
                yAxisId="left"
                type="monotone"
                dataKey="recovery_score"
                name="Recovery %"
                fill="rgba(79,195,247,0.12)"
                stroke="var(--accent)"
                strokeWidth={2}
                dot={false}
              />
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="hrv_rmssd"
                name="HRV ms"
                stroke="var(--purple)"
                strokeWidth={2}
                dot={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </section>

      {/* ---- Sleep Breakdown Chart ---- */}
      <section style={styles.section}>
        <SectionHeader>Sleep Breakdown — 30 days</SectionHeader>
        <p style={styles.chartNote}>
          Stages are trend indicators only — absolute values should not be over-interpreted.
        </p>
        <div style={styles.chartWrap}>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={sleepChartData} margin={{ top: 8, right: 24, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="date" tick={{ fill: "var(--muted)", fontSize: 11 }} interval={4} />
              <YAxis tick={{ fill: "var(--muted)", fontSize: 11 }} unit="h" />
              <Tooltip content={<ChartTooltip />} />
              <Legend wrapperStyle={{ color: "var(--muted)", fontSize: 12 }} />
              <Bar dataKey="light" name="Light (hrs)" stackId="a" fill="#546e7a" />
              <Bar dataKey="rem" name="REM (hrs)" stackId="a" fill="var(--purple)" />
              <Bar dataKey="sws" name="SWS (hrs)" stackId="a" fill="var(--accent)" radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      {/* ---- Day Strain vs Recovery Chart ---- */}
      <section style={styles.section}>
        <SectionHeader>Day Strain vs Recovery Score — 30 days</SectionHeader>
        <div style={styles.chartWrap}>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={strainRecoveryData} margin={{ top: 8, right: 24, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="date" tick={{ fill: "var(--muted)", fontSize: 11 }} interval={4} />
              <YAxis yAxisId="left" domain={[0, 100]} tick={{ fill: "var(--muted)", fontSize: 11 }} />
              <YAxis yAxisId="right" orientation="right" domain={[0, 21]} tick={{ fill: "var(--muted)", fontSize: 11 }} />
              <Tooltip content={<ChartTooltip />} />
              <Legend wrapperStyle={{ color: "var(--muted)", fontSize: 12 }} />
              <Line
                yAxisId="left"
                type="monotone"
                dataKey="recovery_score"
                name="Recovery %"
                stroke="var(--green)"
                strokeWidth={2}
                dot={false}
              />
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="day_strain"
                name="Day Strain"
                stroke="var(--orange)"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>

      {/* ---- Strain:Recovery Ratio Chart ---- */}
      <section style={styles.section}>
        <SectionHeader>Strain:Recovery Ratio — 30 days</SectionHeader>
        <div style={styles.chartWrap}>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={ratioData} margin={{ top: 8, right: 24, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="date" tick={{ fill: "var(--muted)", fontSize: 11 }} interval={4} />
              <YAxis domain={[0, "auto"]} tick={{ fill: "var(--muted)", fontSize: 11 }} />
              <Tooltip content={<ChartTooltip />} />
              <ReferenceLine y={1.0} stroke="var(--red)" strokeDasharray="6 3" label={{ value: "1.0 limit", fill: "var(--red)", fontSize: 11 }} />
              <Line
                type="monotone"
                dataKey="ratio"
                name="Strain:Recovery"
                stroke={strainFlag ? "var(--red)" : "var(--yellow)"}
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>

      {/* ---- Recent Workouts Table ---- */}
      <section style={styles.section}>
        <SectionHeader>Recent Workouts (last 10)</SectionHeader>
        <div style={{ overflowX: "auto" }}>
          <table style={styles.table}>
            <thead>
              <tr>
                {["Date", "Sport", "Duration", "Strain", "Avg HR", "Calories"].map((h) => (
                  <th key={h} style={styles.th}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {recentWorkouts.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ ...styles.td, color: "var(--muted)", textAlign: "center" }}>
                    No workout data available.
                  </td>
                </tr>
              ) : (
                recentWorkouts.map((w) => (
                  <tr key={w.workout_id} style={styles.tr}>
                    <td style={styles.td}>{w.date}</td>
                    <td style={styles.td}>{w.sport_name || "—"}</td>
                    <td style={styles.td}>{w.duration_ms ? `${Math.round(w.duration_ms / 60000)} min` : "—"}</td>
                    <td style={styles.td}>{round1(w.strain_score)}</td>
                    <td style={styles.td}>{round0(w.avg_hr)}</td>
                    <td style={styles.td}>{w.calories ? `${Math.round(w.calories)} kcal` : "—"}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* ---- Journal Panel ---- */}
      <section style={styles.section}>
        <SectionHeader>Log Today's Journal</SectionHeader>
        <JournalPanel onSaved={load} />
      </section>

      <footer style={styles.footer}>
        WHOOP Health Dashboard — data latency ~24 hrs. Sleep stages are trend indicators only.
      </footer>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------
const styles = {
  page: {
    maxWidth: 1100,
    margin: "0 auto",
    padding: "24px 16px 48px",
  },
  header: {
    marginBottom: 32,
  },
  title: {
    fontSize: 24,
    color: "var(--text)",
    marginBottom: 8,
  },
  flagBanner: {
    background: "rgba(239,83,80,0.15)",
    border: "1px solid var(--red)",
    borderRadius: 6,
    padding: "10px 14px",
    color: "var(--red)",
    fontWeight: 600,
    fontSize: 13,
    marginTop: 8,
  },
  section: {
    marginBottom: 40,
  },
  sectionHeader: {
    fontSize: 16,
    color: "var(--accent)",
    marginBottom: 16,
    paddingBottom: 8,
    borderBottom: "1px solid var(--border)",
  },
  statsGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))",
    gap: 12,
    marginBottom: 16,
  },
  card: {
    background: "var(--surface)",
    border: "1px solid var(--border)",
    borderRadius: 8,
    padding: "14px 16px",
  },
  cardLabel: {
    color: "var(--muted)",
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    marginBottom: 4,
  },
  cardValue: {
    fontSize: 22,
    fontWeight: 700,
    color: "var(--text)",
    lineHeight: 1.2,
  },
  cardUnit: {
    fontSize: 13,
    fontWeight: 400,
    color: "var(--muted)",
  },
  trendBadge: (trend) => ({
    display: "inline-block",
    padding: "4px 10px",
    borderRadius: 20,
    fontSize: 12,
    fontWeight: 600,
    marginTop: 4,
    background:
      trend === "positive"
        ? "rgba(102,187,106,0.15)"
        : trend === "declining"
        ? "rgba(239,83,80,0.15)"
        : "rgba(139,143,168,0.15)",
    color:
      trend === "positive"
        ? "var(--green)"
        : trend === "declining"
        ? "var(--red)"
        : "var(--muted)",
  }),
  outliers: {
    marginTop: 12,
    padding: "10px 14px",
    background: "rgba(255,167,38,0.08)",
    border: "1px solid rgba(255,167,38,0.25)",
    borderRadius: 6,
    fontSize: 13,
    color: "var(--text)",
  },
  chartWrap: {
    background: "var(--surface)",
    border: "1px solid var(--border)",
    borderRadius: 8,
    padding: "16px 8px 8px",
  },
  chartNote: {
    color: "var(--muted)",
    fontSize: 11,
    marginBottom: 8,
    fontStyle: "italic",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    background: "var(--surface)",
    border: "1px solid var(--border)",
    borderRadius: 8,
    overflow: "hidden",
  },
  th: {
    padding: "10px 14px",
    textAlign: "left",
    color: "var(--muted)",
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    borderBottom: "1px solid var(--border)",
    background: "var(--surface)",
  },
  td: {
    padding: "10px 14px",
    fontSize: 13,
    borderBottom: "1px solid var(--border)",
    color: "var(--text)",
  },
  tr: {
    transition: "background 0.15s",
  },
  journalForm: {
    background: "var(--surface)",
    border: "1px solid var(--border)",
    borderRadius: 8,
    padding: "20px",
    display: "flex",
    flexDirection: "column",
    gap: 14,
  },
  journalToggles: {
    display: "flex",
    flexWrap: "wrap",
    gap: 14,
  },
  toggleLabel: {
    display: "flex",
    alignItems: "center",
    color: "var(--text)",
    cursor: "pointer",
    fontSize: 13,
  },
  textarea: {
    background: "var(--bg)",
    border: "1px solid var(--border)",
    borderRadius: 6,
    color: "var(--text)",
    padding: "10px 12px",
    fontSize: 13,
    resize: "vertical",
    outline: "none",
  },
  submitBtn: {
    alignSelf: "flex-start",
    background: "var(--accent)",
    color: "#0d0d0f",
    border: "none",
    borderRadius: 6,
    padding: "9px 20px",
    fontWeight: 600,
    fontSize: 13,
  },
  loading: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    minHeight: "80vh",
    color: "var(--muted)",
    fontSize: 16,
  },
  tooltip: {
    background: "var(--surface)",
    border: "1px solid var(--border)",
    borderRadius: 6,
    padding: "8px 12px",
    fontSize: 12,
  },
  footer: {
    color: "var(--muted)",
    fontSize: 11,
    textAlign: "center",
    marginTop: 16,
    paddingTop: 16,
    borderTop: "1px solid var(--border)",
  },
};
