"""Servidor MCP que expõe a base de conhecimento do grupo (slide 20).

Qualquer host compatível com MCP (Claude Desktop, Cursor, um script próprio) pode usar
estas ferramentas sem conhecer o código do projeto.

Executar (transporte stdio):  python -m mentor.mcp_server
Requer o pacote `mcp` 2.x (requirements-aula.txt).
"""

from mcp.server.mcpserver import MCPServer

from mentor.kb import formatar_resultados


def criar_servidor(kb, nome: str = "kb-do-grupo") -> MCPServer:
    servidor = MCPServer(name=nome, instructions="Ferramentas de consulta à base de conhecimento do grupo.")

    @servidor.tool(description="Busca trechos relevantes nos documentos do grupo.")
    def buscar_kb(consulta: str, k: int = 4) -> str:
        return formatar_resultados(kb.buscar(consulta, k=max(1, min(k, 8))))

    @servidor.tool(description="Lista os documentos da base de conhecimento.")
    def listar_documentos() -> str:
        return "\n".join(f"- {nome}: {qtd} trecho(s)" for nome, qtd in kb.documentos().items()) or "Base vazia."

    return servidor


if __name__ == "__main__":
    from mentor.config import carregar_config
    from mentor.kb import BaseConhecimento
    from mentor.llm import LLM

    cfg = carregar_config()
    kb = BaseConhecimento.de_pasta(LLM(cfg.modelo, cfg.modelo_embeddings), cfg.pasta_kb)
    criar_servidor(kb).run()  # stdio: nada pode ser impresso no stdout
