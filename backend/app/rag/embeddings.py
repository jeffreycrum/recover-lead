import structlog
from sentence_transformers import SentenceTransformer

from app.config import settings

logger = structlog.get_logger()

_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    """Get or lazily load the embedding model. Called once per worker via worker_init."""
    global _model
    if _model is None:
        logger.info("loading_embedding_model", model=settings.embedding_model)
        # Force CPU to avoid MPS segfaults in forked Celery workers
        _model = SentenceTransformer(settings.embedding_model, device="cpu")
        logger.info("embedding_model_loaded", dimension=_model.get_sentence_embedding_dimension())
    return _model


def generate_embedding(text: str) -> list[float]:
    """Generate a 384-dimensional embedding for a text string."""
    model = get_embedding_model()
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()


def generate_lead_embedding(lead_text: str) -> list[float]:
    """Generate an embedding for lead data (property + owner + county info)."""
    return generate_embedding(lead_text)


def build_lead_text(
    case_number: str,
    owner_name: str | None,
    property_address: str | None,
    property_city: str | None,
    surplus_amount: float,
    sale_type: str | None,
    county_name: str | None = None,
) -> str:
    """Build a text representation of a lead for embedding."""
    parts = []
    if county_name:
        parts.append(f"County: {county_name}")
    parts.append(f"Case: {case_number}")
    if owner_name:
        parts.append(f"Owner: {owner_name}")
    if property_address:
        addr = property_address
        if property_city:
            addr += f", {property_city}"
        parts.append(f"Property: {addr}")
    parts.append(f"Surplus: ${surplus_amount:,.2f}")
    if sale_type:
        parts.append(f"Sale type: {sale_type.replace('_', ' ')}")
    return " | ".join(parts)
