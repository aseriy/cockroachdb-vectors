#!/usr/bin/env python3
"""
generate_research_prompts.py

Generates domain-specific research criteria prompts from semantic_domains.yaml.
Calls an LLM to transform YAML table definitions into research questions.

Usage:
    python3 generate_research_prompts.py -o assets/research --domain automotive_ev
    python3 generate_research_prompts.py -o assets/research --all
"""

import argparse
import json
import yaml
import logging
import time
import os
from typing import List, Dict
from jinja2 import Template
import textwrap

from openai import OpenAI

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


# ── Domain definitions ───────────────────────────────────────────────────────

DOMAINS = None
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(BASE_DIR, "semantic_domains.yaml"), "r") as file:
    DOMAINS = yaml.safe_load(file)

# ── LLM generation ───────────────────────────────────────────────────────────

def generate_criteria(client: OpenAI, prompt: str, model: str) -> Dict:
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.9,
            )
            content = response.choices[0].message.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            result = json.loads(content)
            if isinstance(result, dict) and "title" in result and "criteria" in result:
                return result
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} failed: {e}")
            time.sleep(2 ** attempt)
    return {}


llm_prompt_tmpl = """
Given the domain YAML below, generate a JSON object with:
- "title":
    the value of the 'domain_name' field from the YAML tables,
    converted to standard title case,
    with common abbreviations uppercased (e.g., AI, EV, IoT, ERP, CRM, B2B, SaaS)
- "criteria": an array of strings, each string is one research question
    (one per entry in the YAML). Each question must ask about what the
    company actually does, operates, or offers in that area — not about
    abstract concepts or field definitions.

Return valid JSON only.
Format: {"title": "AI Customer Experience", "criteria": ["question 1", "question 2", ...]}

YAML:
{{ domain_yaml }}
"""

md_tmpl = """## {{ title }}

{% for item in criteria -%}
{{ loop.index }}. {{ item }}
{% endfor %}
"""


# ── Main ─────────────────────────────────────────────────────────────────────

def run_domain(client, domain_name, domain_def, output_dir, model):
    logger.info(f"=== Domain: {domain_name} ===")

    # Convert domain_def to YAML string
    domain_yaml = yaml.dump({domain_name: domain_def["tables"]}, default_flow_style=False)

    # Render LLM prompt
    template = Template(llm_prompt_tmpl)
    prompt = textwrap.dedent(
        template.render(domain_yaml=domain_yaml)
    )

    logger.info(f"  Generating research criteria...")
    criteria_data = generate_criteria(client, prompt, model)
    if not criteria_data:
        logger.warning("  Empty response, skipping...")
        return

    # Write markdown file
    md_template = Template(md_tmpl)
    content = md_template.render(**criteria_data)

    output_path = os.path.join(output_dir, f"{domain_name}.md")
    with open(output_path, 'w') as f:
        f.write(content)

    logger.info(f"  ✓ {domain_name}.md written")


def main():
    parser = argparse.ArgumentParser(description="Generate research criteria prompts from semantic_domains.yaml")
    parser.add_argument("-o", "--output-dir", required=True, help="Output directory for markdown files")
    parser.add_argument("-d", "--domain", help=f"Domain name. Available: {list(DOMAINS.keys())}")
    parser.add_argument("--all", action="store_true", help="Process all domains")
    parser.add_argument("--model", default="gpt-4o-mini", help="OpenAI model (default: gpt-4o-mini)")
    parser.add_argument("--api-key", help="OpenAI API key (or set OPENAI_API_KEY env var)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Create output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)

    client = OpenAI(api_key=args.api_key) if args.api_key else OpenAI()

    if args.all:
        to_run = DOMAINS
    elif args.domain:
        if args.domain not in DOMAINS:
            logger.error(f"Unknown domain '{args.domain}'. Available: {list(DOMAINS.keys())}")
            return
        to_run = {args.domain: DOMAINS[args.domain]}
    else:
        logger.error("Specify --domain <name> or --all")
        return

    for name, defn in to_run.items():
        run_domain(client, name, defn, args.output_dir, args.model)

    logger.info("All done.")


if __name__ == "__main__":
    main()
