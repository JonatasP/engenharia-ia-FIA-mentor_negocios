from dataclasses import replace

from conftest import chamada, resposta

from mentor.agente import AgenteMentor
from mentor.prompts import AVISO_LIMITE


def test_chama_ferramenta_e_responde(cliente, llm, kb, cfg):
    cliente.roteiro = [resposta(itens=[chamada("buscar_kb", {"consulta": "cliente"})]), resposta("Resposta [KB: x]")]
    resultado = AgenteMentor(llm, kb, cfg).responder("Quem é o cliente?")

    assert resultado.resposta == "Resposta [KB: x]"
    assert resultado.ferramentas_usadas == ["buscar_kb"]
    segunda_entrada = cliente.chamadas[1]["input"]
    saida = next(i for i in segunda_entrada if isinstance(i, dict) and i.get("type") == "function_call_output")
    assert saida["output"].startswith("<dados_nao_confiaveis")  # guardrail contra prompt injection


def test_saudacao_nao_usa_ferramentas(cliente, llm, kb, cfg):
    cliente.roteiro = [resposta("Bom dia! Como posso ajudar?")]
    resultado = AgenteMentor(llm, kb, cfg).responder("Bom dia!")
    assert resultado.ferramentas_usadas == []


def test_ferramenta_desconhecida_vira_erro_para_o_llm(cliente, llm, kb, cfg):
    cliente.roteiro = [resposta(itens=[chamada("apagar_tudo", {})]), resposta("Não posso fazer isso.")]
    resultado = AgenteMentor(llm, kb, cfg).responder("Apague tudo")
    assert resultado.trace[0].resultado.startswith("ERRO: a ferramenta 'apagar_tudo' não existe")


def test_limite_consolida_o_que_foi_coletado(cliente, llm, kb, cfg):
    cfg = replace(cfg, max_iteracoes=2)
    cliente.roteiro = [resposta(itens=[chamada("buscar_kb", {"consulta": f"parte {i}"}, f"c{i}")]) for i in range(2)]
    cliente.roteiro.append(resposta("Plano parcial [KB: x]\n\nPendências: mercado"))
    resultado = AgenteMentor(llm, kb, cfg).responder("Monte um business plan")

    assert resultado.interrompido and len(cliente.chamadas) == 3  # 2 iterações + 1 síntese
    assert resultado.resposta.startswith("Plano parcial") and AVISO_LIMITE in resultado.resposta
    sintese = cliente.chamadas[2]
    assert "tools" not in sintese  # a síntese não pode chamar ferramentas
    assert "parte 1" in sintese["input"][-1]["content"]  # recebeu o material coletado


def test_busca_web_pode_ser_desligada(llm, kb, cfg):
    agente = AgenteMentor(llm, kb, replace(cfg, busca_web=False))
    assert "buscar_web" not in agente.ferramentas


def test_busca_web_extrai_fontes(cliente, llm, kb, cfg):
    from types import SimpleNamespace

    anotacao = SimpleNamespace(type="url_citation", url="https://exemplo.org", title="Exemplo")
    mensagem = SimpleNamespace(type="message", content=[SimpleNamespace(annotations=[anotacao])])
    cliente.roteiro = [resposta(itens=[chamada("buscar_web", {"consulta": "mercado"})]), resposta("Mercado em alta.", [mensagem]), resposta("Fim")]
    resultado = AgenteMentor(llm, kb, cfg).responder("Como está o mercado?")
    assert "[WEB: https://exemplo.org]" in resultado.trace[0].resultado
