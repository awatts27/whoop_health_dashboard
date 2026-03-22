-- WHOOP Health Dashboard — Supabase Schema
-- All upserts are idempotent via ON CONFLICT (date) DO UPDATE

-- ============================================================
-- sleep: one row per night
-- ============================================================
CREATE TABLE IF NOT EXISTS sleep (
    id                      BIGSERIAL PRIMARY KEY,
    date                    DATE        NOT NULL UNIQUE,
    total_sleep_duration_ms BIGINT,
    time_in_bed_ms          BIGINT,
    sleep_efficiency        NUMERIC(5,4),   -- derived: total_sleep / time_in_bed
    sleep_latency_ms        BIGINT,
    light_sleep_ms          BIGINT,
    rem_sleep_ms            BIGINT,
    slow_wave_sleep_ms      BIGINT,
    num_awakenings          INTEGER,
    sleep_need_ms           BIGINT,         -- WHOOP calculated
    sleep_debt_ms           BIGINT,         -- derived: sleep_need - total_sleep
    sleep_score             NUMERIC(5,2),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- recovery: one row per day
-- ============================================================
CREATE TABLE IF NOT EXISTS recovery (
    id                  BIGSERIAL PRIMARY KEY,
    date                DATE        NOT NULL UNIQUE,
    recovery_score      NUMERIC(5,2),
    hrv_rmssd           NUMERIC(8,3),   -- raw ms, not normalized
    resting_hr          NUMERIC(6,2),
    skin_temp_celsius   NUMERIC(6,3),
    spo2_avg            NUMERIC(6,3),
    spo2_min            NUMERIC(6,3),
    respiratory_rate    NUMERIC(6,3),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- workouts: multiple per day possible
-- ============================================================
CREATE TABLE IF NOT EXISTS workouts (
    id          BIGSERIAL PRIMARY KEY,
    date        DATE        NOT NULL,
    workout_id  TEXT        NOT NULL UNIQUE,
    sport_name  TEXT,
    duration_ms BIGINT,
    strain_score NUMERIC(5,2),
    avg_hr      NUMERIC(6,2),
    max_hr      INTEGER,
    calories    NUMERIC(8,2),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- cycles: daily strain cycle
-- ============================================================
CREATE TABLE IF NOT EXISTS cycles (
    id          BIGSERIAL PRIMARY KEY,
    date        DATE        NOT NULL UNIQUE,
    day_strain  NUMERIC(5,2),
    kilojoules  NUMERIC(10,3),
    avg_hr      NUMERIC(6,2),
    max_hr      INTEGER,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- journal: one row per day
-- ============================================================
CREATE TABLE IF NOT EXISTS journal (
    id                  BIGSERIAL PRIMARY KEY,
    date                DATE        NOT NULL UNIQUE,
    notes               TEXT,
    alcohol             BOOLEAN     DEFAULT FALSE,
    travel              BOOLEAN     DEFAULT FALSE,
    sauna               BOOLEAN     DEFAULT FALSE,
    cold_plunge         BOOLEAN     DEFAULT FALSE,
    fasted_training     BOOLEAN     DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- daily_summary: materialized join across all streams
-- ============================================================
CREATE TABLE IF NOT EXISTS daily_summary (
    id                          BIGSERIAL PRIMARY KEY,
    date                        DATE        NOT NULL UNIQUE,
    -- recovery
    recovery_score              NUMERIC(5,2),
    hrv_rmssd                   NUMERIC(8,3),
    resting_hr                  NUMERIC(6,2),
    skin_temp_celsius           NUMERIC(6,3),
    spo2_avg                    NUMERIC(6,3),
    respiratory_rate            NUMERIC(6,3),
    -- sleep
    total_sleep_duration_ms     BIGINT,
    slow_wave_sleep_ms          BIGINT,
    sleep_efficiency            NUMERIC(5,4),
    sleep_latency_ms            BIGINT,
    sleep_debt_ms               BIGINT,
    -- strain
    day_strain                  NUMERIC(5,2),
    total_calories              NUMERIC(10,2),
    -- derived
    strain_to_recovery_ratio    NUMERIC(8,4),   -- day_strain / recovery_score
    -- journal
    alcohol                     BOOLEAN     DEFAULT FALSE,
    travel                      BOOLEAN     DEFAULT FALSE,
    sauna                       BOOLEAN     DEFAULT FALSE,
    cold_plunge                 BOOLEAN     DEFAULT FALSE,
    fasted_training             BOOLEAN     DEFAULT FALSE,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- Indexes for common query patterns
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_sleep_date            ON sleep (date DESC);
CREATE INDEX IF NOT EXISTS idx_recovery_date         ON recovery (date DESC);
CREATE INDEX IF NOT EXISTS idx_workouts_date         ON workouts (date DESC);
CREATE INDEX IF NOT EXISTS idx_cycles_date           ON cycles (date DESC);
CREATE INDEX IF NOT EXISTS idx_journal_date          ON journal (date DESC);
CREATE INDEX IF NOT EXISTS idx_daily_summary_date    ON daily_summary (date DESC);
