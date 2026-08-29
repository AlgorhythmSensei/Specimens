const canvas = document.querySelector('#world');
const ctx = canvas.getContext('2d');
const connection = document.querySelector('#connection');
const state = { specimens: [], zones: [], teleporter: { x: 500, y: 500 }, running: true };
const trails = new Map();
const animalTrails = new Map();
let previousPacket = null;
let priorPacket = null;
let currentSimulationNumber = null;
let packetReceivedAt = performance.now();
let animationFrame = 0;
let purgeFrame = 0;
let editLayoutMode = false;
let draggingZone = null;
let hoveredId = null;
let hoveredDeathMarker = null;
let selectedId = null;
let selectedAnimalId = null;
let focusedId = null;
let hoverTimeout = null;

function clearHoverCards() {
  hoveredId = null;
  hoveredDeathMarker = null;
  document.querySelector('#hover-card').setAttribute('aria-hidden', 'true');
  const zc = document.querySelector('#zone-card');
  zc.setAttribute('aria-hidden', 'true');
  zc.dataset.zone = '';
  zc.dataset.resourceId = '';
  zc.dataset.teleporter = 'false';
  canvas.style.cursor = 'default';
}

function resetHoverTimer() {
  clearTimeout(hoverTimeout);
  hoverTimeout = setTimeout(clearHoverCards, 7000);
}
const colors = { cafe: '#f2b56b', bar: '#d79b88', church: '#b8a8cf', forest: '#9bbd91', homes: '#c7b9a2', pop_up: '#e8d85d', forest_shelter: '#a08060', work: '#7ab3c8' };
const venueDescriptions = {
  cafe: ['Coffee, gossip, and hurried breakfasts.', 'A warm refuge where hunger becomes conversation.'],
  bar: ['Live music, risky bargains, and late-night alliances.', 'A loud corner for flirtation, wagers, and old grudges.'],
  church: ['Quiet reflection, kindness, and unlikely forgiveness.', 'A candlelit meeting place for vows, solace, and secrets.'],
  forest: ['Hiking trails by day; improvised camps after dark.', 'A shadowed shelter where the homeless gather beneath the canopy.'],
  homes: ['Twenty small apartments where households rest and grow.', 'A close-knit residential district full of arrivals and departures.'],
  pop_up: ['A social event is active here.'],
  forest_shelter: ['A makeshift shelter built by forest dwellers. Bears cannot enter.', 'Rough walls of gathered wood and leaves — safer than open ground.'],
  work: ['An office district. Employed adults report here 8:00–17:00.', 'Salaries vary — some earn considerably more than others.'],
};

function zoneTitle(name) { return name === 'pop_up' ? 'SOCIAL EVENT' : name === 'forest_shelter' ? 'FOREST SHELTER' : name === 'work' ? 'WORK' : name.replace('_', ' ').toUpperCase(); }
function zoneDescription(zone, packet) { if (zone.name === 'pop_up' && packet.event_topic) return packet.event_topic; const descriptions = venueDescriptions[zone.name] || ['A place of uncertain significance.']; return descriptions[Math.floor(packet.tick / 40) % descriptions.length]; }

function draw(packet) {
  packet.specimens.forEach(specimen => {
    if (specimen.action === 'teleported') { trails.set(specimen.id, []); return; }
    const trail = trails.get(specimen.id) || [];
    const last = trail[trail.length - 1];
    if (!last || Math.hypot(last.x - specimen.x, last.y - specimen.y) > 0.5) trail.push({ x: specimen.x, y: specimen.y });
    trails.set(specimen.id, trail.slice(-12));
  });
  packet.animals.forEach(animal => {
    const trail = animalTrails.get(animal.id) || [];
    const last = trail[trail.length - 1];
    if (!last || Math.hypot(last.x - animal.x, last.y - animal.y) > 0.5) trail.push({ x: animal.x, y: animal.y });
    animalTrails.set(animal.id, trail.slice(-8));
  });
  const activeIds = new Set(packet.specimens.map(specimen => specimen.id));
  trails.forEach((_, id) => { if (!activeIds.has(id)) trails.delete(id); });
  if (focusedId !== null && !activeIds.has(focusedId)) focusedId = null;
  const activeAnimalIds = new Set(packet.animals.map(animal => animal.id));
  animalTrails.forEach((_, id) => { if (!activeAnimalIds.has(id)) animalTrails.delete(id); });
  if (packet.simulation_number !== currentSimulationNumber) {
    trails.clear();
    animalTrails.clear();
    priorPacket = null;
    currentSimulationNumber = packet.simulation_number;
  }
  priorPacket = previousPacket;
  previousPacket = packet;
  packetReceivedAt = performance.now();
  updateAgentCards(packet);
  render(interpolatedPacket());
}

function interpolatedPacket() {
  if (!previousPacket || !priorPacket) return previousPacket;
  const progress = Math.min(1, (performance.now() - packetReceivedAt) / 100);
  const priorById = new Map(priorPacket.specimens.map(specimen => [specimen.id, specimen]));
  const priorAnimals = new Map(priorPacket.animals.map(animal => [animal.id, animal]));
  return { ...previousPacket, specimens: previousPacket.specimens.map(specimen => { const prior = priorById.get(specimen.id) || specimen; return { ...specimen, x: prior.x + (specimen.x - prior.x) * progress, y: prior.y + (specimen.y - prior.y) * progress }; }), animals: previousPacket.animals.map(animal => { const prior = priorAnimals.get(animal.id) || animal; return { ...animal, x: prior.x + (animal.x - prior.x) * progress, y: prior.y + (animal.y - prior.y) * progress }; }) };
}

