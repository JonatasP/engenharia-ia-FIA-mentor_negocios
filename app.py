"""Interface web do Mentor de Negócios (Gradio), publicada no Render.

Abas:
1. Mentor: conversa com o agente, com o trace das ferramentas usadas.
2. Press release: equipe de agentes pesquisador → redator → revisor, com ajustes do grupo (human-in-the-loop).
3. Plano de negócio: Plan-and-Execute para trabalhos amplos, executados em etapas.
4. Base de conhecimento: documentos do repositório e envio temporário de arquivos.
"""

import os
import sys
import tempfile
from pathlib import Path

import gradio as gr

from mentor.agente import AgenteMentor
from mentor.config import carregar_config
from mentor.equipe import acompanhar_equipe, criar_equipe, proxima_etapa
from mentor.kb import BaseConhecimento
from mentor.llm import LLM
from mentor import plano

if not os.getenv("OPENAI_API_KEY"):
    sys.exit("Defina a variável de ambiente OPENAI_API_KEY (arquivo .env local ou painel do Render).")

cfg = carregar_config()
llm = LLM(cfg.modelo, cfg.modelo_embeddings)
kb_repositorio = BaseConhecimento.de_pasta(llm, cfg.pasta_kb)  # persistente: vem do GitHub


def kb_atual(kb_sessao):
    return kb_sessao or kb_repositorio


def _texto(conteudo) -> str:
    if isinstance(conteudo, str):
        return conteudo
    if isinstance(conteudo, list):
        return " ".join(p.get("text", "") for p in conteudo if isinstance(p, dict))
    return str(conteudo)


# ---------- Aba 1: Mentor ----------
def conversar(mensagem, historico, kb_sessao):
    if not mensagem.strip():
        return historico, "", gr.update()
    agente = AgenteMentor(llm, kb_atual(kb_sessao), cfg)
    memoria = [{"role": m["role"], "content": _texto(m["content"])} for m in historico]
    resultado = agente.responder(mensagem, memoria)
    historico = historico + [
        {"role": "user", "content": mensagem},
        {"role": "assistant", "content": resultado.resposta},
    ]
    return historico, "", resultado.trace_markdown()


# ---------- Aba 2: Press release ----------
def _bastidores_equipe(estado) -> str:
    texto = "\n".join(f"- {e}" for e in estado.get("historico", [])) or "- (nenhuma etapa concluída ainda)"
    if estado.get("parecer"):
        texto += f"\n\n**Último parecer do revisor:**\n\n{estado['parecer']}"
    return texto


def _rodar_equipe(pedido, kb_sessao, anterior=None, feedback=""):
    """Gerador: atualiza a tela após cada nó do grafo (pesquisador, redator, revisor)."""
    equipe = criar_equipe(AgenteMentor(llm, kb_atual(kb_sessao), cfg), llm, cfg.max_revisoes)
    estado = None
    for estado in acompanhar_equipe(equipe, pedido, anterior, feedback):
        status = f"**Em andamento.** {proxima_etapa(estado, cfg.max_revisoes)} O processo leva de 1 a 3 minutos."
        yield status, estado.get("rascunho", ""), _bastidores_equipe(estado), anterior

    if estado.get("aprovado"):
        status = f"**Concluído:** aprovado pelo revisor na rodada {estado['rodada']}."
    else:
        status = "**Concluído:** limite de rodadas atingido. Veja os ajustes pendentes nos bastidores."
    yield status, estado.get("rascunho", ""), _bastidores_equipe(estado), estado


def gerar_press_release(pedido, kb_sessao):
    if not pedido.strip():
        raise gr.Error("Descreva o que a equipe de agentes deve escrever.")
    yield from _rodar_equipe(pedido, kb_sessao)


def revisar_press_release(feedback, estado, kb_sessao):
    if not estado:
        raise gr.Error("Gere um press release primeiro.")
    if not feedback.strip():
        raise gr.Error("Escreva os ajustes desejados.")
    yield from _rodar_equipe(estado["pedido"], kb_sessao, anterior=estado, feedback=feedback)


# ---------- Aba 3: Plano de negócio (Plan-and-Execute) ----------
def gerar_plano(pedido, kb_sessao):
    if not pedido.strip():
        raise gr.Error("Descreva o trabalho, por exemplo: Monte o plano de negócio do nosso projeto.")
    yield "", "**Em andamento.** O planejador está dividindo o trabalho em etapas.", None
    agente = AgenteMentor(llm, kb_atual(kb_sessao), cfg)
    etapas = plano.planejar(llm, pedido, cfg.negocio)
    yield f"Plano definido em {len(etapas)} etapas. Executando a etapa 1…", plano.bastidores(etapas, []), None

    secoes = []
    for secoes in plano.executar_plano(agente, pedido, etapas):
        yield plano.documento_parcial(pedido, secoes, len(etapas)), plano.bastidores(etapas, secoes), None

    documento = plano.montar_documento(llm, pedido, secoes)
    with tempfile.NamedTemporaryFile("w", suffix=".md", prefix="plano_", delete=False, encoding="utf-8") as arquivo:
        arquivo.write(documento)
    yield documento, plano.bastidores(etapas, secoes), arquivo.name


