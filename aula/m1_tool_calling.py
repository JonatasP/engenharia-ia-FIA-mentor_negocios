"""Módulo 1 — Tool calling passo a passo (slides 16 a 18).

Mostra, sem nenhuma abstração, o ciclo:
  1. definimos a ferramenta (schema JSON);
  2. o LLM decide se chama e com quais argumentos;
  3. o nosso código executa;
  4. o resultado volta ao LLM, que continua.

Executar:  python -m aula.m1_tool_calling "Qual é o problema que o nosso negócio resolve?"
"""

import json
import sys

from mentor.config import carregar_config
from mentor.kb import BaseConhecimento, formatar_resultados
from mentor.llm import LLM

cfg = carregar_config()
llm = LLM(cfg.modelo, cfg.modelo_embeddings)
kb = BaseConhecimento.de_pasta(llm, cfg.pasta_kb)

# 1. A ferramenta: o que o LLM vê (schema) e o que o sistema executa (função).
ferramenta_schema = {
    "type": "function",
    "name": "buscar_kb",
    "description": "Busca trechos relevantes nos documentos do grupo.",
    "parameters": {
        "type": "object",
        "properties": {"consulta": {"type": "string", "description": "O que procurar."}},
        "required": ["consulta"],
    },
}


def buscar_kb(consulta: str) -> str:
    return formatar_resultados(kb.buscar(consulta, k=3))


instrucoes = f"Você ajuda o grupo do negócio {cfg.negocio}. Use buscar_kb antes de responder sobre o negócio."
pergunta = sys.argv[1] if len(sys.argv) > 1 else "Qual é o problema que o nosso negócio resolve?"
itens = [{"role": "user", "content": pergunta}]

for passo in range(1, 5):  # limite de passos: guardrail contra loop infinito
    resposta = llm.responder(instrucoes, itens, [ferramenta_schema])
    chamadas = [i for i in resposta.output if i.type == "function_call"]

    if not chamadas:  # 4. sem novas chamadas: o LLM concluiu
        print(f"\n=== Resposta final (passo {passo}) ===\n{resposta.output_text}")
        break

    itens.extend(resposta.output)
    for chamada in chamadas:  # 2. o LLM escolheu a ferramenta e os argumentos
        argumentos = json.loads(chamada.arguments)
        print(f"\n[passo {passo}] LLM pediu: {chamada.name}({argumentos})")
        resultado = buscar_kb(**argumentos)  # 3. o nosso código executa
        print(f"[passo {passo}] Resultado (prévia): {resultado[:200]}…")
        itens.append({"type": "function_call_output", "call_id": chamada.call_id, "output": resultado})
