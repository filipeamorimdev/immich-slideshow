// Immich slideshow cards for Home Assistant: an album or random photos, a smart
// search, and photos from this day in earlier years. Photos and videos come through
// the Immich Slideshow integration, so the cards never see or store an API key.

const IS_VERSION = '0.6.0.2';
const IS_DOMAIN = 'immich_slideshow';
const IS_REPO = 'https://github.com/filipeamorimdev/immich-slideshow';
const IS_DEFAULT_INTERVAL = 10;
const IS_MIN_INTERVAL = 3;
const IS_SIGN_SECONDS = 300;
// A photo's link is used again for this long, which leaves the photo a minute to load.
const IS_SIGN_REUSE_MS = 240 * 1000;
const IS_RELOAD_MS = 60 * 60 * 1000;
const IS_RETRY_MS = 60 * 1000;
const IS_MAX_SKIPS = 5;
const IS_FADE_MS = 1000;
// A video that shows nothing new for this long is given up on.
const IS_STALL_MS = 15 * 1000;
// The automatic fit fills the tile unless that would crop more than this share of the photo.
const IS_MAX_CROP = 0.3;
const IS_MAX_ZOOM = 5;
const IS_SEARCH_COUNT = 50;
const IS_SEARCH_MAX = 250;
// Waits for a pause in typing before searching.
const IS_TYPING_MS = 800;
// What the line under a photo can be made of, and what it's made of unless the card says otherwise.
const IS_TAGS = ['date', 'year', 'place', 'country', 'city', 'people'];
const IS_DEFAULT_TAGS = ['date', 'place'];

const IS_TRANSLATIONS = {
  en: {
    choose_album: 'Choose an album in the card editor.',
    describe: 'Describe the photos to show in the card editor.',
    no_photos: 'This album has no photos',
    no_library: 'No photos found in the library',
    no_matches: 'No photos match this description',
    no_memories: 'No photos from this day in earlier years',
    no_integration: 'Set up the Immich Slideshow integration first.',
    admin_only: 'Only Home Assistant admins can see these photos.',
    photos_failed: "Couldn't load the photos",
    load_failed: "Couldn't get the photos from Immich",
    try_again: 'Try again',
    loading: 'Loading',
    play: 'Play slideshow',
    pause: 'Pause slideshow',
    open_full: 'Open full screen',
    close: 'Close',
    previous: 'Previous',
    next: 'Next',
    position: '{i} of {n}',
    viewer: 'Photo viewer',
    photo_failed: "Couldn't load this photo",
    video_failed: "Couldn't play this video",
    mute: 'Turn sound off',
    unmute: 'Turn sound on',
    editor_unavailable: "Couldn't load the editor. Use the code editor instead.",
    editor_server: 'Immich server',
    editor_source: 'Photos',
    editor_source_album: 'From an album',
    editor_source_random: 'Random from the whole library',
    editor_source_hint: 'Random shows a new set every round, and leaves out hidden, locked, archived and deleted photos.',
    editor_album: 'Album',
    editor_album_current: 'Current album',
    editor_no_albums: 'No albums found. Check that the Immich Slideshow integration is set up.',
    editor_query: 'Show photos of',
    editor_query_hint: 'Describe what to show, such as beach sunset, snow or dogs.',
    editor_count: 'Number of photos',
    editor_count_hint: 'The best matches, up to 250',
    editor_interval: 'Seconds per photo',
    editor_interval_hint: 'At least 3',
    editor_shuffle: 'Shuffle',
    editor_videos: 'Include videos',
    editor_videos_hint: 'Videos play to the end, without sound.',
    editor_fit: 'Photo fit',
    editor_fit_auto: 'Automatic',
    editor_fit_hint: 'Automatic fills the tile, unless that would cut off too much of the photo.',
    editor_fit_cover: 'Fill the tile',
    editor_fit_contain: 'Show the whole photo',
    editor_description: 'Description',
    editor_description_hint: 'What to show under each photo, in this order. Remove everything to show nothing.',
    tag_date: 'Date',
    tag_year: 'Year',
    tag_place: 'Place',
    tag_country: 'Country',
    tag_city: 'City',
    tag_people: 'People',
    editor_title: 'Caption',
    editor_title_hint: 'Leave empty for no caption',
  },
  pt: {
    choose_album: 'Escolha um álbum no editor do cartão.',
    describe: 'Descreva as fotos a mostrar no editor do cartão.',
    no_photos: 'Este álbum não tem fotos',
    no_library: 'Não foram encontradas fotos na biblioteca',
    no_matches: 'Nenhuma foto corresponde a esta descrição',
    no_memories: 'Não há fotos deste dia em anos anteriores',
    no_integration: 'Configure primeiro a integração Immich Slideshow.',
    admin_only: 'Só os administradores do Home Assistant podem ver estas fotos.',
    photos_failed: 'Não foi possível carregar as fotos',
    load_failed: 'Não foi possível obter as fotos do Immich',
    try_again: 'Tentar novamente',
    loading: 'A carregar',
    play: 'Reproduzir apresentação',
    pause: 'Pausar apresentação',
    open_full: 'Abrir em ecrã inteiro',
    close: 'Fechar',
    previous: 'Anterior',
    next: 'Seguinte',
    position: '{i} de {n}',
    viewer: 'Visualizador de fotos',
    photo_failed: 'Não foi possível carregar esta foto',
    video_failed: 'Não foi possível reproduzir este vídeo',
    mute: 'Desligar o som',
    unmute: 'Ligar o som',
    editor_unavailable: 'Não foi possível carregar o editor. Use o editor de código.',
    editor_server: 'Servidor Immich',
    editor_source: 'Fotos',
    editor_source_album: 'De um álbum',
    editor_source_random: 'Aleatórias de toda a biblioteca',
    editor_source_hint: 'As aleatórias mudam a cada volta e deixam de fora as fotos ocultas, bloqueadas, arquivadas e apagadas.',
    editor_album: 'Álbum',
    editor_album_current: 'Álbum atual',
    editor_no_albums: 'Nenhum álbum encontrado. Verifique se a integração Immich Slideshow está configurada.',
    editor_query: 'Mostrar fotos de',
    editor_query_hint: 'Descreva o que mostrar, como pôr do sol na praia, neve ou cães.',
    editor_count: 'Número de fotos',
    editor_count_hint: 'As melhores correspondências, até 250',
    editor_interval: 'Segundos por foto',
    editor_interval_hint: 'Pelo menos 3',
    editor_shuffle: 'Ordem aleatória',
    editor_videos: 'Incluir vídeos',
    editor_videos_hint: 'Os vídeos são reproduzidos até ao fim, sem som.',
    editor_fit: 'Ajuste da foto',
    editor_fit_auto: 'Automático',
    editor_fit_hint: 'O modo automático preenche o cartão, exceto se isso cortar demasiado da foto.',
    editor_fit_cover: 'Preencher o cartão',
    editor_fit_contain: 'Mostrar a foto inteira',
    editor_description: 'Descrição',
    editor_description_hint: 'O que mostrar por baixo de cada foto, por esta ordem. Remova tudo para não mostrar nada.',
    tag_date: 'Data',
    tag_year: 'Ano',
    tag_place: 'Local',
    tag_country: 'País',
    tag_city: 'Cidade',
    tag_people: 'Pessoas',
    editor_title: 'Legenda',
    editor_title_hint: 'Deixe vazio para não mostrar legenda',
  },
  es: {
    choose_album: 'Elige un álbum en el editor de la tarjeta.',
    describe: 'Describe las fotos que quieres mostrar en el editor de la tarjeta.',
    no_photos: 'Este álbum no tiene fotos',
    no_library: 'No se encontraron fotos en la biblioteca',
    no_matches: 'Ninguna foto coincide con esta descripción',
    no_memories: 'No hay fotos de este día en años anteriores',
    no_integration: 'Configura primero la integración Immich Slideshow.',
    admin_only: 'Solo los administradores de Home Assistant pueden ver estas fotos.',
    photos_failed: 'No se pudieron cargar las fotos',
    load_failed: 'No se pudieron obtener las fotos de Immich',
    try_again: 'Reintentar',
    loading: 'Cargando',
    play: 'Reproducir presentación',
    pause: 'Pausar presentación',
    open_full: 'Abrir a pantalla completa',
    close: 'Cerrar',
    previous: 'Anterior',
    next: 'Siguiente',
    position: '{i} de {n}',
    viewer: 'Visor de fotos',
    photo_failed: 'No se pudo cargar esta foto',
    video_failed: 'No se pudo reproducir este vídeo',
    mute: 'Desactivar el sonido',
    unmute: 'Activar el sonido',
    editor_unavailable: 'No se pudo cargar el editor. Usa el editor de código.',
    editor_server: 'Servidor de Immich',
    editor_source: 'Fotos',
    editor_source_album: 'De un álbum',
    editor_source_random: 'Al azar de toda la biblioteca',
    editor_source_hint: 'Al azar muestra un conjunto nuevo en cada vuelta y deja fuera las fotos ocultas, bloqueadas, archivadas y eliminadas.',
    editor_album: 'Álbum',
    editor_album_current: 'Álbum actual',
    editor_no_albums: 'No se encontraron álbumes. Comprueba que la integración Immich Slideshow esté configurada.',
    editor_query: 'Mostrar fotos de',
    editor_query_hint: 'Describe qué mostrar, como atardecer en la playa, nieve o perros.',
    editor_count: 'Número de fotos',
    editor_count_hint: 'Las mejores coincidencias, hasta 250',
    editor_interval: 'Segundos por foto',
    editor_interval_hint: 'Al menos 3',
    editor_shuffle: 'Orden aleatorio',
    editor_videos: 'Incluir vídeos',
    editor_videos_hint: 'Los vídeos se reproducen hasta el final, sin sonido.',
    editor_fit: 'Ajuste de la foto',
    editor_fit_auto: 'Automático',
    editor_fit_hint: 'El modo automático llena la tarjeta, salvo que eso recorte demasiado la foto.',
    editor_fit_cover: 'Llenar la tarjeta',
    editor_fit_contain: 'Mostrar la foto completa',
    editor_description: 'Descripción',
    editor_description_hint: 'Qué mostrar debajo de cada foto, en este orden. Quítalo todo para no mostrar nada.',
    tag_date: 'Fecha',
    tag_year: 'Año',
    tag_place: 'Lugar',
    tag_country: 'País',
    tag_city: 'Ciudad',
    tag_people: 'Personas',
    editor_title: 'Leyenda',
    editor_title_hint: 'Déjalo vacío para no mostrar leyenda',
  },
  fr: {
    choose_album: "Choisissez un album dans l'éditeur de la carte.",
    describe: "Décrivez les photos à afficher dans l'éditeur de la carte.",
    no_photos: 'Cet album ne contient aucune photo',
    no_library: 'Aucune photo trouvée dans la bibliothèque',
    no_matches: 'Aucune photo ne correspond à cette description',
    no_memories: 'Aucune photo de ce jour les années précédentes',
    no_integration: "Configurez d'abord l'intégration Immich Slideshow.",
    admin_only: 'Seuls les administrateurs de Home Assistant peuvent voir ces photos.',
    photos_failed: 'Impossible de charger les photos',
    load_failed: "Impossible d'obtenir les photos d'Immich",
    try_again: 'Réessayer',
    loading: 'Chargement',
    play: 'Lancer le diaporama',
    pause: 'Mettre le diaporama en pause',
    open_full: 'Ouvrir en plein écran',
    close: 'Fermer',
    previous: 'Précédent',
    next: 'Suivant',
    position: '{i} sur {n}',
    viewer: 'Visionneuse de photos',
    photo_failed: 'Impossible de charger cette photo',
    video_failed: 'Impossible de lire cette vidéo',
    mute: 'Couper le son',
    unmute: 'Activer le son',
    editor_unavailable: "Impossible de charger l'éditeur. Utilisez l'éditeur de code.",
    editor_server: 'Serveur Immich',
    editor_source: 'Photos',
    editor_source_album: "D'un album",
    editor_source_random: 'Au hasard dans toute la bibliothèque',
    editor_source_hint: 'Au hasard affiche une nouvelle série à chaque tour, sans les photos masquées, verrouillées, archivées ou supprimées.',
    editor_album: 'Album',
    editor_album_current: 'Album actuel',
    editor_no_albums: "Aucun album trouvé. Vérifiez que l'intégration Immich Slideshow est configurée.",
    editor_query: 'Afficher des photos de',
    editor_query_hint: 'Décrivez ce que vous voulez voir, par exemple coucher de soleil sur la plage, neige ou chiens.',
    editor_count: 'Nombre de photos',
    editor_count_hint: "Les meilleures correspondances, jusqu'à 250",
    editor_interval: 'Secondes par photo',
    editor_interval_hint: 'Au moins 3',
    editor_shuffle: 'Ordre aléatoire',
    editor_videos: 'Inclure les vidéos',
    editor_videos_hint: "Les vidéos sont lues jusqu'à la fin, sans le son.",
    editor_fit: 'Ajustement de la photo',
    editor_fit_auto: 'Automatique',
    editor_fit_hint: 'Le mode automatique remplit la carte, sauf si cela coupe trop la photo.',
    editor_fit_cover: 'Remplir la carte',
    editor_fit_contain: 'Afficher toute la photo',
    editor_description: 'Description',
    editor_description_hint: "Ce qui s'affiche sous chaque photo, dans cet ordre. Retirez tout pour ne rien afficher.",
    tag_date: 'Date',
    tag_year: 'Année',
    tag_place: 'Lieu',
    tag_country: 'Pays',
    tag_city: 'Ville',
    tag_people: 'Personnes',
    editor_title: 'Légende',
    editor_title_hint: 'Laissez vide pour ne pas afficher de légende',
  },
  de: {
    choose_album: 'Wähle im Karteneditor ein Album aus.',
    describe: 'Beschreibe im Karteneditor, welche Fotos gezeigt werden sollen.',
    no_photos: 'Dieses Album enthält keine Fotos',
    no_library: 'Keine Fotos in der Bibliothek gefunden',
    no_matches: 'Keine Fotos passen zu dieser Beschreibung',
    no_memories: 'Keine Fotos von diesem Tag aus früheren Jahren',
    no_integration: 'Richte zuerst die Immich-Slideshow-Integration ein.',
    admin_only: 'Nur Home-Assistant-Administratoren können diese Fotos sehen.',
    photos_failed: 'Die Fotos konnten nicht geladen werden',
    load_failed: 'Die Fotos konnten nicht von Immich abgerufen werden',
    try_again: 'Erneut versuchen',
    loading: 'Wird geladen',
    play: 'Diashow abspielen',
    pause: 'Diashow anhalten',
    open_full: 'Im Vollbild öffnen',
    close: 'Schließen',
    previous: 'Zurück',
    next: 'Weiter',
    position: '{i} von {n}',
    viewer: 'Fotoansicht',
    photo_failed: 'Dieses Foto konnte nicht geladen werden',
    video_failed: 'Dieses Video konnte nicht abgespielt werden',
    mute: 'Ton ausschalten',
    unmute: 'Ton einschalten',
    editor_unavailable: 'Der Editor konnte nicht geladen werden. Verwende stattdessen den Code-Editor.',
    editor_server: 'Immich-Server',
    editor_source: 'Fotos',
    editor_source_album: 'Aus einem Album',
    editor_source_random: 'Zufällig aus der ganzen Bibliothek',
    editor_source_hint: 'Zufällig zeigt in jeder Runde neue Fotos und lässt ausgeblendete, gesperrte, archivierte und gelöschte Fotos weg.',
    editor_album: 'Album',
    editor_album_current: 'Aktuelles Album',
    editor_no_albums: 'Keine Alben gefunden. Prüfe, ob die Immich-Slideshow-Integration eingerichtet ist.',
    editor_query: 'Fotos zeigen von',
    editor_query_hint: 'Beschreibe, was gezeigt werden soll, z. B. Sonnenuntergang am Strand, Schnee oder Hunde.',
    editor_count: 'Anzahl der Fotos',
    editor_count_hint: 'Die besten Treffer, bis zu 250',
    editor_interval: 'Sekunden pro Foto',
    editor_interval_hint: 'Mindestens 3',
    editor_shuffle: 'Zufällige Reihenfolge',
    editor_videos: 'Videos einbeziehen',
    editor_videos_hint: 'Videos werden bis zum Ende und ohne Ton abgespielt.',
    editor_fit: 'Fotoanpassung',
    editor_fit_auto: 'Automatisch',
    editor_fit_hint: 'Automatisch füllt die Karte, außer wenn dabei zu viel vom Foto abgeschnitten würde.',
    editor_fit_cover: 'Karte ausfüllen',
    editor_fit_contain: 'Ganzes Foto anzeigen',
    editor_description: 'Beschreibung',
    editor_description_hint: 'Was unter jedem Foto steht, in dieser Reihenfolge. Alles entfernen, um nichts anzuzeigen.',
    tag_date: 'Datum',
    tag_year: 'Jahr',
    tag_place: 'Ort',
    tag_country: 'Land',
    tag_city: 'Stadt',
    tag_people: 'Personen',
    editor_title: 'Beschriftung',
    editor_title_hint: 'Leer lassen, um keine Beschriftung anzuzeigen',
  },
};

