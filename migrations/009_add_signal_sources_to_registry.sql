-- Add signal source channel settings to the registry
-- These will be used to configure which channel each signal source should post to

-- Use the existing alerts section (section_id = 3)
SET @alerts_section_id = 3;

-- Add a general setting to enable/disable signal processing for the guild
INSERT IGNORE INTO settings_registry (
  setting_key,
  setting_type,
  default_value,
  description,
  section_id,
  display_order,
  is_advanced
) VALUES
  ('signals_enabled', 'boolean', 'false', 'Enable TradingView signal processing for this guild', @alerts_section_id, 19, 0);

-- Note: Signal source channel settings will be added dynamically as needed
-- When a guild configures a signal source channel, the setting will be registered
-- automatically if it doesn't exist yet. This allows for dynamic signal sources
-- without hardcoding them in the migration.