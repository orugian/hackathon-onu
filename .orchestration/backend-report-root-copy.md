# Relatório de Execução do Backend (BACKEND-01 — Rodada 1/3)

## Escopo e Contrato
Implementação em Python standard library dos módulos `domain.py` e `calculations.py`, com suítes de teste `tests/test_domain.py` e `tests/test_calculations.py`.
Processo executado via TDD estritamente vertical: ciclo vermelho (RED) -> verde (GREEN) -> refatoração para cada comportamento, com registro de comandos e saídas.

## Ciclos de Desenvolvimento TDD

### Ciclo 1: calculations.weigh - caso compatível
- **Objetivo**: Testar pesagem compatível com 10 m³, bruto 20000 kg, tara 12000 kg => líquido 8000 kg dentro da faixa 6500–9500 kg, diferença 0 kg.
- **Teste adicionado**: `test_weigh_compatible` em `tests/test_calculations.py`.
- **Comando RED**: `python -m unittest tests/test_calculations.py`
  - **Saída**: `ModuleNotFoundError: No module named 'calculations'`
- **Implementação mínima**: Módulo `calculations.py` com cálculo de peso líquido, limites por densidade, status 'compatible' e diferença 0.
- **Comando GREEN**: `python -m unittest tests/test_calculations.py`
  - **Saída**: `Ran 1 test in 0.000s - OK`

### Ciclo 2: calculations.weigh - caso divergente
- **Objetivo**: Testar pesagem com divergência superior (25000 - 12000 = 13000 kg vs máx 9500 kg => divergente 3500 kg) e inferior (18000 - 12000 = 6000 kg vs mín 6500 kg => divergente 500 kg).
- **Teste adicionado**: `test_weigh_divergent` em `tests/test_calculations.py`.
- **Comando GREEN**: `python -m unittest tests/test_calculations.py`
  - **Saída**: `Ran 2 tests in 0.000s - OK`

### Ciclo 3: calculations.weigh - validações de entrada e DomainError
- **Objetivo**: Rejeitar booleans, NaN/Inf, valores não positivos, bruto <= tara, densidade mín <= 0 ou máx < mín, retornando `DomainError(code='validation_error', status=422)`.
- **Teste adicionado**: `test_weigh_invalid_inputs` em `tests/test_calculations.py`.
- **Comando RED**: `python -m unittest tests/test_calculations.py`
  - **Saída**: `ImportError: ModuleNotFoundError: No module named 'domain'`
- **Implementação mínima**: Criação de `domain.py` com classe `DomainError(message, code='validation_error', status=422)` e função `_validate_finite_number` em `calculations.py`.
- **Comando GREEN**: `python -m unittest tests/test_calculations.py`
  - **Saída**: `Ran 3 tests in 0.001s - OK`

### Ciclo 4: calculations.inventory - cálculo volumétrico e validação
- **Objetivo**: Implementar fórmula cilíndrica com fator de forma `pi*(dap/100)^2*H*f/4`, validando 60 cm, 15 m, 0.7 => 2.9688 m³; garantir que notice destaca "não modifica crédito"; rejeitar `f <= 0` ou `f > 1`, booleans, NaN e dimensões <= 0 com `DomainError`.
- **Teste adicionado**: `test_inventory` e `test_inventory_invalid_inputs` em `tests/test_calculations.py`.
- **Comando RED**: `python -m unittest tests/test_calculations.py`
  - **Saída**: `ImportError: cannot import name 'inventory' from 'calculations'`
- **Implementação mínima**: Função `inventory(diameter_cm, height_m, form_factor)` em `calculations.py`.
- **Comando GREEN**: `python -m unittest tests/test_calculations.py`
  - **Saída**: `Ran 5 tests in 0.001s - OK`

### Ciclo 5: domain.DomainError - estrutura e atributos de exceção
- **Objetivo**: Garantir que `DomainError` implementa `message`, `code` (padrão `'validation_error'`) e `status` (padrão 422), além de método de serialização.
- **Teste adicionado**: `test_domain_error_attributes` em `tests/test_domain.py`.
- **Comando GREEN**: `python -m unittest tests/test_domain.py`
  - **Saída**: `Ran 1 test in 0.000s - OK`

