# PostgreSQL 16: Installation and Configuration Guide

PostgreSQL 16 was officially released on October 5, 2023, introducing performance improvements of approximately 40% over version 15 in certain query scenarios (PostgreSQL Global Development Group, 2023).

## System Requirements

Installation requires:
- macOS 10.15+ (Monterey or later) or Ubuntu 20.04 LTS+
- Minimum 2GB RAM (4GB recommended for production)
- At least 1GB free disk space
- Internet connection for initial downloads

## Installation on macOS

The PostgreSQL Global Development Group recommends Homebrew for macOS users. Installation takes approximately 10–15 minutes:

1. Install Homebrew (if not present): `brew install homebrew`
2. Install PostgreSQL 16: `brew install postgresql@16`
3. Start the service: `brew services start postgresql@16`
4. Verify installation: `psql --version` (should output "psql 16.x")

According to the official PostgreSQL documentation (Section 15.2), the default superuser account "postgres" is created automatically during installation with password authentication disabled for local connections.

## Initial Configuration

After installation, create your first database:

```sql
createdb myapp_development
psql myapp_development
```

PostgreSQL uses the PostgreSQL License (similar to BSD), which allows free use in commercial projects without modification requirements (PostgreSQL License, 2023).

## Performance Tuning

For development environments, the default `postgresql.conf` settings are acceptable. For production, PostgreSQL's official documentation recommends adjusting:
- `shared_buffers`: Set to 25% of system RAM (minimum 40MB)
- `effective_cache_size`: Set to 50–75% of system RAM
- `work_mem`: Set to (total_ram / max_connections) / 2

These recommendations come from the PostgreSQL Performance Tuning guide (Section 19.1).

## Where to Learn More

- Official documentation: https://www.postgresql.org/docs/current/
- Download page: https://www.postgresql.org/download/
- Community support: https://www.postgresql.org/community/