function render(packet) {
  const timeInterp = packet.running !== false ? (performance.now() - packetReceivedAt) * (packet.time_scale || 1) / 25000 : 0;
  const liveTimeOfDay = (packet.time_of_day + timeInterp) % 24;
  ctx.clearRect(0, 0, 1000, 1000);
  ctx.fillStyle = '#dce2d5'; ctx.fillRect(0, 0, 1000, 1000);
  if (packet.weather === 'rain' || packet.weather === 'storm') {
    const count = packet.weather === 'storm' ? 200 : 120;
    ctx.strokeStyle = packet.weather === 'storm' ? 'rgba(140,180,220,0.55)' : 'rgba(140,180,220,0.35)';
    ctx.lineWidth = 1;
    for (let i = 0; i < count; i++) {
      const rx = (animationFrame * 7 + i * 137) % 1000;
      const ry = (animationFrame * 12 + i * 97) % 1000;
      ctx.beginPath();
      ctx.moveTo(rx, ry);
      ctx.lineTo(rx + 8, ry + 18);
      ctx.stroke();
    }
  }
  if (packet.weather === 'drought') {
    ctx.fillStyle = 'rgba(200,140,40,0.06)';
    ctx.fillRect(0, 0, 1000, 1000);
  }
  const DRAGGABLE_ZONES = new Set(['cafe', 'bar', 'work', 'church']);
  packet.zones.forEach(zone => {
    const rx = draggingZone?.name === zone.name ? draggingZone.currentX : zone.x;
    const ry = draggingZone?.name === zone.name ? draggingZone.currentY : zone.y;
    const isDragging = draggingZone?.name === zone.name;
    ctx.fillStyle = colors[zone.name] || '#dce2d5';
    if (isDragging) ctx.globalAlpha = 0.75;
    ctx.fillRect(rx, ry, zone.width, zone.height);
    ctx.globalAlpha = 1;
    ctx.strokeStyle = isDragging ? '#f06b3f' : (editLayoutMode && DRAGGABLE_ZONES.has(zone.name) ? '#f06b3f' : '#788277');
    ctx.lineWidth = isDragging ? 2.5 : 1;
    ctx.setLineDash(isDragging ? [8, 4] : [6, 6]);
    ctx.strokeRect(rx, ry, zone.width, zone.height);
    ctx.setLineDash([]);
    ctx.lineWidth = 1;
    ctx.fillStyle = '#536057';
    ctx.font = '16px DM Mono';
    ctx.fillText(zoneTitle(zone.name), rx + 12, ry + 25);
    if (editLayoutMode && DRAGGABLE_ZONES.has(zone.name) && !isDragging) { ctx.font = '10px DM Mono'; ctx.fillStyle = '#f06b3f'; ctx.fillText('DRAG TO MOVE', rx + 12, ry + zone.height - 10); }
  });
  (packet.death_markers || []).forEach(marker => { ctx.strokeStyle = '#9c3f54'; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(marker.x - 7, marker.y - 7); ctx.lineTo(marker.x + 7, marker.y + 7); ctx.moveTo(marker.x + 7, marker.y - 7); ctx.lineTo(marker.x - 7, marker.y + 7); ctx.stroke(); });
  (packet.fight_locations || []).forEach(loc => { const pulse = Math.sin(animationFrame / 3) * 6; ctx.beginPath(); ctx.arc(loc.x, loc.y, 26 + pulse, 0, Math.PI * 2); ctx.strokeStyle = 'rgba(232,57,57,0.55)'; ctx.lineWidth = 3; ctx.globalAlpha = 0.5 + Math.sin(animationFrame / 3) * 0.5; ctx.stroke(); ctx.globalAlpha = 1; ctx.font = '700 13px DM Mono'; ctx.fillStyle = 'rgba(232,57,57,0.8)'; ctx.fillText('FIGHT', loc.x - 18, loc.y - 30); });
  packet.plants.forEach(plant => { ctx.strokeStyle = plant.poisonous ? '#9c3f54' : '#3f8f50'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(plant.x, plant.y + 5); ctx.lineTo(plant.x, plant.y - 5); ctx.moveTo(plant.x, plant.y); ctx.quadraticCurveTo(plant.x - 7, plant.y - 7, plant.x - 6, plant.y - 1); ctx.moveTo(plant.x, plant.y - 1); ctx.quadraticCurveTo(plant.x + 7, plant.y - 8, plant.x + 6, plant.y - 2); ctx.stroke(); });
  packet.animals.forEach(animal => { const trail = animalTrails.get(animal.id) || []; const isBear = animal.species === 'bear'; if (trail.length > 1) { const rgb = isBear ? [63,40,28] : [139,84,47]; const maxAlpha = isBear ? 0.5 : 0.38; for (let i = 1; i < trail.length; i++) { const alpha = (i / trail.length) * maxAlpha; ctx.beginPath(); ctx.moveTo(trail[i-1].x, trail[i-1].y); ctx.lineTo(trail[i].x, trail[i].y); ctx.strokeStyle = `rgba(${rgb[0]},${rgb[1]},${rgb[2]},${alpha})`; ctx.lineWidth = isBear ? 3 : 1.5; ctx.stroke(); } } ctx.fillStyle = isBear ? '#4a3024' : '#8b542f'; ctx.beginPath(); ctx.ellipse(animal.x, animal.y, isBear ? 10 : 7, isBear ? 7 : 4, 0, 0, Math.PI * 2); ctx.fill(); ctx.beginPath(); ctx.arc(animal.x + (isBear ? 9 : 7), animal.y - 2, isBear ? 4 : 3, 0, Math.PI * 2); ctx.fill(); ctx.strokeStyle = isBear ? '#4a3024' : '#8b542f'; ctx.lineWidth = 1.5; [-4, 1].forEach(offset => { ctx.beginPath(); ctx.moveTo(animal.x + offset, animal.y + 2); ctx.lineTo(animal.x + offset - 1, animal.y + 6); ctx.stroke(); }); if (animal.sleeping) { ctx.font = '500 12px DM Mono'; ctx.fillStyle = '#536057'; ctx.fillText('Zzz', animal.x + 10, animal.y - 8); } if (isBear && animal.mad) { ctx.font = '500 11px DM Mono'; ctx.fillStyle = '#9c3f54'; ctx.fillText('MAD', animal.x + 13, animal.y + 13); } if (animal.new_arrival) { const r = (isBear ? 10 : 7) + 7 + Math.sin(animationFrame / 4) * 3; ctx.beginPath(); ctx.arc(animal.x, animal.y, r, 0, Math.PI * 2); ctx.strokeStyle = '#54a66d'; ctx.globalAlpha = 0.45 + (Math.sin(animationFrame / 4) + 1) * 0.25; ctx.lineWidth = 2; ctx.stroke(); ctx.globalAlpha = 1; }
    if (animal.mating) { const blink = Math.abs(Math.sin(animationFrame / 5)); const pulse = Math.sin(animationFrame / 4) * 3; ctx.beginPath(); ctx.arc(animal.x, animal.y, (isBear ? 10 : 7) + 9 + pulse, 0, Math.PI * 2); ctx.strokeStyle = '#ff69b4'; ctx.lineWidth = 2; ctx.globalAlpha = 0.4 + blink * 0.6; ctx.stroke(); ctx.globalAlpha = 1; ctx.font = `700 ${Math.round(11 + blink * 3)}px DM Mono`; ctx.fillStyle = '#ff69b4'; ctx.globalAlpha = blink; ctx.fillText('♥', animal.x - 4, animal.y - (isBear ? 10 : 7) - 6); ctx.fillText('♥', animal.x + (isBear ? 10 : 7) + 8, animal.y); ctx.globalAlpha = 1; } });
  const tGrow = packet.teleporter.grow_phase || 0; const tRadius = 13 + tGrow * 52 + Math.sin(animationFrame / 8) * (tGrow > 0 ? 6 : 3); ctx.beginPath(); ctx.arc(packet.teleporter.x, packet.teleporter.y, tRadius, 0, Math.PI * 2); ctx.fillStyle = '#d9f264'; ctx.shadowColor = '#d9f264'; ctx.shadowBlur = tGrow > 0 ? 45 + tGrow * 30 : 25; ctx.globalAlpha = tGrow > 0 ? 0.6 + tGrow * 0.4 : 1; ctx.fill(); ctx.globalAlpha = 1; ctx.shadowBlur = 0; if (tGrow > 0) { ctx.beginPath(); ctx.arc(packet.teleporter.x, packet.teleporter.y, tRadius + 8, 0, Math.PI * 2); ctx.strokeStyle = `rgba(217,242,100,${tGrow * 0.5})`; ctx.lineWidth = 3; ctx.stroke(); }
  packet.specimens.forEach(specimen => {
    const trail = trails.get(specimen.id) || [];
    if (trail.length > 1) { const manColor = [232,91,57]; const womanColor = [53,111,120]; const rgb = specimen.gender === 'man' ? manColor : womanColor; for (let i = 1; i < trail.length; i++) { const alpha = (i / trail.length) * 0.35; ctx.beginPath(); ctx.moveTo(trail[i-1].x, trail[i-1].y); ctx.lineTo(trail[i].x, trail[i].y); ctx.strokeStyle = `rgba(${rgb[0]},${rgb[1]},${rgb[2]},${alpha})`; ctx.lineWidth = 1.5; ctx.stroke(); } }
    const radius = 5 + Math.min(4, specimen.hunger / 35); const previous = trail[trail.length - 2] || specimen; const directionX = specimen.x - previous.x; const directionY = specimen.y - previous.y;
    ctx.beginPath(); ctx.moveTo(specimen.x, specimen.y); ctx.lineTo(specimen.x + directionX * 2, specimen.y + directionY * 2); ctx.strokeStyle = '#19231f'; ctx.lineWidth = 2; ctx.stroke();
    ctx.fillStyle = specimen.gender === 'man' ? '#e85b39' : '#356f78'; ctx.beginPath(); ctx.arc(specimen.x, specimen.y - 4, 3, 0, Math.PI * 2); ctx.fill(); ctx.beginPath(); ctx.ellipse(specimen.x, specimen.y + 2, radius - 1, radius + 1, 0, 0, Math.PI * 2); ctx.fill();
    const isNotable = ['teleported', 'conflict'].includes(specimen.action);
    if (isNotable) { ctx.beginPath(); ctx.arc(specimen.x, specimen.y, radius + 7 + Math.sin(animationFrame / 5) * 2, 0, Math.PI * 2); ctx.strokeStyle = specimen.action === 'teleported' ? '#d9f264' : '#19231f'; ctx.lineWidth = 2; ctx.stroke(); }
    if (specimen.sleeping) { ctx.font = '500 12px DM Mono'; ctx.fillStyle = '#536057'; ctx.fillText('Zzz', specimen.x + radius + 9, specimen.y - radius - 5); } else if (isNotable || specimen.id === hoveredId || specimen.id === selectedId) { ctx.font = '500 13px DM Mono'; ctx.fillStyle = '#19231f'; ctx.fillText(specimen.action.toUpperCase(), specimen.x + radius + 9, specimen.y - radius - 5); }
    if (specimen.action === 'fighting' || specimen.action === 'being_attacked' || specimen.action === 'retaliating') { const pulse = Math.sin(animationFrame / 3) * 4; ctx.beginPath(); ctx.arc(specimen.x, specimen.y, radius + 11 + pulse, 0, Math.PI * 2); ctx.strokeStyle = specimen.action === 'fighting' ? '#e83939' : '#f5a623'; ctx.lineWidth = 3; ctx.globalAlpha = 0.65 + Math.sin(animationFrame / 3) * 0.35; ctx.stroke(); ctx.globalAlpha = 1; }
    if (specimen.mating) { const blink = Math.abs(Math.sin(animationFrame / 5)); const pulse = Math.sin(animationFrame / 4) * 3; ctx.beginPath(); ctx.arc(specimen.x, specimen.y, radius + 9 + pulse, 0, Math.PI * 2); ctx.strokeStyle = '#ff69b4'; ctx.lineWidth = 2.5; ctx.globalAlpha = 0.4 + blink * 0.6; ctx.stroke(); ctx.globalAlpha = 1; ctx.font = `700 ${Math.round(12 + blink * 4)}px DM Mono`; ctx.fillStyle = '#ff69b4'; ctx.globalAlpha = blink; ctx.fillText('♥', specimen.x - 4, specimen.y - radius - 6); ctx.fillText('♥', specimen.x + radius + 7, specimen.y); ctx.globalAlpha = 1; }
    if (specimen.pregnant) { ctx.beginPath(); ctx.arc(specimen.x, specimen.y, radius + 5 + Math.sin(animationFrame / 6) * 2, 0, Math.PI * 2); ctx.strokeStyle = '#e87dbf'; ctx.lineWidth = 2.5; ctx.stroke(); ctx.font = '700 11px DM Mono'; ctx.fillStyle = '#e87dbf'; ctx.fillText('♥', specimen.x + radius + 9, specimen.y + radius + 13); }
    if (specimen.new_arrival) { ctx.beginPath(); ctx.arc(specimen.x, specimen.y, radius + 7 + Math.sin(animationFrame / 3) * 3, 0, Math.PI * 2); ctx.strokeStyle = '#f5e642'; ctx.lineWidth = 3; ctx.stroke(); ctx.font = '700 11px DM Mono'; ctx.fillStyle = '#f5e642'; ctx.fillText('NEW', specimen.x + radius + 9, specimen.y + radius + 13); }
    if (specimen.id === focusedId) { const pulse = Math.sin(animationFrame / 6) * 3; ctx.beginPath(); ctx.arc(specimen.x, specimen.y, radius + 13 + pulse, 0, Math.PI * 2); ctx.strokeStyle = specimen.id === selectedId ? '#54a66d' : '#19231f'; ctx.lineWidth = 3; ctx.stroke(); ctx.beginPath(); ctx.moveTo(specimen.x - radius - 18, specimen.y); ctx.lineTo(specimen.x - radius - 7, specimen.y); ctx.moveTo(specimen.x + radius + 7, specimen.y); ctx.lineTo(specimen.x + radius + 18, specimen.y); ctx.moveTo(specimen.x, specimen.y - radius - 18); ctx.lineTo(specimen.x, specimen.y - radius - 7); ctx.moveTo(specimen.x, specimen.y + radius + 7); ctx.lineTo(specimen.x, specimen.y + radius + 18); ctx.strokeStyle = specimen.id === selectedId ? '#54a66d' : '#19231f'; ctx.stroke(); ctx.font = '600 13px DM Mono'; ctx.fillStyle = specimen.id === selectedId ? '#54a66d' : '#19231f'; ctx.fillText(specimen.name, specimen.x + radius + 22, specimen.y + 4); }
    if (specimen.id === selectedId) { ctx.beginPath(); ctx.arc(specimen.x, specimen.y, radius + 19 + Math.sin(animationFrame / 4) * 4, 0, Math.PI * 2); ctx.strokeStyle = '#54a66d'; ctx.globalAlpha = 0.45 + (Math.sin(animationFrame / 4) + 1) * 0.2; ctx.lineWidth = 4; ctx.stroke(); ctx.globalAlpha = 1; }
  });
  if (packet.game_over && purgeFrame > 0) {
    const p = Math.min(1, Math.max(0, (animationFrame - purgeFrame) / 80));
    const r = Math.round(180 + 60 * p), g = Math.round(40 * (1 - p)), b = 0;
    ctx.fillStyle = `rgba(${r},${g},${b},${0.4 + p * 0.55})`; ctx.fillRect(0, 0, 1000, 1000);
    for (let i = 0; i < 18 * p; i++) { const bx = Math.sin(animationFrame * 0.07 + i * 1.7) * 480 + 500; const by = Math.cos(animationFrame * 0.05 + i * 2.1) * 480 + 500; const br = 6 + Math.sin(animationFrame * 0.1 + i) * 4; ctx.beginPath(); ctx.arc(bx, by, br, 0, Math.PI * 2); ctx.fillStyle = `rgba(255,${Math.round(100 + 60 * Math.random())},0,${0.6 + Math.random() * 0.4})`; ctx.fill(); }
    ctx.font = `700 ${Math.round(48 + p * 24)}px DM Mono`; ctx.fillStyle = `rgba(255,200,0,${p})`; ctx.textAlign = 'center'; ctx.fillText('⚡ PURGED ⚡', 500, 420);
    ctx.font = '500 20px DM Mono'; ctx.fillStyle = `rgba(255,100,0,${p})`; ctx.fillText('The world was destroyed.', 500, 480);
    ctx.font = '400 14px DM Mono'; ctx.fillStyle = `rgba(255,200,0,${p * 0.8})`; ctx.fillText('Reset to rebuild civilisation.', 500, 516); ctx.textAlign = 'left';
  } else if (packet.game_over) { ctx.fillStyle = 'rgba(30,70,30,0.82)'; ctx.fillRect(0, 0, 1000, 1000); ctx.font = '700 64px DM Mono'; ctx.fillStyle = '#9bbd91'; ctx.textAlign = 'center'; ctx.fillText('NATURE WINS', 500, 420); ctx.font = '500 22px DM Mono'; ctx.fillStyle = '#d9f264'; ctx.fillText('The forest reclaimed the world.', 500, 480); ctx.font = '400 16px DM Mono'; ctx.fillStyle = '#9bbd91'; ctx.fillText('Reset to begin a new simulation.', 500, 520); ctx.textAlign = 'left'; } else if (packet.reclamation_active) { const cov = packet.forest_coverage || 0; ctx.fillStyle = `rgba(30,70,30,${Math.min(0.55, cov * 0.7)})`; ctx.fillRect(0, 0, 1000, 1000); ctx.font = '700 28px DM Mono'; ctx.fillStyle = '#9bbd91'; ctx.textAlign = 'center'; ctx.fillText(`NATURE RECLAIMS — ${Math.round(cov * 100)}%`, 500, 500); ctx.textAlign = 'left'; }
  const simDay = packet.day_number || 1; const dayNames = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']; const dayName = dayNames[(simDay - 1) % 7];
  const hh = String(Math.floor(liveTimeOfDay)).padStart(2, '0'); const mm = String(Math.floor(liveTimeOfDay % 1 * 60)).padStart(2, '0');
  document.querySelector('#population').textContent = packet.specimens.length; document.querySelector('#homeless').textContent = packet.specimens.filter(s => s.is_homeless).length; document.querySelector('#tick').textContent = packet.tick.toLocaleString(); document.querySelector('#clock').textContent = `${dayName}  ${hh}:${mm}`; document.querySelector('#phase').textContent = liveTimeOfDay >= 6 && liveTimeOfDay < 18 ? 'DAYLIGHT' : 'NIGHT';
  document.querySelector('#weather').textContent = (packet.weather || 'clear').toUpperCase();
  document.querySelector('#deer-count').textContent = packet.deer_count ?? '--';
  document.querySelector('#plant-count').textContent = packet.plant_count ?? '--';
  document.querySelector('#poisonous-count').textContent = packet.poisonous_plant_count ?? '--';
  document.querySelector('#simulation-label').textContent = `TEST SIMULATION #${packet.simulation_number} · Day ${simDay}`;
  const events = document.querySelector('#events'); const notable = packet.specimens.filter(s => ['teleported', 'copulating', 'gave_birth', 'became_father', 'caught_stealing', 'caught_deer', 'fighting', 'being_attacked', 'killed_bear', 'fighting_bear', 'fleeing_to_safety', 'watching_fight', 'sneaking_to_partner', 'with_partner', 'attacked_by_mad_bear'].includes(s.action)).slice(0, 6); events.innerHTML = notable.length ? notable.map(s => `<div class="event"><b>${s.name || '#' + s.id}</b> ${s.action.replace(/_/g,' ')}</div>`).join('') : '<div class="event">Population moving through the field.</div>';
  const analysis = document.querySelector('#analysis-list'); analysis.innerHTML = (packet.behavior_analysis || []).map(item => `<button class="analysis-item" data-specimen-id="${item.id}"><b>${item.name}</b><span>${item.action} · ${item.points} pts</span><p>${item.reason}</p></button>`).join('');
  analysis.querySelectorAll('.analysis-item').forEach(item => item.addEventListener('click', () => { selectedId = Number(item.dataset.specimenId); focusedId = selectedId; document.querySelector('#world').scrollIntoView({ behavior: 'smooth', block: 'center' }); updateAgentCards(packet); }));
}

