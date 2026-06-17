const audio = new Audio();
let isPlaying = false;
let currentPreviewUrl = '';
let currentSongTitle = '';
let currentSongArtist = '';

// Initialize default volume to match visual 80% default width of volume-level bar
audio.volume = 0.8;
let lastVolume = 0.8;

// Format time (seconds to mm:ss)
function formatTime(seconds) {
    if (isNaN(seconds)) return "0:00";
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
}

// Function to play adjacent song in the carousel list
function playAdjacentSong(offset) {
    // Select all currently visible cards in the carousel
    const visibleCards = Array.from(document.querySelectorAll('.carousel-item[data-cancion]'))
        .filter(card => card.style.display !== 'none');
        
    if (visibleCards.length === 0) return;
    
    // Find the index of the current song
    let currentIndex = visibleCards.findIndex(card => {
        const title = card.getAttribute('data-cancion');
        const artist = card.getAttribute('data-artista');
        return title === currentSongTitle && artist === currentSongArtist;
    });
    
    if (currentIndex === -1) {
        currentIndex = 0; // Default to first song if current not found
    }
    
    let nextIndex = currentIndex + offset;
    
    // Circular bounds
    if (nextIndex < 0) {
        nextIndex = visibleCards.length - 1;
    } else if (nextIndex >= visibleCards.length) {
        nextIndex = 0;
    }
    
    const nextCard = visibleCards[nextIndex];
    if (nextCard) {
        // Trigger click on the next card, which handles all UI, class toggles, and playing!
        nextCard.click();
    }
}

// Update all playback icons & active states across the page in real-time
function updateGlobalPlaybackUI() {
    const playBtn = document.getElementById('player-play-btn');
    
    // 1. Update main player bar play button icon
    if (playBtn) {
        if (isPlaying) {
            playBtn.innerHTML = '<i class="ph-fill ph-pause"></i>';
        } else {
            playBtn.innerHTML = '<i class="ph-fill ph-play"></i>';
        }
    }
    
    // 2. Update carousel card items (active class & icon toggling)
    const carouselItems = document.querySelectorAll('.carousel-item[data-cancion]');
    carouselItems.forEach(card => {
        const title = card.getAttribute('data-cancion');
        const artist = card.getAttribute('data-artista');
        const isCurrent = (title === currentSongTitle && artist === currentSongArtist);
        const playIcon = card.querySelector('.play-icon-circle i');
        
        if (isCurrent) {
            if (isPlaying) {
                card.classList.add('active-playing');
                card.classList.remove('active-paused');
                if (playIcon) {
                    playIcon.className = 'ph-fill ph-pause';
                }
            } else {
                card.classList.remove('active-playing');
                card.classList.add('active-paused');
                if (playIcon) {
                    playIcon.className = 'ph-fill ph-play';
                }
            }
        } else {
            card.classList.remove('active-playing');
            card.classList.remove('active-paused');
            if (playIcon) {
                playIcon.className = 'ph-fill ph-play';
            }
        }
    });

    // 3. Update canciones list table rows if present
    const tableRows = document.querySelectorAll('tbody tr');
    tableRows.forEach(row => {
        const titleCol = row.querySelector('.col-name strong');
        if (!titleCol) return;
        const title = titleCol.textContent.trim();
        const isCurrent = (title === currentSongTitle);
        const rowPlayBtn = row.querySelector('.table-play-btn i');
        
        if (isCurrent) {
            row.classList.add('playing-row');
            if (rowPlayBtn) {
                if (isPlaying) {
                    rowPlayBtn.className = 'ph-fill ph-pause';
                } else {
                    rowPlayBtn.className = 'ph-fill ph-play';
                }
            }
        } else {
            row.classList.remove('playing-row');
            if (rowPlayBtn) {
                rowPlayBtn.className = 'ph-fill ph-play';
            }
        }
    });
}

