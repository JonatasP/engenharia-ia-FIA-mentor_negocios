import asyncio

import pytest

pytest.importorskip("mcp")

from mcp import Client  # noqa: E402

from mentor.mcp_server import criar_servidor  # noqa: E402


def test_servidor_mcp_expoe_e_executa_ferramentas(kb):
    async def cenario():
        async with Client(criar_servidor(kb)) as cliente:  # conexão em memória, sem subprocesso
            nomes = {t.name for t in (await cliente.list_tools()).tools}
            resultado = await cliente.call_tool("buscar_kb", {"consulta": "reserva de horário"})
            return nomes, resultado.content[0].text

    nomes, texto = asyncio.run(cenario())
    assert nomes == {"buscar_kb", "listar_documentos"}
    assert "[KB: plugsmart_recharge.md" in texto
