// main.js - Loads and displays tiered data with search and navigation

let configData;
let tierDefinitions = {};

async function loadConfig() {
  // Add detailed logging to diagnose configuration loading issues
  try {
    const response = await fetch('./config.json');
    if (!response.ok) {
      throw new Error(`Failed to load configuration file. HTTP status: ${response.status}`);
    }
    configData = await response.json();
    console.log('Configuration loaded successfully:', configData);
  } catch (error) {
    console.error('Error loading configuration:', error);
  }
}

// Fetch and parse tier definitions from the specified URI in config.json
async function loadTierDefinitions() {
  try {
    if (!configData || !configData.tier_definitions) {
      throw new Error('Tier definitions URI is not specified in the configuration.');
    }
    const response = await fetch(configData.tier_definitions);
    if (!response.ok) {
      throw new Error(`Failed to fetch tier definitions. HTTP status: ${response.status}`);
    }
    tierDefinitions = await response.json();
    console.log('Tier definitions loaded successfully:', tierDefinitions);
  } catch (error) {
    console.error('Error loading tier definitions:', error);
  }
}

document.addEventListener('DOMContentLoaded', async () => {
  await loadConfig();
  await loadTierDefinitions();
  parseURIHash(); // Parse the URI hash on page load to pre-select tab and filters
  if (configData) {
    await init(); // Initialize the application only after config and tier definitions are loaded
  } else {
    console.error('Configuration data is not available. Application initialization aborted.');
  }
});

// Ensure configData is validated before calling fetchData
async function init() {
  if (!configData || !configData.tiered_asset_uris || !configData.untiered_asset_uris) {
    console.error('Configuration data is invalid or not loaded.');
    return;
  }

  const { tiered_asset_uris, untiered_asset_uris } = configData;
  TIERED_FILES.azure = tiered_asset_uris.azure;
  TIERED_FILES.entra = tiered_asset_uris.entra;
  TIERED_FILES.msgraph = tiered_asset_uris.msgraph;

  UNTIERED_FILES.azure = untiered_asset_uris.azure;
  UNTIERED_FILES.entra = untiered_asset_uris.entra;
  UNTIERED_FILES.msgraph = untiered_asset_uris.msgraph;

  const azureUntieredUrl = untiered_asset_uris.azure;
  const entraUntieredUrl = untiered_asset_uris.entra;
  const msGraphUntieredUrl = untiered_asset_uris.msgraph;

  window._untieredAzureCount = await fetchUntieredCount(azureUntieredUrl);
  window._untieredEntraCount = await fetchUntieredCount(entraUntieredUrl);
  window._untieredMsGraphCount = await fetchUntieredCount(msGraphUntieredUrl);

  allData.azure = await fetchData('azure');
  allData.entra = await fetchData('entra');
  allData.msgraph = await fetchData('msgraph');

  renderContent(currentTab);
  setupTabs();
  addDisclaimerButton();
}

// Add a safeguard to ensure configData is defined before accessing its properties
const TIERED_FILES = {};
const UNTIERED_FILES = {};

let currentTab = 'azure';
let allData = { azure: [], entra: [], msgraph: [] };

// Utility: fetch JSON
async function fetchData(tab) {
  // Add a check to ensure the tab parameter is valid in fetchData
  if (!TIERED_FILES[tab]) {
    console.error(`Invalid tab: ${tab}. No matching URL in TIERED_FILES.`);
    return [];
  }
  const resp = await fetch(TIERED_FILES[tab]);
  return await resp.json();
}

// Utility: fetch untiered roles/permissions count from JSON file
async function fetchUntieredCount(url) {
  try {
    const response = await fetch(url);
    if (!response.ok) {
      console.error(`Failed to fetch untiered data from ${url}`);
      return 0;
    }
    const data = await response.json();
    return Array.isArray(data) ? data.length : 0;
  } catch (error) {
    console.error(`Error fetching untiered data from ${url}:`, error);
    return 0;
  }
}

function getTierClass(tab, tier) {
  // Azure: 0-3, Entra/MSGraph: 0-2
  if (tab === 'azure') {
    if (tier === 0 || tier === '0') return 'tier-0';
    if (tier === 1 || tier === '1') return 'tier-1';
    if (tier === 2 || tier === '2') return 'tier-2';
    if (tier === 3 || tier === '3') return 'tier-3';
  } else {
    if (tier === 0 || tier === '0') return 'tier-0';
    if (tier === 1 || tier === '1') return 'tier-1';
    if (tier === 2 || tier === '2') return 'tier-3'; // Use green for Tier 2 in Entra/MS Graph
  }
  return 'tier-x';
}

function getTierLabel(tab, tier) {
  if (tier === undefined || tier === '') return 'Tier ?';
  if (tab === 'azure') {
    if (['0','1','2','3',0,1,2,3].includes(tier)) return 'Tier ' + tier;
  } else {
    if (['0','1','2',0,1,2].includes(tier)) return 'Tier ' + tier;
  }
  return 'Tier ?';
}


function getTierDefinition(assetType, tier) {
  if (!tierDefinitions.tier_definitions) return '';
  const normalizedAssetType = assetType.toLowerCase();
  const tierKey = `tier_${tier}`;
  if (!tierDefinitions.tier_definitions[normalizedAssetType]) return '';
  if (!tierDefinitions.tier_definitions[normalizedAssetType][tierKey]) return '';
  return tierDefinitions.tier_definitions[normalizedAssetType][tierKey] || '';
}

