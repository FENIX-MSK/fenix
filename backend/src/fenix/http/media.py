from typing import Annotated

from fastapi import Depends, Request

from fenix.platform.storage import MediaStorage


def photo_url(key: str | None) -> str | None:
    """Guests load photos from Caddy (`/media/*` → Garage web endpoint), never from the API."""
    return f"/media/{key}" if key else None


def get_storage(request: Request) -> MediaStorage:
    storage: MediaStorage = request.app.state.media_storage
    return storage


StorageDep = Annotated[MediaStorage, Depends(get_storage)]
