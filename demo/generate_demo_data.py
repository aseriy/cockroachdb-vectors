#!/usr/bin/env python3
"""
generate_demo_data.py

Generates synthetic domain-specific demo data for the CockroachDB Vector Demo.
Calls an LLM to generate realistic rows and loads them into CockroachDB Serverless.

Usage:
    python3 generate_demo_data.py -u postgresql://... --domain financial_services
    python3 generate_demo_data.py -u postgresql://... --all
    python3 generate_demo_data.py -u postgresql://... --all --target 10000 --batch-size 50
"""

import argparse
import json
import logging
import time
from typing import List, Dict

import psycopg
from openai import OpenAI

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


# ── Domain definitions ───────────────────────────────────────────────────────

DOMAINS = {

    "financial_services": {
        "tables": {
            "products": {
                "ddl": """
                    CREATE TABLE IF NOT EXISTS products (
                        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name        TEXT NOT NULL,
                        description TEXT NOT NULL
                    )
                """,
                "columns": ["name", "description"],
                "prompt": """Generate {n} realistic financial services product records.
Cover savings accounts, loans, investment products, payment products, FX products,
trading instruments, insurance-linked products, credit facilities.
Descriptions: 1-3 sentences, specific and domain-accurate.
Return a JSON array of objects with keys: name, description.
No duplicates. Raw JSON only, no markdown."""
            },
            "trading_instruments": {
                "ddl": """
                    CREATE TABLE IF NOT EXISTS trading_instruments (
                        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name        TEXT NOT NULL,
                        description TEXT NOT NULL
                    )
                """,
                "columns": ["name", "description"],
                "prompt": """Generate {n} realistic trading instrument records.
Cover FX pairs, equity indices, futures, options, bonds, ETFs, crypto derivatives,
swaps, commodities. Descriptions explain what it is, how it settles, key characteristics.
Return a JSON array of objects with keys: name, description.
No duplicates. Raw JSON only, no markdown."""
            },
            "compliance_policies": {
                "ddl": """
                    CREATE TABLE IF NOT EXISTS compliance_policies (
                        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name        TEXT NOT NULL,
                        description TEXT NOT NULL
                    )
                """,
                "columns": ["name", "description"],
                "prompt": """Generate {n} realistic financial compliance policy records.
Cover AML, KYC, sanctions screening, data privacy, capital requirements,
reporting obligations, insider trading, MiFID II, Basel III, Dodd-Frank, PSD2.
Descriptions: specific, regulatory in tone, 1-3 sentences.
Return a JSON array of objects with keys: name, description.
No duplicates. Raw JSON only, no markdown."""
            },
            "support_tickets": {
                "ddl": """
                    CREATE TABLE IF NOT EXISTS support_tickets (
                        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name        TEXT NOT NULL,
                        description TEXT NOT NULL
                    )
                """,
                "columns": ["name", "description"],
                "prompt": """Generate {n} realistic financial services customer support ticket records.
name is a short subject line. description is the customer's issue in detail.
Cover payment failures, account access, transaction disputes, KYC issues,
FX rate disputes, card problems, failed transfers, regulatory holds.
Descriptions: 2-4 sentences, sound like real customer complaints.
Return a JSON array of objects with keys: name, description.
No duplicates. Raw JSON only, no markdown."""
            },
            "transaction_categories": {
                "ddl": """
                    CREATE TABLE IF NOT EXISTS transaction_categories (
                        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name        TEXT NOT NULL,
                        description TEXT NOT NULL
                    )
                """,
                "columns": ["name", "description"],
                "prompt": """Generate {n} realistic financial transaction category records.
Cover wire transfers, ACH, SWIFT, card payments, repo, settlement types,
cryptocurrency, payroll, standing orders, margin calls, trade settlement.
Descriptions explain mechanics, typical use case, settlement characteristics.
Return a JSON array of objects with keys: name, description.
No duplicates. Raw JSON only, no markdown."""
            }
        }
    },

    "gaming_betting": {
        "tables": {
            "games_catalog": {
                "ddl": """
                    CREATE TABLE IF NOT EXISTS games_catalog (
                        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name        TEXT NOT NULL,
                        description TEXT NOT NULL
                    )
                """,
                "columns": ["name", "description"],
                "prompt": """Generate {n} realistic online casino and gaming records.
Cover slots, table games, live dealer, crash games, poker variants, bingo, lottery.
Descriptions mention theme, mechanics, special features, volatility, jackpot type.
Return a JSON array of objects with keys: name, description.
No duplicates. Raw JSON only, no markdown."""
            },
            "betting_markets": {
                "ddl": """
                    CREATE TABLE IF NOT EXISTS betting_markets (
                        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name        TEXT NOT NULL,
                        description TEXT NOT NULL
                    )
                """,
                "columns": ["name", "description"],
                "prompt": """Generate {n} realistic sports betting market records.
Cover football, tennis, basketball, horse racing, cricket, golf, esports, boxing,
MMA, politics, entertainment. Descriptions explain bet type, settlement rules, conditions.
Return a JSON array of objects with keys: name, description.
No duplicates. Raw JSON only, no markdown."""
            },
            "promotions": {
                "ddl": """
                    CREATE TABLE IF NOT EXISTS promotions (
                        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name        TEXT NOT NULL,
                        description TEXT NOT NULL
                    )
                """,
                "columns": ["name", "description"],
                "prompt": """Generate {n} realistic online gambling promotion records.
Cover welcome bonuses, reload bonuses, free bets, cashback, loyalty rewards,
VIP programs, tournaments, free spins, refer-a-friend, seasonal promotions.
Descriptions include mechanics, wagering requirements, eligibility, time limits.
Return a JSON array of objects with keys: name, description.
No duplicates. Raw JSON only, no markdown."""
            },
            "support_tickets": {
                "ddl": """
                    CREATE TABLE IF NOT EXISTS support_tickets (
                        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name        TEXT NOT NULL,
                        description TEXT NOT NULL
                    )
                """,
                "columns": ["name", "description"],
                "prompt": """Generate {n} realistic online gambling customer support ticket records.
name is a short subject line. description is the customer's detailed issue.
Cover withdrawal delays, bonus disputes, account verification, bet settlement disputes,
responsible gaming limit issues, payment failures, account access, odds errors.
Descriptions: 2-4 sentences, sound like real customer complaints.
Return a JSON array of objects with keys: name, description.
No duplicates. Raw JSON only, no markdown."""
            },
            "responsible_gaming_rules": {
                "ddl": """
                    CREATE TABLE IF NOT EXISTS responsible_gaming_rules (
                        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name        TEXT NOT NULL,
                        description TEXT NOT NULL
                    )
                """,
                "columns": ["name", "description"],
                "prompt": """Generate {n} realistic responsible gambling policy records.
Cover deposit limits, loss limits, session limits, self-exclusion, cooling-off periods,
reality checks, affordability checks, age verification, addiction support referrals.
Descriptions: policy-accurate, specific, reflect real regulatory requirements.
Return a JSON array of objects with keys: name, description.
No duplicates. Raw JSON only, no markdown."""
            }
        }
    },

    "saas_platform": {
        "tables": {
            "product_features": {
                "ddl": """
                    CREATE TABLE IF NOT EXISTS product_features (
                        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name        TEXT NOT NULL,
                        description TEXT NOT NULL
                    )
                """,
                "columns": ["name", "description"],
                "prompt": """Generate {n} realistic SaaS platform product feature records.
Cover authentication, authorization, collaboration, analytics, integrations,
security, compliance, developer tools, notifications, billing, multi-tenancy, APIs.
Descriptions: product-doc quality, explain what it does and why it matters.
Return a JSON array of objects with keys: name, description.
No duplicates. Raw JSON only, no markdown."""
            },
            "integrations_catalog": {
                "ddl": """
                    CREATE TABLE IF NOT EXISTS integrations_catalog (
                        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name        TEXT NOT NULL,
                        description TEXT NOT NULL
                    )
                """,
                "columns": ["name", "description"],
                "prompt": """Generate {n} realistic SaaS third-party integration records.
Cover CRM, ERP, payment, identity, monitoring, storage, communication,
marketing, CI/CD, analytics tools.
Descriptions explain what data syncs, how it connects, the business value.
Return a JSON array of objects with keys: name, description.
No duplicates. Raw JSON only, no markdown."""
            },
            "support_tickets": {
                "ddl": """
                    CREATE TABLE IF NOT EXISTS support_tickets (
                        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name        TEXT NOT NULL,
                        description TEXT NOT NULL
                    )
                """,
                "columns": ["name", "description"],
                "prompt": """Generate {n} realistic SaaS platform customer support ticket records.
name is a short subject line. description is the customer's detailed issue.
Cover login issues, API errors, integration failures, data sync problems,
billing disputes, performance issues, feature bugs, permission errors, export failures.
Descriptions: 2-4 sentences, sound like real developer or admin complaints.
Return a JSON array of objects with keys: name, description.
No duplicates. Raw JSON only, no markdown."""
            },
            "api_endpoints": {
                "ddl": """
                    CREATE TABLE IF NOT EXISTS api_endpoints (
                        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name        TEXT NOT NULL,
                        description TEXT NOT NULL
                    )
                """,
                "columns": ["name", "description"],
                "prompt": """Generate {n} realistic SaaS REST API endpoint records.
name is HTTP method + path (e.g. POST /users, GET /reports/{id}).
description explains what it does, key parameters, typical use case.
Cover user management, auth, data CRUD, exports, webhooks, billing, analytics, admin.
Return a JSON array of objects with keys: name, description.
No duplicates. Raw JSON only, no markdown."""
            },
            "release_notes": {
                "ddl": """
                    CREATE TABLE IF NOT EXISTS release_notes (
                        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        version     TEXT NOT NULL,
                        description TEXT NOT NULL
                    )
                """,
                "columns": ["version", "description"],
                "prompt": """Generate {n} realistic SaaS platform release note records.
version follows semver (e.g. v4.12.0). description summarizes what changed.
Cover new features, bug fixes, performance improvements, security patches,
deprecations, API changes. Descriptions: changelog quality, specific and technical.
Return a JSON array of objects with keys: version, description.
No duplicates. Raw JSON only, no markdown."""
            }
        }
    },

    "logistics": {
        "tables": {
            "shipment_types": {
                "ddl": """
                    CREATE TABLE IF NOT EXISTS shipment_types (
                        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name        TEXT NOT NULL,
                        description TEXT NOT NULL
                    )
                """,
                "columns": ["name", "description"],
                "prompt": """Generate {n} realistic logistics shipment type records.
Cover air freight, ocean, road, rail, last-mile, cold chain, hazmat, oversized, express.
Descriptions explain handling requirements, transit characteristics, regulatory considerations.
Return a JSON array of objects with keys: name, description.
No duplicates. Raw JSON only, no markdown."""
            },
            "routing_rules": {
                "ddl": """
                    CREATE TABLE IF NOT EXISTS routing_rules (
                        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name        TEXT NOT NULL,
                        description TEXT NOT NULL
                    )
                """,
                "columns": ["name", "description"],
                "prompt": """Generate {n} realistic logistics routing rule records.
Cover hub-and-spoke, direct routes, regional carrier selection, weight breaks,
dimensional weight, hazmat routing, time-definite delivery, cross-docking rules.
Descriptions explain when the rule applies, conditions, and business rationale.
Return a JSON array of objects with keys: name, description.
No duplicates. Raw JSON only, no markdown."""
            },
            "carrier_services": {
                "ddl": """
                    CREATE TABLE IF NOT EXISTS carrier_services (
                        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name        TEXT NOT NULL,
                        description TEXT NOT NULL
                    )
                """,
                "columns": ["name", "description"],
                "prompt": """Generate {n} realistic logistics carrier service records.
Cover express, standard, economy, freight, white glove, same-day, international services.
Descriptions include transit times, coverage, weight limits, special capabilities.
Return a JSON array of objects with keys: name, description.
No duplicates. Raw JSON only, no markdown."""
            },
            "support_tickets": {
                "ddl": """
                    CREATE TABLE IF NOT EXISTS support_tickets (
                        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name        TEXT NOT NULL,
                        description TEXT NOT NULL
                    )
                """,
                "columns": ["name", "description"],
                "prompt": """Generate {n} realistic logistics customer support ticket records.
name is a short subject line. description is the issue in detail.
Cover lost shipments, damaged goods, delivery delays, customs holds, wrong address,
missed pickups, tracking not updating, invoice disputes.
Descriptions: 2-4 sentences, sound like real shipper complaints.
Return a JSON array of objects with keys: name, description.
No duplicates. Raw JSON only, no markdown."""
            },
            "warehouse_operations": {
                "ddl": """
                    CREATE TABLE IF NOT EXISTS warehouse_operations (
                        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name        TEXT NOT NULL,
                        description TEXT NOT NULL
                    )
                """,
                "columns": ["name", "description"],
                "prompt": """Generate {n} realistic warehouse operation procedure records.
Cover receiving, putaway, picking, packing, kitting, returns processing,
cycle counting, cross-docking, value-added services, dock scheduling.
Descriptions explain the process, systems involved, and performance metrics.
Return a JSON array of objects with keys: name, description.
No duplicates. Raw JSON only, no markdown."""
            }
        }
    },

    "telecom": {
        "tables": {
            "service_plans": {
                "ddl": """
                    CREATE TABLE IF NOT EXISTS service_plans (
                        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name        TEXT NOT NULL,
                        description TEXT NOT NULL
                    )
                """,
                "columns": ["name", "description"],
                "prompt": """Generate {n} realistic telecom service plan records.
Cover mobile, broadband, enterprise, IoT, MVNO, 5G, fiber, satellite plans.
Descriptions include data allowances, speeds, features, contract terms, target segment.
Return a JSON array of objects with keys: name, description.
No duplicates. Raw JSON only, no markdown."""
            },
            "device_catalog": {
                "ddl": """
                    CREATE TABLE IF NOT EXISTS device_catalog (
                        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name        TEXT NOT NULL,
                        description TEXT NOT NULL
                    )
                """,
                "columns": ["name", "description"],
                "prompt": """Generate {n} realistic telecom device catalog records.
Cover smartphones, tablets, routers, IoT devices, modems, SIM types, wearables.
Descriptions include specs, connectivity, compatibility, use case.
Return a JSON array of objects with keys: name, description.
No duplicates. Raw JSON only, no markdown."""
            },
            "network_incidents": {
                "ddl": """
                    CREATE TABLE IF NOT EXISTS network_incidents (
                        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name        TEXT NOT NULL,
                        description TEXT NOT NULL
                    )
                """,
                "columns": ["name", "description"],
                "prompt": """Generate {n} realistic telecom network incident records.
name is a short incident title. description explains what happened, impact, and resolution.
Cover outages, degraded service, congestion, hardware failure, fiber cuts,
DNS issues, roaming failures, SMS delivery failures.
Descriptions: 2-4 sentences, technical and specific.
Return a JSON array of objects with keys: name, description.
No duplicates. Raw JSON only, no markdown."""
            },
            "support_tickets": {
                "ddl": """
                    CREATE TABLE IF NOT EXISTS support_tickets (
                        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name        TEXT NOT NULL,
                        description TEXT NOT NULL
                    )
                """,
                "columns": ["name", "description"],
                "prompt": """Generate {n} realistic telecom customer support ticket records.
name is a short subject line. description is the customer's detailed issue.
Cover no signal, slow data, billing errors, international roaming, number porting,
device compatibility, contract disputes, SIM swap issues.
Descriptions: 2-4 sentences, sound like real customer complaints.
Return a JSON array of objects with keys: name, description.
No duplicates. Raw JSON only, no markdown."""
            },
            "iot_asset_types": {
                "ddl": """
                    CREATE TABLE IF NOT EXISTS iot_asset_types (
                        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name        TEXT NOT NULL,
                        description TEXT NOT NULL
                    )
                """,
                "columns": ["name", "description"],
                "prompt": """Generate {n} realistic telecom IoT asset type records.
Cover smart meters, fleet trackers, industrial sensors, connected vehicles,
health monitors, environmental sensors, smart city devices, agriculture IoT.
Descriptions explain what the asset does, connectivity type, data it generates.
Return a JSON array of objects with keys: name, description.
No duplicates. Raw JSON only, no markdown."""
            }
        }
    },

    "it_services": {
        "tables": {
            "service_catalog": {
                "ddl": """
                    CREATE TABLE IF NOT EXISTS service_catalog (
                        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name        TEXT NOT NULL,
                        description TEXT NOT NULL
                    )
                """,
                "columns": ["name", "description"],
                "prompt": """Generate {n} realistic IT managed service catalog records.
Cover cloud management, security operations, backup, helpdesk, network monitoring,
patch management, identity services, disaster recovery, compliance management.
Descriptions: service-catalog quality, explain scope, SLA, and deliverables.
Return a JSON array of objects with keys: name, description.
No duplicates. Raw JSON only, no markdown."""
            },
            "security_policies": {
                "ddl": """
                    CREATE TABLE IF NOT EXISTS security_policies (
                        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name        TEXT NOT NULL,
                        description TEXT NOT NULL
                    )
                """,
                "columns": ["name", "description"],
                "prompt": """Generate {n} realistic IT security policy records.
Cover access control, password policy, endpoint security, data classification,
incident response, vulnerability management, zero trust, encryption standards.
Descriptions: policy-document quality, specific and enforceable.
Return a JSON array of objects with keys: name, description.
No duplicates. Raw JSON only, no markdown."""
            },
            "infrastructure_components": {
                "ddl": """
                    CREATE TABLE IF NOT EXISTS infrastructure_components (
                        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name        TEXT NOT NULL,
                        description TEXT NOT NULL
                    )
                """,
                "columns": ["name", "description"],
                "prompt": """Generate {n} realistic IT infrastructure component records.
Cover servers, storage, networking, load balancers, firewalls, VPNs,
hypervisors, container platforms, monitoring tools, backup systems.
Descriptions explain the component role, specs, and integration points.
Return a JSON array of objects with keys: name, description.
No duplicates. Raw JSON only, no markdown."""
            },
            "support_tickets": {
                "ddl": """
                    CREATE TABLE IF NOT EXISTS support_tickets (
                        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name        TEXT NOT NULL,
                        description TEXT NOT NULL
                    )
                """,
                "columns": ["name", "description"],
                "prompt": """Generate {n} realistic IT services support ticket records.
name is a short subject line. description is the issue in detail.
Cover server outages, network connectivity, VPN issues, application failures,
backup failures, security alerts, user access requests, patch failures.
Descriptions: 2-4 sentences, technical and specific.
Return a JSON array of objects with keys: name, description.
No duplicates. Raw JSON only, no markdown."""
            },
            "digital_assets": {
                "ddl": """
                    CREATE TABLE IF NOT EXISTS digital_assets (
                        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name        TEXT NOT NULL,
                        description TEXT NOT NULL
                    )
                """,
                "columns": ["name", "description"],
                "prompt": """Generate {n} realistic IT digital asset catalog records.
Cover software licenses, SSL certificates, domain names, API keys, cloud accounts,
configuration files, deployment scripts, documentation repositories.
Descriptions explain what the asset is, who owns it, expiry and renewal considerations.
Return a JSON array of objects with keys: name, description.
No duplicates. Raw JSON only, no markdown."""
            }
        }
    },

    "retail": {
        "tables": {
            "product_catalog": {
                "ddl": """
                    CREATE TABLE IF NOT EXISTS product_catalog (
                        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name        TEXT NOT NULL,
                        description TEXT NOT NULL
                    )
                """,
                "columns": ["name", "description"],
                "prompt": """Generate {n} realistic retail product catalog records.
Cover apparel, footwear, accessories, homewares, electronics, beauty, sports, food.
Descriptions include materials, features, sizing, use case, and key selling points.
Return a JSON array of objects with keys: name, description.
No duplicates. Raw JSON only, no markdown."""
            },
            "promotions": {
                "ddl": """
                    CREATE TABLE IF NOT EXISTS promotions (
                        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name        TEXT NOT NULL,
                        description TEXT NOT NULL
                    )
                """,
                "columns": ["name", "description"],
                "prompt": """Generate {n} realistic retail promotion records.
Cover seasonal sales, loyalty discounts, bundle offers, clearance, flash sales,
buy-one-get-one, student discounts, member pricing, referral programs.
Descriptions include discount mechanics, eligibility, duration, and exclusions.
Return a JSON array of objects with keys: name, description.
No duplicates. Raw JSON only, no markdown."""
            },
            "store_locations": {
                "ddl": """
                    CREATE TABLE IF NOT EXISTS store_locations (
                        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name        TEXT NOT NULL,
                        description TEXT NOT NULL
                    )
                """,
                "columns": ["name", "description"],
                "prompt": """Generate {n} realistic retail store location records.
name is store name and location (e.g. Oxford Street Flagship, Brooklyn Outlet).
description covers store format, departments, special services, parking, opening hours context.
Return a JSON array of objects with keys: name, description.
No duplicates. Raw JSON only, no markdown."""
            },
            "support_tickets": {
                "ddl": """
                    CREATE TABLE IF NOT EXISTS support_tickets (
                        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name        TEXT NOT NULL,
                        description TEXT NOT NULL
                    )
                """,
                "columns": ["name", "description"],
                "prompt": """Generate {n} realistic retail customer support ticket records.
name is a short subject line. description is the customer issue in detail.
Cover wrong item delivered, return disputes, discount not applied, sizing issues,
delayed shipment, payment failures, loyalty points missing, store complaint.
Descriptions: 2-4 sentences, sound like real customer complaints.
Return a JSON array of objects with keys: name, description.
No duplicates. Raw JSON only, no markdown."""
            },
            "order_types": {
                "ddl": """
                    CREATE TABLE IF NOT EXISTS order_types (
                        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name        TEXT NOT NULL,
                        description TEXT NOT NULL
                    )
                """,
                "columns": ["name", "description"],
                "prompt": """Generate {n} realistic retail order type records.
Cover standard online, click-and-collect, same-day delivery, subscription, wholesale,
dropship, pre-order, back-order, gift, returns, exchanges.
Descriptions explain fulfillment flow, SLA, payment capture timing, and constraints.
Return a JSON array of objects with keys: name, description.
No duplicates. Raw JSON only, no markdown."""
            }
        }
    },

    "aerospace_defense": {
        "tables": {
            "equipment_catalog": {
                "ddl": """
                    CREATE TABLE IF NOT EXISTS equipment_catalog (
                        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name        TEXT NOT NULL,
                        description TEXT NOT NULL
                    )
                """,
                "columns": ["name", "description"],
                "prompt": """Generate {n} realistic aerospace and defense equipment catalog records.
Cover aircraft systems, navigation, avionics, weapons systems, surveillance,
communications, propulsion, ground support equipment, UAVs, satellites.
Descriptions include technical specs, operational context, classification level awareness.
Return a JSON array of objects with keys: name, description.
No duplicates. Raw JSON only, no markdown."""
            },
            "maintenance_procedures": {
                "ddl": """
                    CREATE TABLE IF NOT EXISTS maintenance_procedures (
                        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name        TEXT NOT NULL,
                        description TEXT NOT NULL
                    )
                """,
                "columns": ["name", "description"],
                "prompt": """Generate {n} realistic aerospace maintenance procedure records.
Cover scheduled inspections, component replacement, avionics calibration,
airframe repairs, engine overhaul, pre-flight checks, software updates.
Descriptions explain procedure scope, required certifications, tools, safety requirements.
Return a JSON array of objects with keys: name, description.
No duplicates. Raw JSON only, no markdown."""
            },
            "mission_profiles": {
                "ddl": """
                    CREATE TABLE IF NOT EXISTS mission_profiles (
                        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name        TEXT NOT NULL,
                        description TEXT NOT NULL
                    )
                """,
                "columns": ["name", "description"],
                "prompt": """Generate {n} realistic aerospace and defense mission profile records.
Cover surveillance, air superiority, close air support, humanitarian airlift,
maritime patrol, ISR, electronic warfare, strategic transport, search and rescue.
Descriptions explain mission objectives, platform requirements, operational constraints.
Return a JSON array of objects with keys: name, description.
No duplicates. Raw JSON only, no markdown."""
            },
            "support_tickets": {
                "ddl": """
                    CREATE TABLE IF NOT EXISTS support_tickets (
                        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name        TEXT NOT NULL,
                        description TEXT NOT NULL
                    )
                """,
                "columns": ["name", "description"],
                "prompt": """Generate {n} realistic aerospace and defense technical support ticket records.
name is a short subject line. description is the issue in detail.
Cover avionics faults, parts availability, technical manual discrepancies,
software certification issues, supply chain delays, calibration failures.
Descriptions: 2-4 sentences, technical and domain-accurate.
Return a JSON array of objects with keys: name, description.
No duplicates. Raw JSON only, no markdown."""
            },
            "parts_inventory": {
                "ddl": """
                    CREATE TABLE IF NOT EXISTS parts_inventory (
                        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name        TEXT NOT NULL,
                        description TEXT NOT NULL
                    )
                """,
                "columns": ["name", "description"],
                "prompt": """Generate {n} realistic aerospace parts inventory records.
Cover structural components, avionics modules, engine parts, hydraulic components,
fasteners, seals, electrical harnesses, black boxes, ejection seat components.
Descriptions include part number context, platform compatibility, certification status.
Return a JSON array of objects with keys: name, description.
No duplicates. Raw JSON only, no markdown."""
            }
        }
    }
}


