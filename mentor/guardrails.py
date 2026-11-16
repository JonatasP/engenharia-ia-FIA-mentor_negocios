"""Guardrails do agente (slide 26: riscos exclusivos de agentes).

- Prompt injection via ferramentas: toda saída de ferramenta é marcada como dado não confiável.
- Runaway loops: limite de iterações e de tempo por resposta.
- Excessive agency: só ferramentas da allowlist são executadas, e todas são de leitura.
"""

import time
from dataclasses import dataclass, field

MARCADOR = "dados_nao_confiaveis"
LIMITE_CARACTERES = 6000


def como_dado_nao_confiavel(fonte: str, conteudo: str) -> str:
    conteudo = conteudo.replace(f"</{MARCADOR}>", "")[:LIMITE_CARACTERES]
    return f'<{MARCADOR} fonte="{fonte}">\n{conteudo}\n</{MARCADOR}>'


@dataclass
class Limites:
    max_iteracoes: int
    timeout_segundos: float
    inicio: float = field(default_factory=time.monotonic)

    def esgotado(self, iteracao: int) -> bool:
        return iteracao >= self.max_iteracoes or time.monotonic() - self.inicio > self.timeout_segundos
