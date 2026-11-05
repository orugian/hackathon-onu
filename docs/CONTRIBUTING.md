# Contribuir com RAIZTRACE

1. Execute `py -3 -m unittest discover -s tests -v` antes de alterar o núcleo.
2. Escreva um teste de comportamento que falhe; implemente a menor fatia funcional; execute novamente; refatore apenas no verde.
3. Preserve volumes inteiros em milésimos de m³, transação indivisível, chave de idempotência, histórico e proveniência. Nunca substitua estado persistente por localStorage.
4. Separe dados sintéticos de fontes reais em API, interface, exportações e documentação. Ausência de alerta não confirma regularidade. Não acrescente alegações legais ou botânicas sem evidência.
5. Não envie credenciais, bancos operacionais, dados pessoais, documentos fiscais reais ou coordenadas sensíveis em contribuições.
6. Mudanças de UI requerem fluxo integrado, teclado, tela de 390px e desktop. Ferramentas opcionais: `npm ci` e `npm run test:ui`; não são dependências de execução do produto.
7. Mudanças de contrato exigem versionamento, exemplos e atualização dos consumidores e testes. Revise compatibilidade e documente migração.

## Responsabilidades de um piloto real
Operadores declaram; especialistas validam métodos e identificação; responsáveis técnicos conferem registros; autoridades competentes determinam procedimentos e atos. O protótipo não distribui esses poderes por um botão de aprovação.

## Governança proposta
Núcleo MIT; participação de cooperativas, compradores e órgão competente; canal de contestação, revisão rastreável e portabilidade. Planejar autenticação, segregação de funções, backups, retenção e revisão de segurança antes de exposição em rede.
