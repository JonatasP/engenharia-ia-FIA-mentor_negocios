from mentor.kb import BaseConhecimento, dividir


def test_divide_por_titulos_markdown():
    texto = "# Produto\n\n## Cliente e problema\nMotoristas sem recarga.\n\n## Como funciona\nReserva de horário."
    trechos = dividir("pr.md", texto)
    assert [t.secao for t in trechos] == ["Produto › Cliente e problema", "Produto › Como funciona"]
    assert trechos[0].referencia == "pr.md › Produto › Cliente e problema"


def test_divide_secoes_longas_com_sobreposicao():
    texto = "## Seção\n" + " ".join(f"Frase número {i}." for i in range(300))
    trechos = dividir("longo.md", texto, tamanho=500, sobreposicao=100)
    assert len(trechos) > 1
    assert all(len(t.texto) <= 500 for t in trechos)


def test_kb_do_repositorio_carrega_e_busca(kb):
    assert len(kb) > 0
    trecho, _ = kb.buscar("como o motorista faz a reserva do carregador", k=1)[0]
    assert "plugsmart" in trecho.arquivo


def test_combinar_soma_os_trechos(kb, llm, tmp_path):
    arquivo = tmp_path / "notas.md"
    arquivo.write_text("## Pesquisa\nEntrevistamos 20 motoristas.", encoding="utf-8")
    combinada = kb.combinar(BaseConhecimento.de_arquivos(llm, [arquivo]))
    assert len(combinada) == len(kb) + 1
    assert "notas.md" in combinada.documentos()
