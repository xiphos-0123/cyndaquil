"""Built-in settings, resource identities, and legacy migration keys."""

SYSTEM_AUDIO_ID = "system_default_audio"
SYSTEM_VISUAL_ID = "system_default_visual"

DEFAULT_SETTINGS = {
    "font_family": "Segoe UI",
    "font_size": 10,
    "ritual_seconds": 0,
    "audio_volume": 55,
    "idle_enabled": True,
    "idle_minutes": 8,
    "history_day_start_hour": 0,
    "history_chart_days": 14,
    "visual_framing_profiles": {},
    "custom_icon_path": None,
    "default_audio_path": None,
    "default_visual_path": None,
    # Visual Companion: standalone media window.
    "visual_companion_enabled": True,
    "visual_companion_width": 480,
    "visual_companion_height": 270,
    "visual_companion_lock_aspect": True,
    "visual_companion_opacity": 100,
    # Control Companion: timer and selected controls in one compact window.
    "control_companion_enabled": True,
    "control_companion_width": 360,
    "control_companion_opacity": 96,
    "control_companion_clock_size": 32,
    "control_companion_button_size": 10,
    "control_companion_button_height": 30,
    "control_companion_padding": 8,
    "control_companion_spacing": 4,
    "control_companion_show_timer": True,
    "control_companion_show_status": False,
    "control_companion_show_pause": True,
    "control_companion_show_adjust": True,
    "control_companion_show_main": True,
    "control_companion_show_finish": False,
    "control_companion_show_customize": True,
}

LEGACY_COMPANION_KEYS = {
    "companion_show_mission",
    "companion_show_status",
    "companion_show_visual",
    "companion_show_pause",
    "companion_show_adjust",
    "companion_show_main",
    "companion_show_finish",
    "companion_show_config",
    "companion_show_clock",
    "companion_visual_fit",
    "companion_visual_percent",
    "companion_control_height",
    "companion_button_style",
    "companion_button_spacing",
    "companion_opacity",
    "companion_width",
    "companion_height",
    "companion_timer_height",
    "companion_timer_padding",
    "companion_clock_size",
    "companion_title_size",
    "companion_button_size",
    "companion_padding",
    "companion_visual_ratio",
}


DEFAULT_PRESET = {
    "id": "default",
    "name": "Default",
    "mode": "stopwatch",
    "minutes": 50,
    "music_ids": [SYSTEM_AUDIO_ID],
    "visual_id": SYSTEM_VISUAL_ID,
}
