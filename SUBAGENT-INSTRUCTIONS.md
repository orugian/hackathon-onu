# SUBAGENT-INSTRUCTIONS

Subagentes rodam pelo **Antigravity CLI (`agy`)** com o modelo **Gemini 3.8 Flash, effort High**.

Verificado em 2026-10-26 nesta máquina:

- Executável: `C:\Users\orugi\AppData\Local\agy\bin\agy.exe`.
- Shell efetivo: **PowerShell 5.1** (Windows). Os comandos abaixo usam sintaxe PowerShell.
- Identificador do modelo: `gemini-3.8-flash-high` (o effort faz parte do nome; lista completa em `agy models`).
- Teste de fumaça: `agy --model gemini-3.8-flash-high --mode plan -p "..."` retornou exit 0 com resposta "OK, Gemini 3.8 Flash".
- `agy agents` não lista nenhum agente nomeado. Não use `--agent <nome>` até que um agente seja criado e apareça nessa lista; sem `--agent`, o `agy` usa o agente padrão.

## Comandos

1. Básico (sempre com o modelo explícito):

   ```powershell
   agy --model gemini-3.8-flash-high -p "Sua instrução ou tarefa aqui"
   ```

2. Tarefa somente leitura (auditoria, pesquisa, propostas, revisão): use `--mode plan`.

   ```powershell
   agy --model gemini-3.8-flash-high --mode plan -p "Audite o repositório local sem editar arquivos"
   ```

3. Saída em JSON para scripts: a flag é `--output-format json` (não `--output json`).

   ```powershell
   agy --model gemini-3.8-flash-high --mode plan --output-format json -p "..."
   ```

4. Salvar o relatório em arquivo para revisão:

   ```powershell
   agy --model gemini-3.8-flash-high --mode plan -p "..." 2>&1 | Out-File -Encoding utf8 .\.kaiser\reports\<tarefa>.md
   ```

## Outras flags úteis

- `--print-timeout <duração>`: limite de tempo no modo `-p` (padrão 0 = sem limite).
- `--sandbox`: restringe o terminal do subagente.
- `--mode accept-edits` / `--mode auto`: permitem edições; usar só em tarefas de implementação aprovadas.
- `--add-dir <dir>`: adiciona diretórios ao workspace do subagente.
- `--continue` / `--conversation <id>`: retomar a sessão de um subagente para pedir complementos.

## Permissões no modo headless (`-p`)

- Verificado em 2026-10-26: no modo `-p`, o `agy` nega automaticamente qualquer ferramenta que exija permissão de "command" (terminal). O subagente termina sem saída e o motivo aparece no stderr.
- Alternativas: regras `permissions.allow` em `C:\Users\orugi\.gemini\antigravity-cli\settings.json` (sintaxe sugerida pelo erro: `command(<alvo>)`, não testada) ou `--dangerously-skip-permissions`.
- Não rode `agy changelog` sem limite de tempo: ele ficou mais de uma hora sem retornar.

## Regras

- `--dangerously-skip-permissions` aprova automaticamente qualquer ação do subagente. Use só com autorização explícita do usuário para a tarefa.
  - Autorizado em 2026-10-26 para auditorias somente leitura (AUDIT-01), com instrução explícita de somente leitura no contrato.
  - Sempre que usar: tire um snapshot do repositório antes e depois (`git status --porcelain`, hash do `git diff HEAD`, lista de arquivos com tamanho e data) e compare.
- Defina `--print-timeout` e acompanhe o processo. Encerre o subagente se ele passar do limite.
- Cada chamada `-p` é uma sessão isolada. Proponentes independentes (AGENT.md, seção 4.1) devem rodar em chamadas separadas, sem `--continue` entre eles.
- Prompts longos: grave o contrato da tarefa em arquivo e passe o conteúdo com `Get-Content -Raw`, para evitar problemas de aspas no PowerShell.

## Problemas com timeout

= Use a seguinte referencia para rodar subagentes sem limite de tempo de execução- 'agy --print-timeout 0s' . Caso precise usar com '--dangerously-skip-permissions' certifique-se de que as intruções para apenas leitura estao explicitas
