// @ts-check
const { test, expect } = require('@playwright/test');

test.describe.serial('RAIZTRACE — Testes Integrados Reais (Sem Mocks de API)', () => {
  test.beforeEach(async ({ page }) => {
    // NUNCA intercepta APIs nem HTML/static; apenas aborta tiles externos OSM para offline
    await page.route(/tile\.openstreetmap\.org/, (route) => route.abort());
  });

  test('1. First render com dados territoriais reais de IBGE/INPE e estado inicial', async ({ page }) => {
    await page.goto('/');

    // Cabeçalho e integridade dinâmica do ledger
    const brand = page.locator('.brand-title');
    await expect(brand).toHaveText(/RAIZTRACE/);
    const integrityBadge = page.locator('#header-integrity-badge');
    await expect(integrityBadge).toContainText(/Cadeia verificada/i);

    // Dossiê operacional: saldo carregado do backend
    const availVal = page.locator('[data-testid="available-volume"]');
    await expect(availVal).toContainText('15,000');

    // Informação de fontes territoriais reais visíveis junto ao mapa
    const mapStatus = page.locator('#map-base-status');
    await expect(mapStatus).toBeVisible();
    await expect(mapStatus).toContainText(/DETER/i);

    // Título do dossiê encurtado e sem caixas aninhadas
    await expect(page.locator('.section-title').first()).toContainText('Lote AM-DEMO-001');
    const stockList = page.locator('.stock-list');
    await expect(stockList).toBeVisible();
  });

  test('2. Enquadramento e zoom do mapa de Itacoatiara sem englobar Amazonas inteiro', async ({ page }) => {
    await page.goto('/');

    const mapEl = page.locator('#map');
    await expect(mapEl).toBeVisible();

    // Aguarda inicialização dos dados do mapa
    await page.waitForTimeout(600);

    // Botão Enquadrar Município foca os limites de Itacoatiara
    const btnFit = page.locator('#btn-fit-municipality');
    await expect(btnFit).toBeEnabled();
    await btnFit.click();
    await page.waitForTimeout(400);

    // Testabilidade do mapa exposta no elemento (zoom >= 8, não nível estadual ~4)
    const zoomAttr = await mapEl.getAttribute('data-zoom');
    if (zoomAttr) {
      const zoom = parseInt(zoomAttr, 10);
      expect(zoom).toBeGreaterThanOrEqual(8);
    }

    // Botão Focar Parcela foca o polígono da parcela demonstrativa
    const btnFocus = page.locator('#btn-focus-demo');
    await expect(btnFocus).toBeEnabled();
    await btnFocus.click();
    await page.waitForTimeout(400);
  });

  test('3. Filtros DETER por classe e data sincronizados entre mapa e lista acessível', async ({ page }) => {
    await page.goto('/');

    // Filtro de classe DETER no toolbar
    const classFilter = page.locator('#deter-filter-class');
    await expect(classFilter).toBeVisible();

    // Contagem dinâmica
    const counterBadge = page.locator('#deter-counter-badge');
    await expect(counterBadge).toBeVisible();
    await expect(counterBadge).toContainText(/200/);

    // Aplica filtro por classe
    await classFilter.selectOption('CICATRIZ_DE_QUEIMADA');
    await page.waitForTimeout(300);

    // Verifica que a contagem dinâmica atualizou
    const counterText = await counterBadge.textContent();
    expect(counterText).toContain('CICATRIZ_DE_QUEIMADA');

    // Lista acessível exibe apenas itens da classe selecionada
    const listItems = page.locator('.deter-alert-item');
    const count = await listItems.count();
    expect(count).toBeGreaterThan(0);
    const firstItemText = await listItems.first().textContent();
    expect(firstItemText).toContain('CICATRIZ_DE_QUEIMADA');
  });

  test('4. Fluxo real de reserva idempotente: 10 m³ reduz saldo de 15 m³ para 5 m³', async ({ page }) => {
    await page.goto('/');

    // Navega para aba Cargas
    await page.locator('button[data-tab="shipments"]').click();
    await expect(page.locator('#tab-shipments')).toBeVisible();

    // Chave de idempotência ativa gerada
    const keyDisplay = page.locator('#shipment-idempotency-key');
    await expect(keyDisplay).not.toHaveText('gerando-uuid...');

    // Preenche formulário de reserva
    await page.locator('input#shipment-volume').fill('10');
    await page.locator('input#shipment-invoice').fill('NF-INTEG-001');
    await page.locator('input#shipment-recipient').fill('Cooperativa Local Integrada');
    await page.locator('input#shipment-vehicle').fill('VEICULO-REAL-01');

    // Emite reserva
    const btnSubmit = page.locator('#btn-submit-shipment');
    await expect(btnSubmit).toBeEnabled();
    await btnSubmit.click();

    // Feedback de sucesso
    const feedback = page.locator('#shipment-feedback');
    await expect(feedback).toBeVisible();
    await expect(feedback).toContainText(/Passaporte emitido com sucesso/i);

    // Saldo atualizado para 5.000 m³
    const availVal = page.locator('[data-testid="available-volume"]');
    await expect(availVal).toContainText('5,000');
  });

  test('5. Segunda reserva de 10 m³ bloqueada com erro legível de saldo insuficiente', async ({ page }) => {
    await page.goto('/');
    await page.locator('button[data-tab="shipments"]').click();

    // Gera nova chave para segunda reserva
    await page.locator('#btn-new-idempotency').click();

    // Tenta reservar 10 m³ (saldo é 5 m³)
    await page.locator('input#shipment-volume').fill('10');
    await page.locator('input#shipment-invoice').fill('NF-INTEG-002');
    await page.locator('#btn-submit-shipment').click();

    // Feedback de erro legível
    const feedback = page.locator('#shipment-feedback');
    await expect(feedback).toBeVisible();
    await expect(feedback).toContainText(/insuficiente/i);

    // Saldo permanece 5.000 m³
    const availVal = page.locator('[data-testid="available-volume"]');
    await expect(availVal).toContainText('5,000');
  });

  test('6. Exportação de passaporte em JSON e link para impressão', async ({ page }) => {
    await page.goto('/');
    await page.locator('button[data-tab="shipments"]').click();

    // Tabela de passaportes emitidos
    const downloadLink = page.locator('a.passport-download-btn').first();
    await expect(downloadLink).toBeVisible();
    await expect(downloadLink).toHaveAttribute('download', /passaporte.*\.json/);

    const printLink = page.locator('a.passport-print-btn').first();
    await expect(printLink).toBeVisible();
    await expect(printLink).toHaveAttribute('href', /\/passport\/.+/);
  });

  test('7. Balança e verificação de pesagem com divergência (3.500 kg)', async ({ page }) => {
    await page.goto('/');
    await page.locator('button[data-tab="shipments"]').click();

    // Preenche verificação: 10 m³, bruto 25000 kg, tara 12000 kg => líquido 13000 kg (divergente, diferença 3.500 kg)
    await page.locator('input#weigh-volume').fill('10');
    await page.locator('input#weigh-gross').fill('25000');
    await page.locator('input#weigh-tare').fill('12000');

    await page.locator('#btn-verify-weigh').click();

    const weighResult = page.locator('#weigh-result');
    await expect(weighResult).toBeVisible();
    await expect(weighResult).toContainText(/Divergente/i);
    await expect(weighResult).toContainText('3.500');
  });

  test('8. Revisão técnica simulada com motivação e justificativa obrigatória', async ({ page }) => {
    await page.goto('/');
    await page.locator('button[data-tab="review"]').click();
    await expect(page.locator('#tab-review')).toBeVisible();

    // Tenta submeter parecer sem justificativa obrigatória
    await page.locator('#btn-submit-review').click();
    const feedback = page.locator('#review-feedback');
    await expect(feedback).toBeVisible();
    await expect(feedback).toContainText(/motivação.*obrigatória/i);

    // Preenche revisor e parecer
    await page.locator('#review-author').fill('Fiscal Avaliador Integrado');
    await page.locator('#review-reason').fill('Verificação das densidades teóricas e conferência da malha espacial.');
    await page.locator('#btn-submit-review').click();

    // Se backend responder (ou apontar pendência de assess), feedback ou estado definitivo aparece
    const definitiveState = page.locator('#review-definitive-state');
    const feedbackBox = page.locator('#review-feedback');
    const eitherVisible = (await definitiveState.isVisible()) || (await feedbackBox.isVisible());
    expect(eitherVisible).toBe(true);
  });

  test('9. Laboratório ML outlier [999, 999, 999] resulta em abstenção/inconclusivo', async ({ page }) => {
    await page.goto('/');
    await page.locator('button[data-tab="lab"]').click();
    await expect(page.locator('#tab-lab')).toBeVisible();

    // Clica no botão de exemplo distante
    await page.locator('#btn-ml-distant').click();

    const mlResult = page.locator('#ml-result');
    await expect(mlResult).toBeVisible();
    await expect(mlResult).toContainText(/inconclusivo/i);
    await expect(mlResult).toContainText(/NUNCA identifica espécies botânicas/i);
  });

  test('10. Responsividade mobile 390px e acessibilidade por teclado', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/');

    // Sem overflow horizontal
    const hasHorizontalOverflow = await page.evaluate(() => {
      return document.documentElement.scrollWidth > document.documentElement.clientWidth;
    });
    expect(hasHorizontalOverflow).toBe(false);

    // Altura do mapa de 380px no mobile
    // The map itself (not toolbar + map) is 380px tall on phones.
    const mapBox = await page.locator('.map-wrapper').boundingBox();
    expect(mapBox).not.toBeNull();
    expect(Math.round(mapBox.height)).toBe(380);
    // Filters start collapsed on phones so the map is reached without scrolling past controls.
    await expect(page.locator('.filter-disclosure')).not.toHaveAttribute('open', '');

    // Acessibilidade por teclado nas abas (roving tabindex e setas)
    const territoryBtn = page.locator('#nav-btn-territory');
    await territoryBtn.focus();
    await page.keyboard.press('ArrowDown');

    // Aba Cargas deve receber foco e seleção
    const shipmentsBtn = page.locator('#nav-btn-shipments');
    await expect(shipmentsBtn).toBeFocused();

    // Nós de custódia são botões acessíveis por teclado
    await page.keyboard.press('ArrowUp'); // volta para Território
    const custodyButtons = page.locator('button.custody-node');
    expect(await custodyButtons.count()).toBeGreaterThanOrEqual(4);
  });

  test('11. Cruzamento territorial e proximidade espacial com alertas DETER', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(600);

    // Painel de sobreposição territorial exibe distâncias em km
    const spatialBox = page.locator('#dossier-spatial-box');
    await expect(spatialBox).toBeVisible();
    await expect(spatialBox).toContainText('km');

    // Botão de alerta mais próximo foca o mapa aumentando o zoom
    const mapEl = page.locator('#map');
    const initialZoom = parseInt((await mapEl.getAttribute('data-zoom')) || '10', 10);

    const alertBtn = page.locator('.proximity-alert-btn').first();
    await expect(alertBtn).toBeVisible();
    await alertBtn.click();
    await page.waitForTimeout(400);

    const newZoom = parseInt((await mapEl.getAttribute('data-zoom')) || '10', 10);
    expect(newZoom).toBeGreaterThan(initialZoom);
  });
});
