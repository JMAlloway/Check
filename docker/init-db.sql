-- Initialize database with required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create database if not exists (handled by Docker)

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE check_review TO postgres;