function getTierName(assetType, tier) {
  if (!tierDefinitions.tier_names) return '';
  const normalizedAssetType = assetType.toLowerCase();
  const tierKey = `tier_${tier}`;
  if (!tierDefinitions.tier_names[normalizedAssetType]) return '';
  if (!tierDefinitions.tier_names[normalizedAssetType][tierKey]) return '';
  return tierDefinitions.tier_names[normalizedAssetType][tierKey] || '';
}


// On load, all tiers are shown, but no filter is selected (all buttons greyed out)
let selectedTiers = { azure: [], entra: [], msgraph: [] };
// Asset type filter state
let selectedAssetTypes = { azure: [], entra: [], msgraph: [] };

function getSelectedTiers(tab) {
  // If no filter is selected, show all tiers
  if (!selectedTiers[tab] || selectedTiers[tab].length === 0) {
    if (tab === 'azure') return [0,1,2,3];
    return [0,1,2];
  }
  return selectedTiers[tab];
}

function getSelectedAssetTypes(tab) {
  if (!selectedAssetTypes[tab] || selectedAssetTypes[tab].length === 0) {
    return ['built-in', 'custom'];
  }
  return selectedAssetTypes[tab];
}

function updateURIHash(tab, selectedTiers, selectedTypes) {
  let hash = tab;
  if (selectedTiers && selectedTiers.length > 0) {
    hash += '-tier-' + selectedTiers.join('-');
  }
  if (selectedTypes && selectedTypes.length > 0 && selectedTypes.length < 2) {
    hash += '-type-' + selectedTypes.join('-');
  }
  history.replaceState(null, '', `#${hash}`);
}

function parseURIHash() {
  const hash = window.location.hash.slice(1);
  if (!hash) return;
  const [tab, ...filters] = hash.split('-');
  if (tab && ['azure', 'entra', 'msgraph'].includes(tab)) {
    currentTab = tab;
    let tierIdx = filters.indexOf('tier');
    let typeIdx = filters.indexOf('type');
    if (tierIdx !== -1) {
      const tiers = filters.slice(tierIdx + 1, typeIdx !== -1 ? typeIdx : undefined).map(t => parseInt(t)).filter(t => !isNaN(t));
      selectedTiers[tab] = tiers;
    } else {
      selectedTiers[tab] = [];
    }
    if (typeIdx !== -1) {
      const types = filters.slice(typeIdx + 1).map(t => t.toLowerCase()).filter(t => t === 'built-in' || t === 'custom');
      selectedAssetTypes[tab] = types;
    } else {
      selectedAssetTypes[tab] = [];
    }
  }
}

function renderTierFilter(tab) {
  let maxTier = 3;
  if (tab === 'entra' || tab === 'msgraph') maxTier = 2;
  // Place label and buttons in the same flex container
  let html = '<div class="is-flex is-align-items-center flex-wrap" id="tier-filter-group" style="margin-bottom:1.5em; gap: 0.5em; justify-content:flex-start; display:flex; flex-wrap:wrap; align-items:center;">';
  html += '<span style="font-size:1em;font-weight:600;color:#3570b3;margin-right:0.7em;letter-spacing:0.01em;white-space:nowrap;">Filter:</span>';
  const selected = selectedTiers[tab] || [];
  for (let i = 0; i <= maxTier; i++) {
    let btnClass = `button tier-filter-segment tier-badge ${getTierClass(tab, i)}`;
    if (selected.includes(i)) {
      btnClass += ' is-selected';
    } else {
      btnClass += ' faded-tier';
    }
    html += `<button class="${btnClass}" data-tier="${i}" type="button" style="margin-right:0.4em; margin-bottom:0.3em;">${getTierLabel(tab, i)}</button>`;
  }
  // Asset type filter buttons styled like assetType badges
  const assetTypes = ['built-in', 'custom'];
  const assetTypeLabels = { 'built-in': 'Built-in', 'custom': 'Custom' };
  const assetTypeEmojis = { 'built-in': '🏗️', 'custom': '🛠️' };
  const selectedTypes = selectedAssetTypes[tab] || [];
  assetTypes.forEach(type => {
    let btnClass = `button asset-type-filter-segment asset-type-badge`;
    let style = '';
    if (selectedTypes.includes(type)) {
      btnClass += ' is-selected';
      style = type === 'built-in'
        ? 'background:#3570b3;color:#fff;border-radius:0.7em;padding:0.15em 0.7em;font-size:0.85em;margin-right:0.5em;display:inline-flex;align-items:center;gap:0.3em;min-width:5.5em;justify-content:center;font-weight:bold;box-shadow:0 2px 8px #3570b340;border:2.5px solid #3570b3;'
        : 'background:#b36a00;color:#fff;border-radius:0.7em;padding:0.15em 0.7em;font-size:0.85em;margin-right:0.5em;display:inline-flex;align-items:center;gap:0.3em;min-width:5.5em;justify-content:center;font-weight:bold;box-shadow:0 2px 8px #b36a0030;border:2.5px solid #b36a00;';
    } else {
      btnClass += ' faded-tier';
      style = type === 'built-in'
        ? 'background:#e3f0ff;color:#3570b3;border-radius:0.7em;padding:0.15em 0.7em;font-size:0.85em;margin-right:0.5em;display:inline-flex;align-items:center;gap:0.3em;min-width:5.5em;justify-content:center;opacity:0.7;'
        : 'background:#fff4e3;color:#b36a00;border-radius:0.7em;padding:0.15em 0.7em;font-size:0.85em;margin-right:0.5em;display:inline-flex;align-items:center;gap:0.3em;min-width:5.5em;justify-content:center;opacity:0.7;';
    }
    html += `<button class="${btnClass}" data-asset-type="${type}" type="button" style="${style}">${assetTypeEmojis[type]} ${assetTypeLabels[type]}</button>`;
  });
  html += '</div>';
  return html;
}