function specimenAtEvent(event, packet = previousPacket) {
  if (!packet) return null;
  const bounds = canvas.getBoundingClientRect();
  const x = (event.clientX - bounds.left) * 1000 / bounds.width;
  const y = (event.clientY - bounds.top) * 1000 / bounds.height;
  return packet.specimens.reduce((closest, specimen) => {
    const distance = Math.hypot(specimen.x - x, specimen.y - y);
    return distance < (closest?.distance ?? 22) ? { specimen, distance } : closest;
  }, null);
}

function zoneAtEvent(event, packet = previousPacket) {
  if (!packet) return null;
  const bounds = canvas.getBoundingClientRect();
  const point = { x: (event.clientX - bounds.left) * 1000 / bounds.width, y: (event.clientY - bounds.top) * 1000 / bounds.height };
  return packet.zones.find(zone => point.x >= zone.x && point.x <= zone.x + zone.width && point.y >= zone.y && point.y <= zone.y + zone.height);
}

function resourceAtEvent(event, packet = previousPacket) {
  if (!packet) return null;
  const bounds = canvas.getBoundingClientRect();
  const point = { x: (event.clientX - bounds.left) * 1000 / bounds.width, y: (event.clientY - bounds.top) * 1000 / bounds.height };
  return [...packet.plants, ...packet.animals].reduce((closest, resource) => { const distance = Math.hypot(resource.x - point.x, resource.y - point.y); return distance < (closest?.distance ?? 16) ? { resource, distance } : closest; }, null);
}