const IS_ICONS = {
  photos: 'M22,16V4A2,2 0 0,0 20,2H8A2,2 0 0,0 6,4V16A2,2 0 0,0 8,18H20A2,2 0 0,0 22,16M11,12L13.03,14.71L16,11L20,16H8M2,6V20A2,2 0 0,0 4,22H18V20H4V6',
  search: 'M9.5,3A6.5,6.5 0 0,1 16,9.5C16,11.11 15.41,12.59 14.44,13.73L14.71,14H15.5L20.5,19L19,20.5L14,15.5V14.71L13.73,14.44C12.59,15.41 11.11,16 9.5,16A6.5,6.5 0 0,1 3,9.5A6.5,6.5 0 0,1 9.5,3M9.5,5C7,5 5,7 5,9.5C5,12 7,14 9.5,14C12,14 14,12 14,9.5C14,7 12,5 9.5,5Z',
  play: 'M8,5.14V19.14L19,12.14L8,5.14Z',
  pause: 'M14,19H18V5H14M6,19H10V5H6V19Z',
  previous: 'M15.41,16.58L10.83,12L15.41,7.41L14,6L8,12L14,18L15.41,16.58Z',
  next: 'M8.59,16.58L13.17,12L8.59,7.41L10,6L16,12L10,18L8.59,16.58Z',
  close: 'M19,6.41L17.59,5L12,10.59L6.41,5L5,6.41L10.59,12L5,17.59L6.41,19L12,13.41L17.59,19L19,17.59L13.41,12L19,6.41Z',
  sound_on: 'M14,3.23V5.29C16.89,6.15 19,8.83 19,12C19,15.17 16.89,17.84 14,18.7V20.77C18,19.86 21,16.28 21,12C21,7.72 18,4.14 14,3.23M16.5,12C16.5,10.23 15.5,8.71 14,7.97V16C15.5,15.29 16.5,13.76 16.5,12M3,9V15H7L12,20V4L7,9H3Z',
  sound_off: 'M12,4L9.91,6.09L12,8.18M4.27,3L3,4.27L7.73,9H3V15H7L12,20V13.27L16.25,17.53C15.58,18.04 14.83,18.46 14,18.7V20.77C15.38,20.45 16.63,19.82 17.68,18.96L19.73,21L21,19.73L12,10.73M19,12C19,12.94 18.8,13.82 18.46,14.64L19.97,16.15C20.62,14.91 21,13.5 21,12C21,7.72 18,4.14 14,3.23V5.29C16.89,6.15 19,8.83 19,12M16.5,12C16.5,10.23 15.5,8.71 14,7.97V10.18L16.45,12.63C16.5,12.43 16.5,12.21 16.5,12Z',
};

