# Discord Bot Architecture Documentation

## 🚨 CRITICAL: READ BEFORE MAKING ANY CHANGES

**NEVER CREATE NEW CODE WITHOUT CHECKING IF IT EXISTS**

---

## Core Principles

1. **NO DUPLICATION** - Each piece of logic exists in ONE place only
2. **CHECK FIRST** - Always search for existing functionality before creating
3. **THIN INTERFACES** - Slash commands just route to modules
4. **USE EXISTING SCRIPTS** - Heavy operations have dedicated scripts
5. **MODULAR DESIGN** - Each module has a single responsibility

---

## Directory Structure & Purpose

```
discord-bot/
├── main.py                     # Bot entry point - DO NOT DUPLICATE BOT INITIALIZATION
├── database.py                 # Database connection manager - USE THIS, DON'T CREATE NEW
├── config.*.json              # Config files per environment (dev/prod)
│
├── migrations/                # Database migrations - RUN IN ORDER
│   ├── 001_complete_schema.py # Initial schema (base state)
│   ├── 002_migrate_config.py  # Config data migration  
│   ├── 003_add_settings_registry.py # Settings registry system
│   ├── 004_add_active_days.py # Active days threshold
│   ├── 005_add_warning_settings.py # Warning system config
│   ├── 006_add_market_channels.py # Market display channels
│   └── 007_add_enforce_engagement.py # Latest: enforcement toggle & log channel
│
├── cogs/                      # Discord bot functionality
│   ├── engagement_cog.py     # Orchestrates engagement modules ONLY
│   ├── engagement/           # Modular engagement system
│   │   ├── role_manager.py   # Role assignment logic - ALL ROLE LOGIC HERE
│   │   ├── activity_tracker.py # Message tracking & buffering
│   │   ├── warning_system.py # Warning logic for inactive members
│   │   └── welcome_handler.py # New member welcome logic
│   │
│   ├── slash_commands/        # THIN WRAPPERS - NO BUSINESS LOGIC
│   │   ├── base.py           # Base class for slash commands
│   │   ├── admin_commands.py # Admin hub for member management & server admin
│   │   ├── crypto_commands.py # Routes to crypto data
│   │   ├── setup_commands.py # Bot setup & configuration
│   │   └── ai_commands.py    # AI chat interface
│   │
│   ├── crypto_data_cog.py    # Crypto data fetching & caching
│   ├── timezone_cog.py       # Timezone display in channels
│   ├── volatility_cog.py     # Volatility scanner
│   ├── ai_chat_cog.py        # AI chat functionality
│   └── market_events_cog.py  # Market event tracking
│
├── scripts/                   # STANDALONE SCRIPTS - CALL VIA SUBPROCESS
│   ├── backfill_engagement.py # ⚠️ USE THIS FOR BACKFILL - DON'T REIMPLEMENT
│   └── migrate_*.py          # Various migration scripts
│
├── utils/                     # Shared utilities
│   ├── crypto_api.py         # API client for crypto data
│   ├── config_manager.py     # Configuration management
│   ├── formatters.py         # Message formatting utilities
│   └── moderation.py         # Moderation utilities (purge, etc.)
│
└── pending_delete/           # Files to be removed - DON'T USE THESE
    ├── engagement_cog_old.py # Old monolithic version
    ├── admin_commands.py     # Old prefix commands
    ├── user_commands.py      # Old prefix commands
    └── engagement_commands.py # Redundant slash command (merged into /admin)
```

---

## Existing Functionality - DO NOT DUPLICATE

### Data Collection
- **Price Collection**: `/cron-jobs/collect_prices.py` (runs in Docker cron container)
- **Funding Rates**: `/cron-jobs/collect_funding.py` (runs in Docker cron container)
- **Backfill Engagement**: `/scripts/backfill_engagement.py` - CALL VIA SUBPROCESS
  ```python
  # CORRECT WAY TO BACKFILL:
  process = await asyncio.create_subprocess_exec(
      "python3", script_path,
      "--guild", str(guild_id),
      "--days", "30"
  )
  ```

### Database Operations
- **Database Name**: `cryptowatch_bot` (NOT discord_bot!)
- **Connection Pool**: `database.py` - USE `self.bot.db` 
- **Engagement Stats**: `self.bot.db.get_member_stats()`
- **Settings**: `self.bot.db.get_setting()` / `set_setting()`
- **Settings Registry**: All settings must be registered in `settings_registry` table
  - Settings must have valid `section_id` from `settings_sections` table
  - New settings require migration to add to registry
- **Migrations**: Use numbered migration files in `/migrations/`
  - Migrations receive cursor object, NOT pool
  - Run in order: 001 → 002 → ... → 007 (latest)
- **DO NOT**: Create new database connections or pools
- **DO NOT**: Modify database directly - use migrations

### API Endpoints (Web App)
Located in `/cryptowatchtools/app/routes/api/`:
- `/api/volatility-scanner` - Volatility data
- `/api/symbol-volatility` - Specific symbol volatility
- `/api/funding/*` - Funding rate endpoints
- `/api/market-events` - Market events data
- **DO NOT**: Create duplicate endpoints in the bot

