# Session Notes - 2026-05-08 (Part 3)

## Workflow Redesign and Testing

### Workflow Changes
User requested complete workflow redesign:
1. Step 1: Get Database URL (unchanged)
2. Step 2: Ask for Company Name (unchanged)
3. Step 3: **List Research Criteria** (changed from conducting research)
4. Step 4: **Ask for Additional Criteria** (changed from asking for additional context after research)
5. Step 5: **Conduct Research** using combined criteria set, format as JSON (no temp files)
6. Step 6: **Save Research** using research.py script
7. **STOP** - Removed old "Infer Knowledge Domain" step entirely

### Key Changes
- Research criteria are now **presented** before asking user if they want to add more (Step 3-4)
- Research is **conducted** after getting user input on criteria (Step 5)
- All research must be formatted as JSON and piped directly (no temp files)
- Workflow ends after saving to database (no domain inference)

### Successful Test Run: Delta Airlines

**Execution:**
- Company: Delta Airlines
- Research Date: 2026-05-08 20:26:17 UTC
- Record ID: `a50a3975-83b4-4132-85ba-ef5899da5c1d`
- Database: `research`

**Research Coverage:**
- Industry vertical: Commercial Aviation
- Geographic presence: 64 countries, 325 destinations, 10 international hubs
- Financial data: $63.36B revenue (2025), $14.2B Q1 2026
- Stock: NYSE:DAL (public company)
- Technology: AWS cloud (90% migrated), hybrid mainframe/cloud architecture
- Partnerships: American Express ($8B/year), SkyTeam alliance (19 airlines)
- Scale: 103,000 employees, 200M passengers/year
- Challenges: Legacy systems, crew scheduling crisis (May 2026), CrowdStrike outage (2024)
- Growth: 95 new aircraft orders including first A350-1000 in US

**Technical Notes:**
- Had to install psycopg2-binary via pip3 (not using uv run)
- CRDB_URL environment variable doesn't persist between Bash calls - must export in same command
- Successfully piped JSON directly to research.py without temp files

### Status
✅ Workflow redesign complete
✅ SKILL.md updated with new workflow
✅ Full end-to-end test successful with Delta Airlines
✅ Research saved to database

---

# Session Notes - 2026-05-08 (Part 2)

## CLI Refactoring

### Issue: URL Position in Commands
User requested moving `-u/--url` to precede subcommands for convenience (e.g., `cmd -u $URL subcmd` instead of `cmd subcmd -u $URL`).

**Problem Discovered:**
With required options at group level, `--help` doesn't work:
```bash
$ python3 semantic.py domain --help
Error: Missing option '-u' / '--url'.
```

**Decision:**
Reverted to command-level decorators. This allows `--help` to work without providing URL, which is more important than ergonomics.

### Enhancements to research.py
1. **Default days in list command:** Changed `-d/--days` from required to optional with default of 90 days
2. **Company name normalization:** Added `normalize_company_name()` function that:
   - Strips leading/trailing whitespace
   - Collapses multiple spaces to single spaces
   - Converts to title case (e.g., "cockroach  labs" → "Cockroach Labs")
   - Applied to `save`, `list`, and `load` commands

## Skill Testing

### Test Run: TJX Companies
- Successfully completed Steps 1-4 of workflow
- Gathered comprehensive research on TJX (off-price retailer, $60B revenue, 377K employees)
- **Issue:** Did not complete Step 5 (save research to database) - was waiting for user response to "additional context" question
- User went offline before research could be saved

### Next Session TODO:
- Complete Step 5: Save TJX research to database
- Complete Step 6: Infer knowledge domains based on research
- Test full end-to-end workflow

---

# Session Notes - 2026-05-08 (Part 1)

## New Database Layout Plan

### Multi-Database Architecture
Moving from single database to multiple databases in the cluster:

1. **`domain_knowledge`** - Stores domains and ontologies (reference data, reusable)
2. **`research`** - Stores company research logs
3. **Demo-specific databases** - Created on-the-fly for each specific demo

### Changes Required

**CRDB_URL behavior:**
- Can connect to ANY database in the cluster (whichever database the URL points to)
- The URL is passed to scripts, which are responsible for switching databases
- Scripts MUST execute `USE <dbname>` to switch to the appropriate database
- Scripts should check if the target database exists before attempting to USE it

**Impact:**
- `semantic.py` needs to `USE domain_knowledge` and verify database exists
- `research.py` needs to `USE research` and verify database exists
- Both scripts need connection logic updated to handle database switching

---

# Session Notes - 2026-05-07

## What We Completed

### 1. Created `research.py` Script
**Location:** `/home/ubuntu/git/cockroachdb-vectors/skills/domain-ontology-matcher/scripts/research.py`

**Command:** `research.py -u $CRDB_URL save [OPTIONS] <company_name>`

**Features:**
- Two input methods:
  - STDIN: `echo '{"industry":"..."}' | research.py -u $CRDB_URL save "Company Name"`
  - File: `research.py -u $CRDB_URL save -f /path/to/file.json "Company Name"`
- Creates `public.research` table if it doesn't exist:
  - `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
  - `at TIMESTAMPTZ DEFAULT now()`
  - `company TEXT`
  - `info JSONB`
  - GIN index on `info` column
- Returns JSON with saved record details

### 2. Refactored Both Scripts
**Files Modified:**
- `semantic.py`
- `research.py`

**Changes:**
- Removed connection pooling (unnecessary for short-lived CLI scripts)
- Moved `-u/--url` from group level to command level (allows `--help` without URL)
- Direct `psycopg2.connect()` with try/finally pattern

## What's Next

### TODO: Update SKILL.md Workflow

Current workflow ends at Step 5. Need to insert new step:

**New Step 5: Save research to database**
- Structure all research findings as JSON
- Use Bash tool to pipe JSON into `research.py save`
- This happens BEFORE inferring knowledge domains

**New Step 6: Infer Knowledge Domain** (previously Step 5)
- Analyze the saved research to identify domains

## Environment Setup

Database URL is set: `CRDB_URL` environment variable
Company researched: Cockroach Labs

## Key Decisions

1. **CLI Pattern:** Required options at command level (decorator), NOT group level - memorized as non-negotiable preference
2. **Input Methods:** Support both stdin (for piping) and file input (for manual use)
3. **No Temp Files:** Use stdin piping in skill to avoid temp file creation