// Setup filter button event listeners
function setupTierFilter(tab) {
  const group = document.getElementById('tier-filter-group');
  if (!group) return;
  // Tier buttons
  group.querySelectorAll('.tier-filter-segment').forEach(btn => {
    btn.onclick = function(e) {
      e.stopPropagation();
      const tier = parseInt(this.getAttribute('data-tier'));
      if (isNaN(tier)) return;
      let arr = selectedTiers[tab] || [];
      if (arr.includes(tier)) {
        arr = arr.filter(t => t !== tier);
      } else {
        arr = [...arr, tier];
      }
      selectedTiers[tab] = arr;
      updateURIHash(tab, selectedTiers[tab], selectedAssetTypes[tab]);
      renderContent(tab, document.getElementById('searchInputWide') ? document.getElementById('searchInputWide').value : '');
    };
  });
  // Asset type buttons
  group.querySelectorAll('.asset-type-filter-segment').forEach(btn => {
    btn.onclick = function(e) {
      e.stopPropagation();
      const type = this.getAttribute('data-asset-type');
      if (!type) return;
      let arr = selectedAssetTypes[tab] || [];
      if (arr.includes(type)) {
        arr = arr.filter(t => t !== type);
      } else {
        arr = [...arr, type];
      }
      selectedAssetTypes[tab] = arr;
      updateURIHash(tab, selectedTiers[tab], selectedAssetTypes[tab]);
      renderContent(tab, document.getElementById('searchInputWide') ? document.getElementById('searchInputWide').value : '');
    };
  });
}

// Replace hard-coded tier definitions in renderContent with dynamic calls to getTierName and getTierDefinition
async function renderContent(tab, search = '') {
  let html = '';
  if (tab === 'azure') {
    let b = allData.azure.filter(item => item.id).length;
    let a = window._untieredAzureCount || 0;
    let c = b + a;
    html += `<div class="section-label has-text-grey is-size-7" style="margin-bottom:0.7em; font-weight:500;">Currently untiered: ${a}/${c} (<span class='link-like' onclick=\"showJsonPopup('${UNTIERED_FILES.azure}', 'Currently untiered Azure roles')\">more info</span>)</div>`;
  } else if (tab === 'entra') {
    let b = allData.entra.filter(item => item.id).length;
    let a = window._untieredEntraCount || 0;
    let c = b + a;
    html += `<div class="section-label has-text-grey is-size-7" style="margin-bottom:0.7em; font-weight:500;">Currently untiered: ${a}/${c} (<span class='link-like' onclick=\"showJsonPopup('${UNTIERED_FILES.entra}', 'Currently untiered Entra roles')\">more info</span>)</div>`;
  } else if (tab === 'msgraph') {
    let b = allData.msgraph.filter(item => item.id).length;
    let a = window._untieredMsGraphCount || 0;
    let c = b + a;
    html += `<div class="section-label has-text-grey is-size-7" style="margin-bottom:0.7em; font-weight:500;">Currently untiered: ${a}/${c} (<span class='link-like' onclick=\"showJsonPopup('${UNTIERED_FILES.msgraph}', 'Currently untiered MS Graph application permissions')\">more info</span>)</div>`;
  }
  html += renderTierFilter(tab);
  const selected = selectedTiers[tab] || [];
  const sortedSelected = [...selected].sort((a, b) => Number(a) - Number(b));
  if (sortedSelected.length > 0) {
    let defs = sortedSelected.map(tier => {
      const tierName = getTierName(tab.charAt(0).toUpperCase() + tab.slice(1), tier);
      const tierDefinition = getTierDefinition(tab.charAt(0).toUpperCase() + tab.slice(1), tier);
      // Add tier label with same content, shape, and color as filter menu, but with fixed width and height for consistency
      const tierLabel = `<span class="button tier-filter-segment tier-badge ${getTierClass(tab, tier)}" style="margin-right:0.5em; font-size:0.85em; min-width:4.2em; width:4.2em; height:2em; padding:0; display:inline-flex; align-items:center; justify-content:center;">${getTierLabel(tab, tier)}</span>`;
      return tierDefinition ? `<div class="tier-definition faded-tier" style="margin-bottom:0.5em;display:flex;align-items:center;">${tierLabel}<span class="is-size-7"><strong>${tierName}</strong>: ${tierDefinition}</span></div>` : '';
    }).join('');
    if (defs) {
      html += `<div id="tier-definition-bar" style="margin-bottom:1em;">${defs}</div>`;
    }
  }
  html += '<div class="field" style="margin-bottom:1.5em; position:relative;">' +
    '<div class="control has-icons-left has-icons-right">' +
      '<input class="input is-medium" type="text" id="searchInputWide" placeholder="Search by name or Id">' +
      '<span class="icon is-left">' +
        '<i class="fas fa-search"></i>' +
      '</span>' +
      '<span class="icon is-right" id="search-clear-btn"><i class="fas fa-times"></i></span>' +
    '</div>' +
  '</div>';
  if (tab === 'azure') html += renderAzure(allData.azure, search);
  if (tab === 'entra') html += renderEntra(allData.entra, search);
  if (tab === 'msgraph') html += renderMsGraph(allData.msgraph, search);
  document.getElementById('content-area').innerHTML = html;
  setupTierFilter(tab);
  setupRoleEntryToggles(tab);
  const wideInput = document.getElementById('searchInputWide');
  const clearBtn = document.getElementById('search-clear-btn');
  if (wideInput) {
    wideInput.value = search;
    const wideInputClone = wideInput.cloneNode(true);
    wideInput.parentNode.replaceChild(wideInputClone, wideInput);
    wideInputClone.value = search;
    function updateClearBtn() {
      if (wideInputClone.value.length > 0) {
        clearBtn.classList.add('visible');
      } else {
        clearBtn.classList.remove('visible');
      }
    }
    wideInputClone.addEventListener('input', e => {
      updateClearBtn();
      const value = e.target.value;
      filterRoleEntries(currentTab, value);
    });
    wideInputClone.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') {
        wideInputClone.blur();
      }
    });
    updateClearBtn();
    clearBtn.onclick = function() {
      wideInputClone.value = '';
      updateClearBtn();
      filterRoleEntries(currentTab, '');
      wideInputClone.focus();
    };
  }
}

