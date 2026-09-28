"""Interface language.

English is the default; Turkish is available from the globe button. The
choice is saved with the rest of the session, so it survives a restart.
"""

LANGUAGES = ("en", "tr")

_STRINGS = {
    "subtitle":        ("3D sound enhancement", "3D ses geliştirme"),
    "volume":          ("VOLUME", "SES"),
    "preamp":          ("PRE-AMP", "PRE-AMP"),
    "output":          ("OUTPUT", "ÇIKIŞ"),
    "unknown_output":  ("Unknown", "Bilinmiyor"),

    "surround":        ("3D Surround", "3D Surround"),
    "ambience":        ("Ambience", "Ambience"),
    "fidelity":        ("Fidelity", "Fidelity"),
    "bass":            ("Bass Boost", "Bass Boost"),
    "night":           ("Night Mode", "Night Mode"),

    "one_mode_note":   ("One mode at a time — switching to another turns the "
                        "previous effect completely off",
                        "Aynı anda tek mod çalışır — başka bir moda geçince "
                        "öncekinin efekti tamamen kapanır"),

    "equaliser":       ("EQUALISER", "EKOLAYZIR"),
    "eq_hint":         ("drag a point · double-click to reset",
                        "noktayı sürükle · çift tıkla sıfırla"),
    "save":            ("Save", "Kaydet"),
    "reset_eq":        ("Reset EQ", "EQ Sıfırla"),
    "defaults":        ("Defaults", "Varsayılan"),
    "defaults_tip":    ("Return every setting to its factory value",
                        "Tüm ayarları fabrika değerlerine döndürür"),
    "limiter":         ("LIMITER", "LIMITER"),
    "on":              ("On", "Açık"),
    "off":             ("Off", "Kapalı"),

    "status_off":      ("Off — audio on the original device",
                        "Kapalı — ses orijinal aygıtta"),
    "status_on":       ("Active — audio running through Spatial Linux",
                        "Etkin — ses Spatial Linux üzerinden geçiyor"),
    "already_running": ("Spatial Linux is already switched on in another window "
                        "(the normal version or the Flatpak). Switch that one "
                        "off first, so the sound is not processed twice.",
                        "Spatial Linux başka bir pencerede zaten açık (normal "
                        "sürüm ya da Flatpak). Ses iki kez işlenmesin diye "
                        "önce onu kapatın."),
    "engine_failed":   ("Could not start the engine:",
                        "Motor başlatılamadı:"),
    "tools_missing":   ("Spatial Linux needs these PipeWire tools, which were not "
                        "found on this system. Install PipeWire and WirePlumber "
                        "(and their command-line tools) and try again:",
                        "Spatial Linux'un ihtiyaç duyduğu şu PipeWire araçları "
                        "bu sistemde bulunamadı. PipeWire ve WirePlumber'ı "
                        "(komut satırı araçlarıyla birlikte) kurup tekrar dene:"),
    "preset_failed":   ("Could not load the preset:",
                        "Preset yüklenemedi:"),
    "save_preset":     ("Save preset", "Preset Kaydet"),
    "bad_preset_name": ("A preset name cannot contain / or \\ or start with a dot.",
                        "Preset adı / veya \\ içeremez, nokta ile başlayamaz."),
    "save_failed":     ("Could not save the preset:",
                        "Preset kaydedilemedi:"),
    "name":            ("Name:", "İsim:"),
    "confirm_defaults": ("Every setting will return to its factory value. "
                         "Continue?",
                         "Tüm ayarlar fabrika değerlerine dönecek. "
                         "Devam edilsin mi?"),
    "power_tip":       ("Switch Spatial Linux on / off",
                        "Spatial Linux'u aç / kapat"),
    "preset_flat":     ("Flat", "Düz"),
    "preset_music":    ("Music", "Müzik"),
    "preset_movie":    ("Movie", "Film"),
    "preset_gaming":   ("Gaming", "Oyun"),
    "preset_night":    ("Night", "Gece"),
    "preset_bass":     ("Bass", "Bas"),
    "preset_ph":       ("Preset", "Preset"),
    "language_tip":    ("Language / Dil", "Dil / Language"),

    # feature panels
    "intensity":       ("INTENSITY", "YOĞUNLUK"),
    "subwoofer":       ("SUBWOOFER", "SUBWOOFER"),
    "room":            ("Room", "Ortam"),
    "clarity":         ("Clarity", "Netlik"),
    "low_end":         ("Low end", "Bas"),
    "balance":         ("Balance", "Denge"),

    "surround_hint":   ("Places virtual speakers with a head model: the far "
                        "ear hears it late and darker, both ears hear the room",
                        "Sanal hoparlörleri kafa modeliyle canlandırır: karşı "
                        "kulağa gecikmeli ve tizi kısılmış sinyal, iki kulağa "
                        "oda yansımaları"),
    "ambience_hint":   ("Convolution reverb — gives the sound a room and depth",
                        "Konvolüsyon reverb — sese mekân ve derinlik katar"),
    "fidelity_hint":   ("Lifts the two ranges the ear hears least",
                        "Kulağın en az duyduğu iki ucu yükseltir"),
    "bass_hint":       ("Lifts everything below 110 Hz",
                        "110 Hz altını yükseltir"),
    "night_hint":      ("Pulls your equaliser further down as it rises, and "
                        "softens the dynamics",
                        "Yükseldikçe ekolayzırı daha da aşağı çeker, "
                        "dinamiği yumuşatır"),

    "treble":          ("Treble", "Tiz"),
    "reverb_3d":       ("Reverb", "Reverb"),
    "eq":              ("EQ", "EQ"),
    "eq_tip":          ("Turn your equaliser on or off (the curve is kept)",
                        "Ekolayzırı aç / kapat (eğri korunur)"),
    "spk_front_l":     ("FRONT L", "SOL ÖN"),
    "spk_front_r":     ("FRONT R", "SAĞ ÖN"),
    "spk_side_l":      ("SIDE L", "SOL YAN"),
    "spk_side_r":      ("SIDE R", "SAĞ YAN"),
    "spk_rear_l":      ("REAR L", "SOL ARKA"),
    "spk_rear_r":      ("REAR R", "SAĞ ARKA"),

    # first-run introduction
    "intro_welcome":   ("Welcome to Spatial Linux", "Spatial Linux'a hoş geldin"),
    "intro_open":      ("Free and open source  ·  made by Sali",
                        "Özgür ve açık kaynak  ·  Sali tarafından yapıldı"),
    "intro_what":      ("3D sound for every app on your Linux system: "
                        "surround, room, clarity, bass and a night mode, "
                        "running right inside PipeWire.",
                        "Linux'taki her uygulama için 3D ses: surround, "
                        "ortam, netlik, bas ve gece modu. Doğrudan "
                        "PipeWire içinde çalışır."),
    "intro_next":      ("Next", "İleri"),
    "intro_skip":      ("Skip", "Geç"),
    "intro_start":     ("Let's go", "Başlayalım"),
    "intro_surround":  ("Takes the sound out of your headphones and places it "
                        "in the room around you, using acoustics measured on "
                        "a real head.",
                        "Sesi kulaklığın içinden çıkarıp etrafındaki odaya "
                        "yerleştirir. Gerçek bir kafada ölçülmüş akustik "
                        "kullanır."),
    "intro_ambience":  ("Builds a room around the music: depth and space, "
                        "from a small studio to a hall.",
                        "Müziğin etrafına bir oda kurar: küçük bir stüdyodan "
                        "salona kadar derinlik ve mekân."),
    "intro_fidelity":  ("Lifts the deepest lows and the finest highs, the "
                        "parts the ear catches least, so detail comes forward.",
                        "Kulağın en az duyduğu en derin bası ve en ince tizi "
                        "yükseltir, ayrıntılar öne çıkar."),
    "intro_bass":      ("A warm, clean lift below 110 Hz for music and films "
                        "that need more weight.",
                        "Daha dolgun ses isteyen müzik ve filmler için 110 Hz "
                        "altına sıcak, temiz bir yükseltme."),
    "intro_night":     ("Soft, even sound for late hours: quiet details rise, "
                        "sudden loud peaks come down.",
                        "Gece saatleri için yumuşak, dengeli ses: kısık "
                        "ayrıntılar yükselir, ani yüksek sesler iner."),
    "howto_title":     ("How to use", "Nasıl kullanılır"),
    "howto_1":         ("Press the power button: all your audio now runs "
                        "through Spatial Linux.",
                        "Güç düğmesine bas: bütün sesin Spatial Linux "
                        "üzerinden geçer."),
    "howto_2":         ("Pick a mode on the top row and set it with the "
                        "sliders in its panel.",
                        "Üst sıradan bir mod seç, panelindeki kaydırıcılarla "
                        "ayarla."),
    "howto_3":         ("Shape the sound on the equaliser: drag a point, "
                        "double-click to reset. EQ On / Off bypasses it.",
                        "Ekolayzırda sesi şekillendir: noktayı sürükle, çift "
                        "tıkla sıfırla. EQ Açık / Kapalı ile devre dışı "
                        "bırakılır."),
    "howto_4":         ("Pick a preset or save your own. Everything is "
                        "remembered for next time.",
                        "Bir preset seç ya da kendininkini kaydet. Her şey "
                        "bir sonraki sefere hatırlanır."),
    "mixer_tip":       ("App volumes", "Uygulama sesleri"),
    "mixer_title":     ("APP VOLUMES", "UYGULAMA SESLERİ"),
    "mixer_empty":     ("No app is playing sound right now. Start something "
                        "and it will appear here.",
                        "Şu anda ses çalan bir uygulama yok. Bir şey "
                        "başlattığında burada görünür."),
    "mixer_hint":      ("Each app's own volume. It goes through Spatial Linux "
                        "either way.",
                        "Her uygulamanın kendi ses seviyesi. Ses yine Spatial "
                        "Linux'tan geçer."),
    "mixer_no_tools":  ("The PipeWire tool pw-dump was not found, so the app "
                        "list cannot be read.",
                        "PipeWire aracı pw-dump bulunamadı, uygulama listesi "
                        "okunamıyor."),
    "mute":            ("Mute / unmute", "Sessize al / aç"),
    "hp_tip":          ("Headphones & 3D head", "Kulaklık ve 3D kafa"),
    "hp_title":        ("HEADPHONES", "KULAKLIK"),
    "hp_head":         ("3D HEAD", "3D KAFA"),
    "hp_head_hint":    ("Whose ears the 3D sound is measured with. Heads "
                        "differ, like ears do: pick the one where sound is "
                        "most clearly in front of you and outside your head.",
                        "3D sesin hangi kulaklarla ölçüldüğü. Kafalar da "
                        "kulaklar gibi farklıdır: sesin en net önünde ve "
                        "kafanın dışında duyulduğunu seç."),
    "hp_style":        ("3D SOUND", "3D SES"),
    "style_classic":   ("Classic", "Klasik"),
    "style_classic_tip": ("Spatial Linux's own 3D: your music stays clear and "
                          "close, with space around it",
                          "Spatial Linux'un kendi 3D'si: müzik net ve yakın "
                          "kalır, etrafında bir alan açılır"),
    "style_classic_hint": ("Spatial Linux's own 3D: the sound stays clear and "
                           "close, with width and a touch of room around it.",
                           "Spatial Linux'un kendi 3D'si: ses net ve yakın "
                           "kalır, etrafında genişlik ve biraz oda olur."),
    "style_studio":    ("Studio", "Stüdyo"),
    "style_studio_tip": ("Speakers in a treated studio: close, precise, "
                         "very little room",
                         "Akustiği düzenlenmiş bir stüdyoda hoparlörler: "
                         "yakın, net, çok az oda"),
    "style_studio_hint": ("Virtual speakers in a treated studio. You hear "
                          "speakers in front of you instead of headphones: "
                          "each speaker, and each reflection off the walls, "
                          "floor and ceiling, from its own direction.",
                          "Akustiği düzenlenmiş bir stüdyoda sanal "
                          "hoparlörler. Kulaklık yerine önündeki hoparlörleri "
                          "duyarsın: her hoparlörü ve duvar, zemin, tavandan "
                          "gelen her yansımayı kendi yönünden."),
    "style_living":    ("Living room", "Salon"),
    "style_living_tip": ("Speakers in a living room: natural and relaxed",
                         "Salonda hoparlörler: doğal ve rahat"),
    "style_living_hint": ("Virtual speakers in a living room: a little further "
                          "away, with the room's natural sound around them.",
                          "Salonda sanal hoparlörler: biraz daha uzakta, "
                          "etraflarında odanın doğal sesiyle."),
    "style_cinema":    ("Cinema", "Sinema"),
    "style_cinema_tip": ("Speakers in a cinema: big and spacious",
                         "Sinemada hoparlörler: büyük ve geniş"),
    "style_cinema_hint": ("Virtual speakers in a cinema: far away, big and "
                          "enveloping — made for films and games.",
                          "Sinemada sanal hoparlörler: uzakta, büyük ve saran "
                          "bir ses — filmler ve oyunlar için."),
    "style_custom":    ("Own file", "Kendi dosyan"),
    "style_custom_tip": ("Your own HRIR file (HeSuVi layout, 14 or 7 "
                         "channels); picking this the first time asks for it",
                         "Kendi HRIR dosyan (HeSuVi düzeni, 14 ya da 7 "
                         "kanal); ilk seçişte dosyayı sorar"),
    "style_custom_hint": ("Instead of Spatial Linux's own 3D, every channel "
                          "goes through your own HRIR file (a HeSuVi .wav, "
                          "14 or 7 channels). The intensity blends it with "
                          "the plain sound.",
                          "Spatial Linux'un kendi 3D'si yerine tüm kanallar "
                          "kendi HRIR dosyandan geçer (HeSuVi .wav dosyası, "
                          "14 ya da 7 kanal). Yoğunluk onu düz sesle "
                          "karıştırır."),
    "head_kemar":      ("KEMAR", "KEMAR"),
    "head_kemar_tip":  ("MIT KEMAR dummy head (the original sound)",
                        "MIT KEMAR yapay kafa (orijinal ses)"),
    "head_sadie":      ("KU 100", "KU 100"),
    "head_sadie_tip":  ("Neumann KU 100 dummy head, SADIE II (University of "
                        "York)",
                        "Neumann KU 100 yapay kafa, SADIE II (York "
                        "Üniversitesi)"),
    "hp_choose_hrir":  ("Choose an HRIR file", "HRIR dosyası seç"),
    "hp_change_hrir":  ("Change file…", "Dosyayı değiştir…"),
    "hp_hrir_in_use":  ("File: {name}", "Dosya: {name}"),
    "sony_title":      ("NOISE CANCELLING", "GÜRÜLTÜ ENGELLEME"),
    "sony_nc":         ("Noise cancelling", "Gürültü engelleme"),
    "sony_ambient":    ("Ambient sound", "Ortam sesi"),
    "sony_off":        ("Off", "Kapalı"),
    "sony_hint":       ("Your Sony headphones' own setting, as in Sony's app. "
                        "Ambient sound lets the room in; Off turns both off.",
                        "Sony kulaklığının kendi ayarı, Sony uygulamasındaki "
                        "gibi. Ortam sesi dışarıyı içeri alır; Kapalı ikisini "
                        "de kapatır."),
    "sony_reading":    ("Reading the headphones…", "Kulaklık okunuyor…"),
    "sony_applying":   ("Sending to the headphones…", "Kulaklığa gönderiliyor…"),
    "sony_failed":     ("The headphones did not answer. Check that they are "
                        "connected, and close Sony's app on your phone if it "
                        "is connected to them.",
                        "Kulaklık yanıt vermedi. Bağlı olduğundan emin ol; "
                        "telefonundaki Sony uygulaması bağlıysa onu kapat."),
    "sony_no_bluetooth": ("This Python has no Bluetooth support, so the "
                          "headphones cannot be reached.",
                          "Bu Python'da Bluetooth desteği yok, kulaklığa "
                          "ulaşılamıyor."),
    "hp_eq":           ("HEADPHONE CORRECTION", "KULAKLIK DÜZELTME"),
    "hp_eq_hint":      ("Evens out your headphones' own sound. Download the "
                        "ParametricEQ.txt for your model from autoeq.app "
                        "and load it here.",
                        "Kulaklığının kendi rengini düzeltir. Modelinin "
                        "ParametricEQ.txt dosyasını autoeq.app'ten indirip "
                        "buradan yükle."),
    "hp_load_eq":      ("Load file…", "Dosya yükle…"),
    "hp_remove_eq":    ("Remove", "Kaldır"),
    "hp_no_eq":        ("None loaded", "Yüklenmedi"),
    "hp_surround":     ("Games and films that play 5.1 or 7.1 are heard "
                        "from all around you: every channel from its own "
                        "place. Stereo is not changed.",
                        "5.1 ya da 7.1 çalan oyun ve filmler çevrenden "
                        "duyulur: her kanal kendi yerinden. Stereo "
                        "değişmez."),
    "hrir_bad":        ("This WAV file has {n} channels. An HRIR file in the "
                        "HeSuVi layout has 14 (or 7, for a symmetric head) — "
                        "the files in HeSuVi's hrir folder.",
                        "Bu WAV dosyasının {n} kanalı var. HeSuVi düzenindeki "
                        "bir HRIR dosyasının 14 (simetrik kafalarda 7) kanalı "
                        "olur — HeSuVi'nin hrir klasöründeki dosyalar."),
    "hrir_unreadable": ("This file could not be read as a WAV file.",
                        "Bu dosya WAV dosyası olarak okunamadı."),
    "autoeq_bad":      ("No filters were found in this file. Choose the "
                        "ParametricEQ.txt from autoeq.app.",
                        "Bu dosyada filtre bulunamadı. autoeq.app'teki "
                        "ParametricEQ.txt dosyasını seç."),
    "autoeq_skipped":  ("{n} filter(s) of this file could not be used and "
                        "were left out.",
                        "Bu dosyadaki {n} filtre kullanılamadı ve dışarıda "
                        "bırakıldı."),
    "reconfigure_failed": ("Could not switch the 3D sound:",
                           "3D ses değiştirilemedi:"),
    "info_tip":        ("How to use", "Nasıl kullanılır"),
    "intro_ready_t":   ("You're ready", "Hazırsın"),
    "intro_ready":     ("Press the power button to switch it on. One mode "
                        "runs at a time, "
                        "and everything you set is remembered.",
                        "Açmak için güç düğmesine bas. Aynı anda tek mod "
                        "çalışır, "
                        "yaptığın her ayar hatırlanır."),

    # scene captions
    "cap_depth":       ("Matching depth to your head…",
                        "Başa göre derinlik ayarlanıyor…"),
    "cap_widening":    ("The field is opening up…", "Alan genişliyor…"),
    "cap_bass":        ("The room answers every beat…",
                        "Bas vurdukça oda yanıt veriyor…"),
    "cap_fidelity":    ("Every detail in its place", "Her ayrıntı yerli yerinde"),
    "cap_ambience":    ("Reflections filling the room…",
                        "Yansımalar odayı dolduruyor…"),
    "night_relax":     ("Relaxation", "Rahatlama"),
    "night_soft":      ("Softer sound", "Yumuşak Ses"),
    "night_sleep":     ("Better sleep", "Daha İyi Uyku"),
    "breathe_in":      ("Breathe in…", "Nefes al…"),
    "breathe_out":     ("…let go", "…bırak"),
}

_current = "en"
_listeners = []


def language() -> str:
    return _current


def set_language(code: str):
    global _current
    if code not in LANGUAGES or code == _current:
        return
    _current = code
    for fn in list(_listeners):
        fn()


def on_change(fn):
    """Register a callback fired whenever the language changes."""
    _listeners.append(fn)


def t(key: str) -> str:
    pair = _STRINGS.get(key)
    if pair is None:
        return key
    return pair[LANGUAGES.index(_current)]
