"""Base de conhecimento (KB) do grupo: leitura, divisão em trechos, embeddings e busca.

A busca é por similaridade de cosseno em memória (numpy). Para uma KB de dezenas de
documentos isso é suficiente e dispensa um banco vetorial.
"""

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

EXTENSOES = {".md", ".txt", ".pdf"}
TITULO_MD = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


@dataclass(frozen=True)
class Trecho:
    arquivo: str
    secao: str
    texto: str

    @property
    def referencia(self) -> str:
        return f"{self.arquivo} › {self.secao}" if self.secao else self.arquivo


def ler_documento(caminho: Path) -> str:
    if caminho.suffix.lower() == ".pdf":
        from pypdf import PdfReader

        return "\n\n".join(pagina.extract_text() or "" for pagina in PdfReader(caminho).pages)
    return caminho.read_text(encoding="utf-8", errors="replace")


def dividir(arquivo: str, texto: str, tamanho: int = 1200, sobreposicao: int = 200) -> list[Trecho]:
    """Divide primeiro pelos títulos Markdown e depois por tamanho, com sobreposição."""
    trechos, caminho_titulos, linhas = [], [], []

    def fechar_secao():
        conteudo = "\n".join(linhas).strip()
        if conteudo:
            secao = " › ".join(caminho_titulos[-2:])
            trechos.extend(Trecho(arquivo, secao, parte) for parte in _janelas(conteudo, tamanho, sobreposicao))
        linhas.clear()

    for linha in texto.splitlines():
        titulo = TITULO_MD.match(linha)
        if titulo:
            fechar_secao()
            nivel = len(titulo.group(1))
            caminho_titulos[:] = caminho_titulos[: nivel - 1] + [titulo.group(2)]
        else:
            linhas.append(linha)
    fechar_secao()
    return trechos


def _janelas(texto: str, tamanho: int, sobreposicao: int) -> list[str]:
    if len(texto) <= tamanho:
        return [texto]
    partes, inicio = [], 0
    while inicio < len(texto):
        fim = min(inicio + tamanho, len(texto))
        if fim < len(texto):  # prefere cortar em fim de parágrafo ou de frase
            corte = max(texto.rfind("\n", inicio, fim), texto.rfind(". ", inicio, fim))
            if corte > inicio + tamanho // 2:
                fim = corte + 1
        partes.append(texto[inicio:fim].strip())
        if fim >= len(texto):
            break
        inicio = max(fim - sobreposicao, inicio + 1)
    return partes


class BaseConhecimento:
    def __init__(self, llm, trechos: list[Trecho], vetores: np.ndarray):
        self.llm = llm
        self.trechos = trechos
        self.vetores = vetores

    @classmethod
    def de_arquivos(cls, llm, caminhos) -> "BaseConhecimento":
        trechos = []
        for caminho in map(Path, caminhos):
            if caminho.suffix.lower() in EXTENSOES and not caminho.name.startswith("."):
                trechos.extend(dividir(caminho.name, ler_documento(caminho)))
        vetores = llm.embeddings([f"{t.referencia}\n{t.texto}" for t in trechos])
        return cls(llm, trechos, vetores)

    @classmethod
    def de_pasta(cls, llm, pasta: Path) -> "BaseConhecimento":
        return cls.de_arquivos(llm, sorted(Path(pasta).rglob("*")))

    def combinar(self, outra: "BaseConhecimento") -> "BaseConhecimento":
        if not len(outra):
            return self
        if not len(self):
            return outra
        return BaseConhecimento(self.llm, self.trechos + outra.trechos, np.vstack([self.vetores, outra.vetores]))

    def buscar(self, consulta: str, k: int = 4) -> list[tuple[Trecho, float]]:
        if not self.trechos:
            return []
        consulta_vetor = self.llm.embeddings([consulta])[0]
        similaridades = self.vetores @ consulta_vetor
        melhores = np.argsort(-similaridades)[:k]
        return [(self.trechos[i], float(similaridades[i])) for i in melhores]

    def documentos(self) -> dict[str, int]:
        contagem: dict[str, int] = {}
        for trecho in self.trechos:
            contagem[trecho.arquivo] = contagem.get(trecho.arquivo, 0) + 1
        return contagem

    def __len__(self) -> int:
        return len(self.trechos)


def formatar_resultados(resultados: list[tuple[Trecho, float]]) -> str:
    """Texto entregue ao LLM: cada trecho com o rótulo que ele deve citar."""
    if not resultados:
        return "Nenhum trecho encontrado na base de conhecimento."
    return "\n\n".join(f"[KB: {t.referencia}] (similaridade {s:.2f})\n{t.texto}" for t, s in resultados)
