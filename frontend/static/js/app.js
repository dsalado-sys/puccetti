/* Puccetti · Localizar activo — frontend Leaflet */
(() => {
  const COLOR_DORADO = '#B8960C';
  const COLOR_DORADO_CLARO = '#C9A84C';
  const COLOR_NEGRO = '#0A0A0A';
  const COLOR_BLANCO = '#FFFFFF';

  /* ─── Mapa ──────────────────────────────────────────── */
  const MAX_ZOOM = 22;

  const map = L.map('map', {
    center: [40.4168, -3.7038],
    zoom: 6,
    maxZoom: MAX_ZOOM,
    zoomControl: true,
    attributionControl: true,
  });

  const osm = L.tileLayer(
    'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    {
      attribution: '© OpenStreetMap',
      maxZoom: MAX_ZOOM,
      maxNativeZoom: 19,
    }
  );

  const pnoa = L.tileLayer.wms('https://www.ign.es/wms-inspire/pnoa-ma', {
    layers: 'OI.OrthoimageCoverage',
    format: 'image/jpeg',
    transparent: false,
    version: '1.3.0',
    attribution: '© PNOA · IGN',
    maxZoom: MAX_ZOOM,
    // PNOA sirve hasta resolución submétrica; pedimos al WMS que regenere
    // teselas hasta el zoom máximo en lugar de estirar pixels.
  });

  const catastro = L.tileLayer.wms(
    'https://ovc.catastro.meh.es/Cartografia/WMS/ServidorWMS.aspx',
    {
      layers: 'Catastro',
      format: 'image/png',
      transparent: true,
      version: '1.1.1',
      attribution: '© Catastro DGC',
      maxZoom: MAX_ZOOM,
    }
  );

  pnoa.addTo(map);
  catastro.addTo(map);

  L.control
    .layers(
      { 'Ortofoto PNOA (IGN)': pnoa, 'OpenStreetMap': osm },
      { 'Parcelario Catastro': catastro },
      { collapsed: false, position: 'topright' }
    )
    .addTo(map);

  /* Capas dinámicas para la parcela activa y la planimetría externa */
  let layerParcela = null;
  let layerParcelaOrig = null;  // contorno original cuando hay simplificado encima
  let layerExterna = null;
  let markerCentroide = null;
  let activoActual = null;
  let toleranciaActual = 0;

  function limpiarCapas() {
    if (layerParcela) { map.removeLayer(layerParcela); layerParcela = null; }
    if (layerParcelaOrig) { map.removeLayer(layerParcelaOrig); layerParcelaOrig = null; }
    if (layerExterna) { map.removeLayer(layerExterna); layerExterna = null; }
    if (markerCentroide) { map.removeLayer(markerCentroide); markerCentroide = null; }
  }

  /* Marker en hueco dorado para el centroide */
  function iconoCentroide() {
    return L.divIcon({
      html: `<div style="
        width:22px;height:22px;border-radius:50%;
        background:${COLOR_NEGRO};
        border:3px solid ${COLOR_DORADO};
        box-shadow:0 0 0 3px rgba(184,150,12,0.25);
      "></div>`,
      className: '',
      iconSize: [22, 22],
      iconAnchor: [11, 11],
    });
  }

  /* ─── Click interactivo sobre el mapa ───────────────── */
  map.on('click', async (e) => {
    const { lat, lng } = e.latlng;
    if (map.getZoom() < 12) {
      mostrarError(
        'Acércate más al mapa (zoom 12+) antes de hacer click sobre una parcela.'
      );
      return;
    }
    await buscarPorCoordenadas(lng, lat);
  });

  /* ─── Tabs ──────────────────────────────────────────── */
  document.querySelectorAll('.tab').forEach((tab) => {
    tab.addEventListener('click', () => {
      const target = tab.dataset.tab;
      document.querySelectorAll('.tab').forEach((t) => t.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach((p) => p.classList.remove('active'));
      tab.classList.add('active');
      document.querySelector(`.tab-panel[data-panel="${target}"]`).classList.add('active');
    });
  });

  /* ─── Tools panel (análisis del activo) ─────────────── */
  const toolsPanel = document.getElementById('tools-panel');
  const toolsSubtitle = document.getElementById('tools-panel-subtitle');

  function abrirToolsPanel() {
    if (!activoActual) return;
    toolsSubtitle.textContent =
      `${activoActual.rc || '—'} · ${activoActual.direccion || ''}`;
    toolsPanel.classList.remove('hidden');
  }

  function cerrarToolsPanel() {
    toolsPanel.classList.add('hidden');
  }

  document.getElementById('btn-abrir-analisis').addEventListener('click', abrirToolsPanel);
  document.getElementById('tools-panel-close').addEventListener('click', cerrarToolsPanel);
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !toolsPanel.classList.contains('hidden')) {
      cerrarToolsPanel();
    }
  });

  /* ─── Help modal ────────────────────────────────────── */
  const helpModal = document.getElementById('help-modal');
  document.getElementById('btn-help').addEventListener('click', () =>
    helpModal.classList.remove('hidden')
  );
  document.getElementById('help-close').addEventListener('click', () =>
    helpModal.classList.add('hidden')
  );
  helpModal.addEventListener('click', (e) => {
    if (e.target === helpModal) helpModal.classList.add('hidden');
  });

  /* ─── Normativa: carga única + modal ──────────────────── */
  const USOS_URBANISMO = [
    'residencial', 'hotelero', 'terciario', 'mixto',
    'industrial', 'equipamiento', 'sin_definir',
  ];
  let normativaCache = null;

  async function cargarNormativa() {
    if (normativaCache) return normativaCache;
    const r = await fetch('/api/normativa');
    if (!r.ok) throw new Error('No se pudo cargar la normativa');
    normativaCache = await r.json();
    return normativaCache;
  }

  // Modal normativa
  const normModal = document.getElementById('normativa-modal');
  const normBody = document.getElementById('normativa-body');
  document.getElementById('btn-normativa').addEventListener('click', async () => {
    normModal.classList.remove('hidden');
    try {
      const n = await cargarNormativa();
      renderNormativaTab('hotel', n);
    } catch (e) {
      normBody.innerHTML = `<p class="hint">Error: ${e.message}</p>`;
    }
  });
  document.getElementById('normativa-close').addEventListener('click', () =>
    normModal.classList.add('hidden')
  );
  normModal.addEventListener('click', (e) => {
    if (e.target === normModal) normModal.classList.add('hidden');
  });
  document.querySelectorAll('.norm-tab').forEach((tab) => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.norm-tab').forEach((t) => t.classList.remove('active'));
      tab.classList.add('active');
      renderNormativaTab(tab.dataset.target, normativaCache);
    });
  });

  // Celda editable: input numérico con coordenadas (grupo/categoria/tipologia).
  // Las celdas booleanas (Sí/No) se muestran como texto no editable.
  function celdaEditable(grupo, categoria, tipologia, v) {
    if (v === true) return '<td>Sí</td>';
    if (v === false) return '<td>No</td>';
    const val = (v === null || v === undefined) ? '' : v;
    return `<td class="norm-cell"><input type="number" step="0.01" min="0"
      class="norm-input" value="${val}"
      data-grupo="${grupo}" data-categoria="${categoria}" data-tipologia="${tipologia}" /></td>`;
  }

  function renderNormativaTab(key, n) {
    if (!n) return;
    const tablas = n.anexo_I.tablas;
    const usos = n.anexo_I.usos;
    let html = '';
    if (key === 'hotel') {
      const rows = ['individual', 'doble', 'triple', 'cuadruple', 'salon', 'multiple'];
      const cats = Object.keys(tablas.hotel);
      html += '<h3>A1.1 — Superficies mínimas (m²) por unidad de alojamiento</h3>';
      html += '<table><thead><tr><th class="row-label">Tipo</th>';
      cats.forEach((c) => { html += `<th>${usos.hotelero.categorias[c]}</th>`; });
      html += '</tr></thead><tbody>';
      rows.forEach((r) => {
        html += `<tr><td class="row-label">${labelTipo(r)}</td>`;
        cats.forEach((c) => { html += celdaEditable('hotel', c, r, tablas.hotel[c][r]); });
        html += '</tr>';
      });
      html += '</tbody></table>';
      html += '<h3>Áreas sociales obligatorias (m² por unidad de alojamiento)</h3>';
      html += '<table><thead><tr><th class="row-label">Categoría</th><th>m²/u.a.</th></tr></thead><tbody>';
      Object.entries(tablas.areas_sociales_hotel).forEach(([k, v]) => {
        const lbl = usos.hotelero.categorias[k] || k;
        html += `<tr><td class="row-label">${lbl}</td>${celdaEditable('areas_sociales_hotel', k, 'area_social', v)}</tr>`;
      });
      html += '</tbody></table>';
    } else if (key === 'hotel_apartamento') {
      html = tablaEditableNxM(
        'hotel_apartamento', tablas.hotel_apartamento,
        usos.hotel_apartamento.categorias,
        ['dormitorio_individual', 'dormitorio_doble', 'dormitorio_triple',
         'dormitorio_cuadruple', 'estudio', 'salon_comedor_4p'],
        'A1.2 — Hoteles-Apartamento (m²)',
      );
    } else if (key === 'apt_edificios') {
      html = tablaEditableNxM(
        'apt_edificios', tablas.apt_edificios,
        usos.apartamentos_turisticos.categorias,
        ['vestibulo_por_ua_min15ua', 'areas_sociales_por_ua',
         'dormitorio_individual', 'dormitorio_doble', 'dormitorio_triple',
         'dormitorio_cuadruple', 'estudio', 'salon_comedor_4p',
         'superficie_adicional_por_plaza', 'cocina', 'bano'],
        'A1.3 — Apartamentos turísticos (edificios/complejos) — Decreto 194/2010',
      );
    } else if (key === 'apt_conjuntos') {
      html = tablaEditableNxM(
        'apt_conjuntos', tablas.apt_conjuntos,
        usos.apartamentos_turisticos_conjunto.categorias,
        ['dormitorio_individual', 'dormitorio_doble', 'dormitorio_triple',
         'dormitorio_cuadruple', 'estudio', 'salon_comedor_4p',
         'superficie_adicional_por_plaza', 'cocina', 'bano',
         'segundo_bano_obligatorio_si_mas_5_usuarios'],
        'A1.4 — Apartamentos turísticos (conjuntos)',
      );
    } else if (key === 'vivienda') {
      html += '<h3>A1.5 — Superficie útil máxima (m²)</h3>';
      html += '<table><thead><tr><th class="row-label">Tipología</th><th>m² máx</th></tr></thead><tbody>';
      Object.entries(tablas.vivienda_maximas).forEach(([k, v]) => {
        const lbl = usos.vivienda.categorias[k] || labelTipo(k);
        html += `<tr><td class="row-label">${lbl}</td>${celdaEditable('vivienda_maximas', '_', k, v)}</tr>`;
      });
      html += '</tbody></table>';
      html += '<h3>Estancias mínimas (m²)</h3>';
      html += '<table><thead><tr><th class="row-label">Tipología</th><th>Estancia min</th><th>E + Comedor + Cocina min</th></tr></thead><tbody>';
      Object.entries(tablas.vivienda_estancias).forEach(([k, v]) => {
        html += `<tr><td class="row-label">${labelTipo(k)}</td>`
          + celdaEditable('vivienda_estancias', k, 'estancia_min_m2', v.estancia_min_m2)
          + celdaEditable('vivienda_estancias', k, 'estancia_comedor_cocina_min_m2', v.estancia_comedor_cocina_min_m2)
          + '</tr>';
      });
      html += '</tbody></table>';
      html += '<h3>Otras reglas obligatorias</h3>';
      html += '<table><tbody>';
      Object.entries(tablas.vivienda_reglas).forEach(([k, v]) => {
        html += `<tr><td class="row-label">${labelTipo(k)}</td>${celdaEditable('vivienda_reglas', '_', k, v)}</tr>`;
      });
      html += '</tbody></table>';
    }
    normBody.innerHTML = html;
  }

  function tablaEditableNxM(grupo, tabla, categorias, filas, titulo) {
    let html = `<h3>${titulo}</h3><table><thead><tr><th class="row-label">Tipo</th>`;
    Object.entries(categorias).forEach(([_, lbl]) => { html += `<th>${lbl}</th>`; });
    html += '</tr></thead><tbody>';
    filas.forEach((f) => {
      html += `<tr><td class="row-label">${labelTipo(f)}</td>`;
      Object.keys(categorias).forEach((c) => {
        html += celdaEditable(grupo, c, f, tabla[c]?.[f]);
      });
      html += '</tr>';
    });
    html += '</tbody></table>';
    return html;
  }

  // Guardado de ediciones (delegado sobre el contenedor del modal).
  normBody.addEventListener('change', async (e) => {
    const input = e.target.closest('.norm-input');
    if (!input) return;
    const body = {
      grupo: input.dataset.grupo,
      categoria: input.dataset.categoria,
      tipologia: input.dataset.tipologia,
      valor: input.value === '' ? null : Number(input.value),
    };
    marcarStatus('normativa-status', '', 'Guardando…');
    try {
      const r = await fetch('/api/normativa/valor', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d.detail || r.statusText);
      }
      const payload = await r.json();
      normativaCache = payload.anexo_I ? { anexo_I: payload.anexo_I, anexo_II: normativaCache.anexo_II } : normativaCache;
      marcarStatus('normativa-status', 'saved', 'Guardado');
      input.classList.add('norm-input-saved');
      setTimeout(() => input.classList.remove('norm-input-saved'), 1200);
    } catch (err) {
      marcarStatus('normativa-status', 'error', err.message);
    }
  });

  document.getElementById('normativa-reset').addEventListener('click', async () => {
    if (!confirm('¿Restablecer TODOS los valores de la normativa a los de fábrica?')) return;
    marcarStatus('normativa-status', '', 'Restableciendo…');
    try {
      const r = await fetch('/api/normativa/reset', { method: 'POST' });
      const payload = await r.json();
      normativaCache = { anexo_I: payload.anexo_I, anexo_II: normativaCache.anexo_II };
      const activeTab = document.querySelector('.norm-tab.active');
      renderNormativaTab(activeTab ? activeTab.dataset.target : 'hotel', normativaCache);
      marcarStatus('normativa-status', 'saved', 'Valores restablecidos');
    } catch (err) {
      marcarStatus('normativa-status', 'error', err.message);
    }
  });

  function labelTipo(slug) {
    const map = {
      individual: 'Individual', doble: 'Doble', triple: 'Triple',
      cuadruple: 'Cuádruple', salon: 'Salón', multiple: 'Múltiple',
      dormitorio_individual: 'Dormitorio individual',
      dormitorio_doble: 'Dormitorio doble',
      dormitorio_triple: 'Dormitorio triple',
      dormitorio_cuadruple: 'Dormitorio cuádruple',
      estudio: 'Estudio',
      salon_comedor_4p: 'Salón-comedor (≤4p)',
      vestibulo_por_ua_min15ua: 'Vestíbulo recepción (≥15 u.a.)',
      areas_sociales_por_ua: 'Áreas sociales / u.a.',
      superficie_adicional_por_plaza: 'Sup. adicional / plaza',
      cocina: 'Cocina', bano: 'Baño',
      segundo_bano_obligatorio_si_mas_5_usuarios: '2º baño si >5 usuarios',
      vivienda_1d: '1 dormitorio', vivienda_2d: '2 dormitorios',
      vivienda_3d: '3 dormitorios', vivienda_4d: '4 dormitorios',
      vivienda_5d_o_mas: '5+ dormitorios',
      dormitorio_min_m2: 'Dormitorio mínimo (m²)',
      dormitorio_principal_min_m2: 'Dormitorio principal mínimo (m²)',
      cocina_independiente_min_m2: 'Cocina independiente mín. (m²)',
      pasillo_interior_min_ancho_m: 'Pasillo interior mín. (m)',
      iluminacion_min_pct_superficie_util: 'Iluminación mín. (% sup. útil)',
      ventilacion_min_pct_superficie_util: 'Ventilación mín. (% sup. útil)',
      dos_banos_si_superficie_mayor_m2: '2 baños si sup. > m²',
    };
    return map[slug] || slug;
  }

  /* ─── Estado UI ─────────────────────────────────────── */
  const statusEl = document.getElementById('status');
  const statusMsg = document.getElementById('status-msg');
  const errorEl = document.getElementById('error');
  const errorMsg = document.getElementById('error-msg');
  const fichaEl = document.getElementById('ficha');

  function mostrarStatus(msg) {
    statusMsg.textContent = msg || 'Consultando Catastro…';
    statusEl.classList.remove('hidden');
    errorEl.classList.add('hidden');
    fichaEl.classList.add('hidden');
  }

  function ocultarStatus() {
    statusEl.classList.add('hidden');
  }

  function mostrarError(msg) {
    ocultarStatus();
    errorMsg.textContent = msg;
    errorEl.classList.remove('hidden');
  }

  /* ─── Llamadas API ──────────────────────────────────── */
  async function postJson(url, body) {
    const r = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      const detail = await r.json().catch(() => ({ detail: r.statusText }));
      throw new Error(detail.detail || `${r.status} ${r.statusText}`);
    }
    return r.json();
  }

  async function postForm(url, formData) {
    const r = await fetch(url, { method: 'POST', body: formData });
    if (!r.ok) {
      const detail = await r.json().catch(() => ({ detail: r.statusText }));
      throw new Error(detail.detail || `${r.status} ${r.statusText}`);
    }
    return r.json();
  }

  async function buscarPorCoordenadas(lon, lat) {
    try {
      mostrarStatus('Consultando Catastro por coordenadas…');
      const data = await postJson('/api/locate/coordinates', { lon, lat });
      pintarActivo(data);
    } catch (e) {
      mostrarError(e.message);
    }
  }

  /* ─── Render del activo ─────────────────────────────── */
  function fmtNum(n, dec = 0) {
    if (n === null || n === undefined || Number.isNaN(n)) return '—';
    return Number(n).toLocaleString('es-ES', {
      minimumFractionDigits: dec, maximumFractionDigits: dec,
    });
  }

  function fuenteLabel(f) {
    return ({
      rc: 'Por referencia catastral',
      direccion: 'Por dirección',
      mapa: 'Por click en mapa',
      planimetria: 'Por planimetría externa',
    }[f]) || 'Desconocida';
  }

  function pintarActivo(data) {
    ocultarStatus();
    errorEl.classList.add('hidden');

    document.getElementById('ficha-fuente').textContent = fuenteLabel(data.fuente);
    document.getElementById('ficha-direccion').textContent = data.direccion || '(Sin dirección)';
    document.getElementById('ficha-ubicacion').textContent =
      [data.municipio, data.provincia].filter(Boolean).join(' · ') || '—';

    document.getElementById('f-rc').textContent = data.rc || '—';
    document.getElementById('f-sup').textContent =
      data.superficie_catastral_m2 ? `${fmtNum(data.superficie_catastral_m2, 0)} m²` : '—';
    document.getElementById('f-uso').textContent = data.uso_catastro || '—';

    pintarAgregados(data.agregados);

    const e = data.edificio || {};
    const blqEd = document.getElementById('bloque-edificio');
    if (data.edificio) {
      blqEd.classList.remove('hidden');
      document.getElementById('f-plantas').textContent =
        e.plantas_total || e.plantas_sobre_rasante || '—';
      document.getElementById('f-anio').textContent = e.anio_construccion || '—';
      document.getElementById('f-supc').textContent =
        e.superficie_construida_m2 ? `${fmtNum(e.superficie_construida_m2, 0)} m²` : '—';
      document.getElementById('f-sotanos').textContent =
        e.sotanos !== undefined && e.sotanos !== null ? e.sotanos : '—';
    } else {
      blqEd.classList.add('hidden');
    }

    pintarSubreferencias(data);

    activoActual = data;
    toleranciaActual = 0;
    resetSimplificacionUI(data);
    actualizarUrlsDescarga();
    cargarProyectoEstado(data.id);

    fichaEl.classList.remove('hidden');
    fichaEl.scrollIntoView({ behavior: 'smooth', block: 'start' });

    pintarGeometria(data);
  }

  function actualizarUrlsDescarga() {
    if (!activoActual) return;
    const tol = toleranciaActual || 0;
    const qs = tol > 0 ? `?tolerancia=${tol}` : '';
    document.getElementById('btn-pdf').href =
      `/api/activo/${activoActual.id}/pdf${qs}`;
    document.getElementById('btn-geojson').href =
      `/api/activo/${activoActual.id}/geojson${qs}`;
  }

  function pintarAgregados(ag) {
    const bloque = document.getElementById('bloque-agregados');
    if (!ag) {
      bloque.classList.add('hidden');
      return;
    }
    bloque.classList.remove('hidden');
    document.getElementById('ag-num-ref').textContent = ag.num_referencias ?? '—';
    document.getElementById('ag-suma-sup').textContent =
      ag.suma_superficie_construida_m2 != null
        ? `${fmtNum(ag.suma_superficie_construida_m2, 0)} m²` : '—';
    document.getElementById('ag-edificabilidad').textContent =
      ag.edificabilidad_resultante_m2t_m2s != null
        ? `${fmtNum(ag.edificabilidad_resultante_m2t_m2s, 2)} m²t/m²s` : '—';
    document.getElementById('ag-num-viv').textContent = ag.num_viviendas ?? '—';
    document.getElementById('ag-densidad').textContent =
      ag.densidad_viviendas_viv_ha != null
        ? `${fmtNum(ag.densidad_viviendas_viv_ha, 1)} viv/ha` : '—';
  }

  function pintarSubreferencias(data) {
    const bloque = document.getElementById('bloque-subref');
    const lista = document.getElementById('subref-list');
    const count = document.getElementById('subref-count');
    lista.innerHTML = '';

    const subs = data.subreferencias || [];
    if (!subs.length) {
      bloque.classList.add('hidden');
      return;
    }
    bloque.classList.remove('hidden');
    count.textContent = subs.length;

    const rcActual = data.rc;
    for (const s of subs) {
      const li = document.createElement('li');
      li.className = 'subref-item';
      if (s.rc === rcActual) li.classList.add('activo');

      const rcSpan = document.createElement('span');
      rcSpan.className = 'subref-rc';
      rcSpan.textContent = s.rc;
      li.appendChild(rcSpan);

      const locSpan = document.createElement('span');
      locSpan.className = 'subref-loc';
      locSpan.textContent = s.localizacion || '—';
      li.appendChild(locSpan);

      const metaParts = [];
      if (s.uso) metaParts.push(s.uso);
      if (s.superficie_construida_m2) {
        metaParts.push(`${fmtNum(s.superficie_construida_m2, 0)} m² constr.`);
      }
      if (metaParts.length) {
        const meta = document.createElement('span');
        meta.className = 'subref-meta';
        meta.textContent = metaParts.join(' · ');
        li.appendChild(meta);
      }

      li.addEventListener('click', () => buscarPorRc(s.rc));
      lista.appendChild(li);
    }
  }

  /* ─── Simplificación de contorno ────────────────────── */
  const simplSlider = document.getElementById('simpl-slider');
  const simplValor = document.getElementById('simpl-valor');
  const simplVertices = document.getElementById('simpl-vertices');
  const simplSupOrig = document.getElementById('simpl-sup-orig');
  const simplSupSimp = document.getElementById('simpl-sup-simp');
  const simplDiff = document.getElementById('simpl-diff');
  const simplQuick = document.querySelectorAll('.simpl-quick button');
  let simplTimer = null;

  function fmtTol(v) {
    return `${Number(v).toFixed(1).replace('.', ',')} m`;
  }

  function resetSimplificacionUI(data) {
    simplSlider.value = 0;
    simplValor.textContent = fmtTol(0);
    marcarBotonQuick(0);
    // Estadísticas iniciales con datos del activo si están disponibles
    const supOrig = data.superficie_catastral_m2 || 0;
    simplSupOrig.textContent = supOrig ? `${fmtNum(supOrig, 0)} m²` : '—';
    simplSupSimp.textContent = simplSupOrig.textContent;
    simplVertices.textContent = '—';
    simplDiff.textContent = '0 m² (0,00 %)';
    simplDiff.className = '';
    // Pedimos las estadísticas reales (vértices) en background
    aplicarSimplificacion(0, /*fitBounds*/ false);
  }

  function marcarBotonQuick(tol) {
    simplQuick.forEach((b) => {
      b.classList.toggle('activo', Number(b.dataset.tol) === Number(tol));
    });
  }

  async function aplicarSimplificacion(tolerancia, fitBounds = false) {
    if (!activoActual) return;
    toleranciaActual = Number(tolerancia) || 0;
    simplValor.textContent = fmtTol(toleranciaActual);
    try {
      const r = await fetch(
        `/api/activo/${activoActual.id}/simplificar?tolerancia=${toleranciaActual}`
      );
      if (!r.ok) {
        const det = await r.json().catch(() => ({}));
        throw new Error(det.detail || r.statusText);
      }
      const res = await r.json();
      pintarStatsSimpl(res);
      pintarPoligonoSimpl(res, fitBounds);
      actualizarUrlsDescarga();
    } catch (e) {
      console.error('Error simplificando:', e);
    }
  }

  function pintarStatsSimpl(res) {
    simplVertices.textContent =
      `${res.vertices_original} → ${res.vertices_simplificado}`;
    simplSupOrig.textContent = `${fmtNum(res.superficie_original_m2, 0)} m²`;
    simplSupSimp.textContent = `${fmtNum(res.superficie_simplificada_m2, 0)} m²`;
    const diff = res.diferencia_m2;
    const pct = res.diferencia_pct;
    const sign = diff >= 0 ? '+' : '';
    simplDiff.textContent =
      `${sign}${fmtNum(diff, 1)} m² (${sign}${pct.toFixed(2)} %)`;
    simplDiff.className =
      Math.abs(pct) < 0.01 ? '' : pct >= 0 ? 'positivo' : 'negativo';
  }

  function pintarPoligonoSimpl(res, fitBounds) {
    if (!activoActual) return;
    // Quitamos las capas previas
    if (layerParcela) { map.removeLayer(layerParcela); layerParcela = null; }
    if (layerParcelaOrig) { map.removeLayer(layerParcelaOrig); layerParcelaOrig = null; }

    if (toleranciaActual > 0) {
      // Original como fantasma debajo, simplificado encima en dorado
      const original = filtrarCatastro(activoActual.geojson);
      layerParcelaOrig = L.geoJSON(original, {
        style: {
          color: COLOR_BLANCO, weight: 1, dashArray: '3,3',
          fillColor: COLOR_BLANCO, fillOpacity: 0.04,
        },
      }).addTo(map);
      layerParcela = L.geoJSON(res.geojson, {
        style: {
          color: COLOR_DORADO, weight: 3,
          fillColor: COLOR_DORADO_CLARO, fillOpacity: 0.22,
        },
      }).addTo(map);
    } else {
      const original = filtrarCatastro(activoActual.geojson);
      layerParcela = L.geoJSON(original, {
        style: {
          color: COLOR_DORADO, weight: 3,
          fillColor: COLOR_DORADO_CLARO, fillOpacity: 0.18,
        },
      }).addTo(map);
    }
    if (fitBounds && res.bounds && res.bounds.length === 4) {
      const [minx, miny, maxx, maxy] = res.bounds;
      map.fitBounds(
        [[miny, minx], [maxy, maxx]],
        { padding: [40, 40], maxZoom: 20 }
      );
    }
  }

  function filtrarCatastro(geojson) {
    if (!geojson) return { type: 'FeatureCollection', features: [] };
    return {
      type: 'FeatureCollection',
      features: (geojson.features || []).filter(
        (f) => !f.properties || f.properties.fuente !== 'externa'
      ),
    };
  }

  simplSlider.addEventListener('input', (e) => {
    const v = Number(e.target.value);
    simplValor.textContent = fmtTol(v);
    marcarBotonQuick(v);
    clearTimeout(simplTimer);
    simplTimer = setTimeout(() => aplicarSimplificacion(v, false), 200);
  });

  simplQuick.forEach((btn) => {
    btn.addEventListener('click', () => {
      const v = Number(btn.dataset.tol);
      simplSlider.value = v;
      simplValor.textContent = fmtTol(v);
      marcarBotonQuick(v);
      aplicarSimplificacion(v, false);
    });
  });

  /* ─── Proyecto: uso, urbanismo, diseño, alertas ─────── */
  const SAVE_DEBOUNCE_MS = 400;
  const _saveTimers = {};

  function debounceSave(key, fn) {
    clearTimeout(_saveTimers[key]);
    _saveTimers[key] = setTimeout(fn, SAVE_DEBOUNCE_MS);
  }

  async function cargarProyectoEstado(aid) {
    try {
      await cargarNormativa();
      poblarUsos();
      poblarUsosPermitidos();
    } catch (e) {
      console.warn('Normativa no disponible:', e);
    }
    try {
      const r = await fetch(`/api/activo/${aid}/proyecto`);
      if (!r.ok) throw new Error(r.statusText);
      const payload = await r.json();
      rellenarFormularios(payload.estado);
      renderAlertas(payload.alertas);
    } catch (e) {
      console.error('No se pudo cargar el proyecto:', e);
    }
  }

  function poblarUsos() {
    if (!normativaCache) return;
    const sel = document.getElementById('sel-uso');
    if (sel.options.length > 1) return; // ya poblado
    const usos = normativaCache.anexo_I.usos;
    Object.entries(usos).forEach(([k, v]) => {
      const opt = document.createElement('option');
      opt.value = k;
      opt.textContent = v.etiqueta;
      sel.appendChild(opt);
    });
  }

  function poblarUsosPermitidos() {
    const cont = document.getElementById('urb-usos-permitidos');
    if (cont.children.length) return;
    USOS_URBANISMO.forEach((u) => {
      const lbl = document.createElement('label');
      lbl.className = 'check-inline';
      lbl.innerHTML =
        `<input type="checkbox" value="${u}" data-urb-uso="1" /> ${u.replace('_', ' ')}`;
      cont.appendChild(lbl);
    });
    cont.querySelectorAll('input[data-urb-uso]').forEach((cb) => {
      cb.addEventListener('change', guardarUrbanismo);
    });
  }

  function rellenarFormularios(estado) {
    // Uso + categoría
    const selUso = document.getElementById('sel-uso');
    const selCat = document.getElementById('sel-categoria');
    selUso.value = estado.uso || '';
    actualizarCategorias(estado.uso, estado.categoria);

    // Urbanismo
    const u = estado.urbanismo || {};
    setVal('urb-edificabilidad', u.edificabilidad_m2t_m2s);
    setVal('urb-plantas-max', u.plantas_max);
    setVal('urb-ocupacion-max', u.ocupacion_max_pct);
    setVal('urb-retr-frontal', u.retranqueos_m?.frontal);
    setVal('urb-retr-lat-izq', u.retranqueos_m?.lateral_izquierdo);
    setVal('urb-retr-lat-der', u.retranqueos_m?.lateral_derecho);
    setVal('urb-retr-trasero', u.retranqueos_m?.trasero);
    setVal('urb-patio-luz', u.patio_min_luz_recta_m);
    setVal('urb-patio-sup', u.patio_min_superficie_m2);
    setChecked('urb-atico-edif', u.atico_computa_edificabilidad);
    setChecked('urb-atico-plantas', u.atico_computa_plantas);
    setChecked('urb-sotano-edif', u.sotano_computa_edificabilidad);
    setChecked('urb-sotano-plantas', u.sotano_computa_plantas);
    setVal('urb-fuente', u.fuente);
    setVal('urb-fecha', u.fecha_consulta);
    setVal('urb-notas', u.notas);
    const permitidos = new Set(u.usos_permitidos || []);
    document.querySelectorAll('input[data-urb-uso]').forEach((cb) => {
      cb.checked = permitidos.has(cb.value);
    });

    // Diseño
    const d = estado.diseno || {};
    setVal('dis-muro-fachada', d.muros?.espesor_fachada_m);
    setVal('dis-muro-medianero', d.muros?.espesor_medianero_m);
    setVal('dis-sep-unidades', d.muros?.espesor_separacion_unidades_m);
    setVal('dis-tabique', d.muros?.espesor_tabique_interior_m);
    setVal('dis-pasillo', d.circulacion?.pasillo_min_ancho_m);
    setVal('dis-pasillo-viv', d.circulacion?.pasillo_min_ancho_vivienda_m);
    setVal('dis-vestibulo', d.circulacion?.vestibulo_diametro_min_m);
    setVal('dis-puerta', d.circulacion?.puerta_radio_apertura_m);
    setVal('dis-patio-luz', d.patios?.luz_recta_min_m);
    setVal('dis-patio-sup', d.patios?.superficie_min_m2);
  }

  function setVal(id, v) {
    const el = document.getElementById(id);
    if (!el) return;
    el.value = v === null || v === undefined ? '' : v;
  }
  function setChecked(id, v) {
    const el = document.getElementById(id);
    if (el) el.checked = !!v;
  }

  function actualizarCategorias(uso, categoriaActual) {
    const selCat = document.getElementById('sel-categoria');
    selCat.innerHTML = '<option value="">—</option>';
    if (!uso || !normativaCache) {
      selCat.disabled = true;
      return;
    }
    const cats = normativaCache.anexo_I.usos[uso]?.categorias || {};
    Object.entries(cats).forEach(([k, lbl]) => {
      const opt = document.createElement('option');
      opt.value = k;
      opt.textContent = lbl;
      if (k === categoriaActual) opt.selected = true;
      selCat.appendChild(opt);
    });
    selCat.disabled = false;
  }

  document.getElementById('sel-uso').addEventListener('change', (e) => {
    actualizarCategorias(e.target.value, null);
    guardarUso();
  });
  document.getElementById('sel-categoria').addEventListener('change', guardarUso);

  async function guardarUso() {
    if (!activoActual) return;
    const body = {
      uso: document.getElementById('sel-uso').value || null,
      categoria: document.getElementById('sel-categoria').value || null,
    };
    await guardarParcial(`/api/activo/${activoActual.id}/uso`, 'PUT', body, 'urb-status');
  }

  // Bindings de urbanismo (autosave debounced)
  const camposUrbanismo = [
    'urb-edificabilidad', 'urb-plantas-max', 'urb-ocupacion-max',
    'urb-retr-frontal', 'urb-retr-lat-izq', 'urb-retr-lat-der', 'urb-retr-trasero',
    'urb-patio-luz', 'urb-patio-sup',
    'urb-atico-edif', 'urb-atico-plantas',
    'urb-sotano-edif', 'urb-sotano-plantas',
    'urb-fuente', 'urb-fecha', 'urb-notas',
  ];
  camposUrbanismo.forEach((id) => {
    const el = document.getElementById(id);
    if (!el) return;
    const ev = el.type === 'checkbox' ? 'change' : 'input';
    el.addEventListener(ev, () => debounceSave('urb', guardarUrbanismo));
  });

  async function guardarUrbanismo() {
    if (!activoActual) return;
    const usos_permitidos = [];
    document.querySelectorAll('input[data-urb-uso]').forEach((cb) => {
      if (cb.checked) usos_permitidos.push(cb.value);
    });
    const body = {
      edificabilidad_m2t_m2s: numOrNull('urb-edificabilidad'),
      plantas_max: intOrNull('urb-plantas-max'),
      ocupacion_max_pct: numOrNull('urb-ocupacion-max'),
      retranqueos_m: {
        frontal: numOrZero('urb-retr-frontal'),
        lateral_izquierdo: numOrZero('urb-retr-lat-izq'),
        lateral_derecho: numOrZero('urb-retr-lat-der'),
        trasero: numOrZero('urb-retr-trasero'),
      },
      usos_permitidos,
      patio_min_luz_recta_m: numOrNull('urb-patio-luz'),
      patio_min_superficie_m2: numOrNull('urb-patio-sup'),
      atico_computa_edificabilidad: document.getElementById('urb-atico-edif').checked,
      atico_computa_plantas: document.getElementById('urb-atico-plantas').checked,
      sotano_computa_edificabilidad: document.getElementById('urb-sotano-edif').checked,
      sotano_computa_plantas: document.getElementById('urb-sotano-plantas').checked,
      notas: document.getElementById('urb-notas').value,
      fuente: document.getElementById('urb-fuente').value,
      fecha_consulta: document.getElementById('urb-fecha').value,
    };
    await guardarParcial(`/api/activo/${activoActual.id}/urbanismo`, 'PUT', body, 'urb-status');
  }

  // Bindings de diseño
  const camposDiseno = [
    'dis-muro-fachada', 'dis-muro-medianero', 'dis-sep-unidades', 'dis-tabique',
    'dis-pasillo', 'dis-pasillo-viv', 'dis-vestibulo', 'dis-puerta',
    'dis-patio-luz', 'dis-patio-sup',
  ];
  camposDiseno.forEach((id) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener('input', () => debounceSave('dis', guardarDiseno));
  });

  async function guardarDiseno() {
    if (!activoActual) return;
    const body = {
      muros: {
        espesor_fachada_m: numOrNull('dis-muro-fachada'),
        espesor_medianero_m: numOrNull('dis-muro-medianero'),
        espesor_separacion_unidades_m: numOrNull('dis-sep-unidades'),
        espesor_tabique_interior_m: numOrNull('dis-tabique'),
      },
      circulacion: {
        pasillo_min_ancho_m: numOrNull('dis-pasillo'),
        pasillo_min_ancho_vivienda_m: numOrNull('dis-pasillo-viv'),
        vestibulo_diametro_min_m: numOrNull('dis-vestibulo'),
        puerta_radio_apertura_m: numOrNull('dis-puerta'),
      },
      patios: {
        luz_recta_min_m: numOrNull('dis-patio-luz'),
        superficie_min_m2: numOrNull('dis-patio-sup'),
      },
    };
    await guardarParcial(`/api/activo/${activoActual.id}/diseno`, 'PUT', body, 'dis-status');
  }

  document.getElementById('btn-diseno-reset').addEventListener('click', async () => {
    if (!activoActual) return;
    try {
      const r = await fetch(`/api/activo/${activoActual.id}/diseno/reset`, { method: 'POST' });
      const payload = await r.json();
      rellenarFormularios(payload.estado);
      renderAlertas(payload.alertas);
      marcarStatus('dis-status', 'saved', 'Restablecido a defaults');
    } catch (e) { marcarStatus('dis-status', 'error', e.message); }
  });

  async function guardarParcial(url, method, body, statusId) {
    marcarStatus(statusId, '', 'Guardando…');
    try {
      const r = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d.detail || r.statusText);
      }
      const payload = await r.json();
      renderAlertas(payload.alertas);
      marcarStatus(statusId, 'saved', 'Guardado');
    } catch (e) {
      marcarStatus(statusId, 'error', e.message);
    }
  }

  function marcarStatus(id, cls, msg) {
    const el = document.getElementById(id);
    if (!el) return;
    el.className = 'form-status' + (cls ? ' ' + cls : '');
    el.textContent = msg || '';
    if (cls === 'saved') {
      setTimeout(() => {
        if (el.textContent === msg) { el.textContent = ''; el.className = 'form-status'; }
      }, 2000);
    }
  }

  function numOrNull(id) {
    const v = document.getElementById(id).value;
    if (v === '' || v === null) return null;
    const n = Number(v);
    return Number.isNaN(n) ? null : n;
  }
  function intOrNull(id) {
    const n = numOrNull(id);
    return n === null ? null : Math.round(n);
  }
  function numOrZero(id) {
    const n = numOrNull(id);
    return n === null ? 0 : n;
  }

  function renderAlertas(alertas) {
    const ul = document.getElementById('alertas-list');
    ul.innerHTML = '';
    if (!alertas || !alertas.length) {
      ul.innerHTML = '<li class="alerta-vacia">Sin alertas para los parámetros actuales.</li>';
      return;
    }
    const orden = { error: 0, aviso: 1, info: 2 };
    [...alertas].sort((a, b) => (orden[a.nivel] ?? 9) - (orden[b.nivel] ?? 9))
      .forEach((a) => {
        const li = document.createElement('li');
        li.className = `alerta-item ${a.nivel}`;
        li.innerHTML = `<span></span><div><span class="nivel">${a.nivel}</span>${escapeHtml(a.mensaje)}</div>`;
        ul.appendChild(li);
      });
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  async function buscarPorRc(rc) {
    try {
      mostrarStatus(`Cargando ficha de ${rc}…`);
      const data = await postJson('/api/locate/rc', { rc });
      pintarActivo(data);
    } catch (e) { mostrarError(e.message); }
  }

  function pintarGeometria(data) {
    limpiarCapas();
    if (!data.geojson) return;

    const externas = { type: 'FeatureCollection', features: [] };
    const catastrales = { type: 'FeatureCollection', features: [] };
    for (const f of data.geojson.features || []) {
      if (f.properties && f.properties.fuente === 'externa') {
        externas.features.push(f);
      } else {
        catastrales.features.push(f);
      }
    }

    layerParcela = L.geoJSON(catastrales, {
      style: {
        color: COLOR_DORADO,
        weight: 3,
        fillColor: COLOR_DORADO_CLARO,
        fillOpacity: 0.18,
      },
    }).addTo(map);

    if (externas.features.length) {
      layerExterna = L.geoJSON(externas, {
        style: {
          color: COLOR_BLANCO,
          weight: 2,
          dashArray: '6,4',
          fillColor: COLOR_BLANCO,
          fillOpacity: 0.05,
        },
      }).addTo(map);
    }

    const { lon, lat } = data.centroide;
    markerCentroide = L.marker([lat, lon], { icon: iconoCentroide() })
      .bindPopup(
        `<strong>${data.rc || ''}</strong><br/>` +
          `${data.direccion || ''}<br/>` +
          `${fmtNum(data.superficie_catastral_m2, 0)} m²`
      )
      .addTo(map);

    if (data.bounds && data.bounds.length === 4) {
      const [minx, miny, maxx, maxy] = data.bounds;
      map.fitBounds(
        [[miny, minx], [maxy, maxx]],
        { padding: [40, 40], maxZoom: 19 }
      );
    }
  }

  /* ─── Formularios ───────────────────────────────────── */
  document.getElementById('form-rc').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const rc = ev.target.rc.value.trim().toUpperCase();
    try {
      mostrarStatus('Buscando por referencia catastral…');
      const data = await postJson('/api/locate/rc', { rc });
      pintarActivo(data);
    } catch (e) { mostrarError(e.message); }
  });

  document.getElementById('form-dir').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const fd = new FormData(ev.target);
    const body = Object.fromEntries(fd.entries());
    try {
      mostrarStatus('Buscando por dirección…');
      const data = await postJson('/api/locate/address', body);
      pintarActivo(data);
    } catch (e) { mostrarError(e.message); }
  });

  /* ─── Dropzone planimetría ──────────────────────────── */
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('file-input');
  const dzFilename = document.getElementById('dropzone-filename');
  const btnUpload = document.getElementById('btn-upload');
  let selectedFiles = [];

  function setFiles(fileList) {
    selectedFiles = Array.from(fileList || []);
    if (selectedFiles.length === 0) {
      dzFilename.textContent = 'Sin archivo';
      btnUpload.disabled = true;
      return;
    }
    const total = selectedFiles.reduce((s, f) => s + f.size, 0);
    if (selectedFiles.length === 1) {
      const f = selectedFiles[0];
      dzFilename.textContent = `${f.name} · ${(f.size / 1024).toFixed(1)} KB`;
    } else {
      const names = selectedFiles.map((f) => f.name).join(', ');
      dzFilename.textContent =
        `${selectedFiles.length} archivos · ${(total / 1024).toFixed(1)} KB — ${names}`;
    }
    btnUpload.disabled = false;

    // Aviso si el usuario subió un .shp sin sus sidecars
    const exts = selectedFiles.map((f) =>
      (f.name.match(/\.[^.]+$/) || [''])[0].toLowerCase()
    );
    if (exts.includes('.shp') && !exts.includes('.dbf')) {
      dzFilename.textContent +=
        ' · ⚠ falta .dbf (suele requerirse junto al .shp)';
    }
  }

  dropzone.addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', (e) => setFiles(e.target.files));

  ['dragenter', 'dragover'].forEach((ev) =>
    dropzone.addEventListener(ev, (e) => {
      e.preventDefault();
      dropzone.classList.add('drag');
    })
  );
  ['dragleave', 'drop'].forEach((ev) =>
    dropzone.addEventListener(ev, (e) => {
      e.preventDefault();
      dropzone.classList.remove('drag');
    })
  );
  dropzone.addEventListener('drop', (e) => {
    if (e.dataTransfer.files && e.dataTransfer.files.length) {
      setFiles(e.dataTransfer.files);
    }
  });

  btnUpload.addEventListener('click', async () => {
    if (selectedFiles.length === 0) return;
    const fd = new FormData();
    for (const f of selectedFiles) fd.append('files', f);
    const crs = document.getElementById('file-crs').value.trim();
    if (crs) fd.append('crs_origen', crs);
    try {
      mostrarStatus('Cargando planimetría y consultando Catastro…');
      const data = await postForm('/api/locate/file', fd);
      pintarActivo(data);
    } catch (e) { mostrarError(e.message); }
  });
})();