function deathMarkerAtEvent(event, packet = previousPacket) {
  if (!packet) return null;
  const bounds = canvas.getBoundingClientRect();
  const point = { x: (event.clientX - bounds.left) * 1000 / bounds.width, y: (event.clientY - bounds.top) * 1000 / bounds.height };
  return (packet.death_markers || []).reduce((closest, marker) => { const distance = Math.hypot(marker.x - point.x, marker.y - point.y); return distance < (closest?.distance ?? 18) ? { marker, distance } : closest; }, null);
}

function teleporterAtEvent(event, packet = previousPacket) {
  if (!packet) return false;
  const bounds = canvas.getBoundingClientRect();
  const point = { x: (event.clientX - bounds.left) * 1000 / bounds.width, y: (event.clientY - bounds.top) * 1000 / bounds.height };
  return Math.hypot(packet.teleporter.x - point.x, packet.teleporter.y - point.y) < 28;
}

function vitalsMarkup(specimen) {
  return `<div><span>HUNGER</span><strong>${specimen.hunger}%</strong></div><div><span>FATIGUE</span><strong>${specimen.fatigue}%</strong></div><div><span>WALLET</span><strong>$${specimen.wallet}</strong></div><div><span>STATUS</span><strong>${specimen.is_homeless ? 'homeless' : 'housed'}</strong></div><div><span>GENDER</span><strong>${specimen.gender}</strong></div><div><span>ACTION</span><strong>${specimen.action}</strong></div><div><span>REPUTATION</span><strong>${specimen.reputation}</strong></div>`;
}

