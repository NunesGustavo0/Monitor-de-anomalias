# SetupBox Dashboard + Monitor de Anomalias

Projeto IFAM / AxAcademy - Tarefa 02: Do Diagnóstico ao Monitor de Anomalias.

## Como executar

1. Instale as dependências:

```bash
pip install -r requirements.txt
```

2. Rode o monitor automático:

```bash
python monitor.py
```

O monitor vigia a pasta `logs/`, processa arquivos novos e gera saídas em `outputs/`.

3. Em outro terminal, rode o dashboard:

```bash
streamlit run app.py
```

4. Gere o relatório do monitor:

```bash
python report_monitor.py
```

## Pastas importantes

- `logs/`: coloque os arquivos novos de log.
- `outputs/`: alertas, auditoria, HITL e relatório.
- `docs/`: BPMN To-Be e PDD atualizado.

## Arquivos principais

- `monitor.py`: monitor automático.
- `rules.py`: regras de detecção de anomalias.
- `baseline.py`: cálculo do baseline estatístico.
- `alerts.py`: gravação dos alertas e envio opcional por Telegram.
- `audit.py`: trilha de auditoria.
- `hitl.py`: revisão humana.
- `report_monitor.py`: relatório do monitor.
- `app.py`: dashboard Streamlit com aba Monitor.

## Telegram opcional

Para ativar Telegram, defina no terminal:

```bash
set TELEGRAM_TOKEN=seu_token
set TELEGRAM_CHAT_ID=seu_chat_id
```

Se não configurar, o monitor funciona normalmente usando CSV.