// Update renderers to filter by asset type
function renderAzure(data, search = '') {
  const tiers = getSelectedTiers('azure').map(String);
  const assetTypes = getSelectedAssetTypes('azure');
  return data
    .filter(item => item.tier !== undefined && tiers.includes(String(item.tier)))
    .filter(item => !item.assetType || assetTypes.includes(item.assetType.toLowerCase()))
    .map((item, idx) => {
      const tier = item.tier !== undefined ? item.tier : '';
      const name = item.assetName || item.name || '';
      const id = item.id || '';
      const pathType = item.pathType || '';
      const isDirect = pathType && pathType.toLowerCase() === 'direct';
      // Only match against name and id 
      const match = (name + id).toLowerCase().includes(search.toLowerCase());
      if (!match) return '';
      let details = '';
      // Place assetType badge at the very top of details
      const assetTypeBadge = getAssetTypeBadge(item.assetType);
      if (assetTypeBadge) details += `<div style="margin-bottom:0.5em;">${assetTypeBadge}</div>`;
      // Always show Tier definition first
      details += `<div class="tier-definition faded-tier"><span class="is-size-7"><strong>Tier name:</strong> ${getTierName('Azure', tier)}</span><br><span class="is-size-7"><strong>Tier definition:</strong> ${getTierDefinition('Azure', tier)}</span></div>`;
      // Card stack for details
      let detailBlocks = [];
      if (tier === 2 || tier === '2' || tier === 3 || tier === '3') {
        if (item.worstCaseScenario) detailBlocks.push(`
          <div class="popup-section">
            <span class="popup-section-title"><span class="icon">⚠️</span> <strong>Worst-case scenario:</strong></span>
            <span class="popup-section-value">${item.worstCaseScenario}</span>
          </div>`);
      } else {
        if (pathType) detailBlocks.push(`
          <div class="popup-section">
            <span class="popup-section-title"><span class="icon">🛡️</span> <strong>Path Type:</strong></span>
            <span class="popup-section-value">${pathType}${isDirect ? ' <span class=\'crown-emoji\'>💎</span>' : ''}</span>
          </div>`);
        if (item.shortestPath) detailBlocks.push(`
          <div class="popup-section">
            <span class="popup-section-title"><span class="icon">🗡️</span> <strong>Attack Path:</strong></span>
            <span class="popup-section-value">${item.shortestPath}</span>
          </div>`);
        if (item.example) detailBlocks.push(`
          <div class="popup-section">
            <span class="popup-section-title"><span class="icon">💡</span> <strong>Example:</strong></span>
            <span class="popup-section-value">${item.example}</span>
          </div>`);
      }
      details += detailBlocks.join('');
      const docLink = (item.assetType && item.assetType.toLowerCase() === 'custom')
        ? `<a href="#" onclick="showCustomDefinitionPopup('azure', '${item.id}'); return false;" class="has-text-link is-size-7" style="margin-left: 0.5em;" title="View Definition">📖</a>`
        : (item.documentationUri ? `<a href="${item.documentationUri}" target="_blank" class="has-text-link is-size-7" style="margin-left: 0.5em;" title="View Documentation">📖</a>` : '');

      return `
        <div class="card role-entry" data-idx="${idx}">
          <div class="card-content">
            <span class="tier-badge ${getTierClass('azure', tier)}">${getTierLabel('azure', tier)}</span>
            <strong>${name}</strong>
            ${docLink}
            ${id ? `<span class="has-text-grey is-size-7">Role Id: ${id}</span>` : ''}
            <span class="icon is-pulled-right"><i class="fas fa-chevron-down"></i></span>
            ${isDirect ? '<span class="crown-emoji-entry" style="display:inline-block; float:none; font-size:0.95em; margin-left:0.4em; vertical-align:middle; opacity:0.85; position:relative; top:2px;">💎</span>' : ''}
            <div class="role-details" style="display:none; margin-top:0.7em;">
              ${details}
            </div>
          </div>
        </div>
      `;
    }).join('') || '<p>No results found.</p>';
}

