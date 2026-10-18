"""x402 resource server shared by the paid routes."""
from x402 import ResourceConfig, x402ResourceServer
from x402.http import FacilitatorConfig, HTTPFacilitatorClient
from x402.mechanisms.evm.exact import ExactEvmServerScheme
from x402.schemas import AssetAmount

from payments import config

_server = None


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
            extra={"name": "USDC", "version": "2"},
        ),
        network=config.NETWORK,
        max_timeout_seconds=config.PAYMENT_TIMEOUT_SECONDS,
    )
    return get_server().build_payment_requirements(resource)
