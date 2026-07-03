# Dashboard de Anomalias de Gravação - IFAM / AxAcademy

## Integrantes
- Carlos Eduardo de Souza da Silva
- Gustavo Nunes de Oliveira
- Raquel Andrade da Gama

## Como executar
1. Coloque o arquivo `recording_test_setupbox.xlsx` na mesma pasta do `app.py`.
2. Instale as dependências:

```bash
python3 venv .venv
source .venv/bin/activate
python3 install pip
pip install -r requirements.txt
```

3. Execute o dashboard:

```bash
streamlit run app.py
```

## Entregáveis incluídos
- `app.py`: dashboard em Streamlit, somente leitura.
- `recording_test_setupbox.xlsx`: dataset usado pelo dashboard.
- `requirements.txt`: bibliotecas necessárias.
- `relatorio_achados.md`: relatório inicial exportado com BPMN, PDD e achados principais.

No dashboard há filtros por linha, estação, jig, modelo, firmware, turno, erro, disposition e data. A aba de auditoria permite exportar CSV filtrado e baixar relatório em Markdown.
