"""x402 resource server shared by the paid routes."""
from x402 import ResourceConfig, x402ResourceServer
from x402.http import FacilitatorConfig, HTTPFacilitatorClient
from x402.mechanisms.evm.exact import ExactEvmServerScheme
from x402.mechanisms.evm.default_assets import find_default_asset
from x402.schemas import AssetAmount

from payments import config

_server = None


def token_domain():
    """EIP-712 domain of the token, which the buyer signs: "USDC" on Base Sepolia but "USD Coin" on Base mainnet.
    Taken from the SDK's asset table so the signature matches the contract on every network."""
    info = find_default_asset(config.USDC_ADDRESS, config.NETWORK)
    if info is None:
        raise RuntimeError(f"Unknown token {config.USDC_ADDRESS} on {config.NETWORK}")
    return {"name": info["name"], "version": info["version"]}


def get_server():
    global _server
    if _server is None:
        server = x402ResourceServer(HTTPFacilitatorClient(FacilitatorConfig(url=config.FACILITATOR_URL)))
        server.register(config.NETWORK, ExactEvmServerScheme())
        server.initialize()
        _server = server
    return _server


def build_requirements(amount_atomic, pay_to):
    """Requirements are rebuilt from server-side data every time, never from what the client sends."""
    resource = ResourceConfig(
        scheme="exact",
        pay_to=pay_to,
        price=AssetAmount(
            amount=str(amount_atomic),
            asset=config.USDC_ADDRESS,
            extra=token_domain(),
        ),
        network=config.NETWORK,
        max_timeout_seconds=config.PAYMENT_TIMEOUT_SECONDS,
    )
    return get_server().build_payment_requirements(resource)
