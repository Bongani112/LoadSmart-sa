-- LoadSmart SA — PostgreSQL Database Schema

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    full_name VARCHAR(150) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    monthly_kwh_target NUMERIC(10, 2) DEFAULT 380.00,
    tariff_rate_zar NUMERIC(6, 2) DEFAULT 3.00,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE locations (
    id SERIAL PRIMARY KEY,
    province VARCHAR(100) NOT NULL,
    municipality VARCHAR(120) NOT NULL,
    suburb VARCHAR(120) NOT NULL,
    UNIQUE(province, municipality, suburb)
);

-- Distinguishes verified official schedules from unverified community reports
CREATE TABLE outages (
    id SERIAL PRIMARY KEY,
    location_id INT NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
    title VARCHAR(200) NOT NULL,
    outage_type VARCHAR(50) NOT NULL, -- 'SCHEDULED', 'UNEXPECTED', 'INFRASTRUCTURE', 'RESTORED'
    source_type VARCHAR(30) NOT NULL CHECK (source_type IN ('OFFICIAL', 'COMMUNITY')),
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    notes TEXT,
    reported_by INT REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE electricity_usage (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    usage_date DATE NOT NULL DEFAULT CURRENT_DATE,
    kwh_consumed NUMERIC(10, 2) NOT NULL CHECK (kwh_consumed >= 0),
    estimated_cost_zar NUMERIC(10, 2) NOT NULL
);

CREATE TABLE user_appliances (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(120) NOT NULL,
    power_watts INT NOT NULL CHECK (power_watts > 0),
    daily_hours NUMERIC(4, 2) NOT NULL CHECK (daily_hours >= 0)
);

CREATE TABLE backup_systems (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE CASCADE,
    system_name VARCHAR(100) DEFAULT 'Primary Home Inverter',
    battery_capacity_wh INT NOT NULL CHECK (battery_capacity_wh > 0),
    inverter_rating_w INT NOT NULL CHECK (inverter_rating_w > 0),
    current_charge_pct NUMERIC(5, 2) NOT NULL CHECK (current_charge_pct BETWEEN 0 AND 100),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Performance indexes for location filtering and time-series queries
CREATE INDEX idx_outages_location_time ON outages (location_id, start_time DESC);
CREATE INDEX idx_usage_user_date ON electricity_usage (user_id, usage_date DESC);

-- Seed initial South African locations
INSERT INTO locations (province, municipality, suburb) VALUES
('Gauteng', 'Emfuleni', 'Vanderbijlpark'),
('Gauteng', 'City of Johannesburg', 'Randburg'),
('Western Cape', 'City of Cape Town', 'Bellville');