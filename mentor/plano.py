"""Plan-and-Execute (slide 19) para pedidos amplos: plano de negócio, viabilidade, go-to-market.

    planejador (1 chamada ao LLM) → lista de etapas
    executor   (o AgenteMentor, uma vez por etapa, cada uma com seu próprio limite de passos)
    sumário    (1 chamada ao LLM sobre o documento montado)

Um pedido como "monte um business plan" não cabe no limite de passos de uma única resposta.
Dividido em etapas, cada seção recebe pesquisa própria e o documento final fica completo.
"""

import re
from dataclasses import dataclass, field

from mentor.prompts import INSTRUCOES_PLANEJADOR, INSTRUCOES_SUMARIO, PEDIDO_ETAPA

MAX_ETAPAS = 8

ETAPAS_PADRAO = [
    "Problema e oportunidade: qual dor do cliente o negócio resolve e por que agora",
    "Cliente e segmentos: quem compra, quem usa e qual segmento priorizar",
    "Proposta de valor e solução: o que o produto entrega e como funciona",
    "Mercado e concorrência: tamanho do mercado, concorrentes e diferenciais",
    "Modelo de receita: como o negócio ganha dinheiro e premissas de preço",
    "Operação e go-to-market: como o produto chega ao cliente e parcerias necessárias",
    "Riscos e regulação: riscos operacionais, regulatórios e de mercado, com mitigações",
    "Hipóteses e próximos passos: o que validar primeiro e como medir",
]


@dataclass
class Secao:
    titulo: str
    texto: str
    ferramentas: list[str] = field(default_factory=list)
    interrompida: bool = False


def planejar(llm, pedido: str, negocio: str) -> list[str]:
    """O planejador devolve uma etapa por linha; se a resposta vier fora do formato, usa o plano padrão."""
    resposta = llm.gerar_texto(INSTRUCOES_PLANEJADOR.format(max_etapas=MAX_ETAPAS), f"Negócio: {negocio}\nPedido: {pedido}")
    etapas = []
    for linha in resposta.splitlines():
        item = re.match(r"^\s*(?:\d+[.)]|[-*•])\s+(.+)$", linha)
        if item and len(item.group(1).strip()) > 3:
            etapas.append(item.group(1).strip().strip("*"))
    return etapas[:MAX_ETAPAS] or list(ETAPAS_PADRAO)


def executar_plano(agente, pedido: str, etapas: list[str]):
    """Executa uma etapa por vez e devolve (via yield) as seções prontas, para a interface mostrar o progresso."""
    secoes: list[Secao] = []
    for etapa in etapas:
        anteriores = "\n".join(f"- {s.titulo}: {s.texto[:300]}…" for s in secoes) or "(nenhuma)"
        resultado = agente.responder(PEDIDO_ETAPA.format(pedido=pedido, etapa=etapa, anteriores=anteriores))
        secoes.append(Secao(_titulo(etapa), resultado.resposta, resultado.ferramentas_usadas, resultado.interrompido))
        yield secoes


def montar_documento(llm, pedido: str, secoes: list[Secao]) -> str:
    corpo = "\n\n".join(f"## {s.titulo}\n\n{s.texto}" for s in secoes)
    sumario = llm.gerar_texto(INSTRUCOES_SUMARIO, corpo[:30000])
    return f"# {pedido}\n\n## Sumário executivo\n\n{sumario}\n\n{corpo}\n"


def documento_parcial(pedido: str, secoes: list[Secao], total: int) -> str:
    corpo = "\n\n".join(f"## {s.titulo}\n\n{s.texto}" for s in secoes)
    return f"# {pedido}\n\n_Etapa {len(secoes)} de {total} concluída…_\n\n{corpo}"


def bastidores(etapas: list[str], secoes: list[Secao]) -> str:
    linhas = []
    for i, etapa in enumerate(etapas, 1):
        if i <= len(secoes):
            s = secoes[i - 1]
            usadas = ", ".join(s.ferramentas) or "nenhuma ferramenta"
            aviso = " (consolidada no limite de passos)" if s.interrompida else ""
            linhas.append(f"{i}. **{_titulo(etapa)}**: {usadas}{aviso}")
        else:
            linhas.append(f"{i}. {_titulo(etapa)}: aguardando")
    return "\n".join(linhas)


def _titulo(etapa: str) -> str:
    return etapa.split(":", 1)[0].strip()
