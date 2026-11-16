"""Parametrização do agente.

- grupo.yaml define O QUE o agente faz (negócio, escopo, comportamento).
- Variáveis de ambiente definem ONDE ele roda (chave, modelos).
"""

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

try:  # .env só é usado no desenvolvimento local; no Render as variáveis vêm do painel.
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

RAIZ = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Config:
    grupo: str
    negocio: str
    resumo: str
    publico: str
    instrucoes_adicionais: str
    busca_web: bool
    max_iteracoes: int
    timeout_segundos: float
    max_revisoes: int
    pasta_kb: Path
    modelo: str
    modelo_embeddings: str


def carregar_config(caminho: str | Path | None = None) -> Config:
    caminho = Path(caminho or os.getenv("MENTOR_CONFIG", RAIZ / "grupo.yaml"))
    dados = yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}
    agente = dados.get("agente") or {}

    return Config(
        grupo=dados.get("grupo", "Grupo"),
        negocio=dados["negocio"],
        resumo=(dados.get("resumo") or "").strip(),
        publico=(dados.get("publico") or "").strip(),
        instrucoes_adicionais=(dados.get("instrucoes_adicionais") or "").strip(),
        busca_web=bool(agente.get("busca_web", True)),
        max_iteracoes=int(agente.get("max_iteracoes", 8)),
        timeout_segundos=float(agente.get("timeout_segundos", 150)),
        max_revisoes=int(agente.get("max_revisoes", 3)),
        pasta_kb=RAIZ / dados.get("pasta_kb", "kb"),
        modelo=os.getenv("OPENAI_MODEL", "gpt-6-luna"),
        modelo_embeddings=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
    )
