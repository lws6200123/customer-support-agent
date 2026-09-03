"""RAGFlow-only policy retrieval with deterministic metadata normalization."""

from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
from typing import Any

import httpx
import yaml

from customer_support_agent.core.config import AppSettings, PROJECT_ROOT
from customer_support_agent.core.errors import (
    KnowledgeConfigMissingError,
    KnowledgeServiceUnavailableError,
)
from customer_support_agent.core.schemas import KnowledgeResponse, KnowledgeResult


POLICY_DIR = PROJECT_ROOT / "knowledge" / "policies"


def _policy_metadata(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    _, frontmatter, _ = text.split("---", 2)
    value = yaml.safe_load(frontmatter)
    return value if isinstance(value, dict) else {}


def build_policy_name_index(policy_dir: Path = POLICY_DIR) -> dict[str, dict[str, Any]]:
    """Index stable file-name variants without depending on RAGFlow document IDs."""
    index: dict[str, dict[str, Any]] = {}
    for path in sorted(policy_dir.glob("*.md")):
        metadata = _policy_metadata(path)
        for key in {path.name.casefold(), path.stem.casefold()}:
            index[key] = metadata
    return index


class RAGFlowRetrievalClient:
    """Thin client for the RAGFlow v0.27.1 retrieval endpoint."""

    def __init__(
        self,
        settings: AppSettings | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings or AppSettings()
        self.http_client = http_client
        self.policy_index = build_policy_name_index()

    @property
    def endpoint(self) -> str:
        base = self.settings.ragflow_base_url.rstrip("/")
        if base.endswith("/api/v1"):
            return f"{base}/retrieval"
        return f"{base}/api/v1/retrieval"

    def _payload(self, query: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "question": query,
            "dataset_ids": [self.settings.ragflow_dataset_id],
            "page": 1,
            "page_size": self.settings.ragflow_top_n,
            "similarity_threshold": self.settings.ragflow_similarity_threshold,
            "vector_similarity_weight": self.settings.ragflow_vector_similarity_weight,
            "knn_top_k": 1024,
            "knn_num_candidates": 2048,
            "rerank_candidates_count": max(64, self.settings.ragflow_top_n),
        }
        if self.settings.ragflow_rerank_id:
            payload["rerank_id"] = self.settings.ragflow_rerank_id
        return payload

    @staticmethod
    def _chunk_name(chunk: dict[str, Any]) -> str:
        for field in ("document_name", "document_keyword", "docnm_kwd"):
            value = chunk.get(field)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return "unknown"

    def _normalize_chunk(self, chunk: dict[str, Any]) -> KnowledgeResult:
        document_name = self._chunk_name(chunk)
        metadata = self.policy_index.get(document_name.casefold())
        if metadata is None:
            metadata = self.policy_index.get(Path(document_name).stem.casefold(), {})
        ragflow_document_id = str(
            chunk.get("document_id") or chunk.get("doc_id") or ""
        ) or None
        local_policy_id = str(metadata.get("document_id") or "") or None
        content = chunk.get("content_with_weight", chunk.get("content", ""))
        if not isinstance(content, str):
            content = str(content)
        score = chunk.get("similarity", chunk.get("score", 0.0))
        try:
            normalized_score = float(score)
        except (TypeError, ValueError):
            normalized_score = 0.0
        return KnowledgeResult(
            content=content,
            document_name=document_name,
            document_id=local_policy_id or ragflow_document_id or "unknown",
            local_policy_id=local_policy_id,
            ragflow_document_id=ragflow_document_id,
            chunk_id=str(chunk.get("id") or chunk.get("chunk_id") or "unknown"),
            score=normalized_score,
            source_type=str(metadata.get("source_type") or "") or None,
            source_organization=str(metadata.get("source_organization") or "") or None,
        )

    def search(self, query: str) -> KnowledgeResponse:
        if not self.settings.ragflow_configured:
            raise KnowledgeConfigMissingError()
        headers = {
            "Authorization": (
                f"Bearer {self.settings.ragflow_api_key.get_secret_value()}"
            ),
            "Content-Type": "application/json",
        }
        try:
            manager = (
                nullcontext(self.http_client)
                if self.http_client is not None
                else httpx.Client(
                    timeout=self.settings.ragflow_timeout_seconds,
                    trust_env=False,
                )
            )
            with manager as client:
                response = client.post(
                    self.endpoint,
                    headers=headers,
                    json=self._payload(query),
                )
                response.raise_for_status()
                body = response.json()
        except (httpx.TimeoutException, httpx.RequestError, httpx.HTTPStatusError) as exc:
            raise KnowledgeServiceUnavailableError() from exc
        except (ValueError, TypeError) as exc:
            raise KnowledgeServiceUnavailableError(
                "The knowledge service returned an invalid response."
            ) from exc
        if not isinstance(body, dict) or body.get("code") != 0:
            raise KnowledgeServiceUnavailableError(
                "The knowledge service rejected the retrieval request."
            )
        data = body.get("data")
        chunks = data.get("chunks") if isinstance(data, dict) else None
        if not isinstance(chunks, list) or not all(isinstance(item, dict) for item in chunks):
            raise KnowledgeServiceUnavailableError(
                "The knowledge service returned an invalid chunk structure."
            )
        return KnowledgeResponse(
            query=query,
            results=[self._normalize_chunk(item) for item in chunks],
        )
