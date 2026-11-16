import pytest
from conftest import resposta

pytest.importorskip("langgraph")

from mentor.agente import AgenteMentor  # noqa: E402
from mentor.equipe import criar_equipe, executar_equipe  # noqa: E402


def test_revisao_ate_aprovar(cliente, llm, kb, cfg):
    cliente.roteiro = [
        resposta("pesquisa"),  # pesquisador (sub-agente, sem ferramentas)
        resposta("v1"),  # redator
        resposta("AJUSTES\n- melhorar título"),  # revisor
        resposta("v2"),  # redator
        resposta("APROVADO"),  # revisor
    ]
    estado = executar_equipe(criar_equipe(AgenteMentor(llm, kb, cfg), llm, max_revisoes=3), "press release")
    assert estado["rascunho"] == "v2" and estado["aprovado"] and estado["rodada"] == 2


def test_limite_de_revisoes(cliente, llm, kb, cfg):
    cliente.roteiro = [resposta("pesquisa")] + [resposta(t) for t in ["v1", "AJUSTES", "v2", "AJUSTES"]]
    estado = executar_equipe(criar_equipe(AgenteMentor(llm, kb, cfg), llm, max_revisoes=2), "press release")
    assert not estado["aprovado"] and estado["rodada"] == 2


def test_feedback_humano_reaproveita_pesquisa(cliente, llm, kb, cfg):
    anterior = {"pedido": "pr", "pesquisa": "pesquisa", "rascunho": "v1"}
    cliente.roteiro = [resposta("v2"), resposta("APROVADO")]
    estado = executar_equipe(criar_equipe(AgenteMentor(llm, kb, cfg), llm, 3), "pr", anterior, "foco em frotas")
    assert estado["rascunho"] == "v2"
    assert "foco em frotas" in cliente.chamadas[0]["input"]  # o redator recebeu o ajuste do grupo