### Discord Bot Features

#### Member Management System (via `/admin` command)
Accessed through `/admin` command - all member management in one place:
- Analyze member activity
- Show active/inactive members
- Check individual member stats
- Refresh roles based on activity
- Backfill historical data (calls script)
- Grant vacation roles
- Test warning system
- Set introductions channel
- View/modify engagement settings

**Supporting Modules:**
- **role_manager.py**: 
  - `update_member_roles()` - Update all member roles based on activity
  - `handle_new_member_message()` - Check for intro channel upgrade (50+ chars)
  - `grant_vacation_role()` - Vacation role management
  - `manually_grant_active()` - Admin override to grant Active role
  - **Enforcement**: Only removes roles if `enforce_engagement=true`
  - **Grace Period**: Won't remove roles from members who joined < lookback days ago
  - **Pro-rating**: New members get proportionally reduced thresholds (min 25% of full)
  
- **activity_tracker.py**:
  - `track_message()` - Buffer message counts
  - `flush_buffer()` - Write to database
  - `get_member_activity()` - Get member stats
  - `get_all_member_stats()` - Get all stats
  - **NOT HERE**: Backfill - use the script!

- **warning_system.py**:
  - `check_warning_needed()` - Check if warning needed
  - `send_warning()` - Send warning DM to member
  - `test_warning()` - Test warning on specific member
  - **Only Active When**:
    - `engagement_enabled=true` (tracking enabled)
    - `enforce_engagement=true` (enforcement enabled)  
    - `warning_dm_enabled=true` (DMs enabled)
  - **Grace Period**: Won't warn members who joined < lookback days ago
  - **Warning Window**: Warns members with < warning_min_messages in last warning_days

- **welcome_handler.py**:
  - `handle_member_join()` - Welcome new members with NewMember role
  - `send_welcome_message()` - Send welcome embed with intro instructions
  - **Channel Resolution** (in order):
    1. Database: `welcome_channel_id` setting
    2. Name search: First channel containing 'welcome'
    3. Silent fail if no channel found
  - **Intro Channel** (for mention in welcome):
    1. Database: `introductions_channel_id` setting  
    2. Name search: First channel containing 'introductions'
    3. Generic message if no channel found

#### Crypto Features (`/price`, `/funding`, `/volatility`)
- **crypto_data_cog.py**: Main crypto data handling
- **crypto_api.py**: API client - USE THIS, don't create new HTTP clients
- **Price Cache**: Stored in MySQL `price_snapshots` table
- **Funding Data**: Stored in MySQL `funding_rates` table

#### AI Chat (`/chat`)
- **ai_chat_cog.py**: OpenAI integration
- Uses conversation history from database
- Model: GPT-3.5-turbo

---

## Command Structure

### Slash Commands (Modern - PREFERRED)
All in `/cogs/slash_commands/`:
- `/admin` - Admin hub for member management and server administration
  - Member activity analysis, role management, engagement settings
  - All member-related administrative functions
- `/price` - Crypto prices
- `/funding` - Funding rates
- `/volatility` - Volatility scanner
- `/chat` - AI chat
- `/setup` - Bot configuration
- `/purge` - Message deletion (standalone moderation command)

### Prefix Commands (DEPRECATED - BEING REMOVED)
- **DO NOT CREATE NEW PREFIX COMMANDS**
- Convert any remaining to slash commands
- Remove prefix versions after creating slash

---

## Configuration

### Environment-Based
- **Development**: `config.development.json`
- **Production**: `config.production.json`
- **Switching**: `python switch_env.py dev|prod`

### Database Settings
Most settings now in database via `/setup` commands:

**Engagement Settings** (`/setup engagement`):
- `messages_threshold`: Min messages required for Active role (default: 10)
- `days_threshold`: Lookback period in days (default: 30)
- `active_days_threshold`: Min days with messages (optional)
- `enforce_engagement`: Enable role removal/warnings (default: false)

**Warning Settings** (`/setup warnings`):
- `warning_days`: Days to check for warning trigger (default: 14)
- `warning_min_messages`: Min messages to avoid warning (default: 5)
- `warning_dm_enabled`: Send warning DMs (default: true)

**Channel Settings** (`/setup channels`):
- `welcome_channel_id`: Where to send welcome messages
- `introductions_channel_id`: Where new members introduce themselves
- `engagement_log_channel_id`: Activity logs and role changes
- Market display channels (btc_price, funding_rates, etc.)

**Feature Toggles** (`/setup features`):
- `engagement_enabled`: Master engagement toggle
- `market_enabled`: Market price displays
- `volatility_scanner_enabled`: Volatility tracking
- Various other features

#### Engagement System Modes
1. **Disabled** (`engagement_enabled=false`): 
   - No tracking, no roles, no warnings
   - NewMember → Member upgrade still works in intro channel
   
2. **Tracking Only** (`engagement_enabled=true`, `enforce_engagement=false`):
   - Tracks all message activity
   - Grants Active role to qualifying members
   - NewMember → Member → Active progression works
   - **NO role removal** - once Active, always Active (unless manually removed)
   - **NO warning messages** sent to inactive members
   - Safe for testing thresholds without consequences
   
