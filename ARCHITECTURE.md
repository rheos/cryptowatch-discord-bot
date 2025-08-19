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
- **Connection Pool**: `database.py` - USE `self.bot.db` 
- **Engagement Stats**: `self.bot.db.get_member_stats()`
- **Settings**: `self.bot.db.get_setting()` / `set_setting()`
- **DO NOT**: Create new database connections or pools

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
  - `update_member_roles()` - Update all member roles
  - `handle_new_member_message()` - Check for intro channel upgrade
  - `grant_vacation_role()` - Vacation role management
  
- **activity_tracker.py**:
  - `track_message()` - Buffer message counts
  - `flush_buffer()` - Write to database
  - `get_member_activity()` - Get member stats
  - `get_all_member_stats()` - Get all stats
  - **NOT HERE**: Backfill - use the script!

- **warning_system.py**:
  - `check_warning_needed()` - Check if warning needed
  - `send_warning()` - Send warning to member
  - `test_warning()` - Test warning on member

- **welcome_handler.py**:
  - `handle_member_join()` - Welcome new members
  - `send_welcome_message()` - Send welcome embed

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
Most settings now in database via `/setup config`:
- Engagement thresholds
- Warning settings  
- Channel configurations
- Feature toggles

### Environment Variables (Docker)
Set in `docker-compose.yml`:
- `ENVIRONMENT`: dev/prod
- `API_BASE_URL`: http://app:5173/api (internal Docker network)
- `MYSQL_*`: Database credentials

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