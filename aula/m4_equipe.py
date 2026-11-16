"""Módulo 4 — Multiagente em LangGraph (slides 22 e 31).

Executa a equipe pesquisador → redator → revisor no terminal e mostra os bastidores.
O código da equipe está em mentor/equipe.py; o mesmo grafo roda na aba "Press release".

Executar:  python -m aula.m4_equipe "Press release de um plano de assinatura para empresas"
"""

import sys

from mentor.agente import AgenteMentor
from mentor.config import carregar_config
from mentor.equipe import criar_equipe, executar_equipe
from mentor.kb import BaseConhecimento
from mentor.llm import LLM

cfg = carregar_config()
llm = LLM(cfg.modelo, cfg.modelo_embeddings)
kb = BaseConhecimento.de_pasta(llm, cfg.pasta_kb)
equipe = criar_equipe(AgenteMentor(llm, kb, cfg), llm, cfg.max_revisoes)

pedido = sys.argv[1] if len(sys.argv) > 1 else f"Reescreva o press release do {cfg.negocio} com foco no cliente."
estado = executar_equipe(equipe, pedido)

print("=== Bastidores ===")
print("\n".join(estado["historico"]))
print(f"\nAprovado: {estado['aprovado']} | Rodadas de revisão: {estado['rodada']}")
print("\n=== Press release ===\n")
print(estado["rascunho"])