# ── LLM generation ───────────────────────────────────────────────────────────

def generate_batch(client: OpenAI, prompt: str, n: int, model: str) -> List[Dict]:
    filled = prompt.format(n=n)
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": filled}],
                temperature=0.9,
            )
            content = response.choices[0].message.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            rows = json.loads(content)
            if isinstance(rows, list) and rows:
                return rows
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} failed: {e}")
            time.sleep(2 ** attempt)
    return []


# ── Database operations ───────────────────────────────────────────────────────

def setup_schema(conn, schema: str):
    with conn.cursor() as cur:
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    conn.commit()


def setup_table(conn, schema: str, table: str, ddl: str):
    with conn.cursor() as cur:
        cur.execute(f"SET search_path = {schema}")
        cur.execute(ddl)
    conn.commit()


def row_count(conn, schema: str, table: str) -> int:
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {schema}.{table}")
        return cur.fetchone()[0]


def insert_rows(conn, schema: str, table: str, columns: List[str], rows: List[Dict]) -> int:
    if not rows:
        return 0
    col_str = ", ".join(columns)
    placeholders = ", ".join(["%s"] * len(columns))
    sql = f"INSERT INTO {schema}.{table} (id, {col_str}) VALUES (gen_random_uuid(), {placeholders})"
    values = []
    for row in rows:
        try:
            values.append(tuple(row[c] for c in columns))
        except KeyError as e:
            logger.warning(f"Skipping row missing key {e}")
    with conn.cursor() as cur:
        cur.executemany(sql, values)
    conn.commit()
    return len(values)


