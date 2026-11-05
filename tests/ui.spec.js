// @ts-check
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const ROOT_DIR = path.resolve(__dirname, '..');

// Helper to provide contract-compliant mock responses for API and static files
async function setupApiAndStaticRoutes(page) {
  let state = {
    lots: [
      {
        id: 'AM-DEMO-001',
        plot_id: 'AREA-DEMO-001',
        product: 'Tora Bruta',
        species: 'Demonstrativo Florestal',
        opening_milli: 15000,
        available_milli: 15000,
        reserved_milli: 0,
        unit: 'm3',
        simulated: true
      }
    ],
    shipments: [],
    assessments: [],
    events: [
      {
        id: 'EVT-001',
        at: '2026-11-05T12:00:00Z',
        type: 'abertura_lote',
        payload: { lot_id: 'AM-DEMO-001', volume_m3: 15 },
        hash: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
      }
    ],
    integrity: { valid: true, count: 1 }
  };

  const territory = {
    municipality: {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          properties: { id: '1301902', name: 'Itacoatiara' },
          geometry: {
            type: 'Polygon',
            coordinates: [[[-58.5, -3.1], [-58.3, -3.1], [-58.3, -3.2], [-58.5, -3.2], [-58.5, -3.1]]]
          }
        }
      ]
    },
    state: {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          properties: { id: '13', name: 'Amazonas' },
          geometry: {
            type: 'Polygon',
            coordinates: [[[-70.0, -1.0], [-56.0, -1.0], [-56.0, -9.0], [-70.0, -9.0], [-70.0, -1.0]]]
          }
        }
      ]
    },
    alerts: {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          properties: {
            gid: 101,
            classname: 'DESMATAMENTO_CR',
            view_date: '2026-10-15',
            sensor: 'AWFI',
            satellite: 'CBERS-4A',
            areamunkm: 0.42,
            municipality: 'Itacoatiara',
            mun_geocod: '1301902',
            uf: 'AM'
          },
          geometry: {
            type: 'Polygon',
            coordinates: [[[-58.42, -3.14], [-58.40, -3.14], [-58.40, -3.16], [-58.42, -3.16], [-58.42, -3.14]]]
          }
        }
      ]
    },
    sources: [
      {
        id: 'ibge-municipio',
        name: 'IBGE Malha Municipal Itacoatiara',
        url: 'https://servicodados.ibge.gov.br/api/v3/malhas/municipios/1301902',
        fetched_at: '2026-11-05T12:00:00Z',
        status: 'cached',
        feature_count: 1,
        partial: false,
        total_available: 1
      },
      {
        id: 'deter-inpe',
        name: 'DETER INPE Alertas Recentes',
        url: 'https://terrabrasilis.dpi.inpe.br/geoserver/deter-amz/ows',
        fetched_at: '2026-11-05T12:00:00Z',
        status: 'cached',
        feature_count: 1,
        partial: true,
        total_available: 200
      }
    ],
    demo: {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          properties: { id: 'AREA-DEMO-001', name: 'Parcela Demonstrativa AM-DEMO-001', kind: 'plot', simulated: true, lot_id: 'AM-DEMO-001' },
          geometry: {
            type: 'Polygon',
            coordinates: [[[-58.45, -3.12], [-58.43, -3.12], [-58.43, -3.14], [-58.45, -3.14], [-58.45, -3.12]]]
          }
        },
        {
          type: 'Feature',
          properties: { id: 'TREE-DEMO-001', name: 'Árvore Tombada Demo', kind: 'tree', simulated: true, lot_id: 'AM-DEMO-001' },
          geometry: { type: 'Point', coordinates: [-58.445, -3.125] }
        },
        {
          type: 'Feature',
          properties: { id: 'YARD-DEMO-001', name: 'Pátio de Estocagem Demo', kind: 'yard', simulated: true, lot_id: 'AM-DEMO-001' },
          geometry: { type: 'Point', coordinates: [-58.438, -3.130] }
        },
        {
          type: 'Feature',
          properties: { id: 'ROUTE-DEMO-001', name: 'Ramal de Transporte Demo', kind: 'route', simulated: true, lot_id: 'AM-DEMO-001' },
          geometry: {
            type: 'LineString',
            coordinates: [[-58.438, -3.130], [-58.435, -3.135], [-58.430, -3.140]]
          }
        },
        {
          type: 'Feature',
          properties: { id: 'DEST-DEMO-001', name: 'Destino / Entrega Demo', kind: 'destination', simulated: true, lot_id: 'AM-DEMO-001' },
          geometry: { type: 'Point', coordinates: [-58.430, -3.140] }
        }
      ]
    },
    spatial: {
      intersections: [],
      count: 0,
      notice: 'Nenhuma sobreposição com alertas DETER no recorte analisado.'
    },
    notice: 'Dados territoriais reais IBGE/DETER; feições demonstrativas simuladas.'
  };

  const mlModel = {
    model_version: 'v1.0.0-knn',
    train_count: 90,
    test_count: 30,
    classes: ['A', 'B', 'C'],
    features: ['sinal_densidade', 'sinal_espectro', 'sinal_fuste'],
    metrics: { accuracy: 0.933, macro_f1: 0.931, abstention_rate: 0.05 },
    notice: 'Classificação estritamente estatística de perfis artificiais. NUNCA identifica espécies botânicas.',
    synthetic: true
  };

  let usedKeys = new Set();

  await page.route('**/*', async (route) => {
    const req = route.request();
    const url = new URL(req.url());

    // Intercept OSM tiles to prevent external requests in tests
    if (url.hostname.includes('tile.openstreetmap.org')) {
      return route.fulfill({
        status: 200,
        contentType: 'image/png',
        body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=', 'base64')
      });
    }

    // Serve HTML
    if (url.pathname === '/' || url.pathname === '/index.html') {
      const htmlPath = path.join(ROOT_DIR, 'static', 'index.html');
      if (fs.existsSync(htmlPath)) {
        return route.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', body: fs.readFileSync(htmlPath) });
      }
      return route.fulfill({ status: 404, body: 'Not found yet' });
    }

    // Serve static files
    if (url.pathname.startsWith('/static/')) {
      const rel = url.pathname.replace(/^\/static\//, '');
      const filePath = path.join(ROOT_DIR, 'static', rel);
      if (fs.existsSync(filePath)) {
        const ext = path.extname(filePath);
        let mime = 'application/octet-stream';
        if (ext === '.css') mime = 'text/css';
        else if (ext === '.js') mime = 'application/javascript';
        else if (ext === '.png') mime = 'image/png';
        return route.fulfill({ status: 200, contentType: mime, body: fs.readFileSync(filePath) });
      }
      return route.fulfill({ status: 404, body: 'File not found' });
    }

    // API routes
    if (url.pathname === '/api/state' && req.method() === 'GET') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(state)
      });
    }

    if (url.pathname === '/api/territory' && req.method() === 'GET') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(territory)
      });
    }

    if (url.pathname === '/api/sources/refresh' && req.method() === 'POST') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ...territory,
          notice: 'Fontes territoriais atualizadas com sucesso.'
        })
      });
    }

    if (url.pathname === '/api/ml/model' && req.method() === 'GET') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mlModel)
      });
    }

    if (url.pathname === '/api/audit' && req.method() === 'GET') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ valid: true, count: state.events.length })
      });
    }

    if (url.pathname === '/api/shipments' && req.method() === 'POST') {
      const idempotencyKey = req.headers()['idempotency-key'] || req.headers()['Idempotency-Key'];
      const body = JSON.parse(req.postData() || '{}');
      const volumeM3 = parseFloat(body.volume_m3);
      const requestedMilli = Math.round(volumeM3 * 1000);

      const lot = state.lots.find((l) => l.id === (body.lot_id || 'AM-DEMO-001'));
      if (!lot) {
        return route.fulfill({
          status: 404,
          contentType: 'application/json',
          body: JSON.stringify({ error: { code: 'lot_not_found', message: 'Lote não encontrado.' } })
        });
      }

      if (idempotencyKey && usedKeys.has(idempotencyKey)) {
        // Idempotent retry returns existing shipment
        const existing = state.shipments.find((s) => s.idempotency_key === idempotencyKey);
        if (existing) {
          return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(existing) });
        }
      }

      if (lot.available_milli < requestedMilli) {
        const availStr = (lot.available_milli / 1000).toLocaleString('pt-BR', { minimumFractionDigits: 3, maximumFractionDigits: 3 });
        const reqStr = (requestedMilli / 1000).toLocaleString('pt-BR', { minimumFractionDigits: 3, maximumFractionDigits: 3 });
        return route.fulfill({
          status: 409,
          contentType: 'application/json',
          body: JSON.stringify({
            error: {
              code: 'insufficient_balance',
              message: `Bloqueio: saldo disponível de ${availStr} m³ é insuficiente para reserva de ${reqStr} m³.`
            }
          })
        });
      }

      // Deduct balance
      lot.available_milli -= requestedMilli;
      lot.reserved_milli += requestedMilli;

      if (idempotencyKey) usedKeys.add(idempotencyKey);

      const passport = {
        id: `PASS-${Date.now()}`,
        idempotency_key: idempotencyKey,
        lot_id: lot.id,
        volume_m3: volumeM3,
        balance_after_milli: lot.available_milli,
        recipient: body.recipient,
        vehicle: body.vehicle,
        invoice: body.invoice,
        gross_kg: body.gross_kg,
        tare_kg: body.tare_kg,
        hash: 'b3f5e921d784a0c842b1093156cfd74659b9e3a763a8a958cfb934b123456789',
        weighing: {
          net_kg: body.gross_kg - body.tare_kg,
          status: 'compatible'
        },
        notice: 'Passaporte demonstrativo experimental. Não substitui DOF+, Sinaflor nem documento fiscal.'
      };

      state.shipments.push(passport);
      state.events.push({
        id: `EVT-${Date.now()}`,
        timestamp: new Date().toISOString(),
        type: 'reserva_carga',
        payload: { passport_id: passport.id, volume_m3: volumeM3, balance_after: lot.available_milli },
        hash: 'a1b2c3d4e5f678901234567890abcdef1234567890abcdef1234567890abcdef'
      });

      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(passport)
      });
    }

    if (url.pathname.startsWith('/api/passports/') && req.method() === 'GET') {
      const passId = url.pathname.replace('/api/passports/', '');
      const pass = state.shipments.find((s) => s.id === passId) || {
        id: passId,
        hash: 'b3f5e921d784a0c842b1093156cfd74659b9e3a763a8a958cfb934b123456789',
        volume_m3: 10,
        balance_after_milli: 5000,
        notice: 'Passaporte demonstrativo experimental.'
      };
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(pass) });
    }

    if (url.pathname === '/api/weigh' && req.method() === 'POST') {
      const body = JSON.parse(req.postData() || '{}');
      const vol = parseFloat(body.volume_m3);
      const gross = parseFloat(body.gross_kg);
      const tare = parseFloat(body.tare_kg);
      const net = gross - tare;
      const minKg = vol * 650;
      const maxKg = vol * 950;
      let status = 'compatible';
      let diff = 0;
      if (net < minKg) {
        status = 'divergent';
        diff = net - minKg;
      } else if (net > maxKg) {
        status = 'divergent';
        diff = net - maxKg;
      }
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          net_kg: net,
          net_t: net / 1000,
          min_kg: minKg,
          max_kg: maxKg,
          status: status,
          difference_kg: diff,
          formula: 'net_kg = gross_kg - tare_kg; limits = [volume_m3 * 650, volume_m3 * 950]',
          notice: 'Faixa hipotética de densidade 650–950 kg/m³. Não confirma espécie florestal nem legalidade da carga.'
        })
      });
    }

    if (url.pathname === '/api/inventory' && req.method() === 'POST') {
      const body = JSON.parse(req.postData() || '{}');
      const d = parseFloat(body.diameter_cm) / 100;
      const h = parseFloat(body.height_m);
      const f = parseFloat(body.form_factor || 0.7);
      const vol = (Math.PI * Math.pow(d / 2, 2) * h * f);
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          volume_m3: parseFloat(vol.toFixed(3)),
          min_mass_t: parseFloat((vol * 0.65).toFixed(3)),
          max_mass_t: parseFloat((vol * 0.95).toFixed(3)),
          formula: 'volume = (pi * (d/2)^2) * h * f',
          notice: 'Cálculo geométrico preliminar. NÃO se converte em saldo nem autoriza supressão.'
        })
      });
    }

    if (url.pathname === '/api/assessments' && req.method() === 'POST') {
      const body = JSON.parse(req.postData() || '{}');
      const qty = parseFloat(body.quantity_m3 || 5);
      const item = {
        id: `ASM-${Date.now()}`,
        rule_id: 'SIM-001',
        rule_version: 'v1.0',
        quantity_m3: qty,
        hypothesis: body.hypothesis || 'Discrepância volumétrica estimada',
        reviewer: body.reviewer || 'Fiscal Demonstrativo',
        fine_brl: '1500.00',
        fee_brl: '60.00',
        formula: 'fine = base_300 * quantity_m3; fee = fee_base * 2',
        status: 'pending',
        notice: 'Simulação paramétrica de regra interna (SIM-001). Não constitui autuação real nem possui validade legal.'
      };
      state.assessments.push(item);
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(item) });
    }

    if (url.pathname === '/api/review' && req.method() === 'POST') {
      const body = JSON.parse(req.postData() || '{}');
      if (!body.reason || !body.reason.trim()) {
        return route.fulfill({
          status: 400,
          contentType: 'application/json',
          body: JSON.stringify({ error: { code: 'motivation_required', message: 'Motivação/justificativa técnica é obrigatória para registrar parecer.' } })
        });
      }
      const asm = state.assessments.find((a) => a.id === body.assessment_id) || { id: body.assessment_id, rule_id: 'SIM-001' };
      asm.decision = body.decision;
      asm.reviewer = body.reviewer;
      asm.reason = body.reason;
      asm.status = body.decision === 'agree' ? 'agreed' : 'disagreed';
      asm.reviewed_at = new Date().toISOString();

      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(asm) });
    }

    if (url.pathname === '/api/ml' && req.method() === 'POST') {
      const body = JSON.parse(req.postData() || '{}');
      const feats = body.features || [];
      const isDistant = feats.some((v) => Math.abs(v) > 500);
      if (isDistant) {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            label: null,
            status: 'inconclusive',
            distance: 842.15,
            neighbor_agreement: 0.33,
            notice: 'Amostra fora do espaço dimensional de treinamento. Classificação abstida por distância excessiva.',
            synthetic: true
          })
        });
      }
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          label: 'A',
          status: 'classified',
          distance: 0.24,
          neighbor_agreement: 1.0,
          notice: 'Perfil numérico sintético A classificado. NUNCA identifica espécie botânica real.',
          synthetic: true
        })
      });
    }

    // Default: continue or 404
    return route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ error: { code: 'not_found', message: 'Rota não encontrada' } }) });
  });
}

