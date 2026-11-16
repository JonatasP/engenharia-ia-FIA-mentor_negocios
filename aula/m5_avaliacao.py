"""Módulo 5 — Avaliação do agente, no espírito do BFCL (slides 25 e 32).

Para cada caso de evals/casos.yaml, verificamos:
- seleção de ferramenta: a primeira ferramenta chamada é a esperada? (ou nenhuma, em saudações)
- citação: quando o agente consultou alguma fonte, a resposta traz [KB: ...] ou [WEB: ...]?

Executar:  python -m aula.m5_avaliacao
"""

import yaml

from mentor.agente import AgenteMentor
from mentor.config import RAIZ, carregar_config
from mentor.kb import BaseConhecimento
from mentor.llm import LLM

cfg = carregar_config()
llm = LLM(cfg.modelo, cfg.modelo_embeddings)
agente = AgenteMentor(llm, BaseConhecimento.de_pasta(llm, cfg.pasta_kb), cfg)
casos = yaml.safe_load((RAIZ / "evals" / "casos.yaml").read_text(encoding="utf-8"))

acertos_ferramenta, com_fonte, citou = 0, 0, 0
for caso in casos:
    resultado = agente.responder(caso["pergunta"])
    primeira = resultado.ferramentas_usadas[0] if resultado.ferramentas_usadas else None
    acertou = primeira == caso["ferramenta_esperada"]
    acertos_ferramenta += acertou

    usou_fonte = any(f in ("buscar_kb", "buscar_web") for f in resultado.ferramentas_usadas)
    tem_citacao = "[KB:" in resultado.resposta or "[WEB:" in resultado.resposta
    com_fonte += usou_fonte
    citou += usou_fonte and tem_citacao

    marca = "OK  " if acertou else "ERRO"
    print(f"{marca} | esperado={caso['ferramenta_esperada']} obtido={primeira} | {caso['pergunta']}")

print(f"\nSeleção de ferramenta: {acertos_ferramenta}/{len(casos)}")
print(f"Respostas com citação (entre as que consultaram fontes): {citou}/{com_fonte}")