# ── Main ─────────────────────────────────────────────────────────────────────

def run_domain(conn, client, domain_name, domain_def, target, batch_size, model):
    logger.info(f"=== Domain: {domain_name} ===")
    setup_schema(conn, domain_name)

    for table_name, tdef in domain_def["tables"].items():
        logger.info(f"  Table: {table_name}")
        setup_table(conn, domain_name, table_name, tdef["ddl"])

        current = row_count(conn, domain_name, table_name)
        logger.info(f"  Existing rows: {current} / {target}")

        while current < target:
            n = min(batch_size, target - current)
            logger.info(f"  Generating {n} rows...")
            rows = generate_batch(client, tdef["prompt"], n, model)
            if not rows:
                logger.warning("  Empty batch, retrying...")
                continue
            inserted = insert_rows(conn, domain_name, table_name, tdef["columns"], rows)
            current += inserted
            logger.info(f"  Total: {current} / {target}")

        logger.info(f"  ✓ {table_name} done")


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic demo data for CockroachDB Vector Demo")
    parser.add_argument("-u", "--url", required=True, help="CockroachDB connection URL")
    parser.add_argument("-d", "--domain", help=f"Domain name. Available: {list(DOMAINS.keys())}")
    parser.add_argument("--all", action="store_true", help="Run all domains")
    parser.add_argument("-t", "--target", type=int, default=10000, help="Target rows per table (default: 10000)")
    parser.add_argument("-b", "--batch-size", type=int, default=50, help="Rows per LLM call (default: 50)")
    parser.add_argument("--model", default="gpt-4o-mini", help="OpenAI model (default: gpt-4o-mini)")
    parser.add_argument("--api-key", help="OpenAI API key (or set OPENAI_API_KEY env var)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

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

    with psycopg.connect(args.url) as conn:
        for name, defn in to_run.items():
            run_domain(conn, client, name, defn, args.target, args.batch_size, args.model)

    logger.info("All done.")


if __name__ == "__main__":
    main()