test.describe('RAIZTRACE — Fluxo Integrado de UI Operacional', () => {
  test('1. Renderiza cabeçalho, mapa interativo, dossiê e indicador de fontes reais', async ({ page }) => {
    await setupApiAndStaticRoutes(page);
    await page.goto('/');

    // Header validation
    const brand = page.locator('.brand-title');
    await expect(brand).toHaveText(/RAIZTRACE/);
    await expect(page.locator('.brand-logo-svg')).toBeVisible();

    // Map container exists
    const map = page.locator('#map');
    await expect(map).toBeVisible();

    // Real source visibility in transparency banner or sources list
    const sourceBadge = page.locator('.transparency-notice');
    await expect(sourceBadge).toContainText(/IBGE/);
    await expect(sourceBadge).toContainText(/DETER/);

    // Initial stock balance is 15.000 m³
    const availableVal = page.locator('[data-testid="available-volume"]');
    await expect(availableVal).toContainText('15,000');
  });

  test('2. Alternância de camadas cartográficas e botões de enquadramento', async ({ page }) => {
    await setupApiAndStaticRoutes(page);
    await page.goto('/');

    const layerDeter = page.locator('input#layer-toggle-alerts');
    await expect(layerDeter).toBeChecked();
    await layerDeter.uncheck();
    await expect(layerDeter).not.toBeChecked();

    const layerDemo = page.locator('input#layer-toggle-demo');
    await expect(layerDemo).toBeChecked();

    // Fit and focus buttons are clickable
    const btnFit = page.locator('button#btn-fit-municipality');
    await expect(btnFit).toBeEnabled();
    await btnFit.click();

    const btnFocusDemo = page.locator('button#btn-focus-demo');
    await expect(btnFocusDemo).toBeEnabled();
    await btnFocusDemo.click();
  });

  test('3. Fluxo de reserva idempotente: 10 m³ reduz saldo de 15 m³ para 5 m³', async ({ page }) => {
    await setupApiAndStaticRoutes(page);
    await page.goto('/');

    // Navigate to Cargas tab
    await page.locator('button[data-tab="shipments"]').click();
    await expect(page.locator('#tab-shipments')).toBeVisible();

    // Fill reservation form
    await page.locator('input#shipment-volume').fill('10');
    await page.locator('input#shipment-recipient').fill('Cooperativa demonstrativa');
    await page.locator('input#shipment-vehicle').fill('VEICULO-DEMO');
    await page.locator('input#shipment-invoice').fill('NF-DEMO-001');

    // Submit reservation
    await page.locator('button#btn-submit-shipment').click();

    // Success feedback and passport generated
    const successBox = page.locator('.shipment-feedback.success');
    await expect(successBox).toBeVisible();
    await expect(successBox).toContainText(/Passaporte emitido com sucesso/i);

    // Check updated balance (now 5.000 m³)
    const availableVal = page.locator('[data-testid="available-volume"]');
    await expect(availableVal).toContainText('5,000');
  });

  test('4. Segunda reserva de 10 m³ é bloqueada exibindo erro legível de saldo insuficiente', async ({ page }) => {
    await setupApiAndStaticRoutes(page);
    await page.goto('/');

    await page.locator('button[data-tab="shipments"]').click();

    // First reservation of 10 m³
    await page.locator('input#shipment-volume').fill('10');
    await page.locator('button#btn-submit-shipment').click();
    await expect(page.locator('.shipment-feedback.success')).toBeVisible();

    // New idempotency key for new reservation attempt
    await page.locator('button#btn-new-idempotency').click();

    // Attempt second reservation of 10 m³ (only 5 m³ available)
    await page.locator('input#shipment-volume').fill('10');
    await page.locator('button#btn-submit-shipment').click();

    // Error message must be visible and explain insufficient balance
    const errorBox = page.locator('.shipment-feedback.error');
    await expect(errorBox).toBeVisible();
    await expect(errorBox).toContainText(/saldo disponível de 5,000 m³ é insuficiente/i);
  });

  test('5. Exportação de passaporte em JSON e link para impressão', async ({ page }) => {
    await setupApiAndStaticRoutes(page);
    await page.goto('/');

    await page.locator('button[data-tab="shipments"]').click();
    await page.locator('input#shipment-volume').fill('10');
    await page.locator('button#btn-submit-shipment').click();

    // Passport table/card should have download JSON and print link
    const downloadLink = page.locator('a.passport-download-btn').first();
    await expect(downloadLink).toBeVisible();
    await expect(downloadLink).toHaveAttribute('download', /passaporte.*\.json/);

    const printLink = page.locator('a.passport-print-btn').first();
    await expect(printLink).toBeVisible();
    await expect(printLink).toHaveAttribute('href', /\/passport\/.+/);
  });

  test('6. Verificação de pesagem apontando divergência e aviso regulatório', async ({ page }) => {
    await setupApiAndStaticRoutes(page);
    await page.goto('/');

    await page.locator('button[data-tab="shipments"]').click();

    // Fill weigh inputs: 10 m³, gross 20000 kg, tare 16500 kg => net 3500 kg (divergent)
    await page.locator('input#weigh-volume').fill('10');
    await page.locator('input#weigh-gross').fill('20000');
    await page.locator('input#weigh-tare').fill('16500');

    await page.locator('button#btn-verify-weigh').click();

    const weighResult = page.locator('.weigh-result');
    await expect(weighResult).toBeVisible();
    await expect(weighResult).toContainText(/divergente/i);
    await expect(weighResult).toContainText('3.500'); // net kg formatted
    await expect(weighResult).toContainText(/Faixa hipotética de densidade 650–950 kg\/m³/i);
    await expect(weighResult).toContainText(/Não confirma espécie/i);
  });

  test('7. Revisão humana de inconsistência exige motivação e persiste parecer técnico', async ({ page }) => {
    await setupApiAndStaticRoutes(page);
    await page.goto('/');

    await page.locator('button[data-tab="review"]').click();
    await expect(page.locator('#tab-review')).toBeVisible();

    // Simulate assessment
    await page.locator('input#assessment-qty').fill('5');
    await page.locator('button#btn-simulate-assessment').click();

    const assessmentItem = page.locator('.assessment-item').first();
    await expect(assessmentItem).toBeVisible();
    await expect(assessmentItem).toContainText('SIM-001');
    await expect(assessmentItem).toContainText('1.500,00');

    // Attempt review without motivation/reason
    await page.locator('button#btn-submit-review').click();
    const errorNotice = page.locator('.review-feedback.error');
    await expect(errorNotice).toBeVisible();
    await expect(errorNotice).toContainText(/motivação.*obrigatória/i);

    // Provide reviewer, select decision and motivation
    await page.locator('input#review-author').fill('Analista Maria Silva');
    await page.locator('select#review-decision').selectOption('agree');
    await page.locator('textarea#review-reason').fill('Concordância com apuração volumétrica preliminar baseada em cubagem.');
    await page.locator('button#btn-submit-review').click();

    const reviewStatus = page.locator('.review-definitive-state');
    await expect(reviewStatus).toBeVisible();
    await expect(reviewStatus).toContainText(/Revisão simulada registrada: Concordância \(agree\)/i);
    await expect(reviewStatus).toContainText('Analista Maria Silva');
  });

  test('8. Laboratório: inventário dendrométrico e classificação ML com abstenção para [999,999,999]', async ({ page }) => {
    await setupApiAndStaticRoutes(page);
    await page.goto('/');

    await page.locator('button[data-tab="lab"]').click();
    await expect(page.locator('#tab-lab')).toBeVisible();

    // Inventory calculation
    await page.locator('input#inv-diameter').fill('60');
    await page.locator('input#inv-height').fill('15');
    await page.locator('input#inv-form').fill('0.7');
    await page.locator('button#btn-calc-inventory').click();

    const invResult = page.locator('.inventory-result');
    await expect(invResult).toBeVisible();
    await expect(invResult).toContainText(/NÃO se converte em saldo/i);

    // Test ML with distant values button [999, 999, 999]
    const btnDistant = page.locator('button#btn-ml-distant');
    await btnDistant.click();

    const mlResult = page.locator('.ml-result');
    await expect(mlResult).toBeVisible();
    await expect(mlResult).toContainText(/inconclusivo/i);
    await expect(mlResult).toContainText(/Amostra fora do espaço dimensional/i);
    await expect(mlResult).toContainText(/NUNCA identifica espécies botânicas/i);
  });

  test('9. Responsividade mobile 390px sem overflow horizontal', async ({ page }) => {
    await setupApiAndStaticRoutes(page);
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/');

    // Check no horizontal overflow
    const hasHorizontalScroll = await page.evaluate(() => {
      return document.documentElement.scrollWidth > document.documentElement.clientWidth;
    });
    expect(hasHorizontalScroll).toBe(false);

    // Navigation is visible and usable in mobile
    const nav = page.locator('nav.main-nav');
    await expect(nav).toBeVisible();

    // Map container exists and fits
    const map = page.locator('#map');
    await expect(map).toBeVisible();
  });
});
