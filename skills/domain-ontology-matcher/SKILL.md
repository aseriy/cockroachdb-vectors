---
name: domain-ontology-matcher
description: Research a company and select a representative knowledge domain and ontologies
---

# Domain and Ontology Matcher

## Available scripts

- **`scripts/research.py`** — Saves, lists, and loads company research data to/from the database
- **`scripts/semantic.py`** — Manages knowledge domains and ontologies in the database

## Workflow

Follow these steps in order.

### Step 1: Get Database URL
Check if the `CRDB_URL` environment variable is set.
If it is not set or it is empty, stop and ask the user to provide it.
DO NOT proceed until you have the URL!!!

### Step 2: Ask for Company Name
Ask the user: "Which company would you like me to research?" Wait for their response before proceeding.

### Step 3: Check for Existing Research
Run the list command to check if research already exists:
```bash
uv run scripts/research.py list -u "$CRDB_URL" "<company_name>"
```

**If results are found (1-3 companies):**
- Present the matching companies to the user with their timestamps
- Add option 4: "None of these, conduct new research"
- Wait for user selection
- If user selects options 1-3: Load that company's research using the load command and STOP
- If user selects option 4: Continue to Step 4

**If no results (empty array):**
- Continue to Step 4

### Step 4: Verify Company Name
Use WebSearch to look up the company and gather basic identifying information (official name, industry, headquarters).

Present the findings as numbered options:
1. Company name (official name, industry, headquarters)
2. Company name (if multiple found)
...
[last company + 1]. Enter another company to research
[last company + 2]. Exit

Wait for user selection.
- If user selects a company (1, 2, etc.): Use that company's official name and continue to Step 5
- If user selects "Enter another company": Go back to Step 2
- If user selects "Exit": EXIT the workflow

### Step 5: Classify Company Domains
For each file in `assets/research/*.md`, read its ## heading. Use these headings as the available domain names.

Use the following shell command to extract the headings:

```bash
grep '^##' assets/research/*.md
```

Based on the company information gathered in Step 4, identify the PRIMARY domain that best represents the company's core business operations.

Select ONLY ONE domain. Match criteria:
- The domain must reflect the company's primary business operations
- Exclude domains where the overlap is incidental

Examples of what NOT to match:
- being publicly traded does not qualify as Capital Markets
- offering travel rewards does not qualify as Consumer Hospitality and Retail

Extract the filename (without .md extension) from the matched domain file and store it for Step 9.

Example: if the file is `financial_services.md`, the domain name is `financial_services`.

Present the matched domain heading to the user, then proceed to Step 6.

### Step 6: Build Research Criteria
Load the `assets/research/<domain>.md` file for the matched domain.
Present the research criteria before proceeding to Step 7.

### Step 7: Ask for Additional Criteria
Ask the user: "Would you like to add any other aspects or criteria for the research?"

**STOP HERE. End your response and wait for the user to answer. Do not proceed to Step 7 until the user provides their response (either additional criteria or confirmation they have none).**

### Step 8: Conduct Research
Use WebSearch to gather comprehensive information about the company based on the combined criteria set (pre-canned from Step 6 + any user-provided criteria from Step 7).

Format all research findings as a single JSON object with clear, descriptive keys for each piece of information. Do NOT save the JSON to any temporary file.

### Step 9: Save Research to Database
Save the research to the database using the domain filename from Step 5:
```bash
echo '<json_object>' | uv run scripts/research.py save -u "$CRDB_URL" -d "<domain>" "<Company Name>"
```

Replace `<domain>` with the domain filename stored in Step 5 (e.g., `financial_services`, `aerospace_defense`).

Use the Bash tool to pipe the JSON directly into the research.py script.


### Step 10: 

This is the final step. Stop here.