// Albums saved by earlier versions are media source IDs that end in "|albums|<id>".
function isAlbumId(value) {
  const text = String(value || '');
  const at = text.lastIndexOf('|albums|');
  return at >= 0 ? text.slice(at + 8).split('|')[0] : text;
}

function isCount(value) {
  const count = Math.round(Number(value));
  return Number.isFinite(count) && count > 0 ? Math.min(IS_SEARCH_MAX, count) : IS_SEARCH_COUNT;
}

// What each card shows. `request` returns the photos command, or null until the card is set up.
const IS_KINDS = {
  slideshow: {
    tag: 'immich-slideshow-card',
    name: 'Immich Slideshow',
    description: 'A slideshow of an Immich album, or random photos from your library.',
    shuffle: true,
    placeholder: 'choose_album',
    placeholderIcon: 'photos',
    request(config) {
      if (config.source === 'random') return { source: 'random' };
      const album = isAlbumId(config.album);
      return album ? { source: 'album', album } : null;
    },
    empty: (config) => (config.source === 'random' ? 'no_library' : 'no_photos'),
    // Random photos are a new draw every round.
    reloadEachRound: (config) => config.source === 'random',
  },
  magic: {
    tag: 'immich-magic-card',
    name: 'Immich Magic',
    description: 'A slideshow of the photos that match a description, found by Immich smart search.',
    shuffle: true,
    placeholder: 'describe',
    placeholderIcon: 'search',
    request(config, language) {
      const query = String(config.query ?? '').trim();
      return query ? { source: 'search', query, count: isCount(config.count), language } : null;
    },
    empty: () => 'no_matches',
    reloadEachRound: () => false,
  },
  on_this_day: {
    tag: 'immich-on-this-day-card',
    name: 'Immich On This Day',
    description: 'A slideshow of photos taken on this day in earlier years.',
    shuffle: false,
    placeholder: null,
    request: () => ({ source: 'on_this_day' }),
    empty: () => 'no_memories',
    reloadEachRound: () => false,
  },
};

function isLang(hass) {
  const code = String(hass?.locale?.language || hass?.language || 'en').split('-')[0];
  return IS_TRANSLATIONS[code] ? code : 'en';
}

function isLocale(hass) {
  const locale = String(hass?.locale?.language || hass?.language || 'en');
  try {
    return Intl.getCanonicalLocales(locale)[0];
  } catch (_err) {
    return 'en';
  }
}

function isT(lang, key, vars = {}) {
  const text = IS_TRANSLATIONS[lang]?.[key] ?? IS_TRANSLATIONS.en[key] ?? key;
  return text.replace(/\{(\w+)\}/g, (_, name) => vars[name]);
}

function isIcon(name) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('aria-hidden', 'true');
  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  path.setAttribute('d', IS_ICONS[name]);
  svg.appendChild(path);
  return svg;
}

function isEl(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
}

function isIconButton(name, label, className = 'icon-button') {
  const button = isEl('button', className);
  button.type = 'button';
  button.title = label;
  button.setAttribute('aria-label', label);
  button.appendChild(isIcon(name));
  return button;
}

function isUrl(hass, url) {
  return url.startsWith('/') && hass.hassUrl ? hass.hassUrl(url) : url;
}

function isClamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function isShuffle(list) {
  const out = [...list];
  for (let i = out.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

function isLoadImage(url) {
  return new Promise((resolve, reject) => {
    const image = isEl('img');
    image.alt = '';
    image.addEventListener('load', () => resolve(image));
    image.addEventListener('error', () => reject(new Error('Image failed to load')));
    image.src = url;
  });
}

// Photo and video links signed a short while ago, by path. A new link for the same file
// is a new address, which the browser would load again, so every card on the page shares these.
const isLinks = new Map();

// Returns the link kept for a path, or asks `sign` for one.
function isLink(path, sign) {
  const now = Date.now();
  const kept = isLinks.get(path);
  if (kept && now - kept.at < IS_SIGN_REUSE_MS) return kept.url;
  for (const [key, link] of isLinks) {
    if (now - link.at >= IS_SIGN_REUSE_MS) isLinks.delete(key);
  }
  const link = { at: now, url: sign(path) };
  isLinks.set(path, link);
  link.url.catch(() => {
    if (isLinks.get(path) === link) isLinks.delete(path);
  });
  return link.url;
}

// Why a video's `error` event fired, from the browser's own code for it.
const IS_VIDEO_ERRORS = { 2: 'network', 3: 'decode', 4: 'format' };

// Why `play()` was refused: the browser wants a tap first, or can't play this kind of video.
function isPlayFailure(err) {
  if (err?.name === 'NotAllowedError') return 'refused';
  return err?.name === 'NotSupportedError' ? 'format' : 'unknown';
}

// What the browser knows about a video that failed: its own message, how far loading
// and playing got, and the video's size if that much arrived.
function isVideoDetail(video, err) {
  const parts = [];
  const message = video?.error?.message || err?.message;
  if (message) parts.push(message);
  if (video) {
    parts.push(`loaded ${video.readyState}/4`, `network ${video.networkState}`);
    if (video.videoWidth) parts.push(`${video.videoWidth}x${video.videoHeight}`);
    if (Number.isFinite(video.duration)) parts.push(`${Math.round(video.duration)}s long`);
    parts.push(`at ${video.currentTime.toFixed(1)}s`);
  }
  return parts.join(', ').slice(0, 300);
}

// A video's link has to last until the video has played, not only until it has loaded.
function isVideoSeconds(item) {
  return IS_SIGN_SECONDS + Math.ceil(Number(item.duration) || 0);
}

function isCapitalize(text) {
  return text ? text.charAt(0).toLocaleUpperCase() + text.slice(1) : text;
}

// "Puteaux, France". Immich's names can be rough, so the region is only a fallback for the city.
function isPlace(item) {
  const parts = [item.city || item.state, item.country].filter(Boolean);
  return [...new Set(parts)].join(', ');
}

// Immich gives the time on the camera's clock as if it were UTC, so it's read back as UTC.
function isTaken(item) {
  if (!item.taken) return null;
  const date = new Date(item.taken);
  return Number.isNaN(date.getTime()) ? null : date;
}

// The parts of the line under a photo, in the card's order.
function isTags(config) {
  if (Array.isArray(config.description)) {
    return [...new Set(config.description.filter((tag) => IS_TAGS.includes(tag)))];
  }
  // Earlier versions had a switch for the date and one for the place.
  return IS_DEFAULT_TAGS.filter((tag) => config[`show_${tag}`] !== false);
}

const IS_CARD_STYLE = `
  :host { display: block; height: 100%; }
  [hidden] { display: none !important; }
  ha-card { display: block; position: relative; width: 100%; height: 100%; aspect-ratio: 16 / 9; overflow: hidden; }
  .stage { display: block; position: absolute; inset: 0; width: 100%; height: 100%; padding: 0; border: 0; border-radius: inherit; background: var(--secondary-background-color); cursor: pointer; }
  .stage:focus-visible { outline: 2px solid var(--primary-color); outline-offset: -2px; }
  .slide { position: absolute; inset: 0; overflow: hidden; opacity: 0; transition: opacity ${IS_FADE_MS}ms ease-in-out; }
  .photo, .clip { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
  .slide.whole .photo, .slide.whole .clip { object-fit: contain; }
  .clip { opacity: 0; transition: opacity .3s; }
  .clip.on { opacity: 1; }
  .backdrop { display: none; position: absolute; inset: -10%; width: 120%; height: 120%; object-fit: cover; filter: blur(28px) brightness(.7); }
  .slide.whole .backdrop { display: block; }
  .slide.on { opacity: 1; }
  .caption { position: absolute; left: 0; right: 0; bottom: 0; display: flex; flex-direction: column; gap: 2px; padding: 28px 16px 12px; background: linear-gradient(transparent, rgba(0, 0, 0, .6)); color: #fff; pointer-events: none; text-shadow: 0 1px 2px rgba(0, 0, 0, .4); }
  .caption > div { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .title { font-size: 14px; font-weight: 500; }
  .meta { font-size: 12px; opacity: .9; animation: is-fade ${IS_FADE_MS}ms ease-in-out; }
  .play { position: absolute; top: 8px; right: 8px; display: flex; align-items: center; justify-content: center; width: 40px; height: 40px; padding: 0; border: 0; border-radius: 50%; background: rgba(0, 0, 0, .55); color: #fff; cursor: pointer; }
  .play:focus-visible { outline: 2px solid #fff; outline-offset: 2px; }
  .play svg { width: 24px; height: 24px; fill: currentColor; }
  .message { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; padding: 16px; box-sizing: border-box; text-align: center; font-size: 14px; color: var(--secondary-text-color); background: var(--secondary-background-color); overflow: auto; }
  .message > svg { width: 40px; height: 40px; fill: currentColor; opacity: .6; }
  .message.placeholder { background: linear-gradient(135deg, var(--secondary-background-color), var(--card-background-color, var(--secondary-background-color))); }
  .detail { font-size: 12px; overflow-wrap: anywhere; }
  .action { padding: 6px 14px; border: 1px solid var(--divider-color); border-radius: 18px; background: none; color: var(--primary-color); font: inherit; cursor: pointer; }
  .spinner { width: 28px; height: 28px; border: 3px solid var(--divider-color); border-top-color: var(--primary-color); border-radius: 50%; animation: is-spin 1s linear infinite; }
  @keyframes is-spin { to { transform: rotate(360deg); } }
  @keyframes is-fade { from { opacity: 0; } }
  @media (prefers-reduced-motion: reduce) { .slide, .clip { transition: none; } .meta { animation: none; } .spinner { animation-duration: 3s; } }
`;

const IS_VIEWER_STYLE = `
  :host { position: fixed; inset: 0; z-index: 10000; display: block; color: #fff; font-family: var(--primary-font-family, system-ui, sans-serif); }
  [hidden] { display: none !important; }
  .scrim { position: absolute; inset: 0; background: #000; }
  .stage { position: absolute; inset: 0; overflow: hidden; touch-action: none; user-select: none; -webkit-user-select: none; }
  .media { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; will-change: transform; }
  .media img, .media video { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: contain; -webkit-user-drag: none; }
  .media .full { opacity: 0; transition: opacity .15s; }
  .media .full.ready { opacity: 1; }
  .bar { position: absolute; top: 0; left: 0; right: 0; display: flex; align-items: center; gap: 12px; padding: max(8px, env(safe-area-inset-top)) max(8px, env(safe-area-inset-right)) 24px max(16px, env(safe-area-inset-left)); background: linear-gradient(rgba(0, 0, 0, .6), transparent); pointer-events: none; }
  .bar > * { pointer-events: auto; }
  .caption { flex: 1; min-width: 0; font-size: 14px; }
  .position { font-weight: 500; }
  .about { font-size: 12px; opacity: .75; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .icon-button { flex: none; display: inline-flex; align-items: center; justify-content: center; width: 44px; height: 44px; padding: 0; border: 0; border-radius: 50%; background: rgba(0, 0, 0, .35); color: #fff; cursor: pointer; }
  .icon-button:hover { background: rgba(255, 255, 255, .2); }
  .icon-button:focus-visible { outline: 2px solid #fff; outline-offset: 2px; }
  .icon-button svg { width: 28px; height: 28px; fill: currentColor; }
  .nav { position: absolute; top: 50%; transform: translateY(-50%); }
  .nav.previous { left: max(12px, env(safe-area-inset-left)); }
  .nav.next { right: max(12px, env(safe-area-inset-right)); }
  .status { position: absolute; left: 16px; right: 16px; bottom: max(24px, env(safe-area-inset-bottom)); text-align: center; font-size: 14px; pointer-events: none; }
  .status span { display: inline-block; padding: 8px 14px; border-radius: 18px; background: rgba(0, 0, 0, .7); }
  .spinner { position: absolute; top: 50%; left: 50%; width: 32px; height: 32px; margin: -16px 0 0 -16px; border: 3px solid rgba(255, 255, 255, .25); border-top-color: #fff; border-radius: 50%; animation: is-spin 1s linear infinite, is-show .01s .3s backwards; pointer-events: none; }
  @keyframes is-spin { to { transform: rotate(360deg); } }
  @keyframes is-show { from { visibility: hidden; } }
  @media (hover: none) { .nav { display: none; } }
  @media (prefers-reduced-motion: reduce) { .media .full { transition: none; } }
`;

class ImmichSlideshowViewer extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._pointers = new Map();
    this._onKey = this._onKey.bind(this);
  }

  // `full(item)`, `thumb(item)` and `video(item)` return URLs; `describe(item)` the date and place.
  // `forget(item, size)` is told when a photo's URL didn't load, so it isn't given out again.
  // `report(item, reason, video, err)` is told why a video couldn't be played.
  open({ items, index, lang, full, thumb, video, forget, report, describe, onClose }) {
    Object.assign(this, { _items: items, _lang: lang, _full: full, _thumb: thumb, _video: video, _forget: forget, _report: report, _describe: describe, _onClose: onClose });
    // Videos start without sound, as browsers only allow sound after a tap.
    this._muted = true;
    this._build();
    document.body.appendChild(this);
    this._show(index);
    this._closeButton.focus();
  }

  close() {
    if (!this.isConnected) return;
    this._token = null;
    this._clear();
    this.remove();
    this._onClose?.(this._index);
  }

  connectedCallback() {
    window.addEventListener('keydown', this._onKey, true);
  }

  disconnectedCallback() {
    window.removeEventListener('keydown', this._onKey, true);
    clearTimeout(this._slideTimer);
  }

  _build() {
    const t = (key) => isT(this._lang, key);
    const style = isEl('style');
    style.textContent = IS_VIEWER_STYLE;
    this._scrim = isEl('div', 'scrim');
    this._stage = isEl('div', 'stage');
    this._media = isEl('div', 'media');
    this._stage.appendChild(this._media);

    const bar = isEl('div', 'bar');
    const caption = isEl('div', 'caption');
    this._position = isEl('div', 'position');
    this._about = isEl('div', 'about');
    caption.append(this._position, this._about);
    this._soundButton = isIconButton('sound_off', t('unmute'));
    this._soundButton.addEventListener('click', () => this._setMuted(!this._muted));
    this._closeButton = isIconButton('close', t('close'));
    this._closeButton.addEventListener('click', () => this.close());
    bar.append(caption, this._soundButton, this._closeButton);

    this._previous = isIconButton('previous', t('previous'), 'icon-button nav previous');
    this._next = isIconButton('next', t('next'), 'icon-button nav next');
    this._previous.addEventListener('click', () => this._go(-1));
    this._next.addEventListener('click', () => this._go(1));

    this._status = isEl('div', 'status');
    this._status.setAttribute('role', 'status');

    this.setAttribute('role', 'dialog');
    this.setAttribute('aria-modal', 'true');
    this.setAttribute('aria-label', t('viewer'));
    this.shadowRoot.replaceChildren(style, this._scrim, this._stage, bar, this._previous, this._next, this._status);

    this._stage.addEventListener('pointerdown', (e) => this._onDown(e));
    this._stage.addEventListener('pointermove', (e) => this._onMove(e));
    this._stage.addEventListener('pointerup', (e) => this._onUp(e));
    this._stage.addEventListener('pointercancel', (e) => this._onUp(e, true));
    this._stage.addEventListener('wheel', (e) => this._onWheel(e), { passive: false });
  }

  _go(direction) {
    const index = this._index + direction;
    if (index >= 0 && index < this._items.length) this._show(index);
  }

  _show(index) {
    clearTimeout(this._slideTimer);
    const token = {};
    this._token = token;
    this._index = index;
    this._scale = 1;
    this._tx = 0;
    this._ty = 0;
    this._gesture = null;
    this._pointers.clear();

    const item = this._items[index];
    this._position.textContent = isT(this._lang, 'position', {
      i: (index + 1).toLocaleString(this._lang),
      n: this._items.length.toLocaleString(this._lang),
    });
    this._about.textContent = this._describe(item);
    this._previous.hidden = index === 0;
    this._next.hidden = index === this._items.length - 1;
    this._soundButton.hidden = !item.video;
    this._setMuted(this._muted);
    this._status.replaceChildren();
    this._scrim.style.opacity = '';
    this._clear();
    this._apply();
    this._showItem(item, token);
    this._preload(index);
  }

  // Takes down what's showing, and stops a video from playing or loading any further.
  _clear() {
    for (const video of this._media.querySelectorAll('video')) {
      video.pause();
      video.removeAttribute('src');
      video.load();
    }
    this._media.replaceChildren();
  }

  _setMuted(muted) {
    this._muted = muted;
    const video = this._media.querySelector('video');
    if (video) video.muted = muted;
    const label = isT(this._lang, muted ? 'unmute' : 'mute');
    this._soundButton.title = label;
    this._soundButton.setAttribute('aria-label', label);
    this._soundButton.replaceChildren(isIcon(muted ? 'sound_off' : 'sound_on'));
  }

  _showStatus(key) {
    const text = isEl('span', '', isT(this._lang, key));
    this._status.replaceChildren(text);
  }

  // A photo, or a video that plays once, over a small copy that shows while it loads.
  _showItem(item, token) {
    const placeholder = isEl('img');
    const full = isEl(item.video ? 'video' : 'img', 'full');
    const spinner = isEl('div', 'spinner');
    placeholder.alt = '';
    placeholder.draggable = false;
    if (item.video) {
      full.muted = this._muted;
      full.playsInline = true;
      full.setAttribute('aria-label', this._describe(item));
    } else {
      full.alt = this._describe(item);
      full.draggable = false;
    }
    placeholder.addEventListener('error', () => {
      placeholder.hidden = true;
      this._forget(item, 'thumbnail');
    });
    this._media.append(placeholder, full, spinner);

    this._thumb(item).then((url) => {
      if (url && this._token === token) placeholder.src = url;
    }).catch(() => {});

    const failed = (reason, err) => {
      this._forget(item, item.video ? 'video' : 'fullsize');
      if (this._token !== token) return;
      if (item.video) this._report?.(item, reason, full, err);
      spinner.remove();
      this._showStatus(item.video ? 'video_failed' : 'photo_failed');
    };
    full.addEventListener(item.video ? 'loadeddata' : 'load', () => {
      full.classList.add('ready');
      spinner.remove();
      setTimeout(() => { placeholder.hidden = true; }, 200);
    });
    full.addEventListener('error', () => failed(IS_VIDEO_ERRORS[full.error?.code] || 'unknown'));
    (item.video ? this._video : this._full)(item).then((url) => {
      if (this._token !== token) return;
      full.src = url;
      if (item.video) this._play(full, token);
    }).catch((err) => failed('link', err));
  }

  _play(video, token) {
    video.play().catch((err) => {
      if (this._token !== token || video.muted || err?.name !== 'NotAllowedError') return;
      // The browser wants a tap before it plays sound, so this one starts without.
      this._setMuted(true);
      video.play().catch(() => {});
    });
  }

  _preload(index) {
    this._preloads = [index + 1, index - 1]
      .map((i) => this._items[i])
      .filter((item) => item && !item.video)
      .map((item) => {
        const image = new Image();
        image.addEventListener('error', () => this._forget(item, 'fullsize'));
        this._full(item).then((url) => { image.src = url; }).catch(() => {});
        return image;
      });
  }

  _onKey(e) {
    e.stopPropagation();
    if (e.key === 'Escape') {
      e.preventDefault();
      this.close();
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault();
      this._go(-1);
    } else if (e.key === 'ArrowRight') {
      e.preventDefault();
      this._go(1);
    } else if (e.key === 'Tab') {
      e.preventDefault();
      const stops = [this._soundButton, this._closeButton, this._previous, this._next].filter((el) => !el.hidden);
      const current = stops.indexOf(this.shadowRoot.activeElement);
      const step = e.shiftKey ? -1 : 1;
      stops[(current + step + stops.length) % stops.length].focus();
    }
  }

  _apply(animate = false) {
    this._media.style.transition = animate ? 'transform .18s ease-out' : 'none';
    this._media.style.transform = `translate(${this._tx}px, ${this._ty}px) scale(${this._scale})`;
  }

  _clampPan() {
    const { clientWidth: width, clientHeight: height } = this._stage;
    const maxX = ((this._scale - 1) * width) / 2;
    const maxY = ((this._scale - 1) * height) / 2;
    this._tx = isClamp(this._tx, -maxX, maxX);
    this._ty = isClamp(this._ty, -maxY, maxY);
  }

  // Keeps the point under (x, y) in place while the scale changes.
  _zoomTo(scale, x, y, animate) {
    const rect = this._stage.getBoundingClientRect();
    const px = x - rect.left - rect.width / 2;
    const py = y - rect.top - rect.height / 2;
    const ratio = scale / this._scale;
    this._tx = px - (px - this._tx) * ratio;
    this._ty = py - (py - this._ty) * ratio;
    this._scale = scale;
    this._clampPan();
    this._apply(animate);
  }

  _onWheel(e) {
    e.preventDefault();
    const scale = isClamp(this._scale * Math.exp(-e.deltaY * 0.002), 1, IS_MAX_ZOOM);
    this._zoomTo(scale, e.clientX, e.clientY, false);
  }

  _onDown(e) {
    if (e.pointerType === 'mouse' && e.button !== 0) return;
    this._pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (this._pointers.size === 2) {
      this._startPinch();
    } else if (this._pointers.size === 1) {
      this._startDrag(e.clientX, e.clientY, e.pointerId, false);
    }
  }

  _startDrag(x, y, id, moved) {
    this._gesture = { kind: 'drag', x, y, id, moved, axis: 'x', tx: this._tx, ty: this._ty, dx: 0, dy: 0, at: Date.now() };
  }

  _startPinch() {
    const [a, b] = [...this._pointers.values()];
    this._gesture = {
      kind: 'pinch',
      distance: Math.hypot(a.x - b.x, a.y - b.y) || 1,
      scale: this._scale,
    };
  }

  _onMove(e) {
    const pointer = this._pointers.get(e.pointerId);
    const gesture = this._gesture;
    if (!pointer || !gesture) return;
    pointer.x = e.clientX;
    pointer.y = e.clientY;

    if (gesture.kind === 'pinch') {
      const [a, b] = [...this._pointers.values()];
      if (!b) return;
      const scale = isClamp((gesture.scale * Math.hypot(a.x - b.x, a.y - b.y)) / gesture.distance, 1, IS_MAX_ZOOM);
      this._zoomTo(scale, (a.x + b.x) / 2, (a.y + b.y) / 2, false);
      return;
    }
    if (e.pointerId !== gesture.id) return;

    const dx = e.clientX - gesture.x;
    const dy = e.clientY - gesture.y;
    if (!gesture.moved) {
      if (Math.hypot(dx, dy) < 8) return;
      gesture.moved = true;
      gesture.axis = Math.abs(dx) > Math.abs(dy) ? 'x' : 'y';
      this._stage.setPointerCapture(e.pointerId);
    }
    gesture.dx = dx;
    gesture.dy = dy;

    if (this._scale > 1) {
      this._tx = gesture.tx + dx;
      this._ty = gesture.ty + dy;
      this._clampPan();
      this._apply();
    } else if (gesture.axis === 'x') {
      const hasNeighbour = this._items[this._index + (dx < 0 ? 1 : -1)];
      this._media.style.transition = 'none';
      this._media.style.transform = `translateX(${hasNeighbour ? dx : dx * 0.25}px)`;
    } else {
      const down = Math.max(0, dy);
      this._media.style.transition = 'none';
      this._media.style.transform = `translateY(${down}px)`;
      this._scrim.style.opacity = String(1 - Math.min(0.6, down / this._stage.clientHeight));
    }
  }

  _onUp(e, cancelled = false) {
    if (!this._pointers.delete(e.pointerId)) return;
    const gesture = this._gesture;
    if (!gesture) return;

    if (gesture.kind === 'pinch') {
      const [rest] = this._pointers.entries();
      this._gesture = null;
      if (rest) this._startDrag(rest[1].x, rest[1].y, rest[0], true);
      return;
    }
    if (e.pointerId !== gesture.id) return;
    this._gesture = null;

    if (cancelled) {
      this._snapBack();
    } else if (!gesture.moved) {
      this._tap(e.clientX, e.clientY);
    } else if (this._scale <= 1) {
      this._finishSwipe(gesture);
    }
  }

  _finishSwipe({ axis, dx, dy, at }) {
    const { clientWidth: width, clientHeight: height } = this._stage;
    const distance = Math.abs(dx);
    const speed = distance / Math.max(1, Date.now() - at);
    // A flick needs some distance too, or an unsteady tap would change the photo.
    const isFlick = distance > 40 && speed > 0.5;
    if (axis === 'x' && (distance > width * 0.2 || isFlick)) {
      const direction = dx < 0 ? 1 : -1;
      if (this._items[this._index + direction]) {
        this._slide(direction, width);
        return;
      }
    } else if (axis === 'y' && dy > height * 0.18) {
      this.close();
      return;
    }
    this._snapBack();
  }

  _snapBack() {
    this._scrim.style.opacity = '';
    this._apply(true);
  }

  _slide(direction, width) {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      this._go(direction);
      return;
    }
    this._media.style.transition = 'transform .15s ease-out';
    this._media.style.transform = `translateX(${-direction * width}px)`;
    this._slideTimer = setTimeout(() => this._go(direction), 150);
  }

  _tap(x, y) {
    const now = Date.now();
    const last = this._lastTap;
    this._lastTap = { x, y, at: now };
    if (!last || now - last.at > 300 || Math.hypot(x - last.x, y - last.y) > 30) return;
    this._lastTap = null;
    this._zoomTo(this._scale > 1 ? 1 : 2.5, x, y, true);
  }
}

