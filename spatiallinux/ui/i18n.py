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
