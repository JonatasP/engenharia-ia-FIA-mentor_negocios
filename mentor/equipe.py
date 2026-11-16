"""Equipe multiagente em LangGraph (slides 22 e 31): pesquisador → redator → revisor.

    START → pesquisador → redator → revisor → FIM   (aprovado ou limite de rodadas)
                             ↑            │
                             └── ajustes ─┘
    Na revisão humana, a pesquisa é reaproveitada e o fluxo começa no redator.

- O pesquisador é um sub-agente: reutiliza o AgenteMentor, que decide quais ferramentas usar.
- Redator e revisor são chamadas diretas ao LLM, cada um com seu papel ("especialista").
- O orquestrador é uma função de roteamento: o fluxo é definido em código.
  Por isso, esta equipe é um workflow do tipo evaluator-optimizer (slide 15), e não um agente autônomo.
- Human-in-the-loop: o aluno lê o resultado e pode pedir nova versão com seus ajustes.
"""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from mentor.prompts import INSTRUCOES_REDATOR, INSTRUCOES_REVISOR, MODELO_PRESS_RELEASE, PEDIDO_PESQUISA


class EstadoEquipe(TypedDict, total=False):
    pedido: str
    pesquisa: str
    rascunho: str
    parecer: str
    aprovado: bool
    rodada: int
    feedback_humano: str
    historico: list[str]


def criar_equipe(agente, llm, max_revisoes: int):
    def pesquisador(estado: EstadoEquipe) -> EstadoEquipe:
        resultado = agente.responder(PEDIDO_PESQUISA.format(pedido=estado["pedido"]))
        passos = ", ".join(resultado.ferramentas_usadas) or "nenhuma ferramenta"
        return {"pesquisa": resultado.resposta, "historico": _registrar(estado, f"Pesquisador: usou {passos}.")}

    def redator(estado: EstadoEquipe) -> EstadoEquipe:
        partes = [f"Pedido: {estado['pedido']}", f"Pesquisa:\n{estado['pesquisa']}"]
        if estado.get("rascunho"):
            partes.append(f"Versão anterior:\n{estado['rascunho']}")
        if estado.get("parecer") and not estado.get("aprovado"):
            partes.append(f"Ajustes pedidos pelo revisor:\n{estado['parecer']}")
        if estado.get("feedback_humano"):
            partes.append(f"Ajustes pedidos pelo grupo (prioridade máxima):\n{estado['feedback_humano']}")
        rascunho = llm.gerar_texto(INSTRUCOES_REDATOR.format(modelo=MODELO_PRESS_RELEASE), "\n\n".join(partes))
        return {"rascunho": rascunho, "historico": _registrar(estado, "Redator: escreveu uma versão.")}

    def revisor(estado: EstadoEquipe) -> EstadoEquipe:
        parecer = llm.gerar_texto(INSTRUCOES_REVISOR.format(modelo=MODELO_PRESS_RELEASE), estado["rascunho"])
        aprovado = parecer.strip().upper().startswith("APROVADO")
        rodada = estado.get("rodada", 0) + 1
        resumo = "aprovou" if aprovado else "pediu ajustes"
        return {
            "parecer": parecer,
            "aprovado": aprovado,
            "rodada": rodada,
            "historico": _registrar(estado, f"Revisor (rodada {rodada}): {resumo}."),
        }

    def orquestrador(estado: EstadoEquipe) -> str:
        """Decide o próximo passo. O limite de rodadas evita loop infinito de revisão."""
        if estado.get("aprovado") or estado.get("rodada", 0) >= max_revisoes:
            return "fim"
        return "redator"

    grafo = StateGraph(EstadoEquipe)
    grafo.add_node("pesquisador", pesquisador)
    grafo.add_node("redator", redator)
    grafo.add_node("revisor", revisor)
    grafo.add_conditional_edges(START, lambda e: "redator" if e.get("pesquisa") else "pesquisador", ["pesquisador", "redator"])
    grafo.add_edge("pesquisador", "redator")
    grafo.add_edge("redator", "revisor")
    grafo.add_conditional_edges("revisor", orquestrador, {"redator": "redator", "fim": END})
    return grafo.compile()


def executar_equipe(equipe, pedido: str, anterior: EstadoEquipe | None = None, feedback: str = "") -> EstadoEquipe:
    """Primeira execução: só o pedido. Revisão humana: reaproveita a pesquisa e o rascunho anteriores."""
    estado: EstadoEquipe = {"pedido": pedido, "rodada": 0, "historico": []}
    if anterior and feedback:
        estado.update(pesquisa=anterior["pesquisa"], rascunho=anterior["rascunho"], feedback_humano=feedback)
    return equipe.invoke(estado)


def _registrar(estado: EstadoEquipe, evento: str) -> list[str]:
    return [*estado.get("historico", []), evento]