function animalVitalsMarkup(animal) {
  const maxEnergy = animal.species === 'bear' ? 60 : 28;
  const energyPct = Math.round(animal.energy / maxEnergy * 100);
  const rows = [
    ['SPECIES', animal.species],
    ['ENERGY', `${energyPct}%`],
    ['STATE', animal.sleeping ? 'sleeping' : animal.mad ? 'enraged' : animal.species === 'bear' ? 'hunting' : 'grazing'],
  ];
  return rows.map(([k, v]) => `<div><span>${k}</span><strong>${v}</strong></div>`).join('');
}

function updateAgentCards(packet) {
  if (!packet) return;
  const hovered = packet.specimens.find(specimen => specimen.id === hoveredId);
  const selected = packet.specimens.find(specimen => specimen.id === selectedId);
  const selectedAnimal = selectedAnimalId ? [...packet.animals].find(a => a.id === selectedAnimalId) : null;
  const hoverCard = document.querySelector('#hover-card');
  const zoneCard = document.querySelector('#zone-card');
  const selectedCard = document.querySelector('#selected-card');
  hoverCard.innerHTML = hovered ? `<b>#${hovered.id}</b><span>${hovered.action} · hunger ${hovered.hunger}%</span>` : '';
  hoverCard.setAttribute('aria-hidden', String(!hovered));
  const zone = packet.zones.find(candidate => candidate.name === zoneCard.dataset.zone);
  zoneCard.innerHTML = zone ? `<b>${zoneTitle(zone.name)}</b><span>${zoneDescription(zone, packet)}</span>` : '';
  const resource = zoneCard.dataset.resourceId ? [...packet.plants, ...packet.animals].find(candidate => String(candidate.id) === zoneCard.dataset.resourceId) : null;
  if (resource) {
    if (resource.kind === 'animal') {
      const energyPct = Math.round(resource.energy / (resource.species === 'bear' ? 60 : 28) * 100);
      const desc = resource.species === 'bear'
        ? (resource.mad ? 'MAD: will attack anything nearby.' : 'Predator — hunts deer and threatens specimens.')
        : 'Herbivore — grazes on plants, flees bears and humans.';
      zoneCard.innerHTML = `<b>${resource.species.toUpperCase()} #${resource.id}</b><span>${desc}</span><span>Energy ${energyPct}% · ${resource.sleeping ? 'sleeping' : resource.mad ? 'enraged' : 'active'}</span>`;
    } else {
      zoneCard.innerHTML = `<b>PLANT #${resource.id}</b><span>${resource.poisonous ? 'POISONOUS — deadly if eaten.' : 'Safe plant, edible by any creature.'}</span><span>Energy ${Math.round(resource.energy / 18 * 100)}%</span>`;
    }
  }
  if (zoneCard.dataset.teleporter === 'true') zoneCard.innerHTML = '<b>TELEPORTER ORB</b><span>A volatile moving orb. Touching it instantly sends a specimen to a random location in the world.</span>';
  if (hoveredDeathMarker) zoneCard.innerHTML = `<b>${hoveredDeathMarker.name}</b><span>${hoveredDeathMarker.entity_type === 'animal' ? 'Animal' : 'Specimen'} died from ${hoveredDeathMarker.cause.replaceAll('_', ' ')} while ${hoveredDeathMarker.action.replaceAll('_', ' ')}.</span>`;
  zoneCard.setAttribute('aria-hidden', String(Boolean(hovered) || (!zone && !resource && zoneCard.dataset.teleporter !== 'true')));
  selectedCard.setAttribute('aria-hidden', String(!selected && !selectedAnimal));
  if (selected) {
    const analysis = packet.behavior_analysis?.find(item => item.id === selected.id);
    document.querySelector('#selected-name').textContent = `${selected.name} #${selected.id}`;
    document.querySelector('#selected-vitals').innerHTML = `${vitalsMarkup(selected)}${analysis ? `<div class="analysis-detail"><span>WHY</span><strong>${analysis.reason}</strong></div>` : ''}`;
    document.querySelector('.card-kicker').textContent = 'SPECIMEN VITALS';
  } else if (selectedAnimal) {
    document.querySelector('#selected-name').textContent = `${selectedAnimal.species.toUpperCase()} #${selectedAnimal.id}`;
    document.querySelector('#selected-vitals').innerHTML = animalVitalsMarkup(selectedAnimal);
    document.querySelector('.card-kicker').textContent = 'ANIMAL VITALS';
  }
}