function renderEntra(data, search = '') {
  const tiers = getSelectedTiers('entra').map(String);
  const assetTypes = getSelectedAssetTypes('entra');
  return data
    .filter(item => item.tier !== undefined && tiers.includes(String(item.tier)))
    .filter(item => !item.assetType || assetTypes.includes(item.assetType.toLowerCase()))
    .map((item, idx) => {
      const tier = item.tier !== undefined ? item.tier : '';
      const name = item.assetName || item.name || '';
      const id = item.id || '';
      const pathType = item.pathType || '';
      const isDirect = pathType && pathType.toLowerCase() === 'direct';
      // Only match against name and id
      const match = (name + id).toLowerCase().includes(search.toLowerCase());
      if (!match) return '';
      let details = '';
      // Place assetType badge at the very top of details
      const assetTypeBadge = getAssetTypeBadge(item.assetType);
      if (assetTypeBadge) details += `<div style="margin-bottom:0.5em;">${assetTypeBadge}</div>`;
      // Always show Tier definition first
      details += `<div class="tier-definition faded-tier"><span class="is-size-7"><strong>Tier name:</strong> ${getTierName('Entra', tier)}</span><br><span class="is-size-7"><strong>Tier definition:</strong> ${getTierDefinition('Entra', tier)}</span></div>`;
      let detailBlocks = [];
      if (tier === 1 || tier === '1') {
        if (item.providesFullAccessTo) detailBlocks.push(`
          <div class="popup-section">
            <span class="popup-section-title"><span class="icon">🔓</span> <strong>Provides full access to:</strong></span>
            <span class="popup-section-value">${item.providesFullAccessTo}</span>
          </div>`);
      } else {
        if (pathType) detailBlocks.push(`
          <div class="popup-section">
            <span class="popup-section-title"><span class="icon">🛡️</span> <strong>Path Type:</strong></span>
            <span class="popup-section-value">${pathType}${isDirect ? ' <span class=\'crown-emoji\'>💎</span>' : ''}</span>
          </div>`);
        if (item.shortestPath) detailBlocks.push(`
          <div class="popup-section">
            <span class="popup-section-title"><span class="icon">🗡️</span> <strong>Attack Path:</strong></span>
            <span class="popup-section-value">${item.shortestPath}</span>
          </div>`);
        if (item.example) detailBlocks.push(`
          <div class="popup-section">
            <span class="popup-section-title"><span class="icon">💡</span> <strong>Example:</strong></span>
            <span class="popup-section-value">${item.example}</span>
          </div>`);
      }
      details += detailBlocks.join('');
      const docLink = (item.assetType && item.assetType.toLowerCase() === 'custom')
        ? `<a href="#" onclick="showCustomDefinitionPopup('entra', '${item.id}'); return false;" class="has-text-link is-size-7" style="margin-left: 0.5em;" title="View Definition">📖</a>`
        : (item.documentationUri ? `<a href="${item.documentationUri}" target="_blank" class="has-text-link is-size-7" style="margin-left: 0.5em;" title="View Documentation">📖</a>` : '');

      return `
        <div class="card role-entry" data-idx="${idx}">
          <div class="card-content">
            <span class="tier-badge ${getTierClass('entra', tier)}">${getTierLabel('entra', tier)}</span>
            <strong>${name}</strong>
            ${docLink}
            ${id ? `<span class="has-text-grey is-size-7">Role Id: ${id}</span>` : ''}
            <span class="icon is-pulled-right"><i class="fas fa-chevron-down"></i></span>
            ${isDirect ? '<span class="crown-emoji-entry" style="display:inline-block; float:none; font-size:0.95em; margin-left:0.4em; vertical-align:middle; opacity:0.85; position:relative; top:2px;">💎</span>' : ''}
            <div class="role-details" style="display:none; margin-top:0.7em;">
              ${details}
            </div>
          </div>
        </div>
      `;
    }).join('') || '<p>No results found.</p>';
}

function renderMsGraph(data, search = '') {
  const tiers = getSelectedTiers('msgraph').map(String);
  const assetTypes = getSelectedAssetTypes('msgraph');
  return data
    .filter(item => item.tier !== undefined && tiers.includes(String(item.tier)))
    .filter(item => !item.assetType || assetTypes.includes(item.assetType.toLowerCase()))
    .map((item, idx) => {
      const tier = item.tier !== undefined ? item.tier : '';
      const name = item.assetName || item.name || '';
      const id = item.id || '';
      const pathType = item.pathType || '';
      const isDirect = pathType && pathType.toLowerCase() === 'direct';
      // Only match against name and id
      const match = (name + id).toLowerCase().includes(search.toLowerCase());
      if (!match) return '';
      let details = '';
      // Place assetType badge at the very top of details
      const assetTypeBadge = getAssetTypeBadge(item.assetType);
      if (assetTypeBadge) details += `<div style="margin-bottom:0.5em;">${assetTypeBadge}</div>`;
      // Always show Tier definition first
      details += `<div class="tier-definition faded-tier"><span class="is-size-7"><strong>Tier name:</strong> ${getTierName('MSGraph', tier)}</span><br><span class="is-size-7"><strong>Tier definition:</strong> ${getTierDefinition('MSGraph', tier)}</span></div>`;
      let detailBlocks = [];
      if (pathType) detailBlocks.push(`
        <div class="popup-section">
          <span class="popup-section-title"><span class="icon">🛡️</span> <strong>Path Type:</strong></span>
          <span class="popup-section-value">${pathType}${isDirect ? ' <span class=\'crown-emoji\'>💎</span>' : ''}</span>
        </div>`);
      if (item.shortestPath) detailBlocks.push(`
        <div class="popup-section">
          <span class="popup-section-title"><span class="icon">🗡️</span> <strong>Attack Path:</strong></span>
          <span class="popup-section-value">${item.shortestPath}</span>
        </div>`);
      if (item.example) detailBlocks.push(`
        <div class="popup-section">
          <span class="popup-section-title"><span class="icon">💡</span> <strong>Example:</strong></span>
          <span class="popup-section-value">${item.example}</span>
        </div>`);
      details += detailBlocks.join('');
      const docLink = (item.assetType && item.assetType.toLowerCase() === 'custom')
        ? `<a href="#" onclick="showCustomDefinitionPopup('msgraph', '${item.id}'); return false;" class="has-text-link is-size-7" style="margin-left: 0.5em;" title="View Definition">📖</a>`
        : (item.documentationUri ? `<a href="${item.documentationUri}" target="_blank" class="has-text-link is-size-7" style="margin-left: 0.5em;" title="View Documentation">📖</a>` : '');

      return `
        <div class="card role-entry" data-idx="${idx}">
          <div class="card-content">
            <span class="tier-badge ${getTierClass('msgraph', tier)}">${getTierLabel('msgraph', tier)}</span>
            <strong>${name}</strong>
            ${docLink}
            ${id ? `<span class="has-text-grey is-size-7">Role Id: ${id}</span>` : ''}
            <span class="icon is-pulled-right"><i class="fas fa-chevron-down"></i></span>
            ${isDirect ? '<span class="crown-emoji-entry" style="display:inline-block; float:none; font-size:0.95em; margin-left:0.4em; vertical-align:middle; opacity:0.85; position:relative; top:2px;">💎</span>' : ''}
            <div class="role-details" style="display:none; margin-top:0.7em;">
              ${details}
            </div>
          </div>
        </div>
      `;
    }).join('') || '<p>No results found.</p>';
}

