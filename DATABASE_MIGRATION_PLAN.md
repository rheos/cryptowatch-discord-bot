# Database Migration Plan - V2 to V3

## Current State (V2)
- EAV pattern with string keys for settings
- JSON blobs in settings columns
- Inconsistent channel storage (timezone stored as part of type)
- No proper foreign keys for settings
- Working but not scalable

## Target State (V3)
- Properly normalized relational schema
- Integer foreign keys for settings
- Dedicated tables for different configuration types
- No JSON storage (except where truly variable)
- Optimized for queries with proper indexes

## Migration Strategy

### Phase 1: Parallel Schema (No Downtime, No Data Loss)
1. Create new V3 tables alongside existing V2 tables
2. Migrate existing data to new tables via script
3. Keep both schemas active temporarily
4. No code changes required yet

### Phase 2: Dual-Write (Safety Net)
1. Update database.py to write to BOTH V2 and V3 tables
2. Continue reading from V2 tables only
3. Monitor V3 tables to ensure data integrity
4. Can instantly rollback if issues

### Phase 3: Gradual Read Migration
1. Migrate read operations one at a time
2. Start with low-risk queries (setup show)
3. Move to critical queries (engagement tracking)
4. Test each migration thoroughly

### Phase 4: Cleanup
1. Stop writing to V2 tables
2. Keep V2 tables for 30 days as backup
3. Drop V2 tables after verification

## New Schema Design

### Settings Tables
```sql
-- Settings registry (immutable after creation)
CREATE TABLE settings_registry (
    setting_id INT PRIMARY KEY AUTO_INCREMENT,
    setting_key VARCHAR(50) UNIQUE NOT NULL,
    setting_type ENUM('boolean', 'integer', 'decimal', 'string') NOT NULL,
    default_value VARCHAR(255),
    description TEXT,
    category VARCHAR(50),
    INDEX idx_key (setting_key),
    INDEX idx_category (category)
);

-- Guild settings (normalized)
CREATE TABLE guild_settings_v3 (
    guild_id BIGINT NOT NULL,
    setting_id INT NOT NULL,
    value VARCHAR(255) NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (guild_id, setting_id),
    FOREIGN KEY (setting_id) REFERENCES settings_registry(setting_id),
    INDEX idx_guild (guild_id)
);
```

### Channel Configuration Tables
```sql
-- Timezone channels
CREATE TABLE timezone_channels (
    guild_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    timezone VARCHAR(50) NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (channel_id),
    INDEX idx_guild (guild_id),
    INDEX idx_timezone (timezone)
);

-- Alert channels
CREATE TABLE alert_channels (
    guild_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    alert_type ENUM('market_events', 'funding', 'volatility', 'general') NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (channel_id),
    UNIQUE KEY uk_guild_type (guild_id, alert_type),
    INDEX idx_guild (guild_id)
);

-- Market event channels
CREATE TABLE market_channels (
    guild_id BIGINT NOT NULL,
    countdown_channel_id BIGINT,
    schedule_channel_id BIGINT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (guild_id)
);
```

### Future: User Preferences Tables
```sql
-- User alert preferences (for future DM alerts)
CREATE TABLE user_alert_preferences (
    user_id BIGINT NOT NULL,
    guild_id BIGINT NOT NULL,
    alert_type ENUM('volatility', 'funding', 'price') NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    dm_enabled BOOLEAN DEFAULT FALSE,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, guild_id, alert_type),
    INDEX idx_guild_type (guild_id, alert_type)
);

-- User coin watchlist
CREATE TABLE user_watchlist (
    user_id BIGINT NOT NULL,
    guild_id BIGINT NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    volatility_threshold DECIMAL(5,2),
    funding_threshold DECIMAL(5,2),
    price_alert_above DECIMAL(20,8),
    price_alert_below DECIMAL(20,8),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, guild_id, symbol),
    INDEX idx_symbol (symbol),
    INDEX idx_guild (guild_id)
);

-- Guild threshold overrides
CREATE TABLE guild_thresholds (
    guild_id BIGINT NOT NULL,
    threshold_type ENUM('volatility_1h', 'volatility_4h', 'volatility_24h', 
                       'funding_positive', 'funding_negative') NOT NULL,
    value DECIMAL(10,2) NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (guild_id, threshold_type)
);
```

## Data Migration Scripts

### 1. Populate settings_registry
```sql
INSERT INTO settings_registry (setting_key, setting_type, default_value, category) VALUES
('engagement.enabled', 'boolean', 'false', 'engagement'),
('engagement.messages_threshold', 'integer', '10', 'engagement'),
('engagement.days_threshold', 'integer', '30', 'engagement'),
('engagement.warning_days', 'integer', '7', 'engagement'),
('market_events.enabled', 'boolean', 'false', 'market'),
-- etc...
```

### 2. Migrate guild_settings
```sql
INSERT INTO guild_settings_v3 (guild_id, setting_id, value)
SELECT 
    gs.guild_id,
    sr.setting_id,
    gs.setting_value
FROM guild_settings gs
JOIN settings_registry sr ON sr.setting_key = gs.setting_key;
```

### 3. Migrate channel configurations
```sql
-- Timezone channels (fix the messy storage)
INSERT INTO timezone_channels (guild_id, channel_id, timezone)
SELECT 
    guild_id,
    channel_id,
    JSON_UNQUOTE(JSON_EXTRACT(settings, '$.timezone'))
FROM guild_channels
WHERE channel_type LIKE 'timezone_%';

-- Alert channels
INSERT INTO alert_channels (guild_id, channel_id, alert_type)
SELECT guild_id, channel_id, channel_type
FROM guild_channels
WHERE channel_type IN ('market_events', 'funding', 'alerts');
```

## Rollback Plan
1. Keep V2 tables intact during migration
2. If issues arise, simply revert code to read from V2 tables
3. No data loss since we're dual-writing
4. Can re-attempt migration after fixing issues

## Success Criteria
- [ ] All existing data migrated successfully
- [ ] No increase in query latency
- [ ] All bot features working identically
- [ ] Can handle 1000+ guilds without performance degradation
- [ ] Queries for user preferences complete in <100ms

## Timeline
- Week 1: Create V3 schema, migration scripts, backfill tools
- Week 2: Deploy parallel schema, begin dual-write
- Week 3: Gradually migrate read operations
- Week 4: Monitor, optimize, and cleanup

## Risk Assessment
- **Low Risk**: Running parallel schemas temporarily
- **Medium Risk**: Data consistency during dual-write phase
- **Mitigation**: Extensive logging, monitoring, ability to instant rollback