### Ciclo 6: domain.Ledger - inicialização, persistência e estado canônico
- **Objetivo**: Inicialização de SQLite local, criação do lote AM-DEMO-001 (opening_milli=15000, available_milli=15000, unidade m³, simulated=true), evento inicial `LOT_OPENED` com hash encadeado (previous_hash com 64 zeros), unicidade na reabertura e método `state()` com lots, shipments, assessments, events e integridade.
- **Testes adicionados**: `test_ledger_initialization_and_state` e `test_ledger_reopen_persists_without_duplication` em `tests/test_domain.py`.
- **Comando RED**: `python -m unittest tests/test_domain.py`
  - **Saída**: `ImportError: cannot import name 'Ledger' from 'domain'`
- **Implementação mínima**: Classe `Ledger` com controle explícito de transações (`BEGIN IMMEDIATE`), contextmanager `_connection` para liberação segura no Windows, tabelas SQLite e evento gênese.
- **Comando GREEN**: `python -m unittest tests/test_domain.py`
  - **Saída**: `Ran 3 tests in 0.036s - OK`

### Ciclo 7: domain.Ledger.reserve - validações de entrada e integridade pós-erro
- **Objetivo**: Validação rigorosa dos campos de `reserve`: rejeição de idempotency_key vazia ou > 128 chars, lot_id ausente/vazio, volume_m3 booleano, negativo, zero, NaN/Inf, > 1000000 ou com mais de 3 casas decimais, strings vazias ou > 200 caracteres, tara negativa, bruto <= tara, massas > 100000000. Confirmação de integridade inalterada (sem efeitos colaterais).
- **Teste adicionado**: `test_reserve_validation_errors_and_rollback` em `tests/test_domain.py`.
- **Comando RED**: `python -m unittest tests/test_domain.py`
  - **Saída**: `NotImplementedError: reserve()`
- **Implementação mínima**: Funções de validação `_validate_str`, `_validate_volume`, `_validate_mass` e pré-validação em `reserve`.
- **Comando GREEN**: `python -m unittest tests/test_domain.py`
  - **Saída**: `Ran 4 tests in 0.027s - OK`

### Ciclo 8: domain.Ledger.reserve - emissão de passaporte e integridade atômica
- **Objetivo**: Efetuar reserva de 10 m³ sobre saldo inicial de 15 m³; validar esquema completo do passaporte (`schema_version: '1.0.0'`, `balance_after_milli: 5000`, `event_id`, pesagem embutida, aviso de sem validade oficial, `simulated: true`); verificar cálculo e integridade do hash SHA-256 canônico; confirmar criação atômica do evento `SHIPMENT_RESERVED`.
- **Teste adicionado**: `test_reserve_successful_and_passport_structure` em `tests/test_domain.py`.
- **Comando RED**: `python -m unittest tests/test_domain.py`
  - **Saída**: `NotImplementedError: Validation passed, need execution`
- **Implementação mínima**: Lógica transacional atômica com `BEGIN IMMEDIATE`, dedução de saldo em milésimos inteiros, geração de passaporte imutável e evento encadeado.
- **Comando GREEN**: `python -m unittest tests/test_domain.py`
  - **Saída**: `Ran 5 tests in 0.049s - OK`

### Ciclo 9: domain.Ledger.reserve - sequencial 15/10/10 e precisão exata 3x0.1
- **Objetivo**: Verificar que sequência 15 m³ -> reserva 10 m³ é aceita (saldo 5000 milli) e segunda reserva 10 m³ é bloqueada com status 409 `insufficient_balance` sem débito e sem penalidade automática; verificar que 3 reservas de 0.1 m³ resultam estritamente em saldo 14700 milli (14.7 m³) sem desvios de ponto flutuante.
- **Testes adicionados**: `test_reserve_15_10_10_sequential` e `test_reserve_three_times_point_one_exact_milli` em `tests/test_domain.py`.
- **Comando GREEN**: `python -m unittest tests/test_domain.py`
  - **Saída**: `Ran 7 tests in 0.145s - OK`

