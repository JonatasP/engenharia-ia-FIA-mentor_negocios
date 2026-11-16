"""Ferramentas do agente (tool calling).

Cada ferramenta tem três partes: nome, descrição e schema JSON dos parâmetros (o que o
LLM vê) e a função Python (o que o sistema executa). O LLM decide QUANDO chamar e COM
QUAIS argumentos; quem executa é sempre o nosso código.
"""

import json
from dataclasses import dataclass
from typing import Callable

from mentor.guardrails import como_dado_nao_confiavel
from mentor.kb import formatar_resultados
from mentor.prompts import MODELO_PRESS_RELEASE


@dataclass(frozen=True)
class Ferramenta:
    nome: str
    descricao: str
    parametros: dict
    funcao: Callable[..., str]

    def schema(self) -> dict:
        """Formato de function calling da Responses API."""
        return {"type": "function", "name": self.nome, "description": self.descricao, "parameters": self.parametros}


def _sem_parametros() -> dict:
    return {"type": "object", "properties": {}, "required": []}


def criar_ferramentas(kb, llm, cfg) -> dict[str, Ferramenta]:
    def listar_documentos() -> str:
        documentos = kb.documentos()
        if not documentos:
            return "A base de conhecimento está vazia."
        return "\n".join(f"- {nome}: {qtd} trecho(s)" for nome, qtd in documentos.items())

    def buscar_kb(consulta: str, k: int = 4) -> str:
        resultados = kb.buscar(consulta, k=max(1, min(int(k), 8)))
        return como_dado_nao_confiavel("base de conhecimento", formatar_resultados(resultados))

    def buscar_web(consulta: str) -> str:
        texto, fontes = llm.pesquisar_web(consulta)
        rotulos = "\n".join(f"[WEB: {f['url']}] {f['titulo']}" for f in fontes) or "(sem fontes retornadas)"
        return como_dado_nao_confiavel("internet", f"{texto}\n\nFontes:\n{rotulos}")

    def modelo_press_release() -> str:
        return MODELO_PRESS_RELEASE

    ferramentas = [
        Ferramenta(
            "listar_documentos",
            "Lista os documentos que o grupo carregou na base de conhecimento.",
            _sem_parametros(),
            listar_documentos,
        ),
        Ferramenta(
            "buscar_kb",
            "Busca trechos relevantes nos documentos do grupo (press release, notas, pesquisas).",
            {
                "type": "object",
                "properties": {
                    "consulta": {"type": "string", "description": "O que procurar, em linguagem natural."},
                    "k": {"type": "integer", "description": "Quantidade de trechos (1 a 8).", "default": 4},
                },
                "required": ["consulta"],
            },
            buscar_kb,
        ),
        Ferramenta(
            "modelo_press_release",
            "Retorna o modelo de press release em 8 seções e as perguntas de verificação.",
            _sem_parametros(),
            modelo_press_release,
        ),
    ]
    if cfg.busca_web:
        ferramentas.append(
            Ferramenta(
                "buscar_web",
                "Pesquisa na internet contexto de mercado: concorrentes, regulação, tendências, números do setor.",
                {
                    "type": "object",
                    "properties": {"consulta": {"type": "string", "description": "Pergunta objetiva para a busca."}},
                    "required": ["consulta"],
                },
                buscar_web,
            )
        )
    return {f.nome: f for f in ferramentas}


def executar_ferramenta(ferramentas: dict[str, Ferramenta], nome: str, argumentos_json: str) -> str:
    """Executa só o que está na allowlist e devolve erros como texto, para o LLM se corrigir."""
    ferramenta = ferramentas.get(nome)
    if ferramenta is None:
        return f"ERRO: a ferramenta '{nome}' não existe. Disponíveis: {', '.join(ferramentas)}."
    try:
        argumentos = json.loads(argumentos_json or "{}")
        return ferramenta.funcao(**argumentos)
    except (json.JSONDecodeError, TypeError) as erro:
        return f"ERRO: argumentos inválidos para '{nome}': {erro}"
    except Exception as erro:  # falha da ferramenta não derruba o agente
        return f"ERRO ao executar '{nome}': {erro}"
