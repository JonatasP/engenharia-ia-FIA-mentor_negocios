from conftest import chamada, resposta

from mentor import plano
from mentor.agente import AgenteMentor


def test_planejador_le_lista_numerada(cliente, llm):
    cliente.roteiro = [resposta("Segue o plano:\n1. Mercado: tamanho e concorrentes\n2) Receita: modelos de preço\n- Riscos: regulação")]
    assert plano.planejar(llm, "business plan", "PlugSmart") == [
        "Mercado: tamanho e concorrentes",
        "Receita: modelos de preço",
        "Riscos: regulação",
    ]


def test_planejador_fora_do_formato_usa_plano_padrao(cliente, llm):
    cliente.roteiro = [resposta("Não sei.")]
    assert plano.planejar(llm, "business plan", "PlugSmart") == plano.ETAPAS_PADRAO


def test_executa_uma_etapa_por_vez_e_monta_documento(cliente, llm, kb, cfg):
    etapas = ["Mercado: concorrentes", "Receita: preço"]
    cliente.roteiro = [
        resposta(itens=[chamada("buscar_kb", {"consulta": "mercado"})]),
        resposta("Texto do mercado [KB: x]"),
        resposta("Texto da receita"),
        resposta("Sumário do plano"),
    ]
    agente = AgenteMentor(llm, kb, cfg)
    secoes = list(plano.executar_plano(agente, "Plano de negócio", etapas))[-1]
    documento = plano.montar_documento(llm, "Plano de negócio", secoes)

    assert [s.titulo for s in secoes] == ["Mercado", "Receita"]
    assert secoes[0].ferramentas == ["buscar_kb"]
    assert "Texto do mercado" in cliente.chamadas[2]["input"][-1]["content"]  # a etapa 2 vê a etapa 1
    assert documento.startswith("# Plano de negócio\n\n## Sumário executivo\n\nSumário do plano")
    assert "## Receita\n\nTexto da receita" in documento
    assert "Mercado**: buscar_kb" in plano.bastidores(etapas, secoes)
