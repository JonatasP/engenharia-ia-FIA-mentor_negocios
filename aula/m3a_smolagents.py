"""Módulo 3a — O mesmo agente com um framework: smolagents (slide 21).

Compare com mentor/agente.py: o framework assume o loop ReAct, o limite de passos
e a conversão das funções em schemas (a partir das type hints e da docstring).

Usamos ToolCallingAgent, que chama ferramentas via JSON. O CodeAgent dos slides gera
e executa código Python; em produção, ele exige sandbox.

O OpenAIServerModel usa a Chat Completions API. Se o modelo de OPENAI_MODEL não estiver
disponível nela, defina outro modelo antes de executar.

Instalar:  pip install -r requirements-aula.txt
Executar:  python -m aula.m3a_smolagents "Quem é o cliente do nosso negócio?"
"""

import os
import sys

from smolagents import OpenAIServerModel, ToolCallingAgent, tool

from mentor.config import carregar_config
from mentor.kb import BaseConhecimento, formatar_resultados
from mentor.llm import LLM

cfg = carregar_config()
kb = BaseConhecimento.de_pasta(LLM(cfg.modelo, cfg.modelo_embeddings), cfg.pasta_kb)


@tool
def buscar_kb(consulta: str) -> str:
    """Busca trechos relevantes nos documentos do grupo.

    Args:
        consulta: O que procurar, em linguagem natural.
    """
    return formatar_resultados(kb.buscar(consulta, k=3))


agente = ToolCallingAgent(
    tools=[buscar_kb],
    model=OpenAIServerModel(model_id=cfg.modelo, api_key=os.environ["OPENAI_API_KEY"]),
    max_steps=5,  # guardrail contra loop infinito
)

pergunta = sys.argv[1] if len(sys.argv) > 1 else "Quem é o cliente do nosso negócio?"
print(agente.run(f"Você ajuda o grupo do negócio {cfg.negocio}. {pergunta}"))
