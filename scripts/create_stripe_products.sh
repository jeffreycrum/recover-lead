#!/usr/bin/env bash
set -euo pipefail

echo "=== Creating Stripe Products & Prices ==="

# --- Starter ---
echo "Creating Starter product..."
STARTER_PROD=$(stripe products create --name="RecoverLead Starter" | jq -r '.id')
echo "Starter product: $STARTER_PROD"

STARTER_MONTHLY=$(stripe prices create \
  --product="$STARTER_PROD" \
  --unit-amount=7900 \
  --currency=usd \
  -d "recurring[interval]=month" \
  | jq -r '.id')
echo "Starter monthly price: $STARTER_MONTHLY"

STARTER_ANNUAL=$(stripe prices create \
  --product="$STARTER_PROD" \
  --unit-amount=49900 \
  --currency=usd \
  -d "recurring[interval]=year" \
  | jq -r '.id')
echo "Starter annual price: $STARTER_ANNUAL"

# --- Pro ---
echo ""
echo "Creating Pro product..."
PRO_PROD=$(stripe products create --name="RecoverLead Pro" | jq -r '.id')
echo "Pro product: $PRO_PROD"

PRO_MONTHLY=$(stripe prices create \
  --product="$PRO_PROD" \
  --unit-amount=19900 \
  --currency=usd \
  -d "recurring[interval]=month" \
  | jq -r '.id')
echo "Pro monthly price: $PRO_MONTHLY"

PRO_ANNUAL=$(stripe prices create \
  --product="$PRO_PROD" \
  --unit-amount=199000 \
  --currency=usd \
  -d "recurring[interval]=year" \
  | jq -r '.id')
echo "Pro annual price: $PRO_ANNUAL"

# --- Agency ---
echo ""
echo "Creating Agency product..."
AGENCY_PROD=$(stripe products create --name="RecoverLead Agency" | jq -r '.id')
echo "Agency product: $AGENCY_PROD"

AGENCY_MONTHLY=$(stripe prices create \
  --product="$AGENCY_PROD" \
  --unit-amount=49900 \
  --currency=usd \
  -d "recurring[interval]=month" \
  | jq -r '.id')
echo "Agency monthly price: $AGENCY_MONTHLY"

AGENCY_ANNUAL=$(stripe prices create \
  --product="$AGENCY_PROD" \
  --unit-amount=499000 \
  --currency=usd \
  -d "recurring[interval]=year" \
  | jq -r '.id')
echo "Agency annual price: $AGENCY_ANNUAL"

echo ""
echo "=== Done! Update billing_service.py with these price IDs ==="
echo ""
echo "PLAN_CONFIG = {"
echo "    \"starter\": {"
echo "        \"monthly_price_id\": \"$STARTER_MONTHLY\","
echo "        \"annual_price_id\": \"$STARTER_ANNUAL\","
echo "    },"
echo "    \"pro\": {"
echo "        \"monthly_price_id\": \"$PRO_MONTHLY\","
echo "        \"annual_price_id\": \"$PRO_ANNUAL\","
echo "    },"
echo "    \"agency\": {"
echo "        \"monthly_price_id\": \"$AGENCY_MONTHLY\","
echo "        \"annual_price_id\": \"$AGENCY_ANNUAL\","
echo "    },"
echo "}"