# ---------- Aba 4: Base de conhecimento ----------
def descrever_kb(kb_sessao) -> str:
    kb = kb_atual(kb_sessao)
    linhas = [f"- `{nome}`: {qtd} trecho(s)" for nome, qtd in kb.documentos().items()] or ["- (vazia)"]
    origem = "repositório + arquivos enviados nesta sessão" if kb_sessao else "repositório (pasta kb/)"
    return f"**Origem:** {origem}\n\n" + "\n".join(linhas)


def adicionar_arquivos(arquivos, kb_sessao):
    if not arquivos:
        raise gr.Error("Selecione ao menos um arquivo .md, .txt ou .pdf.")
    caminhos = [Path(getattr(a, "name", a)) for a in arquivos]
    novos = BaseConhecimento.de_arquivos(llm, caminhos)
    kb_sessao = kb_atual(kb_sessao).combinar(novos)
    return kb_sessao, descrever_kb(kb_sessao)


def limpar_sessao():
    return None, descrever_kb(None)


with gr.Blocks(title=f"Mentor de Negócios — {cfg.negocio}") as demo:
    kb_sessao = gr.State(None)
    estado_equipe = gr.State(None)

    gr.Markdown(f"# Mentor de Negócios — {cfg.negocio}\n{cfg.grupo} · modelo `{cfg.modelo}`")

    with gr.Tab("Mentor"):
        chat = gr.Chatbot(type="messages", height=480, label="Conversa")
        entrada = gr.Textbox(placeholder="Pergunte sobre o negócio, peça críticas, pesquisa de mercado ou um FAQ…", label="Mensagem")
        enviar = gr.Button("Enviar", variant="primary")
        with gr.Accordion("Trace das ferramentas", open=False):
            trace = gr.Markdown()
        enviar.click(conversar, [entrada, chat, kb_sessao], [chat, entrada, trace])
        entrada.submit(conversar, [entrada, chat, kb_sessao], [chat, entrada, trace])

    with gr.Tab("Press release"):
        pedido = gr.Textbox(lines=3, label="Pedido para a equipe de agentes", placeholder="Ex.: Escreva o press release de uma nova linha de serviço para frotas corporativas.")
        gerar = gr.Button("Gerar com a equipe de agentes", variant="primary")
        status_equipe = gr.Markdown()
        with gr.Accordion("Bastidores da equipe de agentes", open=True):
            bastidores_equipe = gr.Markdown()
        press_release = gr.Markdown()
        feedback = gr.Textbox(lines=2, label="Ajustes do grupo (human-in-the-loop)")
        revisar = gr.Button("Gerar nova versão com os ajustes")
        saidas_equipe = [status_equipe, press_release, bastidores_equipe, estado_equipe]
        gerar.click(gerar_press_release, [pedido, kb_sessao], saidas_equipe)
        revisar.click(revisar_press_release, [feedback, estado_equipe, kb_sessao], saidas_equipe)

    with gr.Tab("Plano de negócio"):
        gr.Markdown(
            "Para trabalhos amplos: o planejador divide o pedido em etapas e o agente executa uma por vez, "
            "com pesquisa própria em cada uma. Leva alguns minutos."
        )
        pedido_plano = gr.Textbox(lines=2, label="Trabalho", value="Monte o plano de negócio do nosso projeto")
        gerar_plano_btn = gr.Button("Gerar em etapas", variant="primary")
        with gr.Accordion("Etapas e ferramentas usadas", open=True):
            etapas_plano = gr.Markdown()
        documento_plano = gr.Markdown()
        download_plano = gr.File(label="Baixar em Markdown (para revisar e colocar em kb/)")
        gerar_plano_btn.click(gerar_plano, [pedido_plano, kb_sessao], [documento_plano, etapas_plano, download_plano])

    with gr.Tab("Base de conhecimento"):
        resumo_kb = gr.Markdown(descrever_kb(None))
        gr.Markdown(
            "Arquivos enviados aqui valem **só para esta sessão** e se perdem quando o serviço reinicia. "
            "Para mantê-los, adicione-os à pasta `kb/` do repositório e faça push no GitHub."
        )
        arquivos = gr.File(file_count="multiple", file_types=[".md", ".txt", ".pdf"], label="Documentos")
        with gr.Row():
            adicionar = gr.Button("Adicionar à sessão", variant="primary")
            limpar = gr.Button("Voltar só para o repositório")
        adicionar.click(adicionar_arquivos, [arquivos, kb_sessao], [kb_sessao, resumo_kb])
        limpar.click(limpar_sessao, None, [kb_sessao, resumo_kb])


if __name__ == "__main__":
    senha = os.getenv("APP_SENHA")
    demo.queue(default_concurrency_limit=4)  # integrantes do grupo usam o app ao mesmo tempo
    demo.launch(
        server_name="0.0.0.0",
        server_port=int(os.getenv("PORT", "7860")),  # o Render define PORT
        auth=(os.getenv("APP_USUARIO", "grupo"), senha) if senha else None,
        show_error=True,  # mostra a mensagem de erro na tela, em vez de só "Error"
    )
