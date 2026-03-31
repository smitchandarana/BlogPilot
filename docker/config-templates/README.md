# Config Templates

Two settings profiles used by the Platform API when provisioning containers:

## `admin-settings.yaml`
Owner's (Phoenix Solution) personalized config. Contains:
- Tuned daily budgets, rate limits, and delays
- 20 business analytics topics + 36 hashtags
- 13 target industries
- 30+ Reddit subreddits for research
- RSS feeds (TDS, Analytics Vidhya)
- IST timezone, 9am-11pm active window
- All modules enabled

**Used for**: Admin's own container only. Not shared with other users.

## `default-settings.yaml`
Clean starter config for new user signups. Contains:
- Conservative daily budgets (half of admin's)
- Empty topics, hashtags, industries (user fills via Topics page)
- UTC timezone, Mon-Fri 9-6 active window
- Only core modules enabled
- Lower worker count (2 vs 3)
- Higher relevance threshold (7 vs 6) — safer for new accounts
- Research sources empty (user configures their own subreddits/feeds)

**Used for**:
- New user container provisioning
- Account reset (replaces user's settings.yaml with this file)

## Prompts
Prompt templates (`prompts/*.txt`) are shared across all containers from the main
`prompts/` directory. Users can edit their copies via the Prompt Editor UI — edits
are saved to each container's own volume and don't affect other users.