class ImmichSlideshowCard extends HTMLElement {
  static get kind() {
    return 'slideshow';
  }

  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._kind = IS_KINDS[this.constructor.kind];
    this._items = [];
    this._token = 0;
    this._run = 0;
    this._visible = false;
    this._playing = false;
    this._onVisibility = () => this._sync();
    this._onMotion = () => this._restart();
  }

  setConfig(config) {
    const previous = this._config;
    this._config = config;
    this._build();
    const key = this._requestKey();
    if (!previous || key !== this._key) {
      this._key = key;
      this._reset();
      // Wait for a pause in typing before searching again.
      this._delay = previous && this.constructor.kind === 'magic' ? IS_TYPING_MS : 0;
    } else if (previous.shuffle !== config.shuffle) {
      this._order = null;
    }
    this._renderChrome();
    this._maybeLoad();
  }

  set hass(hass) {
    const previousLang = this._lang;
    this._hass = hass;
    this._lang = isLang(hass);
    this._locale = isLocale(hass);
    if (previousLang !== this._lang) this._renderChrome();
    this._maybeLoad();
  }

  get hass() {
    return this._hass;
  }

  connectedCallback() {
    this._build();
    document.addEventListener('visibilitychange', this._onVisibility);
    this._motion = window.matchMedia('(prefers-reduced-motion: reduce)');
    this._motion.addEventListener('change', this._onMotion);
    this._observer = new IntersectionObserver((entries) => {
      this._visible = entries[entries.length - 1].isIntersecting;
      this._sync();
    });
    this._observer.observe(this);
    this._resizer = new ResizeObserver(() => this._applyFitAll());
    this._resizer.observe(this._stage);
    this._maybeLoad();
  }

  disconnectedCallback() {
    document.removeEventListener('visibilitychange', this._onVisibility);
    this._motion.removeEventListener('change', this._onMotion);
    this._observer?.disconnect();
    this._resizer?.disconnect();
    this._visible = false;
    this._clearTimers();
    this._viewer?.close();
    this._stop();
  }

  getCardSize() {
    return 4;
  }

  getGridOptions() {
    return { columns: 6, rows: 4, min_columns: 3, min_rows: 2 };
  }

  static getConfigElement() {
    return document.createElement(`${IS_KINDS[this.kind].tag}-editor`);
  }

  static getStubConfig() {
    return {};
  }

  _t(key, vars) {
    return isT(this._lang, key, vars);
  }

  _interval() {
    const seconds = Number.parseFloat(this._config.interval);
    const value = Number.isFinite(seconds) ? seconds : IS_DEFAULT_INTERVAL;
    return Math.max(IS_MIN_INTERVAL, value) * 1000;
  }

  _shuffled() {
    return typeof this._config.shuffle === 'boolean' ? this._config.shuffle : this._kind.shuffle;
  }

  _request() {
    const request = this._kind.request(this._config, this._lang);
    if (request && this._config.server) request.server = this._config.server;
    if (request && this._config.videos === true) request.videos = true;
    // Who is in each photo is only asked for when the card shows it.
    if (request && isTags(this._config).includes('people')) request.people = true;
    return request;
  }

  // Identifies the set of photos. The language is left out: it only tunes a search.
  _requestKey() {
    const request = this._request();
    if (request) delete request.language;
    return JSON.stringify(request);
  }

  _build() {
    if (this._stage) return;
    const style = isEl('style');
    style.textContent = IS_CARD_STYLE;
    this._card = isEl('ha-card');
    this._stage = isEl('button', 'stage');
    this._stage.type = 'button';
    this._stage.addEventListener('click', () => this._openViewer());
    this._caption = isEl('div', 'caption');
    this._titleEl = isEl('div', 'title');
    this._metaEl = isEl('div', 'meta');
    this._caption.append(this._titleEl, this._metaEl);
    this._playButton = isEl('button', 'play');
    this._playButton.type = 'button';
    this._playButton.hidden = true;
    this._playButton.addEventListener('click', () => {
      this._playing = !this._playing;
      this._restart();
    });
    this._messageEl = isEl('div', 'message');
    this._card.append(this._stage, this._caption, this._playButton, this._messageEl);
    this.shadowRoot.replaceChildren(style, this._card);
  }

  _renderChrome() {
    if (!this._config || !this._lang || !this._stage) return;
    this._stage.setAttribute('aria-label', this._t('open_full'));
    this._applyFitAll();
    this._titleEl.textContent = String(this._config.title ?? '').trim();
    this._renderMeta(false);
    this._renderPlayButton();
    this._renderMessage();
  }

  // The description of the photo on screen. With `fade`, it fades in with the photo.
  _renderMeta(fade) {
    const text = this._current ? this._describe(this._current) : '';
    if (fade) {
      const meta = isEl('div', 'meta', text);
      this._metaEl.replaceWith(meta);
      this._metaEl = meta;
    } else {
      this._metaEl.textContent = text;
    }
    this._titleEl.hidden = !this._titleEl.textContent;
    this._metaEl.hidden = !text;
    this._caption.hidden = this._titleEl.hidden && this._metaEl.hidden;
  }

  // The viewer always shows the date and place.
  _describe(item, always = false) {
    const tags = always ? IS_DEFAULT_TAGS : isTags(this._config);
    return tags.map((tag) => this._part(tag, item)).filter(Boolean).join(' · ');
  }

  _part(tag, item) {
    if (tag === 'date') return this._date(item);
    if (tag === 'year') return isTaken(item)?.getUTCFullYear().toString();
    if (tag === 'place') return isPlace(item);
    if (tag === 'people') return this._people(item);
    return item[tag];
  }

  // "Ana, Rui and Maria".
  _people(item) {
    const names = Array.isArray(item.people) ? item.people.filter(Boolean) : [];
    try {
      return new Intl.ListFormat(this._locale || 'en', { style: 'long', type: 'conjunction' }).format(names);
    } catch (_err) {
      return names.join(', ');
    }
  }

  _date(item) {
    const taken = isTaken(item);
    if (!taken) return '';
    const locale = this._locale || 'en';
    if (this.constructor.kind === 'on_this_day') {
      const year = Number(String(this._day || '').slice(0, 4)) || new Date().getFullYear();
      const years = year - taken.getUTCFullYear();
      if (years > 0) {
        return isCapitalize(new Intl.RelativeTimeFormat(locale, { numeric: 'auto' }).format(-years, 'year'));
      }
    }
    return new Intl.DateTimeFormat(locale, { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' }).format(taken);
  }

  // People who ask for reduced motion start and stop the slideshow themselves.
  _renderPlayButton() {
    if (!this._playButton || !this._lang) return;
    const show = Boolean(this._motion?.matches && this._current && (this._items.length > 1 || this._current.video));
    this._playButton.hidden = !show;
    if (!show) return;
    const label = this._t(this._playing ? 'pause' : 'play');
    this._playButton.title = label;
    this._playButton.setAttribute('aria-label', label);
    this._playButton.replaceChildren(isIcon(this._playing ? 'pause' : 'play'));
  }

  // A message is { key, detail, retry }, or { loading: true }, or null while photos show.
  _setMessage(message) {
    this._message = message;
    this._renderMessage();
  }

  _renderMessage() {
    if (!this._messageEl || !this._lang) return;
    const placeholder = !this._request();
    const message = placeholder ? { key: this._kind.placeholder } : this._message;
    this._messageEl.hidden = !message;
    this._messageEl.classList.toggle('placeholder', placeholder);
    this._messageEl.replaceChildren();
    if (!message) return;
    if (placeholder) this._messageEl.appendChild(isIcon(this._kind.placeholderIcon));
    if (message.loading) {
      this._messageEl.setAttribute('aria-label', this._t('loading'));
      this._messageEl.appendChild(isEl('div', 'spinner'));
      return;
    }
    this._messageEl.removeAttribute('aria-label');
    this._messageEl.appendChild(isEl('div', '', this._t(message.key)));
    if (message.detail) this._messageEl.appendChild(isEl('div', 'detail', message.detail));
    if (message.retry) {
      const button = isEl('button', 'action', this._t('try_again'));
      button.type = 'button';
      button.addEventListener('click', message.retry);
      this._messageEl.appendChild(button);
    }
  }

  _clearTimers() {
    clearTimeout(this._retryTimer);
    clearTimeout(this._delayTimer);
  }

  _reset() {
    this._stop();
    this._clearTimers();
    this._token += 1;
    this._loaded = false;
    this._loading = false;
    this._items = [];
    this._order = null;
    this._position = 0;
    this._current = null;
    this._slide = null;
    this._shownAt = 0;
    this._nextSlide = null;
    this._playing = false;
    this._day = null;
    this._refreshAt = 0;
    this._message = null;
    this._stage?.replaceChildren();
  }

  _maybeLoad() {
    if (this._loaded || !this._hass || !this._config || !this._request() || !this.isConnected) return;
    this._loaded = true;
    if (this._delay) {
      this._setMessage({ loading: true });
      this._delayTimer = setTimeout(() => this._load(), this._delay);
      this._delay = 0;
    } else {
      this._load();
    }
  }

  // A background reload keeps the current photos on screen if it fails, and its
  // photos wait for the next round. With `restart` they replace the round under way.
  async _load(background = false, restart = false) {
    const token = ++this._token;
    this._clearTimers();
    this._loading = true;
    if (!background) this._setMessage({ loading: true });
    try {
      const result = await this._hass.callWS({ type: `${IS_DOMAIN}/photos`, ...this._request() });
      if (token !== this._token) return;
      this._loading = false;
      const items = result.photos || [];
      this._server = result.server;
      this._day = result.date || null;
      this._refreshAt = result.refresh_at || 0;
      this._loadedAt = Date.now();
      if (!items.length) {
        if (background && !restart) return;
        this._showEmpty();
        return;
      }
      this._items = items;
      if (background && !restart) return;
      this._order = null;
      this._nextSlide = null;
      if (this._message) this._setMessage(null);
      if (restart) this._restart();
      else this._sync();
    } catch (err) {
      if (token !== this._token) return;
      this._loading = false;
      if (background) {
        // Keep showing what's there, and try again in a minute rather than on every photo.
        if (restart && this._refreshAt) this._refreshAt = Date.now() + IS_RETRY_MS;
        if (!this._items.length) this._retryTimer = setTimeout(() => this._load(true, true), IS_RETRY_MS);
        return;
      }
      this._loaded = false;
      const missing = ['unknown_command', 'not_configured'].includes(err?.code);
      // Home Assistant only lets admins read photos from Immich.
      const refused = err?.code === 'unauthorized';
      let key = 'load_failed';
      if (missing) key = 'no_integration';
      else if (refused) key = 'admin_only';
      this._setMessage({
        key,
        detail: missing || refused ? undefined : err?.message,
        retry: () => this._maybeLoad(),
      });
      this._retryTimer = setTimeout(() => this._maybeLoad(), IS_RETRY_MS);
    }
  }

  // Nothing to show yet: look again in an hour, or when the day changes.
  _showEmpty() {
    this._stop();
    this._items = [];
    this._order = null;
    this._current = null;
    this._slide = null;
    this._nextSlide = null;
    for (const old of this._stage.children) this._releaseClip(old);
    this._stage.replaceChildren();
    this._renderMeta(false);
    this._renderPlayButton();
    this._setMessage({ key: this._kind.empty(this._config) });
    const until = this._refreshAt ? this._refreshAt - Date.now() : IS_RELOAD_MS;
    this._retryTimer = setTimeout(() => this._load(true, true), isClamp(until, 1000, IS_RELOAD_MS));
  }

  // Runs the slideshow only while someone can see it.
  _sync() {
    const active = this.isConnected && this._visible && !document.hidden && !this._viewer && this._items.length > 0;
    if (active && !this._running) this._start();
    else if (!active && this._running) this._stop();
  }

  _still() {
    return Boolean(this._motion?.matches && !this._playing);
  }

  _restart() {
    if (this._running) this._stop();
    this._renderPlayButton();
    this._sync();
  }

  _start() {
    this._running = true;
    this._loop(++this._run);
  }

  _stop() {
    this._running = false;
    this._run += 1;
    clearTimeout(this._waitTimer);
    this._waitDone?.();
  }

  _wait(ms) {
    return new Promise((resolve) => {
      this._waitDone = resolve;
      this._waitTimer = setTimeout(resolve, ms);
    });
  }

  // Whether the slideshow stays on what it shows: with reduced motion until it's
  // asked to play, and on an only photo. An only video plays again and again.
  _rests() {
    return this._still() || (this._items.length <= 1 && !this._current.video);
  }

  async _loop(run) {
    if (this._current) {
      if (this._rests()) return;
      await this._hold(run);
    }
    while (run === this._run) {
      this._nextSlide = this._nextSlide || this._prepare();
      const slide = await this._nextSlide;
      if (run !== this._run) return;
      this._nextSlide = null;
      if (slide) {
        this._show(slide);
        if (this._rests()) return;
        this._nextSlide = this._prepare();
        await this._hold(run);
      } else {
        if (!this._current) this._setMessage({ key: 'photos_failed' });
        await this._wait(this._interval());
      }
    }
  }

  // Gives what's on screen its time: the interval, or longer for a video that runs longer.
  async _hold(run) {
    if (this._current.video) await this._playClip(this._slide, run);
    if (run !== this._run) return;
    await this._wait(Math.max(0, this._interval() - (Date.now() - this._shownAt)));
  }

  // Plays a slide's video once, over its still. Resolves when the video ends or can't
  // go on, which leaves the still, or when the slideshow stops, which pauses the video.
  async _playClip(slide, run) {
    if (slide._over) return;
    slide._clip = slide._clip || this._loadClip(slide);
    const clip = await slide._clip;
    if (!clip || slide._over || run !== this._run) return;
    const item = slide._item;
    await new Promise((resolve) => {
      let settled = false;
      let stalled;
      // `failed` is why the video can't go on, and `err` what the browser said about it.
      const done = (over, failed, err) => {
        if (settled) return;
        settled = true;
        clearTimeout(stalled);
        for (const [type, handler] of Object.entries(handlers)) clip.removeEventListener(type, handler);
        clip.pause();
        slide._over = over;
        if (failed) {
          this._reportVideo(item, failed, clip, err, 'slideshow');
          clip.classList.remove('on');
          this._forgetLink(item, 'video');
        }
        resolve();
      };
      const watch = () => {
        clearTimeout(stalled);
        stalled = setTimeout(() => done(true, 'stalled'), IS_STALL_MS);
      };
      const handlers = {
        playing: () => clip.classList.add('on'),
        timeupdate: watch,
        ended: () => done(true),
        error: () => done(true, IS_VIDEO_ERRORS[clip.error?.code] || 'unknown'),
      };
      for (const [type, handler] of Object.entries(handlers)) clip.addEventListener(type, handler);
      // A stopped slideshow carries on from here when it starts again.
      this._waitDone = () => done(false);
      watch();
      // Browsers that won't start a video on their own leave the still.
      clip.play().catch((err) => done(true, isPlayFailure(err), err));
    });
  }

  // The video starts loading when its slide is on screen, not ahead like its still.
  async _loadClip(slide) {
    const clip = isEl('video', 'clip');
    clip.muted = true;
    clip.playsInline = true;
    try {
      clip.src = await this._videoLink(slide._item);
    } catch (err) {
      this._reportVideo(slide._item, 'link', null, err, 'slideshow');
      return null;
    }
    // The slide was taken down while the link was on its way.
    if (!slide._clip) return null;
    slide.appendChild(clip);
    return clip;
  }

  // Stops a slide's video from loading any further, once the slide is done with.
  // A video that is only paused keeps its connection open for a while.
  _releaseClip(slide) {
    const loading = slide._clip;
    if (!loading) return;
    slide._clip = null;
    slide._over = true;
    loading.then((clip) => {
      if (!clip) return;
      clip.pause();
      clip.removeAttribute('src');
      clip.load();
    });
  }

  // Finds the next photo that loads, skipping a few that don't. A video loads as its still.
  async _prepare() {
    const attempts = Math.min(this._items.length, IS_MAX_SKIPS);
    for (let i = 0; i < attempts; i += 1) {
      const item = this._nextItem();
      try {
        const image = await this._loadPhoto(item);
        return { item, slide: await this._buildSlide(item, image) };
      } catch (_err) {
        // Try the next photo.
      }
    }
    return null;
  }

  _nextItem() {
    if (this._refreshAt && Date.now() >= this._refreshAt && !this._loading) {
      // A new day: start over with that day's photos once they arrive.
      this._load(true, true);
    }
    if (!this._order || this._position >= this._order.length) {
      this._order = this._shuffled() ? isShuffle(this._items) : [...this._items];
      this._position = 0;
      // Don't repeat the same photo when a shuffled round starts again.
      if (this._order.length > 1 && this._order[0] === this._current) {
        this._order.push(this._order.shift());
      }
      // Fetch the next round's photos while this round plays.
      const due = this._kind.reloadEachRound(this._config) || Date.now() - this._loadedAt > IS_RELOAD_MS;
      if (due && !this._loading) this._load(true);
    }
    const item = this._order[this._position];
    this._position += 1;
    return item;
  }

  _path(item, size) {
    return `/api/${IS_DOMAIN}/${this._server}/${item.id}/${size}`;
  }

  // The tile uses Immich's preview size, which is far smaller than the full image.
  async _loadPhoto(item) {
    try {
      return await this._loadImage(item, 'preview');
    } catch (_err) {
      return this._loadImage(item, 'fullsize');
    }
  }

  async _loadImage(item, size) {
    try {
      return await isLoadImage(await this._link(item, size));
    } catch (err) {
      this._forgetLink(item, size);
      throw err;
    }
  }

  // A photo's link is used again while it lasts, so the browser shows the copy it has:
  // the one the viewer loaded ahead, or a photo that comes round again.
  _link(item, size) {
    return isLink(this._path(item, size), (path) => this._sign(path));
  }

  // A video's link lasts as long as the video and five minutes more, so it too can be
  // used again: an only video, which plays again and again, is then loaded once.
  _videoLink(item) {
    return isLink(this._path(item, 'video'), (path) => this._sign(path, isVideoSeconds(item)));
  }

  // Tells Home Assistant why a video couldn't be played, for its log. The card keeps
  // the still and moves on, and a wall display has no console to read the reason in.
  _reportVideo(item, reason, video, err, place) {
    this._hass?.callWS({
      type: `${IS_DOMAIN}/video_failed`,
      asset: item.id,
      reason,
      place,
      detail: isVideoDetail(video, err),
      browser: navigator.userAgent.slice(0, 300),
    }).catch(() => {});
  }

  // A link that didn't load isn't used again.
  _forgetLink(item, size) {
    isLinks.delete(this._path(item, size));
  }

  async _sign(path, seconds = IS_SIGN_SECONDS) {
    const signed = await this._hass.callWS({ type: 'auth/sign_path', path, expires: seconds });
    return isUrl(this._hass, signed.path);
  }

  _fit() {
    return ['cover', 'contain'].includes(this._config.fit) ? this._config.fit : 'auto';
  }

  // Whether a photo is shown whole over a blurred copy, rather than cropped to fill the tile.
  _showWhole(image) {
    const fit = this._fit();
    if (fit !== 'auto') return fit === 'contain';
    const { clientWidth: width, clientHeight: height } = this._stage;
    if (!width || !height || !image.naturalWidth || !image.naturalHeight) return false;
    const photo = image.naturalWidth / image.naturalHeight;
    const tile = width / height;
    return 1 - Math.min(photo / tile, tile / photo) > IS_MAX_CROP;
  }

  // Waits for the backdrop, so a slide never fades in without it.
  async _buildSlide(item, image) {
    const slide = isEl('div', 'slide');
    image.className = 'photo';
    slide.appendChild(image);
    slide._item = item;
    slide._photo = image;
    await this._applyFit(slide);
    return slide;
  }

  _applyFit(slide) {
    const whole = this._showWhole(slide._photo);
    slide.classList.toggle('whole', whole);
    if (whole && !slide._backdrop) slide._backdrop = this._loadBackdrop(slide);
    return slide._backdrop;
  }

  _applyFitAll() {
    for (const slide of this._stage?.children || []) this._applyFit(slide);
  }

  // The backdrop is blurred, so the small thumbnail is enough.
  async _loadBackdrop(slide) {
    try {
      const backdrop = await this._loadImage(slide._item, 'thumbnail');
      backdrop.className = 'backdrop';
      slide.prepend(backdrop);
    } catch (_err) {
      // The photo still shows, on the plain background.
    }
  }

  _show({ item, slide }) {
    this._stage.appendChild(slide);
    // Commit the starting opacity so the fade runs.
    void slide.offsetWidth;
    slide.classList.add('on');
    this._current = item;
    this._slide = slide;
    this._shownAt = Date.now();
    this._renderMeta(true);
    this._renderPlayButton();
    if (this._message) this._setMessage(null);
    setTimeout(() => {
      for (const old of [...this._stage.children]) {
        if (old === this._stage.lastElementChild) continue;
        this._releaseClip(old);
        old.remove();
      }
    }, IS_FADE_MS + 100);
  }

  _openViewer() {
    const current = this._current;
    if (!current) return;
    // The round under way, or the photo alone if the photos were just replaced.
    let items = this._order?.includes(current) ? this._order : this._items;
    if (!items.includes(current)) items = [current];
    this._viewer = document.createElement('immich-slideshow-viewer');
    this._sync();
    this._viewer.open({
      items,
      index: items.indexOf(current),
      lang: this._lang,
      full: (item) => this._link(item, 'fullsize'),
      thumb: (item) => this._link(item, 'thumbnail'),
      video: (item) => this._videoLink(item),
      forget: (item, size) => this._forgetLink(item, size),
      report: (item, reason, video, err) => this._reportVideo(item, reason, video, err, 'viewer'),
      describe: (item) => this._describe(item, true),
      onClose: () => {
        this._viewer = null;
        this._stage.focus({ preventScroll: true });
        this._sync();
      },
    });
  }
}

class ImmichMagicCard extends ImmichSlideshowCard {
  static get kind() {
    return 'magic';
  }
}

class ImmichOnThisDayCard extends ImmichSlideshowCard {
  static get kind() {
    return 'on_this_day';
  }
}

// Home Assistant only registers ha-form once something needs it, so a custom
// editor asks for a built-in card's editor, which imports it.
async function isLoadForm() {
  if (customElements.get('ha-form')) return true;
  try {
    const helpers = await window.loadCardHelpers();
    const card = await helpers.createCardElement({ type: 'button', entity: 'sun.sun' });
    await card.constructor.getConfigElement();
  } catch (_err) {
    // Reported below, as the form still isn't defined.
  }
  return Boolean(customElements.get('ha-form'));
}

const IS_EDITOR_KEYS = ['server', 'source', 'album', 'query', 'count', 'interval', 'shuffle', 'videos', 'fit', 'title'];

class ImmichSlideshowCardEditor extends HTMLElement {
  static get kind() {
    return 'slideshow';
  }

  setConfig(config) {
    this._config = config;
    if (!this._form) {
      this._start();
      return;
    }
    this._form.data = this._formData();
    this._form.schema = this._schema();
    // The albums belong to one server, so another server needs its own list.
    if (this._albumsLoaded && this._formData().server !== this._albumServer) this._loadAlbums();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._form) this._form.hass = hass;
    else this._start();
  }

  _t(key) {
    return isT(isLang(this._hass), key);
  }

  _defaults() {
    return {
      source: 'album',
      count: IS_SEARCH_COUNT,
      interval: IS_DEFAULT_INTERVAL,
      shuffle: IS_KINDS[this.constructor.kind].shuffle,
      videos: false,
      fit: 'auto',
    };
  }

  async _start() {
    if (this._starting || !this._hass || !this._config) return;
    this._starting = true;
    if (!(await isLoadForm())) {
      const message = isEl('div', '', this._t('editor_unavailable'));
      message.style.padding = '16px';
      this.replaceChildren(message);
      return;
    }
    this._servers = [];
    this._albums = [];
    this._albumsLoaded = false;
    this._albumRequest = 0;
    this._form = document.createElement('ha-form');
    this._form.computeLabel = (schema) => this._t(`editor_${schema.name}`);
    this._form.computeHelper = (schema) => this._helper(schema.name);
    this._form.addEventListener('value-changed', (e) => this._onChange(e));
    this._form.hass = this._hass;
    this._form.data = this._formData();
    this._form.schema = this._schema();
    this.replaceChildren(this._form);
    await this._loadServers();
    this._loadAlbums();
  }

  // Shows the defaults in the form, without writing them to the config.
  _formData() {
    const data = { ...this._defaults(), ...this._config };
    if (data.album) data.album = isAlbumId(data.album);
    data.description = isTags(this._config);
    if (this._servers.length > 1 && !data.server) data.server = this._servers[0].id;
    return data;
  }

  _helper(name) {
    if (name === 'album') {
      return this._albumsLoaded && !this._albums.length ? this._t('editor_no_albums') : undefined;
    }
    if (['source', 'query', 'count', 'interval', 'videos', 'fit', 'description', 'title'].includes(name)) return this._t(`editor_${name}_hint`);
    return undefined;
  }

  _select(name, options) {
    return { name, required: true, selector: { select: { mode: 'dropdown', options } } };
  }

  _schema() {
    const kind = this.constructor.kind;
    const fields = [];
    if (this._servers.length > 1) {
      fields.push(this._select('server', this._servers.map((server) => ({ value: server.id, label: server.name }))));
    }
    const random = kind === 'slideshow' && this._config.source === 'random';
    if (kind === 'slideshow') {
      fields.push(this._select('source', [
        { value: 'album', label: this._t('editor_source_album') },
        { value: 'random', label: this._t('editor_source_random') },
      ]));
      if (!random) {
        const options = [...this._albums];
        const current = isAlbumId(this._config.album);
        if (current && !options.some((option) => option.value === current)) {
          options.push({ value: current, label: this._t('editor_album_current') });
        }
        fields.push(this._select('album', options));
      }
    }
    if (kind === 'magic') {
      fields.push({ name: 'query', required: true, selector: { text: {} } });
      fields.push({ name: 'count', selector: { number: { mode: 'box', min: 1, max: IS_SEARCH_MAX, step: 1 } } });
    }
    fields.push({
      name: 'interval',
      selector: { number: { mode: 'box', min: IS_MIN_INTERVAL, step: 1, unit_of_measurement: 's' } },
    });
    // Random photos are already in random order.
    if (!random) fields.push({ name: 'shuffle', selector: { boolean: {} } });
    fields.push({ name: 'videos', selector: { boolean: {} } });
    fields.push(this._select('fit', [
      { value: 'auto', label: this._t('editor_fit_auto') },
      { value: 'cover', label: this._t('editor_fit_cover') },
      { value: 'contain', label: this._t('editor_fit_contain') },
    ]));
    // Chips that can be added, removed and dragged into another order.
    fields.push({
      name: 'description',
      selector: {
        select: {
          multiple: true,
          reorder: true,
          mode: 'dropdown',
          options: IS_TAGS.map((tag) => ({ value: tag, label: this._t(`tag_${tag}`) })),
        },
      },
    });
    fields.push({ name: 'title', selector: { text: {} } });
    return fields;
  }

  async _loadServers() {
    try {
      const result = await this._hass.callWS({ type: `${IS_DOMAIN}/servers` });
      this._servers = result.servers || [];
    } catch (_err) {
      this._servers = [];
    }
    this._form.data = this._formData();
    this._form.schema = this._schema();
  }

  async _loadAlbums() {
    if (this.constructor.kind !== 'slideshow' || !this._form) return;
    this._albumRequest += 1;
    const request = this._albumRequest;
    const { server } = this._formData();
    this._albumServer = server;
    try {
      const message = { type: `${IS_DOMAIN}/albums` };
      if (server) message.server = server;
      const result = await this._hass.callWS(message);
      if (request !== this._albumRequest) return;
      this._albums = (result.albums || []).map((album) => ({ value: album.id, label: album.name }));
    } catch (_err) {
      if (request !== this._albumRequest) return;
      this._albums = [];
    }
    this._albumsLoaded = true;
    this._form.schema = this._schema();
  }

  // Keeps only what differs from the defaults, so the YAML stays short.
  _onChange(e) {
    e.stopPropagation();
    const value = e.detail.value;
    const defaults = this._defaults();
    const config = { ...this._config };
    for (const key of IS_EDITOR_KEYS) {
      if (!(key in value)) continue;
      const next = value[key];
      if (next === undefined || next === null || next === '' || next === defaults[key]) delete config[key];
      else config[key] = next;
    }
    // The description replaces the date and place switches of earlier versions.
    if ('description' in value) {
      const tags = isTags({ description: value.description || [] });
      delete config.show_date;
      delete config.show_place;
      if (tags.join() === IS_DEFAULT_TAGS.join()) delete config.description;
      else config.description = tags;
    }
    // An album saved by an earlier version is rewritten as a plain album ID.
    if (config.album) config.album = isAlbumId(config.album);
    // With one server there's nothing to choose, so none is saved.
    if (this._servers.length <= 1) delete config.server;
    this._config = config;
    this.dispatchEvent(new CustomEvent('config-changed', {
      detail: { config },
      bubbles: true,
      composed: true,
    }));
  }
}

