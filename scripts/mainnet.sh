#!/bin/zsh
# Runs a command on Base mainnet (REAL USDC): exports .env.mainnet on top of .env, which stays the testnet config.
#
#   scripts/mainnet.sh .venv/bin/python scripts/preflight.py
#   scripts/mainnet.sh .venv/bin/uvicorn gateway.main:app --port 8000
#   cd frontend && ../scripts/mainnet.sh npm run dev
#
# Create the mainnet wallets once: .venv/bin/python scripts/create_wallets.py --env-file .env.mainnet --buyers 1
set -e
ROOT=${0:A:h:h}
if [[ ! -f "$ROOT/.env.mainnet" ]]; then
  echo "missing $ROOT/.env.mainnet (see the header of this script)" >&2
  exit 1
fi
set -a
source "$ROOT/.env.mainnet"
set +a
export NEXT_PUBLIC_CHAIN=base NEXT_PUBLIC_EXPLORER_URL="$EXPLORER_URL"
[[ -n "$MAINNET_BUYER_ADDRESS" ]] && export NEXT_PUBLIC_BUYER_WALLET="$MAINNET_BUYER_ADDRESS"
echo "== Base mainnet, real USDC (network $NETWORK, facilitator $FACILITATOR_URL)" >&2
exec "$@"
