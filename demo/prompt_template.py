from jinja2 import Template
import textwrap
import os
import yaml
import json

# tmpl_vars = {
#     "concept_domain": "financial account",
#     "entry_count": 120,
#     "concept_unit": "account",
#     "concept_scope_examples": "account type, ownership model, status, or structural variant",
#     "instance_exclusion_rules": "no IDs, no numbers, no dates, no people, no balances",
#     "trivial_variant_example": '"basic checking account" vs "standard checking account"',
#     "distinctness_criteria": "function or structure",
#     "domain_name": "financial services",
#     "terminology_domain": "financial",
#     "domain_scope": "retail, business, payments, digital wallets, etc.",
#     "example_name": "Checking Account",
#     "example_description": "A deposit account designed for frequent transactions such as payments, withdrawals, and transfers.",
# }

prompt_tmpl = """
        You are generating a controlled vocabulary, not sample data.

        Task: Produce a list of distinct {{ concept_domain }} concepts.

        Output requirements:

        Return valid JSON only
        Format: an array of objects with exactly two fields: "name" and "description"
        Generate {{ entry_count }} entries
        Each entry must represent a unique {{ concept_unit }} concept (e.g., {{ concept_scope_examples }})
        Do not generate specific instances ({{ instance_exclusion_rules }})
        Avoid synonyms or near-duplicates
        Avoid trivial variants (e.g., {{ trivial_variant_example }})
        Keep names concise (2-5 words)
        Descriptions: 1 sentence, precise and non-overlapping
        Use standard {{ terminology_domain }} terminology

        Quality constraints:

        Concepts must be meaningfully distinct in {{ distinctness_criteria }}
        No repetition or rewording of the same idea
        Stay within realistic {{ domain_name }} domain ({{ domain_scope }})

        Output format example:

        [
            {
                "name": "{{ example_name }}",
                "description": "{{ example_description }}"
            }
        ]

        Now generate the full list.
"""

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(BASE_DIR, "semantic_clusters.yaml"), "r") as file:
    DOMAINS = yaml.safe_load(file)

tmpl_vars = DOMAINS['financial_services']['tables']['accounts']

template = Template(prompt_tmpl)
prompt = textwrap.dedent(
    template.render(**tmpl_vars)
)
 
print(prompt)
