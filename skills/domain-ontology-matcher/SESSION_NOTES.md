# Session Notes - 2026-05-08

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
