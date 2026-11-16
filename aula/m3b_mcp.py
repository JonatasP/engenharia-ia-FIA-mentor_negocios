"""Módulo 3b — MCP: host, client e server (slide 20).

- Server: mentor/mcp_server.py, que expõe a KB do grupo como ferramentas MCP.
- Client: a biblioteca `mcp`, que inicia o servidor (stdio) e conversa com ele.
- Host: este script, que entrega as ferramentas descobertas ao LLM.

Repare que o host não conhece as ferramentas de antemão: ele as descobre com list_tools().

Instalar:  pip install -r requirements-aula.txt
Executar:  python -m aula.m3b_mcp "Como o nosso produto funciona?"
"""

import asyncio
import json
import os
import sys

from mcp import Client, StdioServerParameters

from mentor.config import RAIZ, carregar_config
from mentor.llm import LLM


async def main(pergunta: str):
    cfg = carregar_config()
    llm = LLM(cfg.modelo, cfg.modelo_embeddings)
    # env explícito: por padrão o cliente repassa ao servidor só variáveis básicas (sem OPENAI_API_KEY).
    servidor = StdioServerParameters(
        command=sys.executable, args=["-m", "mentor.mcp_server"], env=dict(os.environ), cwd=RAIZ
    )

    async with Client(servidor) as cliente:
        descobertas = (await cliente.list_tools()).tools
        print("Ferramentas descobertas via MCP:", [t.name for t in descobertas])
        ferramentas = [
            {"type": "function", "name": t.name, "description": t.description or "", "parameters": t.input_schema}
            for t in descobertas
        ]

        itens = [{"role": "user", "content": pergunta}]
        for _ in range(5):
            resposta = llm.responder(f"Você ajuda o grupo do negócio {cfg.negocio}.", itens, ferramentas)
            chamadas = [i for i in resposta.output if i.type == "function_call"]
            if not chamadas:
                print("\n" + resposta.output_text)
                return
            itens.extend(resposta.output)
            for chamada in chamadas:
                print(f"→ chamando via MCP: {chamada.name}({chamada.arguments})")
                resultado = await cliente.call_tool(chamada.name, json.loads(chamada.arguments))
                texto = "\n".join(getattr(c, "text", "") for c in resultado.content)
                itens.append({"type": "function_call_output", "call_id": chamada.call_id, "output": texto})


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "Como o nosso produto funciona?"))
