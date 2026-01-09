-- Initialize database with required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create database if not exists (handled by Docker)

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE check_review TO postgres;

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
