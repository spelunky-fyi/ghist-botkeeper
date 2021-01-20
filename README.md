# ghist-botkeeper
Discord Bot used in Spelunky Community server

## Environment Setup

```
# Copy example environment config to local file.
# This file should not be checked in and is part of the .gitignore
cp ghist-bot.env.example ghist-bot.env

# Build the container
make docker-build

# Run the bot
make docker-run
```
