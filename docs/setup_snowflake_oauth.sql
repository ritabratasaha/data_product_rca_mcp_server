-- =============================================================================
-- Snowflake OAuth Integration Setup for MCP Server
-- =============================================================================
-- This script creates a Snowflake OAuth security integration that allows the
-- MCP server to authenticate users via their Snowflake credentials.
--
-- Prerequisites:
-- 1. You must have ACCOUNTADMIN or SECURITYADMIN role to create security integrations
-- 2. Note your Snowflake account identifier (e.g., "abc12345" or "abc12345.us-east-1")
--
-- After running this script:
-- 1. Get the CLIENT_ID and CLIENT_SECRET from DESCRIBE SECURITY INTEGRATION
-- 2. Add them to your .env file as SNOWFLAKE_OAUTH_CLIENT_ID and SNOWFLAKE_OAUTH_CLIENT_SECRET
-- =============================================================================

-- Use ACCOUNTADMIN role to create security integration
USE ROLE ACCOUNTADMIN;

-- =============================================================================
-- Step 1: Create the OAuth Security Integration
-- =============================================================================
-- This creates a Snowflake OAuth integration for the MCP server
-- Adjust OAUTH_REDIRECT_URI to match your server's callback URL

CREATE OR REPLACE SECURITY INTEGRATION mcp_server_oauth
    TYPE = OAUTH
    ENABLED = TRUE
    OAUTH_CLIENT = CUSTOM
    OAUTH_CLIENT_TYPE = 'CONFIDENTIAL'
    OAUTH_REDIRECT_URI = 'http://localhost:8000/auth/callback'
    OAUTH_ISSUE_REFRESH_TOKENS = TRUE
    OAUTH_REFRESH_TOKEN_VALIDITY = 86400  -- 24 hours in seconds
    COMMENT = 'OAuth integration for MCP RCA Server';

-- =============================================================================
-- Step 2: Get the Client Credentials
-- =============================================================================
-- After creating the integration, get the CLIENT_ID and CLIENT_SECRET
-- IMPORTANT: The CLIENT_SECRET is only shown once when you run this command!
-- Make sure to save it immediately.

-- Show integration details (includes CLIENT_ID)
DESCRIBE SECURITY INTEGRATION mcp_server_oauth;

-- Get the client secret (only shown once!)
-- Copy this value to your .env file as SNOWFLAKE_OAUTH_CLIENT_SECRET
SELECT SYSTEM$SHOW_OAUTH_CLIENT_SECRETS('MCP_SERVER_OAUTH');

-- =============================================================================
-- Step 3: Configure Environment Variables
-- =============================================================================
-- Add these to your .env file:
--
-- # Snowflake OAuth Configuration
-- SNOWFLAKE_ACCOUNT=<your-account-identifier>
-- SNOWFLAKE_OAUTH_CLIENT_ID=<CLIENT_ID from DESCRIBE above>
-- SNOWFLAKE_OAUTH_CLIENT_SECRET=<SECRET from SYSTEM$SHOW_OAUTH_CLIENT_SECRETS>
-- SNOWFLAKE_OAUTH_ROLES=PUBLIC  # Comma-separated list of roles to request
--
-- =============================================================================

-- =============================================================================
-- Step 4: (Optional) Grant Additional Roles for OAuth Users
-- =============================================================================
-- By default, OAuth users can only use roles granted to them.
-- Grant additional roles if needed:

-- Example: Grant a specific role to a user for OAuth access
-- GRANT ROLE ANALYST TO USER your_username;

-- =============================================================================
-- Step 5: (Optional) Modify Integration Settings
-- =============================================================================
-- If you need to change settings later:

-- Change redirect URI for production deployment
-- ALTER SECURITY INTEGRATION mcp_server_oauth
--     SET OAUTH_REDIRECT_URI = 'https://your-production-server.com/auth/callback';

-- Extend refresh token validity (max 90 days = 7776000 seconds)
-- ALTER SECURITY INTEGRATION mcp_server_oauth
--     SET OAUTH_REFRESH_TOKEN_VALIDITY = 7776000;

-- =============================================================================
-- Troubleshooting Commands
-- =============================================================================

-- List all OAuth integrations
-- SHOW SECURITY INTEGRATIONS;

-- Check integration status
-- DESCRIBE SECURITY INTEGRATION mcp_server_oauth;

-- View OAuth authorization history
-- SELECT * FROM SNOWFLAKE.ACCOUNT_USAGE.OAUTH_ACCESS_TOKEN_AUDIT_LOG
-- WHERE CLIENT_ID = '<your-client-id>'
-- ORDER BY EVENT_TIMESTAMP DESC
-- LIMIT 10;

-- =============================================================================
-- Cleanup (if needed)
-- =============================================================================
-- To remove the OAuth integration:
-- DROP SECURITY INTEGRATION mcp_server_oauth;


-- =============================================================================
-- Testing User Setup (for MCP Evals / CI)
-- =============================================================================
-- Create a minimal user with PUBLIC role only for running MCP evals.
-- This user can connect and query INFORMATION_SCHEMA but has no access to
-- application data.
--
-- IMPORTANT: Change the password before running in production!
-- =============================================================================

-- Create testing user with PUBLIC role only
CREATE USER IF NOT EXISTS MCP_TESTING_USER
    PASSWORD = 'TestingPassword123!'
    DEFAULT_ROLE = PUBLIC
    DEFAULT_WAREHOUSE = COMPUTE_WH
    MUST_CHANGE_PASSWORD = FALSE
    COMMENT = 'Minimal user for MCP server testing and CI/CD evals';

-- Grant PUBLIC role (implicitly granted, but explicit for clarity)
GRANT ROLE PUBLIC TO USER MCP_TESTING_USER;

-- Verify user was created
SHOW USERS LIKE 'MCP_TESTING_USER';

-- =============================================================================
-- Testing User Environment Variables
-- =============================================================================
-- Add these to your .env file for TESTING mode:
--
-- TESTING_SNOWFLAKE_USER=MCP_TESTING_USER
-- TESTING_SNOWFLAKE_PASSWORD=TestingPassword123!
--
-- =============================================================================

-- =============================================================================
-- Testing User Cleanup (if needed)
-- =============================================================================
-- To remove the testing user:
-- DROP USER MCP_TESTING_USER;
