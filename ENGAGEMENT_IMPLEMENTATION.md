# CryptoWatch Discord Engagement System - Implementation Guide

## Overview
This guide outlines the retroactive implementation of an engagement-based channel access system for the CryptoWatch Discord server.

## System Design

### Role Structure
- **@NewMember** - Brand new joins, limited to welcome channels
- **@Member** - Has posted at least once, access to general channels  
- **@Active** - Regular participants, access to premium channels
- **@Vacation** - Temporary role to preserve Active status during breaks

### Channel Structure
```
Welcome Tier (@NewMember can see):
├── #welcome (read-only rules)
├── #welcome-chat (introduce yourself)
└── #bot-commands (basic commands)

General Tier (@Member can see):
├── #general-chat
├── #funding-alerts
├── #market-discussion
├── #memes
└── [all current channels]

Premium Tier (@Active can see):
├── #premium-chat
├── #advanced-alerts
├── #research-collab
└── #early-access
```

## Implementation Phases

### Phase 1: Silent Setup (Day 1)
1. Create roles (don't assign yet)
2. Create premium channels (keep hidden)
3. Deploy EngagementCog in monitoring mode
4. Test bot commands with admin role

### Phase 2: Analysis (Day 2-3)
Run analysis command to understand current state:
```
!analyze_members
```

Expected output:
- Total members
- Active in last 7/30/90 days
- Message count distribution
- Recommended grandfather settings

### Phase 3: Grandfather Period (Day 4-7)
1. Announce new system in #general-chat
2. Give 7-day grace period
3. Run grandfather command:
```
!grandfather_active days:30 messages:10
```

Settings to decide:
- **days**: How far back to check (recommend 30)
- **messages**: Minimum messages to be Active (recommend 10)

### Phase 4: Soft Launch (Day 8)
1. Enable premium channels for @Active members
2. New members start in @NewMember flow
3. Existing members keep current access
4. Monitor for issues

### Phase 5: Full Activation (Day 30+)
Optional - apply rules to all members:
```
!apply_engagement_rules
```

## Bot Commands

### Admin Commands
- `!analyze_members` - Show member activity stats
- `!grandfather_active days:X messages:Y` - Grant Active to qualifying members
- `!check_user @user` - See user's engagement stats
- `!grant_active @user` - Manually grant Active role
- `!grant_vacation @user days:X` - Grant vacation mode

### User Commands  
- `!mystats` - Check your own engagement
- `!vacation` - Request vacation mode (if Active)

## Engagement Tracking

### What Counts as Activity
- Sending messages (not commands)
- Helpful reactions (📈, 💡, ✅)
- Sharing analysis/charts
- Answering questions

### Activity Thresholds
- **Member**: 1+ messages ever
- **Active**: 10+ messages in last 30 days
- **Lose Active**: No activity for 30 days

### Special Cases
- Admins/Mods always keep access
- Vacation mode preserves Active for up to 30 days
- Quality > Quantity (helpful posts weighted more)

## Monitoring & Adjustments

### Weekly Review
- Check engagement stats
- Adjust thresholds if needed
- Address member concerns

### Monthly Metrics
- New member retention
- Active member percentage  
- Premium channel engagement
- Bot command usage

## Rollback Plan

If issues arise:
1. `!disable_engagement` - Stops all automatic role changes
2. `!restore_access` - Gives @Member to everyone
3. Manually fix edge cases
4. Adjust and retry

## FAQ for Implementation

**Q: Will current active members lose access?**
A: No, grandfather period ensures active members get @Active automatically.

**Q: What about members on vacation?**
A: They can request @Vacation role to pause activity requirements.

**Q: Can we adjust thresholds later?**
A: Yes, all thresholds are configurable and can be tuned.

**Q: What if someone objects?**
A: Admins can manually override any automatic decisions.

## Timeline Summary

- **Day 1-3**: Setup and analysis
- **Day 4-10**: Announcement and grace period  
- **Day 11**: Soft launch for new members
- **Day 30+**: Optional full implementation
- **Ongoing**: Monitor and adjust

## Success Metrics

- 50%+ of members achieve Active status
- Increased messages per member
- Higher quality discussions
- Positive member feedback
- New member retention improvement