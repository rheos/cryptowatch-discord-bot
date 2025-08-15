-- Drop all tables in cryptowatch_bot database
SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS user_watchlist;
DROP TABLE IF EXISTS user_alert_preferences;
DROP TABLE IF EXISTS alert_history;
DROP TABLE IF EXISTS guild_usage;
DROP TABLE IF EXISTS guild_subscriptions;
DROP TABLE IF EXISTS member_status;
DROP TABLE IF EXISTS member_activity_daily;
DROP TABLE IF EXISTS timezone_channels;
DROP TABLE IF EXISTS guild_settings;
DROP TABLE IF EXISTS settings_registry;
DROP TABLE IF EXISTS settings_sections;
DROP TABLE IF EXISTS timezone_definitions;
DROP TABLE IF EXISTS audit_log;
DROP TABLE IF EXISTS subscription_tiers;
DROP TABLE IF EXISTS guilds;
DROP TABLE IF EXISTS schema_migrations;

SET FOREIGN_KEY_CHECKS = 1;

SELECT 'All tables dropped successfully' as message;