"""Platform adapters for resume sync."""

from .base import PlatformAdapter, SyncResult
from .linkedin import LinkedInAdapter
from .naukri import NaukriAdapter
from .wellfound import WellfoundAdapter

ADAPTERS: dict[str, PlatformAdapter] = {
    adapter.name: adapter()
    for adapter in (LinkedInAdapter, WellfoundAdapter, NaukriAdapter)
}


def get_adapter(platform: str) -> PlatformAdapter | None:
    return ADAPTERS.get(platform)
