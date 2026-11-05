/**
 * RAIZTRACE — Aplicação Operacional de Conciliação Florestal
 * Vanilla JavaScript sem frameworks ou dependências externas.
 */

(function () {
  'use strict';

  // --- Utilitários de Formatação e Segurança ---

  function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function formatMilli(milli) {
    const val = (Number(milli) || 0) / 1000;
    return val.toLocaleString('pt-BR', { minimumFractionDigits: 3, maximumFractionDigits: 3 });
  }

  function formatNumber(num, decimals = 2) {
    return (Number(num) || 0).toLocaleString('pt-BR', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
  }

  function generateUUID() {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
      return crypto.randomUUID();
    }
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
      const r = (Math.random() * 16) | 0;
      const v = c === 'x' ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }

  // --- Estado da Aplicação ---

  const state = {
    currentTab: 'territory',
    activeIdempotencyKey: generateUUID(),
    lots: [],
    shipments: [],
    assessments: [],
    events: [],
    integrity: { valid: true, count: 0 },
    territory: null,
    allAlertFeatures: [],
    mlModel: null,
    map: null,
    networkError: false
  };

  // --- Inicialização ---

  document.addEventListener('DOMContentLoaded', () => {
    // Filters stay open on desktop; on phones they start collapsed so the map is visible first.
    const filters = document.querySelector('.filter-disclosure');
    if (filters && window.matchMedia('(max-width: 768px)').matches) filters.open = false;
    initNavigation();
    initMap();
    initDeterFilters();
    initShipmentsModule();
    initWeighModule();
    initReviewModule();
    initLabModule();
    initSourcesModule();

    // Carga inicial assíncrona
    fetchState();
    fetchTerritory();
    fetchMlModel();
  });

  // --- Navegação entre Abas (com Roving Tabindex e Acessibilidade por Teclado) ---

  function initNavigation() {
    const navButtons = Array.from(document.querySelectorAll('.main-nav .nav-item-btn'));

    function focusAndSelectTab(index) {
      const targetBtn = navButtons[index];
      if (!targetBtn) return;
      const targetTab = targetBtn.getAttribute('data-tab');
      switchTab(targetTab);
      targetBtn.focus();
    }

    navButtons.forEach((btn, index) => {
      btn.addEventListener('click', () => {
        const targetTab = btn.getAttribute('data-tab');
        switchTab(targetTab);
      });

      btn.addEventListener('keydown', (e) => {
        let newIndex = index;
        if (e.key === 'ArrowDown' || e.key === 'ArrowRight') {
          e.preventDefault();
          newIndex = (index + 1) % navButtons.length;
          focusAndSelectTab(newIndex);
        } else if (e.key === 'ArrowUp' || e.key === 'ArrowLeft') {
          e.preventDefault();
          newIndex = (index - 1 + navButtons.length) % navButtons.length;
          focusAndSelectTab(newIndex);
        } else if (e.key === 'Home') {
          e.preventDefault();
          focusAndSelectTab(0);
        } else if (e.key === 'End') {
          e.preventDefault();
          focusAndSelectTab(navButtons.length - 1);
        }
      });
    });

    const btnQuickReserve = document.getElementById('btn-quick-reserve');
    if (btnQuickReserve) {
      btnQuickReserve.addEventListener('click', () => {
        switchTab('shipments');
        const shipmentsBtn = document.getElementById('nav-btn-shipments');
        if (shipmentsBtn) shipmentsBtn.focus();
      });
    }
  }

  function switchTab(tabId) {
    state.currentTab = tabId;

    const navButtons = document.querySelectorAll('.main-nav .nav-item-btn');
    const tabPanes = document.querySelectorAll('.tab-viewport .tab-pane');

    navButtons.forEach((btn) => {
      const isTarget = btn.getAttribute('data-tab') === tabId;
      btn.setAttribute('aria-selected', isTarget ? 'true' : 'false');
      btn.setAttribute('tabindex', isTarget ? '0' : '-1');
    });

    tabPanes.forEach((pane) => {
      if (pane.id === `tab-${tabId}`) {
        pane.classList.add('active');
      } else {
        pane.classList.remove('active');
      }
    });

    if (tabId === 'territory' && state.map && state.map.map) {
      setTimeout(() => {
        state.map.map.invalidateSize();
      }, 100);
    }
  }

  // --- Módulo Cartográfico (Território) ---

  function initMap() {
    if (typeof window.RaizMap === 'undefined') return;

    state.map = new window.RaizMap('map');
    state.map.init();

    // Controles de camadas
    const toggleLimits = document.getElementById('layer-toggle-limits');
    if (toggleLimits) {
      toggleLimits.addEventListener('change', (e) => {
        state.map.toggleLayer('limits', e.target.checked);
      });
    }

    const toggleAlerts = document.getElementById('layer-toggle-alerts');
    if (toggleAlerts) {
      toggleAlerts.addEventListener('change', (e) => {
        state.map.toggleLayer('alerts', e.target.checked);
      });
    }

    const toggleDemo = document.getElementById('layer-toggle-demo');
    if (toggleDemo) {
      toggleDemo.addEventListener('change', (e) => {
        state.map.toggleLayer('demo', e.target.checked);
      });
    }

    // Botões de ação do mapa
    const btnFit = document.getElementById('btn-fit-municipality');
    if (btnFit) {
      btnFit.addEventListener('click', () => state.map.focusMunicipality());
    }

    const btnFocusDemo = document.getElementById('btn-focus-demo');
    if (btnFocusDemo) {
      btnFocusDemo.addEventListener('click', () => state.map.focusDemo());
    }

    const btnToggleBase = document.getElementById('btn-toggle-base');
    if (btnToggleBase) {
      btnToggleBase.addEventListener('click', () => state.map.toggleBaseLayer());
    }

    // Callback de seleção de alerta DETER no mapa
    state.map.onAlertSelect((props) => {
      displayFeatureDrawer('Alerta DETER (INPE)', [
        { label: 'Identificador (GID)', value: props.gid || 'N/A' },
        { label: 'Classe de Alerta', value: props.classname || 'Desmatamento' },
        { label: 'Data de Observação', value: props.view_date || 'N/A' },
        { label: 'Sensor / Satélite', value: `${props.sensor || ''} (${props.satellite || ''})` },
        { label: 'Área Municipal (km²)', value: `${formatNumber(props.areamunkm || 0, 3)} km²` },
        { label: 'Município / UF', value: `${props.municipality || 'Itacoatiara'} / ${props.uf || 'AM'}` },
        { label: 'Fonte Oficial', value: 'INPE TerraBrasilis WFS' }
      ]);
    });

    // Callback de seleção de elemento do cenário demo
    state.map.onDemoSelect((props) => {
      highlightCustodyNode(props.id);
      displayFeatureDrawer(`Cenário Demo: ${props.name}`, [
        { label: 'Identificador', value: props.id },
        { label: 'Tipo de Elemento', value: props.kind },
        { label: 'Lote Associado', value: props.lot_id },
        { label: 'Natureza', value: 'Demonstrativo Técnico (Simulado)' }
      ]);
    });

    // Drawer close
    const btnCloseDrawer = document.getElementById('btn-close-drawer');
    if (btnCloseDrawer) {
      btnCloseDrawer.addEventListener('click', () => {
        const drawer = document.getElementById('feature-drawer');
        if (drawer) drawer.classList.remove('visible');
      });
    }

    // Interação com a timeline de custódia
    const custodyNodes = document.querySelectorAll('.custody-node');
    custodyNodes.forEach((node) => {
      node.addEventListener('click', () => {
        const id = node.getAttribute('data-id');
        highlightCustodyNode(id);
        if (state.map) {
          state.map.highlightCustodyPath();
          state.map.focusDemo();
        }
      });
    });
  }

  function highlightCustodyNode(nodeId) {
    const custodyNodes = document.querySelectorAll('.custody-node');
    custodyNodes.forEach((n) => {
      if (n.getAttribute('data-id') === nodeId) {
        n.classList.add('active');
      } else {
        n.classList.remove('active');
      }
    });
  }

  function displayFeatureDrawer(title, rows) {
    const drawer = document.getElementById('feature-drawer');
    const titleEl = document.getElementById('drawer-feature-title');
    const contentEl = document.getElementById('drawer-feature-content');

    if (!drawer || !titleEl || !contentEl) return;

    titleEl.textContent = title;
    contentEl.textContent = '';

    const table = document.createElement('table');
    table.style.width = '100%';
    table.style.fontSize = '12px';
    table.style.marginTop = '6px';

    rows.forEach((r) => {
      const tr = document.createElement('tr');
      const tdLabel = document.createElement('td');
      tdLabel.style.fontWeight = '600';
      tdLabel.style.color = 'var(--color-ink-secondary)';
      tdLabel.style.padding = '3px 0';
      tdLabel.textContent = r.label;

      const tdVal = document.createElement('td');
      tdVal.style.textAlign = 'right';
      tdVal.style.padding = '3px 0';
      tdVal.textContent = r.value;

      tr.appendChild(tdLabel);
      tr.appendChild(tdVal);
      table.appendChild(tr);
    });

    contentEl.appendChild(table);
    drawer.classList.add('visible');
  }

  // --- Filtros DETER (Classe e Intervalo de Datas) ---

  function initDeterFilters() {
    const classFilter = document.getElementById('deter-filter-class');
    const startDateFilter = document.getElementById('deter-filter-start');
    const endDateFilter = document.getElementById('deter-filter-end');
    const btnClear = document.getElementById('btn-clear-deter-filters');

    if (classFilter) {
      classFilter.addEventListener('change', applyDeterFilters);
    }
    if (startDateFilter) {
      startDateFilter.addEventListener('change', applyDeterFilters);
    }
    if (endDateFilter) {
      endDateFilter.addEventListener('change', applyDeterFilters);
    }
    if (btnClear) {
      btnClear.addEventListener('click', () => {
        if (classFilter) classFilter.value = 'ALL';
        if (startDateFilter) startDateFilter.value = '';
        if (endDateFilter) endDateFilter.value = '';
        applyDeterFilters();
      });
    }
  }

  function applyDeterFilters() {
    const classFilter = document.getElementById('deter-filter-class');
    const startDateFilter = document.getElementById('deter-filter-start');
    const endDateFilter = document.getElementById('deter-filter-end');

    const selectedClass = classFilter ? classFilter.value : 'ALL';
    const startDate = startDateFilter ? startDateFilter.value : '';
    const endDate = endDateFilter ? endDateFilter.value : '';

    const all = state.allAlertFeatures || [];
    const filtered = all.filter((f) => {
      const p = f.properties || {};
      if (selectedClass && selectedClass !== 'ALL' && p.classname !== selectedClass) {
        return false;
      }
      if (startDate && p.view_date && p.view_date < startDate) {
        return false;
      }
      if (endDate && p.view_date && p.view_date > endDate) {
        return false;
      }
      return true;
    });

    if (state.map) {
      state.map.filterAlerts(filtered);
    }

    renderAccessibleAlertsList(filtered);

    // Contagem e rótulo no badge de alertas
    const counterBadge = document.getElementById('deter-counter-badge');
    if (counterBadge) {
      const deterSource = state.territory && state.territory.sources
        ? state.territory.sources.find((s) => s.id === 'deter_alerts')
        : null;
      const totalAvailable = (deterSource && deterSource.total_available)
        || (state.territory && state.territory.proximity && state.territory.proximity.total_available)
        || 815;
      const evaluatedCount = all.length || 200;

      if (selectedClass && selectedClass !== 'ALL') {
        counterBadge.textContent = `${filtered.length} de ${evaluatedCount} alertas · ${selectedClass} (recorte de ${totalAvailable} na fonte)`;
      } else {
        counterBadge.textContent = `Exibindo ${filtered.length} de ${evaluatedCount} alertas (recorte de ${totalAvailable} na fonte)`;
      }
    }
  }

  function renderAccessibleAlertsList(features) {
    const container = document.getElementById('deter-accessible-list');
    if (!container) return;
    container.textContent = '';

    if (!features || features.length === 0) {
      container.textContent = 'Nenhum alerta DETER para o filtro selecionado.';
      return;
    }

    const list = document.createElement('ul');
    list.style.listStyle = 'none';
    list.style.padding = '0';
    list.style.margin = '0';

    const slice = features.slice(0, 200);
    slice.forEach((f) => {
      const p = f.properties || {};
      const li = document.createElement('li');
      li.className = 'deter-alert-item';
      li.setAttribute('tabindex', '0');
      li.setAttribute('role', 'button');
      li.style.padding = '6px 8px';
      li.style.borderBottom = '1px solid var(--color-border-subtle)';
      li.style.fontSize = '12px';
      li.style.display = 'flex';
      li.style.justifyContent = 'space-between';
      li.style.cursor = 'pointer';

      const label = document.createElement('span');
      label.textContent = `${p.classname || 'Alerta'} (${p.view_date || 'N/D'})`;

      const area = document.createElement('span');
      area.className = 'num';
      area.textContent = `${formatNumber(p.areamunkm || 0, 2)} km²`;

      li.appendChild(label);
      li.appendChild(area);

      const onSelect = () => {
        if (state.map) state.map.focusAlert(f);
        displayFeatureDrawer(`Alerta DETER #${p.gid || ''}`, [
          { label: 'Identificador (GID)', value: p.gid || 'N/A' },
          { label: 'Classe de Alerta', value: p.classname || 'Desmatamento' },
          { label: 'Data de Observação', value: p.view_date || 'N/A' },
          { label: 'Sensor / Satélite', value: `${p.sensor || ''} (${p.satellite || ''})` },
          { label: 'Área Municipal (km²)', value: `${formatNumber(p.areamunkm || 0, 3)} km²` },
          { label: 'Município / UF', value: `${p.municipality || 'Itacoatiara'} / ${p.uf || 'AM'}` },
          { label: 'Fonte Oficial', value: 'INPE TerraBrasilis WFS' }
        ]);
      };

      li.addEventListener('click', onSelect);
      li.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onSelect();
        }
      });

      list.appendChild(li);
    });

    container.appendChild(list);
  }

  // --- Sincronização de Estado Operacional (/api/state) ---

  async function fetchState() {
    state.networkError = false;
    try {
      const res = await fetch('/api/state');
      if (!res.ok) throw new Error(`Falha HTTP ${res.status}`);
      const data = await res.json();

      state.lots = data.lots || [];
      state.shipments = data.shipments || [];
      state.assessments = data.assessments || [];
      state.events = data.events || [];
      state.integrity = data.integrity || { valid: true, count: 0 };

      renderStockBalances();
      renderPassportsTable();
      renderAssessmentsModule();
      renderAuditEvents();
      renderIntegrityHeader();
      updateReservationButtonsState();
    } catch (err) {
      console.warn('Erro ao carregar estado do servidor:', err);
      state.networkError = true;
      renderIntegrityHeader();
    }
  }

  function renderIntegrityHeader() {
    const badge = document.getElementById('header-integrity-badge');
    if (!badge) return;

    if (state.networkError) {
      badge.className = 'integrity-badge error';
      badge.innerHTML = 'Estado indisponível — <button type="button" id="btn-retry-state" class="badge-retry-btn">tentar novamente</button>';
      const btnRetry = document.getElementById('btn-retry-state');
      if (btnRetry) {
        btnRetry.addEventListener('click', (e) => {
          e.stopPropagation();
          badge.className = 'integrity-badge';
          badge.textContent = 'Verificando cadeia…';
          fetchState();
        });
      }
      return;
    }

    const count = (state.integrity && state.integrity.count) || (state.events && state.events.length) || 0;
    if (state.integrity && state.integrity.valid) {
      badge.className = 'integrity-badge';
      badge.textContent = `Cadeia verificada · ${count} eventos`;
    } else {
      badge.className = 'integrity-badge divergent';
      badge.textContent = 'Cadeia com divergência';
    }
  }

  function updateReservationButtonsState() {
    const demoLot = state.lots.find((l) => l.id === 'AM-DEMO-001') || state.lots[0];
    const canReserve = Boolean(demoLot && state.integrity && state.integrity.valid);

    const btnSubmit = document.getElementById('btn-submit-shipment');
    if (btnSubmit) {
      btnSubmit.disabled = !canReserve;
    }

    const btnQuick = document.getElementById('btn-quick-reserve');
    if (btnQuick) {
      btnQuick.disabled = !canReserve;
    }
  }

  function renderStockBalances() {
    const demoLot = state.lots.find((l) => l.id === 'AM-DEMO-001') || state.lots[0];
    if (!demoLot) return;

    const elAvail = document.getElementById('dossier-available-volume');
    const elOpening = document.getElementById('dossier-opening-volume');
    const elReserved = document.getElementById('dossier-reserved-volume');

    if (elAvail) elAvail.textContent = `${formatMilli(demoLot.available_milli)} m³`;
    if (elOpening) elOpening.textContent = `${formatMilli(demoLot.opening_milli)} m³`;
    if (elReserved) elReserved.textContent = `${formatMilli(demoLot.reserved_milli)} m³`;
  }

  // --- Carga de Território (/api/territory) e Análise Espacial/Proximidade ---

  async function fetchTerritory() {
    try {
      const res = await fetch('/api/territory');
      if (!res.ok) throw new Error(`Falha HTTP ${res.status}`);
      const data = await res.json();
      state.territory = data;
      state.allAlertFeatures = (data.alerts && data.alerts.features) || [];

      if (state.map) {
        state.map.setTerritoryData(data);
      }

      applyDeterFilters();
      renderSpatialAndProximity();
      renderSourcesTable(data.sources);

      // Atualiza data de consulta real no status do mapa
      const mapSourceEl = document.getElementById('map-source-text');
      if (mapSourceEl) {
        const deterSource = (data.sources || []).find((s) => s.id === 'deter_alerts');
        const fetchedAt = (deterSource && deterSource.fetched_at)
          || (data.spatial && data.spatial.source_fetched_at)
          || 'Recente';
        let latestObs = '2026-10-23';
        if (state.allAlertFeatures.length > 0) {
          latestObs = state.allAlertFeatures[0].properties.view_date || latestObs;
        }
        mapSourceEl.textContent = `Fonte: INPE DETER TerraBrasilis WFS · Consulta: ${fetchedAt} · Última obs: ${latestObs}`;
      }
    } catch (err) {
      console.warn('Erro ao carregar território:', err);
    }
  }

  function renderSpatialAndProximity() {
    const container = document.getElementById('spatial-info-content');
    if (!container) return;
    container.textContent = '';

    const territory = state.territory;
    if (!territory) return;

    const prox = territory.proximity;
    const spatial = territory.spatial;

    if (!prox || (spatial && spatial.status === 'not_evaluated')) {
      const unav = document.createElement('div');
      unav.style.fontSize = '12px';
      unav.style.color = 'var(--color-ink-secondary)';
      unav.textContent = 'Não avaliado — fonte indisponível. Ausência de dados não confirma regularidade.';

      const notice = document.createElement('div');
      notice.className = 'spatial-notice-box';
      notice.textContent = (spatial && spatial.notice) || 'Fonte de alertas territoriais indisponível no momento.';

      container.appendChild(unav);
      container.appendChild(notice);
      return;
    }

    // 1. Linha sobreposições
    const lineOverlap = document.createElement('div');
    lineOverlap.style.fontSize = '13px';
    const alertEv = prox.alerts_evaluated || (territory.alerts && territory.alerts.features && territory.alerts.features.length) || 200;
    const alertTot = prox.total_available || 815;
    lineOverlap.innerHTML = `<strong>Sobreposição com a área:</strong> <span class="num">${spatial.count}</span> alertas (recorte de ${alertEv} de ${alertTot})`;
    container.appendChild(lineOverlap);

    // 2. Linha alerta mais próximo
    if (prox.nearest) {
      const lineNearest = document.createElement('div');
      lineNearest.style.fontSize = '13px';
      lineNearest.style.marginTop = '4px';
      lineNearest.innerHTML = `<strong>Alerta mais próximo:</strong> <span class="num">${formatNumber(prox.nearest.distance_km, 1)} km</span> · ${escapeHtml(prox.nearest.classname)} · ${escapeHtml(prox.nearest.view_date)}`;
      container.appendChild(lineNearest);
    }

    // 3. Contagens por raio
    if (prox.within && prox.within.length > 0) {
      const lineRadius = document.createElement('div');
      lineRadius.style.fontSize = '13px';
      lineRadius.style.marginTop = '4px';
      const countsStr = prox.within.map((w) => `≤${w.radius_km} km (<span class="num">${w.count}</span>)`).join(', ');
      lineRadius.innerHTML = `<strong>Contagem por raio:</strong> ${countsStr}`;
      container.appendChild(lineRadius);
    }

    // 4. Área dentro do município IBGE
    const lineMuni = document.createElement('div');
    lineMuni.style.fontSize = '13px';
    lineMuni.style.marginTop = '4px';
    const insideText = prox.plot_inside_municipality ? 'sim' : 'não';
    lineMuni.innerHTML = `<strong>Área dentro do município IBGE:</strong> ${insideText}`;
    container.appendChild(lineMuni);

    // 5. Lista dos 5 alertas mais próximos como botões
    if (prox.closest && prox.closest.length > 0) {
      const closestSection = document.createElement('div');
      closestSection.style.marginTop = '8px';

      const closestTitle = document.createElement('div');
      closestTitle.style.fontSize = '12px';
      closestTitle.style.fontWeight = '600';
      closestTitle.style.color = 'var(--color-ink-secondary)';
      closestTitle.style.marginBottom = '6px';
      closestTitle.textContent = 'Alertas mais próximos (clique para focar):';
      closestSection.appendChild(closestTitle);

      const btnGroup = document.createElement('div');
      btnGroup.className = 'proximity-alerts-list';

      prox.closest.forEach((item) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'proximity-alert-btn';
        btn.innerHTML = `<span class="num">${formatNumber(item.distance_km, 1)} km</span> · ${escapeHtml(item.classname)} (${escapeHtml(item.view_date)})`;
        btn.addEventListener('click', () => {
          if (territory.alerts && territory.alerts.features) {
            const feat = territory.alerts.features.find((f) => (f.properties && f.properties.gid === item.gid) || f.id === item.gid);
            if (feat && state.map) {
              state.map.focusAlert(feat);
              displayFeatureDrawer(`Alerta DETER #${item.gid}`, [
                { label: 'Identificador (GID)', value: item.gid },
                { label: 'Classe de Alerta', value: item.classname },
                { label: 'Data de Observação', value: item.view_date },
                { label: 'Distância da Parcela', value: `${formatNumber(item.distance_km, 2)} km` },
                { label: 'Status Espacial', value: 'Proximidade Aferida (Sem Sobreposição)' },
                { label: 'Fonte Oficial', value: 'INPE TerraBrasilis WFS' }
              ]);
            }
          }
        });
        btnGroup.appendChild(btn);
      });

      closestSection.appendChild(btnGroup);
      container.appendChild(closestSection);
    }

    // 6. Aviso / Notice curto
    const noticeText = prox.notice || (spatial && spatial.notice) || '';
    if (noticeText) {
      const noticeEl = document.createElement('div');
      noticeEl.className = 'spatial-notice-box';
      noticeEl.textContent = noticeText;
      container.appendChild(noticeEl);
    }
  }

  // --- Módulo Cargas e Reservas Idempotentes ---

  function initShipmentsModule() {
    updateIdempotencyKeyDisplay();

    const btnNewKey = document.getElementById('btn-new-idempotency');
    if (btnNewKey) {
      btnNewKey.addEventListener('click', () => {
        state.activeIdempotencyKey = generateUUID();
        updateIdempotencyKeyDisplay();
      });
    }

    const formShipment = document.getElementById('form-shipment');
    if (formShipment) {
      formShipment.addEventListener('submit', async (e) => {
        e.preventDefault();
        await handleShipmentSubmit();
      });
    }
  }

  function updateIdempotencyKeyDisplay() {
    const el = document.getElementById('shipment-idempotency-key');
    if (el) el.textContent = state.activeIdempotencyKey;
  }

  async function handleShipmentSubmit() {
    const feedback = document.getElementById('shipment-feedback');
    const btnSubmit = document.getElementById('btn-submit-shipment');
    if (feedback) {
      feedback.className = 'feedback-box shipment-feedback';
      feedback.textContent = '';
    }

    const lotId = document.getElementById('shipment-lot-id').value;
    const volumeVal = parseFloat(document.getElementById('shipment-volume').value);
    const invoiceVal = document.getElementById('shipment-invoice').value.trim();
    const recipientVal = document.getElementById('shipment-recipient').value.trim();
    const vehicleVal = document.getElementById('shipment-vehicle').value.trim();
    const grossVal = parseFloat(document.getElementById('shipment-gross').value) || 0;
    const tareVal = parseFloat(document.getElementById('shipment-tare').value) || 0;

    if (isNaN(volumeVal) || volumeVal <= 0) {
      showShipmentFeedback('Informe um volume válido maior que zero.', 'error');
      return;
    }

    const payload = {
      lot_id: lotId,
      volume_m3: String(volumeVal),
      invoice: invoiceVal,
      recipient: recipientVal,
      vehicle: vehicleVal,
      gross_kg: grossVal,
      tare_kg: tareVal
    };

    if (btnSubmit) btnSubmit.disabled = true;

    try {
      const res = await fetch('/api/shipments', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Idempotency-Key': state.activeIdempotencyKey
        },
        body: JSON.stringify(payload)
      });

      const data = await res.json();

      if (!res.ok) {
        const errorMsg = (data.error && data.error.message) || 'Falha ao processar reserva.';
        showShipmentFeedback(errorMsg, 'error');
        return;
      }

      // Sucesso na emissão
      showShipmentFeedback(
        `Passaporte emitido com sucesso! ID: ${data.id}. Saldo restante: ${formatMilli(data.balance_after_milli)} m³.`,
        'success'
      );

      // Nova chave gerada após operação bem sucedida
      state.activeIdempotencyKey = generateUUID();
      updateIdempotencyKeyDisplay();

      // Atualiza estado e tabela de passaportes
      await fetchState();
    } catch (err) {
      showShipmentFeedback(`Erro de comunicação com o servidor: ${err.message}`, 'error');
    } finally {
      if (btnSubmit) btnSubmit.disabled = false;
    }
  }

  function showShipmentFeedback(msg, type) {
    const feedback = document.getElementById('shipment-feedback');
    if (!feedback) return;
    feedback.textContent = msg;
    feedback.className = `feedback-box shipment-feedback visible ${type}`;
  }

  function renderPassportsTable() {
    const tbody = document.getElementById('passports-tbody');
    if (!tbody) return;
    tbody.textContent = '';

    if (!state.shipments || state.shipments.length === 0) {
      const tr = document.createElement('tr');
      const td = document.createElement('td');
      td.colSpan = 6;
      td.style.textAlign = 'center';
      td.style.color = 'var(--color-ink-secondary)';
      td.style.padding = '16px';
      td.textContent = 'Nenhum passaporte emitido nesta sessão de teste.';
      tr.appendChild(td);
      tbody.appendChild(tr);
      return;
    }

    state.shipments.forEach((p) => {
      const tr = document.createElement('tr');

      // ID
      const tdId = document.createElement('td');
      tdId.style.fontWeight = '600';
      tdId.textContent = p.id;

      // Lote
      const tdLot = document.createElement('td');
      tdLot.textContent = p.lot_id || 'AM-DEMO-001';

      // Volume
      const tdVol = document.createElement('td');
      tdVol.className = 'num';
      tdVol.textContent = `${formatNumber(p.volume_m3, 3)} m³`;

      // Saldo após
      const tdBal = document.createElement('td');
      tdBal.className = 'num';
      tdBal.textContent = `${formatMilli(p.balance_after_milli)} m³`;

      // Hash SHA256 truncado
      const tdHash = document.createElement('td');
      tdHash.style.fontFamily = 'monospace';
      tdHash.style.fontSize = '12px';
      tdHash.textContent = (p.hash || '').substring(0, 16) + '...';

      // Ações (Download e Impressão)
      const tdActions = document.createElement('td');
      const actionsWrap = document.createElement('div');
      actionsWrap.className = 'table-actions';

      // Link download JSON via endpoint oficial /api/passports/{id}
      const btnDownload = document.createElement('a');
      btnDownload.className = 'passport-download-btn';
      btnDownload.href = `/api/passports/${encodeURIComponent(p.id)}`;
      btnDownload.setAttribute('download', `passaporte-${p.id}.json`);
      btnDownload.textContent = 'Baixar JSON';

      // Link impressão oficial /passport/{id}
      const btnPrint = document.createElement('a');
      btnPrint.className = 'passport-print-btn';
      btnPrint.href = `/passport/${encodeURIComponent(p.id)}`;
      btnPrint.target = '_blank';
      btnPrint.rel = 'noopener';
      btnPrint.textContent = 'Imprimir';

      actionsWrap.appendChild(btnDownload);
      actionsWrap.appendChild(btnPrint);
      tdActions.appendChild(actionsWrap);

      tr.appendChild(tdId);
      tr.appendChild(tdLot);
      tr.appendChild(tdVol);
      tr.appendChild(tdBal);
      tr.appendChild(tdHash);
      tr.appendChild(tdActions);

      tbody.appendChild(tr);
    });
  }

  // --- Módulo Balança e Verificação Físico-Volumétrica ---

  function initWeighModule() {
    const formWeigh = document.getElementById('form-weigh');
    if (formWeigh) {
      formWeigh.addEventListener('submit', async (e) => {
        e.preventDefault();
        await handleWeighSubmit();
      });
    }
  }

  async function handleWeighSubmit() {
    const vol = parseFloat(document.getElementById('weigh-volume').value);
    const gross = parseFloat(document.getElementById('weigh-gross').value);
    const tare = parseFloat(document.getElementById('weigh-tare').value);
    const resultCard = document.getElementById('weigh-result');

    if (isNaN(vol) || isNaN(gross) || isNaN(tare)) return;

    try {
      const res = await fetch('/api/weigh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ volume_m3: vol, gross_kg: gross, tare_kg: tare })
      });

      const data = await res.json();
      if (!res.ok) {
        resultCard.textContent = `Erro: ${(data.error && data.error.message) || 'Falha no cálculo'}`;
        resultCard.className = 'result-card weigh-result visible';
        return;
      }

      resultCard.textContent = '';
      const pill = document.createElement('span');
      pill.className = `result-pill ${data.status}`;
      pill.textContent = data.status === 'compatible' ? 'Compatível com volume' : 'Divergente / Incompatível';

      const pInfo = document.createElement('div');
      pInfo.style.marginTop = '6px';
      pInfo.innerHTML = `
        <div><strong>Peso Líquido Aferido:</strong> <span class="num">${formatNumber(data.net_kg, 0)} kg</span> (${formatNumber(data.net_t, 2)} t)</div>
        <div><strong>Faixa Teórica Permitida:</strong> <span class="num">${formatNumber(data.min_kg, 0)} kg a ${formatNumber(data.max_kg, 0)} kg</span></div>
        <div><strong>Diferença em Relação aos Limites:</strong> <span class="num">${formatNumber(data.difference_kg, 0)} kg</span></div>
        <div style="margin-top: 6px; font-size: 12px; color: var(--color-ink-secondary);">Fórmula: ${escapeHtml(data.formula)}</div>
        <div style="margin-top: 6px; font-size: 12px; color: var(--color-amber);">Aviso: ${escapeHtml(data.notice)}</div>
      `;

      resultCard.appendChild(pill);
      resultCard.appendChild(pInfo);
      resultCard.className = 'result-card weigh-result visible';
    } catch (err) {
      resultCard.textContent = `Erro de conexão: ${err.message}`;
      resultCard.className = 'result-card weigh-result visible';
    }
  }

  // --- Módulo Revisão Técnica (SIM-001) ---

  function initReviewModule() {
    const formAssessment = document.getElementById('form-assessment');
    if (formAssessment) {
      formAssessment.addEventListener('submit', async (e) => {
        e.preventDefault();
        await handleAssessmentSubmit();
      });
    }

    const formReview = document.getElementById('form-review');
    if (formReview) {
      formReview.addEventListener('submit', async (e) => {
        e.preventDefault();
        await handleReviewSubmit();
      });
    }
  }

  async function handleAssessmentSubmit() {
    const qty = parseFloat(document.getElementById('assessment-qty').value);
    const hyp = document.getElementById('assessment-hypothesis').value.trim();
    const rev = document.getElementById('assessment-reviewer').value.trim();

    try {
      const res = await fetch('/api/assessments', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ quantity_m3: qty, hypothesis: hyp, reviewer: rev })
      });

      const data = await res.json();
      if (!res.ok) {
        alert((data.error && data.error.message) || 'Erro ao simular avaliação');
        return;
      }

      state.assessments.push(data);
      renderAssessmentsModule();
    } catch (err) {
      alert(`Falha: ${err.message}`);
    }
  }

  async function handleReviewSubmit() {
    const targetSelect = document.getElementById('review-target-id');
    const assessmentId = targetSelect.value;
    const author = document.getElementById('review-author').value.trim();
    const decision = document.getElementById('review-decision').value;
    const reason = document.getElementById('review-reason').value.trim();
    const feedback = document.getElementById('review-feedback');
    const definitiveState = document.getElementById('review-definitive-state');

    feedback.className = 'feedback-box review-feedback';
    feedback.textContent = '';

    // Validação estrita: motivação é OBRIGATÓRIA
    if (!reason) {
      feedback.textContent = 'A motivação e justificativa técnica é obrigatória para homologação de parecer.';
      feedback.className = 'feedback-box review-feedback visible error';
      return;
    }

    if (!author) {
      feedback.textContent = 'Identificação do parecerista é obrigatória.';
      feedback.className = 'feedback-box review-feedback visible error';
      return;
    }

    try {
      const res = await fetch('/api/review', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          assessment_id: assessmentId,
          decision: decision,
          reviewer: author,
          reason: reason
        })
      });

      const data = await res.json();
      if (!res.ok) {
        feedback.textContent = (data.error && data.error.message) || 'Falha ao registrar parecer.';
        feedback.className = 'feedback-box review-feedback visible error';
        return;
      }

      // Renderiza estado definitivo
      const decisionLabel = decision === 'agree' ? 'Concordância (agree)' : 'Discordância (disagree)';
      definitiveState.innerHTML = `
        <span class="result-pill compatible">Revisão simulada registrada: ${decisionLabel}</span>
        <div style="margin-top: 6px;"><strong>Parecerista:</strong> ${escapeHtml(author)}</div>
        <div><strong>Data UTC:</strong> ${new Date().toISOString()}</div>
        <div style="margin-top: 4px;"><strong>Justificativa Técnica:</strong> ${escapeHtml(reason)}</div>
        <div style="margin-top: 6px; font-size: 12px; color: var(--color-ink-secondary);">Decisão registrada no histórico transacional do sistema.</div>
      `;
      definitiveState.className = 'result-card review-definitive-state visible';

      await fetchState();
    } catch (err) {
      feedback.textContent = `Erro ao salvar parecer: ${err.message}`;
      feedback.className = 'feedback-box review-feedback visible error';
    }
  }

  function renderAssessmentsModule() {
    const select = document.getElementById('review-target-id');
    const container = document.getElementById('assessments-list-container');
    if (!select || !container) return;

    select.textContent = '';
    container.textContent = '';

    if (!state.assessments || state.assessments.length === 0) {
      select.innerHTML = '<option value="">Nenhum apontamento disponível</option>';
      container.innerHTML = '<p style="font-size: 13px; color: var(--color-ink-secondary);">Nenhum apontamento pendente no momento.</p>';
      return;
    }

    state.assessments.forEach((asm) => {
      const opt = document.createElement('option');
      opt.value = asm.id;
      opt.textContent = `${asm.id} (${asm.rule_id || 'SIM-001'} - ${asm.quantity_m3 || 0} m³) - ${asm.status || 'pendente'}`;
      select.appendChild(opt);

      const div = document.createElement('div');
      div.className = 'assessment-item';
      div.style.padding = '10px 12px';
      div.style.marginBottom = '8px';
      div.style.border = '1px solid var(--color-border)';
      div.style.borderRadius = 'var(--radius-sm)';
      div.style.backgroundColor = 'var(--color-surface-white)';
      div.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <strong>${escapeHtml(asm.id)} — Regra ${escapeHtml(asm.rule_id || 'SIM-001')}</strong>
          <span class="result-pill ${asm.status === 'agreed' || asm.status === 'disagreed' ? 'compatible' : 'inconclusive'}">${escapeHtml(asm.status || 'pendente')}</span>
        </div>
        <div style="font-size: 12px; margin-top: 4px;">Volume: <span class="num">${asm.quantity_m3} m³</span> | Multa Paramétrica: <span class="num">R$ ${formatNumber(asm.fine_brl, 2)}</span></div>
        <div style="font-size: 12px; color: var(--color-ink-secondary); margin-top: 2px;">Hipótese: ${escapeHtml(asm.hypothesis || '')}</div>
      `;
      container.appendChild(div);
    });
  }

  // --- Módulo Laboratório (Inventário + ML) ---

  function initLabModule() {
    const formInventory = document.getElementById('form-inventory');
    if (formInventory) {
      formInventory.addEventListener('submit', async (e) => {
        e.preventDefault();
        await handleInventorySubmit();
      });
    }

    const formMl = document.getElementById('form-ml');
    if (formMl) {
      formMl.addEventListener('submit', async (e) => {
        e.preventDefault();
        await handleMlSubmit([
          parseFloat(document.getElementById('ml-signal-1').value),
          parseFloat(document.getElementById('ml-signal-2').value),
          parseFloat(document.getElementById('ml-signal-3').value)
        ]);
      });
    }

    const btnDistant = document.getElementById('btn-ml-distant');
    if (btnDistant) {
      btnDistant.addEventListener('click', async () => {
        document.getElementById('ml-signal-1').value = '999';
        document.getElementById('ml-signal-2').value = '999';
        document.getElementById('ml-signal-3').value = '999';
        await handleMlSubmit([999, 999, 999]);
      });
    }
  }

  async function handleInventorySubmit() {
    const d = parseFloat(document.getElementById('inv-diameter').value);
    const h = parseFloat(document.getElementById('inv-height').value);
    const f = parseFloat(document.getElementById('inv-form').value);
    const resultCard = document.getElementById('inventory-result');

    try {
      const res = await fetch('/api/inventory', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ diameter_cm: d, height_m: h, form_factor: f })
      });

      const data = await res.json();
      if (!res.ok) {
        resultCard.textContent = `Erro: ${(data.error && data.error.message) || 'Falha no cálculo'}`;
        resultCard.className = 'result-card inventory-result visible';
        return;
      }

      resultCard.innerHTML = `
        <div><strong>Volume Comercial Estimado:</strong> <span class="num" style="font-size: 16px; color: var(--color-forest);">${formatNumber(data.volume_m3, 3)} m³</span></div>
        <div><strong>Faixa de Biomassa Teórica:</strong> <span class="num">${formatNumber(data.min_mass_t, 3)} t a ${formatNumber(data.max_mass_t, 3)} t</span></div>
        <div style="font-size: 12px; color: var(--color-ink-secondary); margin-top: 4px;">Fórmula: ${escapeHtml(data.formula)}</div>
        <div style="font-size: 12px; color: var(--color-amber); margin-top: 6px;">Aviso: ${escapeHtml(data.notice)}</div>
      `;
      resultCard.className = 'result-card inventory-result visible';
    } catch (err) {
      resultCard.textContent = `Falha: ${err.message}`;
      resultCard.className = 'result-card inventory-result visible';
    }
  }

  async function fetchMlModel() {
    try {
      const res = await fetch('/api/ml/model');
      if (!res.ok) return;
      state.mlModel = await res.json();
    } catch (_e) {
      // ignore
    }
  }

  async function handleMlSubmit(features) {
    const resultCard = document.getElementById('ml-result');
    try {
      const res = await fetch('/api/ml', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ features: features })
      });

      const data = await res.json();
      if (!res.ok) {
        resultCard.textContent = `Erro: ${(data.error && data.error.message) || 'Falha na predição'}`;
        resultCard.className = 'result-card ml-result visible';
        return;
      }

      const isClassified = data.status === 'classified';
      const statusLabel = isClassified ? 'Classificado (classified)' : 'Inconclusivo / Abstenção (inconclusive)';
      resultCard.innerHTML = `
        <span class="result-pill ${isClassified ? 'compatible' : 'inconclusive'}">Status: ${statusLabel}</span>
        <div style="margin-top: 6px;"><strong>Perfil Sintético Atribuído:</strong> ${escapeHtml(data.label || 'Nenhum (Abstenção)')}</div>
        <div><strong>Distância ao Vizinho Mais Próximo:</strong> <span class="num">${formatNumber(data.distance, 2)}</span></div>
        <div><strong>Concordância de Vizinhos (k-NN):</strong> <span class="num">${Math.round((data.neighbor_agreement || 0) * 100)}%</span></div>
        <div style="margin-top: 6px; font-size: 12px; color: var(--color-amber);">Aviso: ${escapeHtml(data.notice)}</div>
        <div style="margin-top: 4px; font-size: 12px; color: var(--color-ink-secondary);">Ressalva: NUNCA identifica espécies botânicas reais.</div>
      `;
      resultCard.className = 'result-card ml-result visible';
    } catch (err) {
      resultCard.textContent = `Falha: ${err.message}`;
      resultCard.className = 'result-card ml-result visible';
    }
  }

  // --- Módulo Histórico e Fontes ---

  function initSourcesModule() {
    const btnRefresh = document.getElementById('btn-refresh-sources');
    if (btnRefresh) {
      btnRefresh.addEventListener('click', async () => {
        btnRefresh.disabled = true;
        btnRefresh.textContent = 'Atualizando fontes...';
        try {
          const res = await fetch('/api/sources/refresh', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
          });
          const data = await res.json();
          if (res.ok) {
            state.territory = data;
            state.allAlertFeatures = (data.alerts && data.alerts.features) || [];
            if (state.map) state.map.setTerritoryData(data);
            applyDeterFilters();
            renderSpatialAndProximity();
            renderSourcesTable(data.sources);
            alert(data.notice || 'Fontes territoriais atualizadas com sucesso.');
          } else {
            alert((data.error && data.error.message) || 'Falha ao atualizar fontes.');
          }
        } catch (err) {
          alert(`Erro na atualização: ${err.message}`);
        } finally {
          btnRefresh.disabled = false;
          btnRefresh.textContent = 'Atualizar fontes públicas';
        }
      });
    }

    const btnVerifyAudit = document.getElementById('btn-verify-audit');
    if (btnVerifyAudit) {
      btnVerifyAudit.addEventListener('click', async () => {
        try {
          const res = await fetch('/api/audit');
          const data = await res.json();
          alert(`Auditoria de Integridade:\nStatus: ${data.valid ? '100% VÁLIDO' : 'INVÁLIDO'}\nTotal de eventos encadeados: ${data.count}`);
        } catch (err) {
          alert(`Erro: ${err.message}`);
        }
      });
    }
  }

  function renderSourcesTable(sources) {
    const tbody = document.getElementById('sources-tbody');
    if (!tbody || !sources) return;
    tbody.textContent = '';

    sources.forEach((s) => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><strong>${escapeHtml(s.id)}</strong></td>
        <td>${escapeHtml(s.name)}</td>
        <td style="font-size: 12px; word-break: break-all;">${escapeHtml(s.url)}</td>
        <td><span class="result-pill compatible">${escapeHtml(s.status)}</span></td>
        <td style="font-size: 12px;">${escapeHtml(s.fetched_at || '')}</td>
        <td>${s.partial ? `Recorte ${s.feature_count} de ${s.total_available || 815}` : `${s.feature_count} feições`}</td>
      `;
      tbody.appendChild(tr);
    });
  }

  function renderAuditEvents() {
    const tbody = document.getElementById('audit-events-tbody');
    if (!tbody) return;
    tbody.textContent = '';

    if (!state.events || state.events.length === 0) {
      tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: var(--color-ink-secondary); padding: 16px;">Nenhum evento registrado no livro.</td></tr>';
      return;
    }

    state.events.forEach((evt) => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><strong>${escapeHtml(evt.id)}</strong></td>
        <td style="font-size: 12px;">${escapeHtml(evt.timestamp || evt.at || '')}</td>
        <td><span class="result-pill compatible">${escapeHtml(evt.type)}</span></td>
        <td style="font-family: monospace; font-size: 12px;">${escapeHtml((evt.hash || '').substring(0, 24))}...</td>
      `;
      tbody.appendChild(tr);
    });
  }
})();
