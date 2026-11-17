"""Agente mentor: o loop ReAct com tool calling, sem framework.

    pensar (LLM) → agir (ferramenta) → observar (resultado) → ... → resposta final

O LLM decide o fluxo; o código só executa as ferramentas e aplica os limites.
"""

import json
import time
from dataclasses import dataclass, field

from mentor.guardrails import Limites
from mentor.prompts import AVISO_LIMITE, PEDIDO_SINTESE, instrucoes_mentor
from mentor.tools import criar_ferramentas, executar_ferramenta

LIMITE_COLETADO = 24000  # caracteres de resultados de ferramentas enviados na síntese


@dataclass
class Passo:
    ferramenta: str
    argumentos: dict
    resultado: str
    segundos: float


@dataclass
class Resultado:
    resposta: str
    trace: list[Passo] = field(default_factory=list)
    interrompido: bool = False

    @property
    def ferramentas_usadas(self) -> list[str]:
        return [p.ferramenta for p in self.trace]

    def trace_markdown(self) -> str:
        if not self.trace:
            return "Nenhuma ferramenta foi chamada nesta resposta."
        linhas = []
        for i, p in enumerate(self.trace, 1):
            previa = p.resultado[:300].replace("\n", " ")
            linhas.append(f"**{i}. `{p.ferramenta}`** {json.dumps(p.argumentos, ensure_ascii=False)} — {p.segundos:.1f}s\n> {previa}…")
        if self.interrompido:
            linhas.append("**Interrompido pelo limite de iterações ou de tempo.**")
        return "\n\n".join(linhas)


class AgenteMentor:
    def __init__(self, llm, kb, cfg):
        self.llm = llm
        self.cfg = cfg
        self.instrucoes = instrucoes_mentor(cfg)
        self.ferramentas = criar_ferramentas(kb, llm, cfg)
        self.schemas = [f.schema() for f in self.ferramentas.values()]

    def responder(self, pergunta: str, historico: list[dict] | None = None) -> Resultado:
        """`historico` é a memória de curto prazo: mensagens anteriores {role, content}."""
        itens = list(historico or []) + [{"role": "user", "content": pergunta}]
        limites = Limites(self.cfg.max_iteracoes, self.cfg.timeout_segundos)
        trace: list[Passo] = []
-
        iteracao = 0
        while not limites.esgotado(iteracao):
            iteracao += 1
            resposta = self.llm.responder(self.instrucoes, itens, self.schemas)
            chamadas = [item for item in resposta.output if item.type == "function_call"]
            if not chamadas:
                return Resultado(resposta.output_text, trace)

            itens.extend(resposta.output)  # o modelo precisa ver as próprias chamadas
            for chamada in chamadas:
                inicio = time.monotonic()
                saida = executar_ferramenta(self.ferramentas, chamada.name, chamada.arguments)
                trace.append(Passo(chamada.name, _argumentos(chamada.arguments), saida, time.monotonic() - inicio))
                itens.append({"type": "function_call_output", "call_id": chamada.call_id, "output": saida})

        # Limite atingido: em vez de descartar o que foi coletado, consolida uma resposta sem novas ferramentas.
        return Resultado(f"{self._sintetizar(pergunta, historico, trace)}\n\n{AVISO_LIMITE}", trace, interrompido=True)

    def _sintetizar(self, pergunta: str, historico: list[dict] | None, trace: list["Passo"]) -> str:
        coletado = "\n\n".join(
            f"### {p.ferramenta} {json.dumps(p.argumentos, ensure_ascii=False)}\n{p.resultado}" for p in trace
        )[:LIMITE_COLETADO]
        pedido = PEDIDO_SINTESE.format(pergunta=pergunta, coletado=coletado or "(nada foi coletado)")
        return self.llm.gerar_texto(self.instrucoes, list(historico or []) + [{"role": "user", "content": pedido}])


def _argumentos(argumentos_json: str) -> dict:
    try:
        return json.loads(argumentos_json or "{}")
    except json.JSONDecodeError:
        return {"bruto": argumentos_json}