// Add this function to filter entries without re-rendering the input
function filterRoleEntries(tab, search) {
  let html = '';
  if (tab === 'azure') html = renderAzure(allData.azure, search);
  if (tab === 'entra') html = renderEntra(allData.entra, search);
  if (tab === 'msgraph') html = renderMsGraph(allData.msgraph, search);
  // Replace only the entries, not the whole content
  const contentArea = document.getElementById('content-area');
  if (!contentArea) return;
  // Find the first .field (search bar) and tier filter, keep them, replace the rest
  const nodes = Array.from(contentArea.children);
  let lastStaticIdx = 0;
  for (let i = 0; i < nodes.length; ++i) {
    if (nodes[i].classList.contains('field')) {
      lastStaticIdx = i;
    }
  }
  // Remove all nodes after the search bar
  while (contentArea.children.length > lastStaticIdx + 1) {
    contentArea.removeChild(contentArea.lastChild);
  }
  // Insert new entries
  const temp = document.createElement('div');
  temp.innerHTML = html;
  Array.from(temp.children).forEach(child => {
    contentArea.appendChild(child);
  });
  setupRoleEntryToggles(tab);
}

function setupRoleEntryToggles(tab) {
  const entries = document.querySelectorAll('.role-entry');
  entries.forEach(entry => {
    // Remove previous click listeners by cloning
    const newEntry = entry.cloneNode(true);
    entry.parentNode.replaceChild(newEntry, entry);
    newEntry.addEventListener('click', function(e) {
      // Prevent event bubbling if clicking inside details
      if (e.target.closest('.role-details')) return;
      const details = this.querySelector('.role-details');
      if (details) {
        // Hide all other details first (accordion behavior)
        document.querySelectorAll('.role-details').forEach(d => {
          if (d !== details) d.style.display = 'none';
        });
        // Toggle current
        details.style.display = details.style.display === 'none' || details.style.display === '' ? 'block' : 'none';
        const icon = this.querySelector('.icon i');
        if (icon) {
          icon.classList.toggle('fa-chevron-down');
          icon.classList.toggle('fa-chevron-up');
        }
      }
    });
  });
}

// Tab navigation
function setupTabs() {
  const tabList = document.getElementById('main-tabs');
  if (!tabList) return;
  // Replace the entire #main-tabs element with a minimalistic triple toggle switch using images and a sliding effect
  const toggle = document.createElement('div');
  toggle.className = 'tab-toggle-switch';
  toggle.innerHTML = `
    <div class="tab-toggle-slider"></div>
    <button class="tab-toggle-btn toggle-left" data-tab="azure"><img src="images/azure.png" alt="Azure">Azure Roles</button>
    <button class="tab-toggle-btn toggle-middle" data-tab="entra"><img src="images/entraid.png" alt="Entra">Entra Roles</button>
    <button class="tab-toggle-btn toggle-right" data-tab="msgraph"><img src="images/msgraph.png" alt="MS Graph">MS Graph Application Permissions</button>
  `;
  tabList.parentNode.replaceChild(toggle, tabList);

  const slider = toggle.querySelector('.tab-toggle-slider');
  const btns = toggle.querySelectorAll('.tab-toggle-btn');
  const tabOrder = ['azure', 'entra', 'msgraph'];

  function updateToggleActive() {
    btns.forEach(btn => {
      btn.classList.remove('is-active');
      if (btn.getAttribute('data-tab') === currentTab) btn.classList.add('is-active');
    });
    // Move slider
    const idx = tabOrder.indexOf(currentTab);
    // Desktop: horizontal slider
    if (window.innerWidth > 700) {
      slider.style.left = `calc(${idx * 33.333}% + 0.15em)`;
      slider.style.top = '0.15em';
      slider.style.width = 'calc(33.333% - 0.2em)';
      slider.style.height = 'calc(100% - 0.3em)';
    } else {
      // Mobile: vertical slider
      slider.style.left = '0.15em';
      slider.style.width = 'calc(100% - 0.3em)';
      slider.style.height = 'calc(33.333% - 0.2em)';
      slider.style.top = `calc(${idx} * 33.333% + 0.15em)`;
      slider.style.setProperty('--slider-idx', idx);
    }
    // Optionally, update background gradient for each tab
    if (idx === 0) slider.style.background = 'linear-gradient(90deg, #4a90e2 60%, #3570b3 100%)';
    else if (idx === 1) slider.style.background = 'linear-gradient(90deg, #3570b3 60%, #4a90e2 100%)';
    else slider.style.background = 'linear-gradient(90deg, #3570b3 60%, #4a90e2 100%)';
  }

  btns.forEach(btn => {
    btn.onclick = () => {
      currentTab = btn.getAttribute('data-tab');
      updateURIHash(currentTab, selectedTiers[currentTab]);
      updateToggleActive();
      renderContent(currentTab, document.getElementById('searchInputWide') ? document.getElementById('searchInputWide').value : '');
    };
  });
  window.addEventListener('resize', updateToggleActive);
  updateToggleActive();
}

