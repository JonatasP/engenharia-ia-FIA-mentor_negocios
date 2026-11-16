"""Cliente OpenAI falso: permite testar o agente sem rede e sem custo."""

import hashlib
import json
import re
from types import SimpleNamespace

import pytest

from mentor.config import RAIZ, carregar_config
from mentor.kb import BaseConhecimento
from mentor.llm import LLM


def _vetor(texto: str, dimensoes: int = 256) -> list[float]:
    """Embedding de brinquedo: saco de palavras com hashing (textos parecidos → vetores parecidos)."""
    vetor = [0.0] * dimensoes
    for palavra in re.findall(r"\w+", texto.lower()):
        vetor[int(hashlib.md5(palavra.encode()).hexdigest(), 16) % dimensoes] += 1.0
    return vetor


def chamada(nome: str, argumentos: dict, call_id: str = "c1"):
    return SimpleNamespace(type="function_call", name=nome, arguments=json.dumps(argumentos), call_id=call_id)


def resposta(texto: str = "", itens=None):
    return SimpleNamespace(output=list(itens or []), output_text=texto)


class ClienteFalso:
    def __init__(self):
        self.roteiro = []  # respostas devolvidas em ordem por responses.create
        self.chamadas = []  # parâmetros recebidos, para inspeção nos testes
        self.responses = SimpleNamespace(create=self._responder)
        self.embeddings = SimpleNamespace(create=self._embeddings)

    def _responder(self, **parametros):
        self.chamadas.append(parametros)
        return self.roteiro.pop(0) if self.roteiro else resposta("ok")

    def _embeddings(self, model, input):
        return SimpleNamespace(data=[SimpleNamespace(embedding=_vetor(t)) for t in input])


@pytest.fixture
def cliente():
    return ClienteFalso()


@pytest.fixture
def cfg():
    return carregar_config(RAIZ / "grupo.yaml")


@pytest.fixture
def llm(cliente, cfg):
    return LLM(cfg.modelo, cfg.modelo_embeddings, client=cliente)


@pytest.fixture
def kb(llm, cfg):
    return BaseConhecimento.de_pasta(llm, cfg.pasta_kb)