canvas.addEventListener('pointermove', event => {
  if (draggingZone) {
    const bounds = canvas.getBoundingClientRect();
    const mouseX = (event.clientX - bounds.left) * 1000 / bounds.width;
    const mouseY = (event.clientY - bounds.top) * 1000 / bounds.height;
    draggingZone.currentX = Math.max(0, Math.min(1000 - draggingZone.width, draggingZone.startZoneX + mouseX - draggingZone.startMouseX));
    draggingZone.currentY = Math.max(0, Math.min(1000 - draggingZone.height, draggingZone.startZoneY + mouseY - draggingZone.startMouseY));
    canvas.style.cursor = 'grabbing';
    return;
  }
  const hit = specimenAtEvent(event);
  const zone = zoneAtEvent(event);
  const resourceHit = resourceAtEvent(event);
  const deathHit = deathMarkerAtEvent(event);
  const teleporterHit = teleporterAtEvent(event);
  hoveredId = hit?.specimen.id ?? null;
  hoveredDeathMarker = !hit && deathHit ? deathHit.marker : null;
  if (editLayoutMode && zone && new Set(['cafe','bar','work','church']).has(zone.name)) { canvas.style.cursor = 'grab'; }
  else { canvas.style.cursor = hit || resourceHit || teleporterHit || hoveredDeathMarker ? 'pointer' : (editLayoutMode ? 'default' : 'default'); }
  const hoverCard = document.querySelector('#hover-card');
  const zoneCard = document.querySelector('#zone-card');
  if (hit) { hoverCard.style.left = `${event.offsetX + 16}px`; hoverCard.style.top = `${event.offsetY + 16}px`; }
  zoneCard.dataset.zone = hit ? '' : zone?.name || '';
  zoneCard.dataset.resourceId = resourceHit && !hit && !teleporterHit && !hoveredDeathMarker ? String(resourceHit.resource.id) : '';
  zoneCard.dataset.teleporter = String(teleporterHit && !hit && !resourceHit && !hoveredDeathMarker);
  if ((zone || teleporterHit || resourceHit || hoveredDeathMarker) && !hit) { zoneCard.style.left = `${event.offsetX + 16}px`; zoneCard.style.top = `${event.offsetY + 16}px`; }
  updateAgentCards(previousPacket);
  if (hit || resourceHit || teleporterHit || hoveredDeathMarker || zone) resetHoverTimer();
  else { clearTimeout(hoverTimeout); clearHoverCards(); }
});
canvas.addEventListener('pointerleave', event => { if (!draggingZone) clearHoverCards(); });
canvas.addEventListener('pointerdown', event => {
  if (!editLayoutMode) return;
  const zone = zoneAtEvent(event);
  if (!zone || !new Set(['cafe','bar','work','church']).has(zone.name)) return;
  const bounds = canvas.getBoundingClientRect();
  const mouseX = (event.clientX - bounds.left) * 1000 / bounds.width;
  const mouseY = (event.clientY - bounds.top) * 1000 / bounds.height;
  draggingZone = { name: zone.name, width: zone.width, height: zone.height, startMouseX: mouseX, startMouseY: mouseY, startZoneX: zone.x, startZoneY: zone.y, currentX: zone.x, currentY: zone.y };
  canvas.setPointerCapture(event.pointerId);
  canvas.style.cursor = 'grabbing';
  event.preventDefault();
});
canvas.addEventListener('pointerup', event => {
  if (!draggingZone) return;
  window.simSocket?.send(JSON.stringify({ type: 'move_zone', name: draggingZone.name, x: draggingZone.currentX, y: draggingZone.currentY }));
  draggingZone = null;
  canvas.style.cursor = editLayoutMode ? 'grab' : 'default';
});
canvas.addEventListener('click', event => {
  const hit = specimenAtEvent(event);
  if (hit) {
    selectedId = hit.specimen.id; selectedAnimalId = null; focusedId = selectedId;
    if (hit.specimen.sleeping) window.simSocket?.send(JSON.stringify({ type: 'wake_specimen', id: hit.specimen.id }));
  } else {
    const resourceHit = resourceAtEvent(event);
    if (resourceHit && resourceHit.resource.kind === 'animal') { selectedAnimalId = resourceHit.resource.id; selectedId = null; focusedId = null; }
    else { selectedId = null; selectedAnimalId = null; focusedId = null; }
  }
  updateAgentCards(previousPacket);
});
document.querySelector('#close-card').addEventListener('click', event => { event.stopPropagation(); selectedId = null; selectedAnimalId = null; updateAgentCards(previousPacket); });

