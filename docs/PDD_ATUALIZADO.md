# PDD Atualizado - Monitor de Anomalias SetupBox

## Objetivo
Transformar o diagnóstico da Tarefa 01 em um monitor automático capaz de ingerir logs periodicamente, detectar anomalias assim que surgirem, classificar severidade, sugerir ação e registrar auditoria.

## Entradas
- Arquivos `.xlsx` ou `.csv` na pasta `logs/`.
- Planilha principal com aba `recordings`.
- Campos usados: `timestamp`, `line`, `station`, `jig_id`, `firmware_version`, `serial_number`, `mac_address`, `result`, `failed_step`, `error_code`, `total_cycle_s`.

## Janela móvel
- O monitor usa os últimos 100 registros de cada arquivo processado.
- A janela reduz ruído e permite alerta mais rápido do que análise de fim do dia.

## Baseline
- Para taxa de falha por jig, o baseline é calculado por média + 3 desvios-padrão da taxa de falha dos jigs na janela.
- Há limite mínimo de 5% para evitar alertas causados por janelas perfeitas ou pequenas.

## Regras de anomalia
1. Taxa alta de falha por Jig: volume mínimo de 20 tentativas e 3 falhas.
2. PPM alto por Firmware: PPM >= 50.000, mínimo de 30 tentativas e 2 falhas.
3. MAC duplicado: mesmo MAC em mais de um serial.
4. Drift de Cycle Time: média do jig acima de média + 3 desvios da janela.

## Separação entre outlier e anomalia sistemática
- O monitor exige volume mínimo de tentativas e falhas antes de alertar.
- Falhas isoladas são registradas no dashboard, mas não viram alerta crítico automaticamente.

## Severidades
- Média: desvio relevante, mas sem impacto imediato crítico.
- Alta: exige ação e revisão humana.
- Crítica: risco direto ao processo, provisionamento ou lote.

## Runbook
| Tipo | Severidade | Ação sugerida |
|---|---|---|
| Falha alta por Jig | Alta/Crítica | Verificar jig, parar se crítico e abrir manutenção |
| PPM alto por Firmware | Alta/Crítica | Bloquear lote e investigar firmware |
| MAC duplicado | Crítica | Revisar provisionamento imediatamente |
| Drift de Cycle Time | Média | Verificar gargalo, equipamento e operador |

## HITL
- Casos Alta ou Crítica são enviados para `outputs/hitl_pendentes.csv`.
- O humano deve aprovar, rejeitar ou comentar a ação.

## Auditoria
- Todo alerta é registrado em `outputs/auditoria_alertas.csv`.
- Os alertas emitidos ficam em `outputs/alerts.csv`.
- Arquivos já processados ficam em `outputs/processados.txt`.

## Saídas
- Alertas estruturados.
- Trilha de auditoria.
- Casos HITL.
- Relatório do monitor em Markdown.
- Aba visual no dashboard Streamlit.
