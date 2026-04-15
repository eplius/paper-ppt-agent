"""Providers endpoint."""

from fastapi import APIRouter

from backend.api.schemas import ProviderListItem, ProviderModel, ProvidersResponse
from backend.llm import list_providers

router = APIRouter()


@router.get("/providers", response_model=ProvidersResponse)
async def get_providers() -> ProvidersResponse:
    providers = []
    for provider in list_providers():
        providers.append(
            ProviderListItem(
                name=provider.name,
                display_name=provider.display_name,
                models=[
                    ProviderModel(
                        id=model.id,
                        display_name=model.display_name,
                        supports_vision=model.supports_vision,
                    )
                    for model in provider.models
                ],
            )
        )
    return ProvidersResponse(providers=providers)