function animate() { animationFrame += 1; if (previousPacket) render(interpolatedPacket()); requestAnimationFrame(animate); }

function connect() { const protocol = location.protocol === 'https:' ? 'wss' : 'ws'; const socket = new WebSocket(`${protocol}://${location.host}/ws`); socket.onopen = () => { connection.textContent = 'LIVE'; document.querySelector('.status').classList.add('connected'); }; socket.onmessage = event => { const packet = JSON.parse(event.data); if (packet.specimens) draw(packet); }; socket.onclose = () => { connection.textContent = 'RECONNECTING'; document.querySelector('.status').classList.remove('connected'); setTimeout(connect, 1200); }; window.simSocket = socket; }
document.querySelector('#pause').onclick = event => {
  window.simSocket?.send('toggle');
  state.running = !state.running;
  event.currentTarget.textContent = state.running ? 'Pause simulation' : 'Resume simulation';
  const dot = document.querySelector('#connection-dot');
  const label = document.querySelector('#connection');
  const statusEl = document.querySelector('.status');
  if (state.running) {
    dot.style.background = '';
    label.textContent = 'LIVE';
    statusEl.classList.add('connected');
  } else {
    dot.style.background = '#e85b39';
    label.textContent = 'PAUSED';
    statusEl.classList.remove('connected');
  }
};
// ── Reset / Scenario dialog ──────────────────────────────────────────────────
let selectedScenario = 'balanced';
const resetDialog = document.querySelector('#reset-dialog');

document.querySelector('#reset').onclick = async () => {
  const cardsEl = document.querySelector('#scenario-cards');
  cardsEl.innerHTML = '<div style="font:11px DM Mono,monospace;color:var(--muted)">Loading scenarios…</div>';
  resetDialog.showModal();
  try {
    const res = await fetch('/api/scenarios');
    const scenarios = await res.json();
    selectedScenario = 'balanced';
    cardsEl.innerHTML = Object.entries(scenarios).map(([key, s]) => `
      <button class="scenario-card${key === 'balanced' ? ' selected' : ''}" data-key="${key}">
        <b>${s.label}</b>
        <p>${s.description}</p>
      </button>`).join('');
    cardsEl.querySelectorAll('.scenario-card').forEach(card => {
      card.onclick = () => {
        cardsEl.querySelectorAll('.scenario-card').forEach(c => c.classList.remove('selected'));
        card.classList.add('selected');
        selectedScenario = card.dataset.key;
      };
    });
  } catch (e) {
    cardsEl.innerHTML = `<p style="color:var(--orange)">${e.message}</p>`;
  }
};
document.querySelector('#close-reset').onclick = () => resetDialog.close();
document.querySelector('#intensity-slider').oninput = e => {
  document.querySelector('#intensity-value').value = e.target.value;
};
document.querySelector('#launch-scenario').onclick = () => {
  const intensity = Number(document.querySelector('#intensity-slider').value);
  window.simSocket?.send(JSON.stringify({ type: 'reset_scenario', scenario: selectedScenario, intensity }));
  state.running = true;
  document.querySelector('#pause').textContent = 'Pause simulation';
  document.querySelector('#connection-dot').style.background = '';
  document.querySelector('#connection').textContent = 'LIVE';
  document.querySelector('.status').classList.add('connected');
  resetDialog.close();
};
const speedSlider = document.querySelector('#speed-slider');
const speedDisplay = document.querySelector('#speed-display');
speedSlider.addEventListener('input', () => {
  const speed = parseInt(speedSlider.value, 10);
  speedDisplay.textContent = `${speed}×`;
  window.simSocket?.send(JSON.stringify({ type: 'set_speed', speed }));
});
document.querySelector('#open-add').onclick = () => document.querySelector('#add-dialog').showModal();
document.querySelector('#close-add').onclick = () => document.querySelector('#add-dialog').close();
document.querySelectorAll('#add-form input[type="range"]').forEach(input => input.addEventListener('input', () => { document.querySelector(`#${input.id}-value`).value = input.value; }));
document.querySelector('#add-form').addEventListener('submit', event => {
  event.preventDefault();
  const values = Object.fromEntries(new FormData(event.currentTarget));
  values.gender = document.querySelector('#gender').value;
  values.housed = document.querySelector('#housed').value === 'true';
  window.simSocket?.send(JSON.stringify({ type: 'add_specimen', values }));
  document.querySelector('#add-dialog').close();
});
document.querySelector('#edit-layout-btn').onclick = () => {
  editLayoutMode = !editLayoutMode;
  draggingZone = null;
  document.querySelector('#edit-layout-btn').classList.toggle('active', editLayoutMode);
  canvas.style.cursor = editLayoutMode ? 'grab' : 'default';
};
document.querySelector('#purge-btn').onclick = () => {
  const btn = document.querySelector('#purge-btn');
  btn.disabled = true;
  btn.textContent = '💥 PURGING…';
  purgeFrame = animationFrame;
  window.simSocket?.send('purge');
  setTimeout(() => { btn.disabled = false; btn.textContent = '☄ PURGE'; }, 3000);
};

