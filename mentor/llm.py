"""Único ponto de contato com a API da OpenAI.

Concentrar as chamadas aqui facilita trocar de provedor e testar o agente
sem rede (os testes substituem o `client` por um falso).
"""

import numpy as np

from mentor.prompts import INSTRUCOES_BUSCA_WEB


class LLM:
    def __init__(self, modelo: str, modelo_embeddings: str, client=None):
        if client is None:
            from openai import OpenAI

            client = OpenAI()  # lê OPENAI_API_KEY do ambiente
        self.client = client
        self.modelo = modelo
        self.modelo_embeddings = modelo_embeddings

    def responder(self, instrucoes: str, entrada, ferramentas: list[dict] | None = None):
        """Uma chamada à Responses API. `entrada` é um texto ou uma lista de itens."""
        parametros = {"model": self.modelo, "instructions": instrucoes, "input": entrada}
        if ferramentas:
            parametros["tools"] = ferramentas
        return self.client.responses.create(**parametros)

    def gerar_texto(self, instrucoes: str, entrada) -> str:
        """Resposta em texto, sem ferramentas. `entrada` é um texto ou uma lista de mensagens."""
        return self.responder(instrucoes, entrada).output_text

    def embeddings(self, textos: list[str]) -> np.ndarray:
        """Vetores normalizados: o produto escalar entre eles é a similaridade de cosseno."""
        if not textos:
            return np.zeros((0, 0), dtype=np.float32)
        vetores = []
        for inicio in range(0, len(textos), 100):
            lote = textos[inicio : inicio + 100]
            resposta = self.client.embeddings.create(model=self.modelo_embeddings, input=lote)
            vetores.extend(item.embedding for item in resposta.data)
        matriz = np.asarray(vetores, dtype=np.float32)
        normas = np.linalg.norm(matriz, axis=1, keepdims=True)
        return matriz / np.clip(normas, 1e-12, None)

    def pesquisar_web(self, consulta: str) -> tuple[str, list[dict]]:
        """Usa a ferramenta hospedada `web_search` e devolve o resumo e as fontes citadas."""
        resposta = self.responder(INSTRUCOES_BUSCA_WEB, consulta, ferramentas=[{"type": "web_search"}])
        fontes, vistas = [], set()
        for item in resposta.output:
            for parte in getattr(item, "content", None) or []:
                for anotacao in getattr(parte, "annotations", None) or []:
                    url = getattr(anotacao, "url", None)
                    if getattr(anotacao, "type", "") == "url_citation" and url not in vistas:
                        vistas.add(url)
                        fontes.append({"titulo": getattr(anotacao, "title", url), "url": url})
        return resposta.output_text, fontes
