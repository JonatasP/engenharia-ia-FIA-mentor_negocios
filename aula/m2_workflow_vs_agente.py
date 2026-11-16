"""Módulo 2 — Workflow vs agente (slides 13 a 15).

A mesma pergunta respondida de dois jeitos:
- Workflow: o ENGENHEIRO define o fluxo (buscar na KB → gerar resposta). Sempre 1 busca + 1 chamada.
- Agente: o LLM decide o fluxo (quais ferramentas, quantas vezes, em que ordem).

Executar:  python -m aula.m2_workflow_vs_agente "Quais riscos o nosso negócio corre e como está o mercado?"
"""

import sys
import time

from mentor.agente import AgenteMentor
from mentor.config import carregar_config
from mentor.kb import BaseConhecimento, formatar_resultados
from mentor.llm import LLM

cfg = carregar_config()
llm = LLM(cfg.modelo, cfg.modelo_embeddings)
kb = BaseConhecimento.de_pasta(llm, cfg.pasta_kb)
pergunta = sys.argv[1] if len(sys.argv) > 1 else "Quais riscos o nosso negócio corre e como está o mercado?"


def workflow(pergunta: str) -> str:
    contexto = formatar_resultados(kb.buscar(pergunta, k=4))  # passo fixo 1
    return llm.gerar_texto(  # passo fixo 2
        f"Responda sobre o negócio {cfg.negocio} usando apenas o contexto. Cite [KB: ...].",
        f"Contexto:\n{contexto}\n\nPergunta: {pergunta}",
    )


inicio = time.monotonic()
print("=== WORKFLOW (fluxo definido no código) ===")
print(workflow(pergunta))
print(f"\n→ 1 busca fixa + 1 chamada ao LLM, {time.monotonic() - inicio:.1f}s")

inicio = time.monotonic()
resultado = AgenteMentor(llm, kb, cfg).responder(pergunta)
print("\n=== AGENTE (fluxo decidido pelo LLM) ===")
print(resultado.resposta)
print(f"\n→ ferramentas escolhidas: {resultado.ferramentas_usadas or 'nenhuma'}, {time.monotonic() - inicio:.1f}s")