3. **Full Enforcement** (`engagement_enabled=true`, `enforce_engagement=true`):
   - All tracking features active
   - Removes Active role from inactive members
   - Sends warnings before role removal (if warning_dm_enabled)
   - **Grace Period Protection**:
     - New members (< lookback period in guild) are NOT subject to enforcement
     - Roles won't be removed until member has been in guild >= lookback days
     - Warnings won't be sent to members in grace period
   - Vacation role exempts members from enforcement

### Environment Variables (Docker)
Set in `docker-compose.yml`:
- `ENVIRONMENT`: dev/prod
- `API_BASE_URL`: http://app:5173/api (internal Docker network)
- `MYSQL_*`: Database credentials
  - `MYSQL_DATABASE`: `cryptowatch_bot` (Discord bot database)
  - Note: Main app uses `cryptowatchtools` database

---

## Docker Architecture

### Containers
1. **app**: React web application (port 5173 internal, 3000 external)
2. **mysql**: Database (port 3306)
3. **discord-bot**: This bot
4. **cron**: Python data collectors
5. **convex**: Convex backend (cloud)

### Internal Communication
- Bot → Web API: `http://app:5173/api`
- Bot → MySQL: `mysql:3306` (service name)
- **NEVER USE localhost** in Docker

---

## Common Mistakes to AVOID

### ❌ DON'T DO THIS:
```python
# Creating duplicate backfill logic
async def backfill_activity(self, guild, days=30):
    for channel in guild.text_channels:
        async for message in channel.history():
            # NO! Use scripts/backfill_engagement.py
```

```python
# Creating new database connections
conn = pymysql.connect(...)  # NO! Use self.bot.db
```

```python
# Reimplementing API calls
async with aiohttp.ClientSession() as session:
    # NO! Use utils/crypto_api.py
```

```python
# Adding business logic to slash commands
@app_commands.command()
async def something(self, interaction):
    # 100 lines of logic here  # NO! Call a module
```

### ✅ DO THIS INSTEAD:
```python
# Use existing scripts
process = await asyncio.create_subprocess_exec(
    "python3", "scripts/backfill_engagement.py",
    "--guild", str(guild_id)
)

# Use existing database
stats = await self.bot.db.get_member_stats(guild_id, user_id)

# Use existing API client
data = await self.api_client.get_volatility_scanner()

# Thin slash commands
@app_commands.command()
async def something(self, interaction):
    result = await self.module.do_something()  # Delegate
    await interaction.response.send_message(result)
```

---

## Adding New Features - CHECKLIST

Before writing ANY code:

1. **Search for existing functionality**
   ```bash
   grep -r "feature_name" .
   grep -r "similar_function" .
   ```

2. **Check these locations**:
   - `/cogs/` - Does this bot feature exist?
   - `/scripts/` - Is there a script for this?
   - `/app/routes/api/` - Does the web app have this endpoint?
   - `/cron-jobs/` - Is this data being collected?
   - `/utils/` - Is there a utility for this?

3. **If it exists**: USE IT, don't duplicate
4. **If it doesn't exist**: 
   - Put business logic in appropriate module
   - Keep slash commands thin
   - Consider if it should be a script for heavy operations

---

## Module Responsibilities

### Single Responsibility Principle
Each module does ONE thing:

- **role_manager.py**: ONLY role assignment logic
- **activity_tracker.py**: ONLY activity tracking
- **warning_system.py**: ONLY warning logic
- **welcome_handler.py**: ONLY welcome messages
- **crypto_api.py**: ONLY external API calls
- **database.py**: ONLY database operations

### If a module is doing multiple things: REFACTOR IT

---

## Testing Changes

1. **Check Docker logs**: `docker-compose logs -f discord-bot`
2. **Verify no duplication**: Search codebase for similar functions
3. **Ensure thin interfaces**: Slash commands should be <50 lines
4. **Module independence**: Changes to one module shouldn't break others

---

## Migration Path

### From Prefix to Slash Commands
1. Create slash command that calls existing module
2. Remove prefix command
3. DO NOT duplicate the logic

### From Monolithic to Modular
1. Extract logic into focused modules
2. Update imports
3. Delete old monolithic file

---

## Questions to Ask BEFORE Writing Code

1. **Does this already exist?** → Search first
2. **Where should this logic live?** → One place only
3. **Is this a heavy operation?** → Maybe use a script
4. **Am I duplicating anything?** → Stop and refactor
5. **Is my slash command thin?** → Move logic to modules

---

## Summary

**The bot is MODULAR and COMPLETE. Most functionality already exists.**

Before creating ANYTHING:
1. READ this document
2. SEARCH the codebase  
3. USE existing modules
4. DON'T duplicate

If you're writing more than 50 lines in a slash command, you're doing it wrong.
If you're creating a new database connection, you're doing it wrong.
If you're reimplementing backfill/data collection, you're doing it wrong.

**REUSE > RECREATE**