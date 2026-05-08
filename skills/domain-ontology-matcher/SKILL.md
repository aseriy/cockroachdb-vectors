---
name: domain-ontology-matcher
description: Research a company and select a representative knowledge domain and ontologies
---

# Domain and Ontology Matcher

## Workflow

Follow these steps in order. Do not skip any step.

### Step 1: Get Database URL
Check if the `CRDB_URL` environment variable is set. If it is not set, stop and ask the user to provide it. Do not proceed until you have the URL.

### Step 2: Ask for Company Name
Ask the user: "Which company would you like me to research?" Wait for their response before proceeding.

### Step 3: Research Company
Use WebSearch to gather comprehensive information about the company. Research these areas:
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

### Step 4: Ask for Additional Information
After completing your research, ask the user: "Do you have any additional context or information about this company that wasn't found in the research?" Wait for their response.

### Step 5: Infer Knowledge Domain
Based on the research findings and any additional information from the user, identify the knowledge domain(s) that apply to this company. Present your findings clearly, explaining why each domain is relevant.

This is the final step. Stop here.