class ImmichMagicCardEditor extends ImmichSlideshowCardEditor {
  static get kind() {
    return 'magic';
  }
}

class ImmichOnThisDayCardEditor extends ImmichSlideshowCardEditor {
  static get kind() {
    return 'on_this_day';
  }
}

// Guard against the file being loaded twice, which would otherwise throw on the second define().
if (!customElements.get('immich-slideshow-viewer')) {
  customElements.define('immich-slideshow-viewer', ImmichSlideshowViewer);
  const cards = [
    [ImmichSlideshowCard, ImmichSlideshowCardEditor],
    [ImmichMagicCard, ImmichMagicCardEditor],
    [ImmichOnThisDayCard, ImmichOnThisDayCardEditor],
  ];
  window.customCards = window.customCards || [];
  for (const [card, editor] of cards) {
    const kind = IS_KINDS[card.kind];
    customElements.define(`${kind.tag}-editor`, editor);
    customElements.define(kind.tag, card);
    window.customCards.push({
      type: kind.tag,
      name: kind.name,
      description: kind.description,
      documentationURL: IS_REPO,
      preview: true,
    });
  }
  console.info(`%c IMMICH-SLIDESHOW %c ${IS_VERSION} `, 'background:#4250af;color:#fff', 'background:#ddd;color:#000');
}
