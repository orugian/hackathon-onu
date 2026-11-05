/**
 * RAIZTRACE — Módulo Cartográfico Leaflet Local
 * Suporta camadas vetoriais IBGE/DETER e cenário demonstrativo.
 */

(function (window) {
  'use strict';

  // Coordenadas centrais de Itacoatiara/AM
  const ITACOATIARA_CENTER = [-3.1436, -58.4442];
  const DEFAULT_ZOOM = 10;

  class RaizMap {
    constructor(containerId) {
      this.containerId = containerId;
      this.map = null;
      this.baseTileLayer = null;
      this.baseLayerVisible = true;
      this.tileErrorCount = 0;

      this.layerLimits = null;
      this.layerAlerts = null;
      this.layerDemo = null;
      this.custodyHighlightLayer = null;
      this.alertHighlightLayer = null;

      this.territoryData = null;
      this.municipalityBounds = null;
      this.onAlertSelectCallback = null;
      this.onDemoSelectCallback = null;
    }

    init() {
      const container = document.getElementById(this.containerId);
      if (!container) return;

      if (typeof window.L === 'undefined') {
        console.warn('Leaflet não carregado.');
        return;
      }

      // Inicializa mapa do Leaflet
      this.map = window.L.map(this.containerId, {
        center: ITACOATIARA_CENTER,
        zoom: DEFAULT_ZOOM,
        zoomControl: true,
        attributionControl: true
      });

      // Escala métrica real
      window.L.control.scale({ metric: true, imperial: false, position: 'bottomleft' }).addTo(this.map);

      // Base OSM Tile Layer
      this.baseTileLayer = window.L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 18,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
      });

      this.baseTileLayer.on('tileerror', () => {
        this.tileErrorCount++;
        const statusEl = document.getElementById('map-base-text');
        if (statusEl && this.tileErrorCount > 2) {
          statusEl.textContent = 'Base OSM: Indisponível (Modo offline vetorial)';
        }
      });

      this.baseTileLayer.on('tileload', () => {
        const statusEl = document.getElementById('map-base-text');
        if (statusEl && this.tileErrorCount <= 2) {
          statusEl.textContent = 'Base OSM: Ativa';
        }
      });

      this.baseTileLayer.addTo(this.map);

      // Camadas vetoriais
      // Limites: Estado (codarea='13') tem preenchimento tênue; Município tem contorno forte
      this.layerLimits = window.L.geoJSON(null, {
        style: (feature) => {
          const isState = feature.properties && (feature.properties.codarea === '13' || feature.properties.id === '13');
          if (isState) {
            return { color: '#2b533f', weight: 1.5, fillOpacity: 0.03, fillColor: '#2b533f' };
          }
          return { color: '#173a2c', weight: 2.5, fillOpacity: 0.08, fillColor: '#387853' };
        }
      }).addTo(this.map);

      this.layerAlerts = window.L.geoJSON(null, {
        style: () => ({
          color: '#b45309',
          weight: 1.5,
          fillColor: '#d97706',
          fillOpacity: 0.45
        }),
        onEachFeature: (feature, layer) => {
          layer.on('click', () => {
            if (this.onAlertSelectCallback) {
              this.onAlertSelectCallback(feature.properties, feature);
            }
          });
        }
      }).addTo(this.map);

      this.layerDemo = window.L.geoJSON(null, {
        style: (feature) => {
          const kind = (feature.properties && feature.properties.kind) || '';
          if (kind === 'plot') {
            return { color: '#173a2c', weight: 2.5, fillColor: '#c5f67c', fillOpacity: 0.35, dashArray: '5, 5' };
          }
          if (kind === 'route') {
            return { color: '#173a2c', weight: 3, opacity: 0.85, dashArray: '6, 4' };
          }
          return { color: '#173a2c', weight: 2, fillColor: '#c5f67c', fillOpacity: 0.8 };
        },
        pointToLayer: (feature, latlng) => {
          const kind = (feature.properties && feature.properties.kind) || '';
          let radius = 6;
          let fillColor = '#c5f67c';
          if (kind === 'tree') {
            radius = 7;
            fillColor = '#84cc16';
          } else if (kind === 'yard') {
            radius = 8;
            fillColor = '#eab308';
          } else if (kind === 'destination') {
            radius = 9;
            fillColor = '#10b981';
          }
          return window.L.circleMarker(latlng, {
            radius: radius,
            color: '#173a2c',
            weight: 2,
            fillColor: fillColor,
            fillOpacity: 0.95
          });
        },
        onEachFeature: (feature, layer) => {
          layer.on('click', () => {
            if (this.onDemoSelectCallback) {
              this.onDemoSelectCallback(feature.properties, feature);
            }
            this.highlightCustodyPath();
          });
        }
      }).addTo(this.map);

      this.custodyHighlightLayer = window.L.layerGroup().addTo(this.map);
      this.alertHighlightLayer = window.L.layerGroup().addTo(this.map);

      // Adiciona legenda cartográfica
      this._addLegend();

      // Atualiza atributos de testabilidade no elemento DOM do mapa
      this._updateTestability();
      this.map.on('moveend zoomend', () => this._updateTestability());
    }

    _addLegend() {
      if (!this.map || typeof window.L.control !== 'function') return;
      const legend = window.L.control({ position: 'bottomright' });
      legend.onAdd = () => {
        const div = window.L.DomUtil.create('div', 'map-legend-control');
        const isMobile = window.innerWidth <= 768;
        const openAttr = isMobile ? '' : ' open';
        div.innerHTML = `
          <details class="legend-details"${openAttr}>
            <summary class="legend-title">Convenções</summary>
            <div class="legend-content">
              <div class="legend-item"><span class="legend-swatch muni-swatch"></span> Limite Itacoatiara (IBGE)</div>
              <div class="legend-item"><span class="legend-swatch alert-swatch"></span> Alerta DETER (INPE)</div>
              <div class="legend-item"><span class="legend-swatch plot-swatch"></span> Parcela Demo (Simulada)</div>
            </div>
          </details>
        `;
        return div;
      };
      legend.addTo(this.map);
    }

    _updateTestability() {
      const container = document.getElementById(this.containerId);
      if (!container || !this.map) return;
      try {
        const zoom = this.map.getZoom();
        const center = this.map.getCenter();
        const bounds = this.map.getBounds();
        container.dataset.zoom = String(zoom);
        container.dataset.centerLat = center.lat.toFixed(4);
        container.dataset.centerLng = center.lng.toFixed(4);
        if (bounds && bounds.isValid()) {
          container.dataset.bounds = `${bounds.getSouth().toFixed(4)},${bounds.getWest().toFixed(4)},${bounds.getNorth().toFixed(4)},${bounds.getEast().toFixed(4)}`;
        }
      } catch (_e) {
        // ignore
      }
    }

    setTerritoryData(data) {
      if (!this.map || !data) return;
      this.territoryData = data;

      // Limpa camadas
      this.layerLimits.clearLayers();
      this.layerAlerts.clearLayers();
      this.layerDemo.clearLayers();
      this.custodyHighlightLayer.clearLayers();
      this.alertHighlightLayer.clearLayers();

      // Adiciona limites estaduais (se presentes)
      if (data.state) {
        this.layerLimits.addData(data.state);
      }

      // Adiciona limites municipais e calcula bounds EXCLUSIVAMENTE do município
      if (data.municipality) {
        this.layerLimits.addData(data.municipality);
        const tempMuni = window.L.geoJSON(data.municipality);
        this.municipalityBounds = tempMuni.getBounds();
      }

      // Adiciona alertas DETER
      if (data.alerts) {
        this.layerAlerts.addData(data.alerts);
      }

      // Adiciona cenário demonstrativo
      if (data.demo) {
        this.layerDemo.addData(data.demo);
      }

      // Enquadra EXCLUSIVAMENTE o município de Itacoatiara
      if (this.municipalityBounds && this.municipalityBounds.isValid()) {
        try {
          this.map.fitBounds(this.municipalityBounds, { padding: [20, 20] });
        } catch (_e) {
          this.map.setView(ITACOATIARA_CENTER, DEFAULT_ZOOM);
        }
      } else {
        this.map.setView(ITACOATIARA_CENTER, DEFAULT_ZOOM);
      }

      this._updateTestability();
    }

    focusMunicipality() {
      if (!this.map) return;
      if (this.municipalityBounds && this.municipalityBounds.isValid()) {
        try {
          this.map.fitBounds(this.municipalityBounds, { padding: [20, 20] });
        } catch (_e) {
          this.map.setView(ITACOATIARA_CENTER, DEFAULT_ZOOM);
        }
      } else {
        this.map.setView(ITACOATIARA_CENTER, DEFAULT_ZOOM);
      }
      this._updateTestability();
    }

    focusDemo() {
      if (!this.map || !this.territoryData || !this.territoryData.demo) return;
      try {
        // Foca APENAS a parcela (plot), não a rota inteira de 45km
        const plotFeature = this.territoryData.demo.features.find(
          (f) => f.properties && f.properties.kind === 'plot'
        );
        if (plotFeature) {
          const plotLayer = window.L.geoJSON(plotFeature);
          const bounds = plotLayer.getBounds();
          if (bounds.isValid()) {
            this.map.fitBounds(bounds, { padding: [40, 40], maxZoom: 15 });
            this._updateTestability();
            return;
          }
        }
        // Fallback caso não encontre plot específico
        const bounds = this.layerDemo.getBounds();
        if (bounds.isValid()) {
          this.map.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 });
        }
      } catch (_e) {
        // fallback
      }
      this._updateTestability();
    }

    focusAlert(feature) {
      if (!this.map || !feature) return;
      try {
        this.alertHighlightLayer.clearLayers();
        const alertLayer = window.L.geoJSON(feature, {
          style: {
            color: '#ef4444',
            weight: 3,
            fillColor: '#f87171',
            fillOpacity: 0.65
          }
        });
        this.alertHighlightLayer.addLayer(alertLayer);

        const bounds = alertLayer.getBounds();
        if (bounds.isValid()) {
          this.map.fitBounds(bounds, { padding: [50, 50], maxZoom: 16, animate: false });
        }
      } catch (_e) {
        // fallback
      }
      this._updateTestability();
    }

    filterAlerts(features) {
      if (!this.map || !this.layerAlerts) return;
      this.layerAlerts.clearLayers();
      this.alertHighlightLayer.clearLayers();
      if (features && features.length > 0) {
        this.layerAlerts.addData({
          type: 'FeatureCollection',
          features: features
        });
      }
    }

    toggleBaseLayer() {
      if (!this.map || !this.baseTileLayer) return;
      const statusEl = document.getElementById('map-base-text');
      if (this.baseLayerVisible) {
        this.map.removeLayer(this.baseTileLayer);
        this.baseLayerVisible = false;
        if (statusEl) statusEl.textContent = 'Base OSM: Desativada (Fundo vetorial)';
      } else {
        this.baseTileLayer.addTo(this.map);
        this.baseLayerVisible = true;
        if (statusEl) statusEl.textContent = 'Base OSM: Ativa';
      }
    }

    toggleLayer(layerKey, isVisible) {
      if (!this.map) return;
      let target = null;
      if (layerKey === 'limits') target = this.layerLimits;
      else if (layerKey === 'alerts') target = this.layerAlerts;
      else if (layerKey === 'demo') target = this.layerDemo;

      if (!target) return;

      if (isVisible) {
        if (!this.map.hasLayer(target)) this.map.addLayer(target);
      } else {
        if (this.map.hasLayer(target)) this.map.removeLayer(target);
      }
    }

    highlightCustodyPath() {
      if (!this.map || !this.custodyHighlightLayer || !this.territoryData || !this.territoryData.demo) return;
      this.custodyHighlightLayer.clearLayers();

      const routeFeature = this.territoryData.demo.features.find(
        (f) => f.properties && f.properties.kind === 'route'
      );

      if (routeFeature && routeFeature.geometry && routeFeature.geometry.coordinates) {
        const latlngs = routeFeature.geometry.coordinates.map((c) => [c[1], c[0]]);
        const glowLine = window.L.polyline(latlngs, {
          color: '#c5f67c',
          weight: 7,
          opacity: 0.9,
          lineCap: 'round'
        });
        this.custodyHighlightLayer.addLayer(glowLine);
      }
    }

    onAlertSelect(fn) {
      this.onAlertSelectCallback = fn;
    }

    onDemoSelect(fn) {
      this.onDemoSelectCallback = fn;
    }
  }

  window.RaizMap = RaizMap;
})(window);