// Add Disclaimer button and popup logic
function addDisclaimerButton() {
  // Disclaimer button is now in HTML and styled with .disclaimer-btn-custom
  const btn = document.getElementById('disclaimer-btn');
  if (btn && !btn.hasAttribute('data-setup')) {
    btn.setAttribute('data-setup', 'true');
    btn.addEventListener('click', showDisclaimerPopup);
  }
  // Responsive: change title text on mobile
  function updateTitleForMobile() {
    const title = document.getElementById('main-title');
    if (!title) return;

    const companyNameSpan = (configData && configData.company_name)
      ? `<span style="color: red; font-weight: 600;">${configData.company_name}</span> `
      : '';

    if (window.innerWidth <= 600) {
      title.innerHTML = `🌩️ ${companyNameSpan}AzTier`;
    } else {
      title.innerHTML = `🌩️ ${companyNameSpan}Azure Administrative Tiering (AzTier)`;
    }
  }
  window.addEventListener('resize', updateTitleForMobile);
  updateTitleForMobile();
}

async function showDisclaimerPopup() {
  if (document.getElementById('disclaimer-popup')) return;
  const popup = document.createElement('div');
  popup.id = 'disclaimer-popup';
  popup.innerHTML = [
    '<div class="disclaimer-modal-bg"></div>',
    '<div class="disclaimer-modal-box">',
      '<div class="info-section">',
        '<div class="info-section-title" style="text-align:left;font-size:1.15em;font-weight:600;margin-bottom:0.7em;"><span class="icon">⚙️</span> <strong>Project Configuration</strong></div>',
        '<div id="config-section-content" class="info-section-content" style="margin-bottom:1.2em; font-size:1.05em;"><span>Loading configuration...</span></div>',
      '</div>',
      '<button class="button is-primary" id="close-disclaimer">Close</button>',
    '</div>'
  ].join('');
  document.body.appendChild(popup);
  document.getElementById('close-disclaimer').onclick = () => popup.remove();
  popup.querySelector('.disclaimer-modal-bg').onclick = () => popup.remove();

  // Load config.json if not already loaded
  if (!configData) {
    try {
      const response = await fetch('./config.json');
      if (response.ok) {
        configData = await response.json();
      }
    } catch (e) {}
  }
  // Fetch and display the project configuration file as a pretty table
  if (configData && configData.project_configuration_uri) {
    try {
      const resp = await fetch(configData.project_configuration_uri);
      if (!resp.ok) throw new Error('Failed to fetch project configuration');
      const data = await resp.json();

      // Key renaming and value formatting map
      const keyMap = {
        keepLocalChanges: 'Keep local changes',
        // Add more key mappings here as needed
      };
      function prettyKey(key) {
        // Convert camelCase or snake_case to Title Case if not mapped
        if (keyMap[key]) return keyMap[key];
        return key.replace(/([A-Z])/g, ' $1').replace(/_/g, ' ').replace(/^./, c => c.toUpperCase());
      }
      function prettyValue(key, value) {
        if (typeof value === 'boolean') {
          // For keepLocalChanges, show yes/no
          if (key === 'keepLocalChanges') return value ? 'yes' : 'no';
          return value ? 'yes' : 'no';
        }
        if (value === null) return '<span class="has-text-grey">(none)</span>';
        if (typeof value === 'object') return '<code style="font-size:0.97em;">' + JSON.stringify(value, null, 2) + '</code>';
        return value;
      }
      function renderTable(obj) {
        let rows = '';
        for (const key in obj) {
          if (!Object.prototype.hasOwnProperty.call(obj, key)) continue;
          rows += `<tr><td style='font-weight:600;padding:0.3em 1em 0.3em 0;text-align:left;'>${prettyKey(key)}</td><td style='padding:0.3em 0;text-align:left;'>${prettyValue(key, obj[key])}</td></tr>`;
        }
        return `<table style='width:100%;font-size:1em;background:#f6f8fa;border-radius:6px;text-align:left;'><tbody>${rows}</tbody></table>`;
      }
      document.getElementById('config-section-content').innerHTML = renderTable(data) +
        `<div style="margin-top:1.2em;font-size:0.93em;color:#888;text-align:left;opacity:0.7;line-height:1.5;max-width:600px;">
          <div class='info-section-title' style='text-align:left;font-size:1.15em;font-weight:600;margin-bottom:0.3em;'><span class='icon'>📢</span> <strong>Project disclaimer</strong></div>
          AzTier is not a Microsoft service or product, but a personal project with no implicit or explicit obligations. For more information, see the project's <a href='https://github.com/emiliensocchi/azure-tiering?tab=readme-ov-file#-disclaimer' target='_blank' style='color:#888;text-decoration:underline dotted;'>original disclaimer</a>.
        </div>`;
    } catch (e) {
      document.getElementById('config-section-content').innerHTML = `<span class='has-text-danger'>Error loading configuration: ${e.message}</span>`;
    }
  } else {
    document.getElementById('config-section-content').innerHTML = `<span class='has-text-danger'>No project_configuration_uri found in config.json.</span>`;
  }
}