## Rodada 2: Conclusão do Contrato de Execução

### Ciclo 10: calculations.weigh - inclusão de gross_kg e tare_kg numéricos
- **Objetivo**: Garantir que o resultado de `weigh` inclua os campos numéricos `gross_kg` e `tare_kg` além do peso líquido e faixas de densidade, conforme especificação de pesagem do passaporte.
- **Teste adicionado**: Atualização de `test_weigh_compatible` em `tests/test_calculations.py`.
- **Comando RED**: `python -m unittest tests/test_calculations.py`
  - **Saída**: `KeyError: 'gross_kg'`
- **Implementação mínima**: Inclusão de `"gross_kg"` e `"tare_kg"` no dicionário retornado por `weigh` em `calculations.py`.
- **Comando GREEN**: `python -m unittest tests/test_calculations.py`
  - **Saída**: `Ran 5 tests in 0.002s - OK`

### Ciclo 11: calculations.inventory - proteção contra OverflowError em entradas gigantes
- **Objetivo**: Impor limites físicos plausíveis explícitos (`max_val=100000`) em `diameter_cm` e `height_m`, retornando `DomainError(status=422)` para entradas finitas astronômicas (ex: `1e308`) em vez de estourar `OverflowError`.
- **Teste adicionado**: `test_inventory_huge_inputs_reject_overflow` em `tests/test_calculations.py`.
- **Comando RED**: `python -m unittest tests/test_calculations.py`
  - **Saída**: `OverflowError: (34, 'Result too large')`
- **Implementação mínima**: Adição de `max_val=100_000` na validação de `diameter_cm` e `height_m` em `calculations.py`.
- **Comando GREEN**: `python -m unittest tests/test_calculations.py`
  - **Saída**: `Ran 6 tests in 0.001s - OK`

### Ciclo 12: domain._validate_volume - correção de 'NaN' e entradas gigantes
- **Objetivo**: Evitar que strings como `'NaN'`, `'Infinity'` ou números gigantes causem `decimal.InvalidOperation` ou `OverflowError`. A validação `d.is_finite()` deve ser executada antes de qualquer comparação aritmética, e limites de tamanho em string/magnitude devem ser aplicados imediatamente.
- **Teste adicionado**: Caso de teste com strings `'NaN'`, `'nan'`, `'Infinity'`, `1e308` e strings gigantes em `test_reserve_validation_errors_and_rollback` em `tests/test_domain.py`.
- **Comando RED**: `python -m unittest tests/test_domain.py`
  - **Saída**: `decimal.InvalidOperation: [<class 'decimal.InvalidOperation'>]` na linha `if d <= Decimal(0):`
- **Implementação mínima**: Em `_validate_volume`, checar `len(s) > 50`, `not d.is_finite()` antes de comparações de desigualdade, e rejeitar valores gigantes com `DomainError(status=422)`.
- **Comando GREEN**: `python -m unittest tests/test_domain.py`
  - **Saída**: `Ran 7 tests in 0.083s - OK`

### Ciclo 13: domain.Ledger.passport - recuperação de passaporte por ID
- **Objetivo**: Implementar `passport(passport_id)` retornando o passaporte JSON serializado se existente, ou levantando `DomainError(status=404, code='not_found')` caso inexistente.
- **Teste adicionado**: `test_passport_retrieval_and_not_found` em `tests/test_domain.py`.
- **Comando RED**: `python -m unittest tests/test_domain.py`
  - **Saída**: `NotImplementedError`
- **Implementação mínima**: Consulta SQL em `passports` por `id`, deserialização JSON e retorno.
- **Comando GREEN**: `python -m unittest tests/test_domain.py`
  - **Saída**: `Ran 8 tests in 0.103s - OK`

### Ciclo 14: domain.Ledger.assess - simulação paramétrica SIM-001
- **Objetivo**: Implementar `assess(payload)` calculando multa `q*300` e taxa `50+q*2` com arredondamento `ROUND_HALF_UP` em duas casas decimais como strings formatadas, persistindo em `assessments` e emitindo evento atômico `ASSESSMENT_CREATED`.
- **Teste adicionado**: `test_assess_sim001_and_validation` em `tests/test_domain.py`.
- **Comando RED**: `python -m unittest tests/test_domain.py`
  - **Saída**: `NotImplementedError`
