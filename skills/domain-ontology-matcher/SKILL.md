---
name: domain-ontology-matcher
description: Research a company and select a representative knowledge domain and ontologies
---

# Domain and Ontology Matcher

## Available scripts

- **`scripts/research.py`** — Saves, lists, and loads company research data to/from the database
- **`scripts/semantic.py`** — Manages knowledge domains and ontologies in the database

## Workflow

Follow these steps in order. Do not skip any step.

### Step 1: Get Database URL
Check if the `CRDB_URL` environment variable is set. If it is not set, stop and ask the user to provide it. Do not proceed until you have the URL.

### Step 2: Ask for Company Name
Ask the user: "Which company would you like me to research?" Wait for their response before proceeding.

### Step 3: List Research Criteria
Present the criteria by which the company will be evaluated:
   - Industry vertical
   - Headquarters location and geographic presence/markets
   - Lines of business, products, and customer base
   - If public: exchange and ticker symbol
   - Technology stack and infrastructure
   - Recent significant news or business direction changes
   - Key use cases and problems they solve for customers
   - Target customer segments (B2B, B2C, B2G, Enterprise, SMB, etc.)
   - Regulatory/compliance requirements (HIPAA, PCI-DSS, SOX, etc.)
   - Core technical challenges (real-time data, analytics, scale, global distribution, AI/ML)
   - Partnerships and ecosystem integrations
   - Company stage/scale (startup, growth, enterprise) and employee count
   - Known pain points or challenges (from blog posts, job postings, interviews, etc.)
   - Growth trajectory and scaling needs

### Step 4: Ask for Additional Criteria
Ask the user: "Would you like to add any other aspects or criteria for the research?"

**STOP HERE. End your response and wait for the user to answer. Do not proceed to Step 5 until the user provides their response (either additional criteria or confirmation they have none).**

### Step 5: Conduct Research
Use WebSearch to gather comprehensive information about the company based on the combined criteria set (pre-canned from Step 3 + any user-provided criteria from Step 4).

Format all research findings as a single JSON object with clear, descriptive keys for each piece of information. Do NOT save the JSON to any temporary file.

### Step 6: Save Research to Database
Save the research to the database using:
```bash
echo '<json_object>' | uv run scripts/research.py save -u "$CRDB_URL" "<Company Name>"
```

Use the Bash tool to pipe the JSON directly into the research.py script.

This is the final step. Stop here.