// Function to open the popup and load JSON data
async function showJsonPopup(url, title) {
  const popup = document.getElementById('json-popup');
  const content = document.getElementById('json-content');
  const popupTitle = document.getElementById('json-popup-title');
  content.innerHTML = '<p>Loading...</p>';
  popupTitle.textContent = title;
  popup.classList.add('is-active');

  try {
    const response = await fetch(url);
    if (!response.ok) throw new Error('Failed to fetch data');
    const data = await response.json();
    content.innerHTML = `<pre>${JSON.stringify(data, null, 2)}</pre>`;
  } catch (error) {
    content.innerHTML = `<p class="has-text-danger">Error: ${error.message}</p>`;
  }
}

async function showCustomDefinitionPopup(tab, roleId) {
  const item = allData[tab].find(d => d.id === roleId);
  if (!item) return;

  const popup = document.getElementById('json-popup');
  const content = document.getElementById('json-content');
  const popupTitle = document.getElementById('json-popup-title');

  popupTitle.textContent = `Custom documentation: ${item.assetName}`;
  
  let definitionHtml = '<div class="popup-section">';
  definitionHtml += `<span class=\"popup-section-title\"><span class=\"icon\">📝</span> <strong>Definition</strong></span>`;
  definitionHtml += `<div class=\"popup-section-value\" style=\"margin-bottom:0.7em;\">${item.assetDefinition || '<span class=\"has-text-grey\">No definition available.</span>'}</div>`;
  definitionHtml += `<span class=\"popup-section-title\"><span class=\"icon\">🔍</span> <strong>Assignable Scope</strong></span>`;
  if (item.assignableScope) {
    // If assignableScope contains a comma, split and show as a list
    if (item.assignableScope.includes(',')) {
      const scopes = item.assignableScope.split(',').map(s => s.trim()).filter(Boolean);
      // Use only padding-left for <ul> to ensure bullet points are visible
      definitionHtml += `<ul style='margin:0.5em 0 0.5em 0;padding-left:1.5em;list-style-type:disc;'>` +
        scopes.map(scope => `<li style='list-style-position:inside;'><code style='font-size:1em;'>${scope}</code></li>`).join('') +
        `</ul>`;
    } else {
      definitionHtml += `<div class=\"popup-section-value\"><code style='font-size:1em;'>${item.assignableScope}</code></div>`;
    }
  } else {
    definitionHtml += '<span class=\"has-text-grey\">No assignable scope specified.</span>';
  }
  definitionHtml += '</div>';

  content.innerHTML = definitionHtml;
  popup.classList.add('is-active');
}

// Function to close the popup
function closeJsonPopup() {
  const popup = document.getElementById('json-popup');
  popup.classList.remove('is-active');
}

// Attach event listeners for closing the popup
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('close-popup').addEventListener('click', closeJsonPopup);
  document.querySelector('.modal-background').addEventListener('click', closeJsonPopup);
});

// Update the onclick handlers to pass the appropriate title
function addMoreInfoButtons() {
  const entraMoreInfoBtn = document.createElement('button');
  entraMoreInfoBtn.className = 'button is-small is-info';
  entraMoreInfoBtn.textContent = 'More Info';
  entraMoreInfoBtn.onclick = () => showJsonPopup(UNTIERED_FILES.entra, 'Currently untiered Entra roles');

  const msGraphMoreInfoBtn = document.createElement('button');
  msGraphMoreInfoBtn.className = 'button is-small is-info';
  msGraphMoreInfoBtn.textContent = 'More Info';
  msGraphMoreInfoBtn.onclick = () => showJsonPopup(UNTIERED_FILES.msgraph, 'Currently untiered MS Graph application permissions');

  // Append buttons to respective sections (assuming IDs exist for these sections)
  const entraSection = document.getElementById('entra-untiered-section');
  const msGraphSection = document.getElementById('msgraph-untiered-section');

  if (entraSection) entraSection.appendChild(entraMoreInfoBtn);
  if (msGraphSection) msGraphSection.appendChild(msGraphMoreInfoBtn);
}

// Show a badge with emoji and label for assetType (Built-in or Custom) in the expanded accordion details for each role/permission.
function getAssetTypeBadge(assetType) {
  if (!assetType) return '';
  const type = assetType.toLowerCase();
  if (type === 'built-in') {
    return '<span class="asset-type-badge built-in" title="Built-in" style="background:#e3f0ff;color:#3570b3;border-radius:0.7em;padding:0.15em 0.7em;font-size:0.85em;margin-right:0.5em;display:inline-flex;align-items:center;gap:0.3em;"><span style="font-size:1.1em;">🏗️</span>Built-in</span>';
  } else if (type === 'custom') {
    return '<span class="asset-type-badge custom" title="Custom" style="background:#fff4e3;color:#b36a00;border-radius:0.7em;padding:0.15em 0.7em;font-size:0.85em;margin-right:0.5em;display:inline-flex;align-items:center;gap:0.3em;"><span style="font-size:1.1em;">🛠️</span>Custom</span>';
  }
  return '';
}