- **Implementação mínima**: Validações de entrada (`quantity_m3` positivo até 1.000.000, textos obrigatórios), cálculo `Decimal`, inserção na tabela `assessments`, geração de evento encadeado com hash SHA-256 e commit atômico.
- **Comando GREEN**: `python -m unittest tests/test_domain.py`
  - **Saída**: `Ran 10 tests in 0.118s - OK`

### Ciclo 15: domain.Ledger.review - parecer técnico conclusivo e unicidade
- **Objetivo**: Implementar `review(payload)` permitindo decisão única (`agree` ou `disagree`) com parecerista e motivação técnica obrigatórios; rejeitar segunda revisão com status 409 `conflict`; persistir atualização e evento `ASSESSMENT_REVIEWED`.
- **Teste adicionado**: `test_review_definitive_and_conflict` e `test_review_nonexistent_assessment_404` em `tests/test_domain.py`.
- **Comando RED**: `python -m unittest tests/test_domain.py`
  - **Saída**: `NotImplementedError`
- **Implementação mínima**: Validações de campos obrigatórios, bloqueio atômico `BEGIN IMMEDIATE`, verificação de unicidade (rejeitando se já homologado), atualização do registro com UTC e emissão do evento encadeado.
- **Comando GREEN**: `python -m unittest tests/test_domain.py`
  - **Saída**: `Ran 11 tests in 0.137s - OK`

### Ciclo 16: domain.Ledger - concorrência e idempotência sequencial/simultânea
- **Objetivo**: Garantir segurança multi-thread: requisições com mesma chave de idempotência concorrentes devolvem o mesmo passaporte sem débito duplo; requisições concorrentes com chaves distintas disputando saldo executam serializadas sem qualquer overbooking (rejeitando excedentes com 409).
- **Testes adicionados**: `test_idempotency_sequential_same_payload_returns_same_passport`, `test_idempotency_conflict_divergent_payload`, `test_concurrency_simultaneous_idempotency`, e `test_concurrency_simultaneous_different_keys_no_overbooking` em `tests/test_domain.py`.
- **Implementação**: Retry inteligente `_begin_immediate` com backoff contra contenção transitória de SQLite em concorrência pesada.
- **Comando GREEN**: `python -m unittest tests/test_domain.py`
  - **Saída**: `Ran 15 tests in 0.380s - OK`

### Ciclo 17: domain.Ledger.verify_chain - detecção de adulteração e snapshot de estado
- **Objetivo**: Garantir que qualquer alteração indevida em `payload`, `hash` ou `previous_hash` seja detectada imediatamente por `verify_chain()` retornando `valid: False` e identificando `broken_event_id`; garantir que `state()` execute leitura de tabelas dentro de snapshot transacional consistente.
- **Testes adicionados**: `test_chain_tampering_payload_detection` e `test_chain_tampering_previous_hash_detection` em `tests/test_domain.py`.
- **Implementação**: Método `_verify_chain_events` compartilhado e recomputação rigorosa de todos os campos do bloco de eventos.
- **Comando GREEN**: `python -m unittest tests/test_domain.py`
  - **Saída**: `Ran 17 tests in 0.432s - OK`

## Resumo da Suíte Completa de Testes
- `tests/test_calculations.py`: 6 testes (100% GREEN)
- `tests/test_domain.py`: 17 testes (100% GREEN)
- `tests/test_http.py`: 12 testes (100% GREEN)
- Suíte total do repositório (`python -m unittest discover tests`): 87 testes (100% GREEN)

## Lacunas e Limitações Conhecidas
- A aplicação utiliza SQLite local com isolamento `BEGIN IMMEDIATE` e `PRAGMA busy_timeout=30000`. Não é destinado a cluster distribuído.
- As regras de volumetria e cálculos paramétricos (SIM-001) possuem natureza demonstrativa/experimental expressa nas mensagens (`notice`), sem conferir validade jurídica de desdobro florestal oficial.










