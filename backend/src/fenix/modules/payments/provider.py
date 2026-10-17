"""Payment providers (AD-9). Until v1 only the test one exists."""

import uuid
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ProviderPayment:
    provider_payment_id: str
    # Where the guest pays; None when the Mini App shows its own test screen.
    confirmation_url: str | None


class PaymentProvider(Protocol):
    name: str

    async def create(self, payment_id: uuid.UUID, amount: int, description: str) -> ProviderPayment:
        """Idempotent by payment_id: the same id gives the same provider payment."""
        ...

    async def refund(self, provider_payment_id: str, amount: int) -> None: ...


class MockProvider:
    """Test acquiring: no money moves; the guest confirms or declines in the Mini App and
    that is delivered to `payments` like a provider notification would be."""

    name = "mock"

    async def create(self, payment_id: uuid.UUID, amount: int, description: str) -> ProviderPayment:
        return ProviderPayment(f"mock_{payment_id}", None)

    async def refund(self, provider_payment_id: str, amount: int) -> None:
        return None