async function playSong(title, artist) {
    // 1. Play/Pause toggle if clicking the already active song
    if (currentSongTitle === title && currentSongArtist === artist && currentPreviewUrl) {
        if (isPlaying) {
            audio.pause();
        } else {
            audio.play();
        }
        return;
    }

    // Registrar la reproducción en tiempo real en la base de datos de SoundWave
    const currentUser = localStorage.getItem('soundwave_user');
    let usuarioId = null;
    if (currentUser) {
        try {
            usuarioId = JSON.parse(currentUser).usuarioId;
        } catch (e) {
            console.error('[SoundWave] Error parsing soundwave_user:', e);
        }
    }
    
    fetch('/api/reproducir', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            titulo: title,
            artista: artist,
            album: artist,
            usuarioId: usuarioId,
            dispositivo: /iPhone|iPad|iPod/i.test(navigator.userAgent) ? 'iPhone' : /Android/i.test(navigator.userAgent) ? 'Android' : 'Web'
        })
    }).then(r => r.json())
      .then(data => {
          console.log('[SoundWave] Reproducción registrada en BD:', data);
      }).catch(err => {
          console.error('[SoundWave] Error al registrar reproducción:', err);
      });


    const player = document.getElementById('global-player');
    const playBtn = document.getElementById('player-play-btn');
    const coverImg = document.getElementById('player-cover');
    const titleEl = document.getElementById('player-title');
    const artistEl = document.getElementById('player-artist');
    
    // Save current active track state
    currentSongTitle = title;
    currentSongArtist = artist;
    
    titleEl.textContent = 'Buscando...';
    artistEl.textContent = `${title} - ${artist}`;
    player.classList.add('active');
    playBtn.innerHTML = '<i class="ph ph-spinner-gap"></i>';
    
    // Instantly update states to show searching cover spinner
    updateGlobalPlaybackUI();
    
    try {
        const query = encodeURIComponent(`${title} ${artist}`);
        const response = await fetch(`https://itunes.apple.com/search?term=${query}&media=music&limit=1`);
        const data = await response.json();
        
        if (data.results && data.results.length > 0) {
            const track = data.results[0];
            
            titleEl.textContent = track.trackName;
            artistEl.textContent = track.artistName;
            coverImg.src = track.artworkUrl100 || 'https://via.placeholder.com/56';
            
            if (track.previewUrl) {
                if (currentPreviewUrl !== track.previewUrl) {
                    audio.src = track.previewUrl;
                    currentPreviewUrl = track.previewUrl;
                }
                
                audio.play();
            } else {
                titleEl.textContent = 'Preview no disponible';
                isPlaying = false;
                updateGlobalPlaybackUI();
            }
        } else {
            titleEl.textContent = 'Canción no encontrada';
            isPlaying = false;
            updateGlobalPlaybackUI();
        }
    } catch (error) {
        console.error('Error fetching song from iTunes:', error);
        titleEl.textContent = 'Error de conexión';
        isPlaying = false;
        updateGlobalPlaybackUI();
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const playBtn = document.getElementById('player-play-btn');
    const backBtn = document.getElementById('player-back-btn');
    const forwardBtn = document.getElementById('player-forward-btn');
    
    const progressBar = document.getElementById('player-progress');
    const currentTimeEl = document.getElementById('player-current-time');
    const totalTimeEl = document.getElementById('player-total-time');
    
    // Volume Elements
    const volumeBar = document.querySelector('.volume-bar');
    const volumeLevel = document.querySelector('.volume-level');
    const volumeIcon = document.querySelector('.player-volume i');
    
    // Set initial visual volume bar position to match default 80% volume
    if (volumeLevel) {
        volumeLevel.style.width = '80%';
    }

    // Audio native element event listeners for automatic synchronization
    audio.addEventListener('play', () => {
        isPlaying = true;
        updateGlobalPlaybackUI();
    });
    
    audio.addEventListener('pause', () => {
        isPlaying = false;
        updateGlobalPlaybackUI();
    });
    
    audio.addEventListener('ended', () => {
        isPlaying = false;
        progressBar.style.width = '0%';
        currentTimeEl.textContent = '0:00';
        updateGlobalPlaybackUI();
        
        // Auto-play the next song in list for perfect radio-like flow!
        playAdjacentSong(1);
    });
    
    audio.addEventListener('timeupdate', () => {
        if (isDraggingProgress) return; // Don't interrupt while dragging
        const percent = (audio.currentTime / audio.duration) * 100;
        progressBar.style.width = `${percent}%`;
        currentTimeEl.textContent = formatTime(audio.currentTime);
        totalTimeEl.textContent = formatTime(audio.duration);
    });

    // Play/Pause toggle
    playBtn.addEventListener('click', () => {
        if (!currentPreviewUrl) return;
        
        if (isPlaying) {
            audio.pause();
        } else {
            audio.play();
        }
    });
    
    // Skip Back (Rewind / Prev Song)
    if (backBtn) {
        backBtn.addEventListener('click', () => {
            if (!currentSongTitle) return;
            // Always skip directly to previous song for instant responsive feel
            playAdjacentSong(-1);
        });
    }
    
    // Skip Forward (Next Song)
    if (forwardBtn) {
        forwardBtn.addEventListener('click', () => {
            if (!currentSongTitle) return;
            playAdjacentSong(1);
        });
    }
    
    // Interactive & Draggable Progress Bar (Seek)
    const progressContainer = document.querySelector('.progress-bar');
    let isDraggingProgress = false;

    function setProgressFromEvent(e) {
        if (!currentPreviewUrl || isNaN(audio.duration)) return;
        const rect = progressContainer.getBoundingClientRect();
        const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
        audio.currentTime = pct * audio.duration;
        progressBar.style.width = `${pct * 100}%`;
        currentTimeEl.textContent = formatTime(audio.currentTime);
    }

    if (progressContainer) {
        const parent = progressContainer.parentElement;
        parent.style.cursor = 'pointer';
        
        parent.addEventListener('mousedown', (e) => {
            if (!currentPreviewUrl || isNaN(audio.duration)) return;
            isDraggingProgress = true;
            setProgressFromEvent(e);
        });
        
        document.addEventListener('mousemove', (e) => {
            if (isDraggingProgress) {
                setProgressFromEvent(e);
            }
        });
        
        document.addEventListener('mouseup', () => {
            isDraggingProgress = false;
        });
    }
    
    // Fully Functional Click & Drag Volume Control
    let isDraggingVolume = false;

    function setVolumeFromEvent(e) {
        if (!volumeBar) return;
        const rect = volumeBar.getBoundingClientRect();
        const pct = (e.clientX - rect.left) / rect.width;
        const volume = Math.max(0, Math.min(1, pct));
        
        audio.volume = volume;
        volumeLevel.style.width = `${volume * 100}%`;
        
        // Update speaker dynamic icons
        if (volumeIcon) {
            if (volume === 0) {
                volumeIcon.className = 'ph ph-speaker-x';
            } else if (volume < 0.35) {
                volumeIcon.className = 'ph ph-speaker-low';
            } else if (volume < 0.7) {
                volumeIcon.className = 'ph ph-speaker-simple';
            } else {
                volumeIcon.className = 'ph ph-speaker-high';
            }
        }
    }

    if (volumeBar && volumeLevel) {
        volumeBar.addEventListener('mousedown', (e) => {
            isDraggingVolume = true;
            setVolumeFromEvent(e);
        });
        
        document.addEventListener('mousemove', (e) => {
            if (isDraggingVolume) {
                setVolumeFromEvent(e);
            }
        });
        
        document.addEventListener('mouseup', () => {
            isDraggingVolume = false;
        });
    }

    // Dynamic Speaker Icon Click - Mute / Unmute Toggle
    if (volumeIcon) {
        volumeIcon.style.cursor = 'pointer';
        volumeIcon.addEventListener('click', () => {
            if (audio.volume > 0) {
                lastVolume = audio.volume;
                audio.volume = 0;
                volumeLevel.style.width = '0%';
                volumeIcon.className = 'ph ph-speaker-x';
            } else {
                audio.volume = lastVolume;
                volumeLevel.style.width = `${lastVolume * 100}%`;
                if (lastVolume < 0.35) {
                    volumeIcon.className = 'ph ph-speaker-low';
                } else if (lastVolume < 0.7) {
                    volumeIcon.className = 'ph ph-speaker-simple';
                } else {
                    volumeIcon.className = 'ph ph-speaker-high';
                }
            }
        });
    }
});