document.querySelector('#field-notes-btn').onclick = async () => {
  const btn = document.querySelector('#field-notes-btn');
  const commentaryEl = document.querySelector('#ai-commentary');
  const statusEl = document.querySelector('#ai-status');
  btn.disabled = true;
  btn.textContent = 'Observing…';
  commentaryEl.textContent = 'Calling Groq…';
  statusEl.textContent = '…';
  try {
    const res = await fetch('/api/field-notes', { method: 'POST' });
    const data = await res.json();
    commentaryEl.textContent = data.commentary || 'No observation returned.';
    statusEl.textContent = 'GROQ';
  } catch (e) {
    commentaryEl.textContent = 'Failed: ' + e.message;
  } finally {
    btn.disabled = false;
    btn.textContent = 'Field Notes';
  }
};

document.querySelector('#read-minds-btn').onclick = async () => {
  const dialog = document.querySelector('#read-minds-dialog');
  const contentEl = document.querySelector('#read-minds-content');
  contentEl.textContent = 'Connecting to Gemini…';
  dialog.showModal();
  try {
    const res = await fetch('/api/read-minds', { method: 'POST' });
    const data = await res.json();
    const thoughts = data.thoughts || {};
    const entries = Object.values(thoughts);
    if (!entries.length) {
      contentEl.textContent = 'No thoughts returned — population may be too idle.';
    } else {
      contentEl.innerHTML = entries.map(t =>
        `<div class="mind-entry"><div class="mind-header"><b>${t.name}</b><span>${t.action.replace(/_/g,' ')}</span></div><p class="mind-thought">"${t.thought}"</p></div>`
      ).join('');
    }
  } catch (e) {
    contentEl.textContent = 'Failed: ' + e.message;
  }
};
document.querySelector('#close-read-minds').onclick = () => document.querySelector('#read-minds-dialog').close();

document.querySelector('#analyse-btn').onclick = async () => {
  const dialog = document.querySelector('#analyse-dialog');
  const statsEl = document.querySelector('#analyse-stats');
  const textEl = document.querySelector('#analyse-text');
  statsEl.innerHTML = '';
  textEl.textContent = 'Running LLM analysis…';
  dialog.showModal();
  try {
    const res = await fetch('/api/analyse', { method: 'POST' });
    const data = await res.json();
    const s = data.stats || {};
    statsEl.innerHTML = `
      <div class="stat-row"><span>Population</span><strong>${s.population ?? '--'}</strong></div>
      <div class="stat-row"><span>Homeless</span><strong>${s.homeless ?? '--'}</strong></div>
      <div class="stat-row"><span>Avg Hunger</span><strong>${s.avg_hunger ?? '--'}%</strong></div>
      <div class="stat-row"><span>Avg Wallet</span><strong>$${s.avg_wallet ?? '--'}</strong></div>
      <div class="stat-row full"><span>Top Actions</span><strong>${(s.top_actions || []).map(([a,n]) => `${a}:${n}`).join(' · ')}</strong></div>
    `;
    textEl.textContent = data.analysis || 'No analysis returned.';
  } catch (e) {
    textEl.textContent = 'Analysis failed: ' + e.message;
  }
};
document.querySelector('#close-analyse').onclick = () => document.querySelector('#analyse-dialog').close();

document.querySelector('#optimise-btn').onclick = async () => {
  const dialog = document.querySelector('#optimise-dialog');
  const problemsEl = document.querySelector('#optimise-problems');
  const traitsEl = document.querySelector('#optimise-traits');
  problemsEl.textContent = 'Groq analysing problems… Gemini prescribing traits…';
  traitsEl.innerHTML = '';
  dialog.showModal();
  try {
    const res = await fetch('/api/optimise', { method: 'POST' });
    const data = await res.json();
    problemsEl.textContent = data.problems || 'No problems identified.';
    const p = data.prescribed || {};
    const traits = ['friendliness','curiosity','aggression','risk_taking','loyalty','morality','discipline','fearfulness','fertility','speed','eyesight','mutation_rate'];
    if (p.man || p.woman) {
      traitsEl.innerHTML = `
        <div class="optimise-reasoning">${p.reasoning || ''}</div>
        <table class="trait-table">
          <thead><tr><th>Trait</th><th>Man</th><th>Woman</th></tr></thead>
          <tbody>${traits.map(t => `<tr><td>${t}</td><td>${p.man?.[t] ?? '–'}</td><td>${p.woman?.[t] ?? '–'}</td></tr>`).join('')}</tbody>
        </table>
      `;
    } else {
      traitsEl.textContent = 'No trait prescription returned.';
    }
  } catch (e) {
    problemsEl.textContent = 'Optimisation failed: ' + e.message;
  }
};
document.querySelector('#close-optimise').onclick = () => document.querySelector('#optimise-dialog').close();

fetch('/api/status').then(response => response.json()).then(draw); connect();
animate();
