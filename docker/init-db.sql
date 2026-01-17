-- Initialize database with required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create database if not exists (handled by Docker)

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE check_review TO postgres;

-- Create PostgreSQL enum types required by fraud models
-- These must be created before tables because models use create_type=False

-- fraud_type enum
DO $$ BEGIN
    CREATE TYPE fraud_type AS ENUM (
        'check_kiting', 'counterfeit_check', 'forged_signature', 'altered_check',
        'account_takeover', 'identity_theft', 'first_party_fraud', 'synthetic_identity',
        'duplicate_deposit', 'unauthorized_endorsement', 'payee_alteration',
        'amount_alteration', 'fictitious_payee', 'other'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- fraud_channel enum
DO $$ BEGIN
    CREATE TYPE fraud_channel AS ENUM (
        'branch', 'atm', 'mobile', 'rdc', 'mail', 'online', 'other'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- amount_bucket enum
DO $$ BEGIN
    CREATE TYPE amount_bucket AS ENUM (
        'under_100', '100_to_500', '500_to_1000', '1000_to_5000',
        '5000_to_10000', '10000_to_50000', 'over_50000'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- fraud_event_status enum
DO $$ BEGIN
    CREATE TYPE fraud_event_status AS ENUM (
        'draft', 'submitted', 'withdrawn'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- match_severity enum
DO $$ BEGIN
    CREATE TYPE match_severity AS ENUM (
        'low', 'medium', 'high'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- Fix minimum_alert_severity column type if it's an enum (convert to varchar)
-- This handles the case where the table was created with the old enum type
DO $$
BEGIN
    -- Check if the column exists and is an enum type, then alter it
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'tenant_fraud_configs'
        AND column_name = 'minimum_alert_severity'
        AND udt_name = 'match_severity'
    ) THEN
        ALTER TABLE tenant_fraud_configs
        ALTER COLUMN minimum_alert_severity TYPE VARCHAR(10)
        USING minimum_alert_severity::text;
    END IF;
END $$;
