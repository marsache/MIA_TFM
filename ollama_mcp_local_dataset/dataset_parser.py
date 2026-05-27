"""
Dataset parser for the local song dataset.

Parses MusicXML (.xml) files from the «Cancionero básico de Castilla y León»
and MuseScore (.mscz) files from the «Muiñeiras» collection, producing a
uniform list of song metadata dictionaries.

Each song dict has:
    id              – unique integer identifier
    title           – song title (from filename or embedded metadata)
    collection      – top-level collection name
    subcollection   – sub-folder / cancionero name (may be empty)
    category        – thematic category folder (may be empty)
    key             – key name, e.g. «G major» (empty string if unknown)
    time_signature  – e.g. «3/4» (empty string if unknown)
    tempo_bpm       – integer BPM or None
    lyrics          – full lyric text (empty string if unavailable)
    file_path       – absolute path to the source file
    file_type       – «musicxml» or «musescore»
"""

from __future__ import annotations

import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from config import CANCIONERO_DIR, MUINEIRAS_DIR

# ---------------------------------------------------------------------------
# Key-signature helpers
# ---------------------------------------------------------------------------

# MusicXML «fifths» value → key name (assuming major unless minor clue found)
_FIFTHS_TO_MAJOR: dict[int, str] = {
    -7: "Cb major", -6: "Gb major", -5: "Db major", -4: "Ab major",
    -3: "Eb major", -2: "Bb major", -1: "F major",   0: "C major",
     1: "G major",   2: "D major",   3: "A major",   4: "E major",
     5: "B major",   6: "F# major",  7: "C# major",
}

# MuseScore key index: negative = flats major, positive = sharps major
# (same mapping as MusicXML fifths, but MuseScore stores it as an integer
# attribute on the <key> element inside <KeySig>)
_MUSESCORE_KEY_TO_NAME: dict[int, str] = _FIFTHS_TO_MAJOR  # identical mapping


def _fifths_to_key(fifths_str: str | None) -> str:
    """Convert a MusicXML «fifths» text value to a human-readable key name."""
    if fifths_str is None:
        return ""
    try:
        return _FIFTHS_TO_MAJOR.get(int(fifths_str), "")
    except ValueError:
        return ""


def _musescore_key_to_name(key_str: str | None) -> str:
    """Convert a MuseScore key integer to a human-readable key name."""
    if key_str is None:
        return ""
    try:
        return _MUSESCORE_KEY_TO_NAME.get(int(key_str), "")
    except ValueError:
        return ""


# ---------------------------------------------------------------------------
# MusicXML parser
# ---------------------------------------------------------------------------

def _parse_musicxml(file_path: Path) -> dict:
    """Extract metadata from a MusicXML file.

    Returns a partial song dict (without ``id``).
    """
    song: dict = {
        "title": "",
        "key": "",
        "time_signature": "",
        "tempo_bpm": None,
        "lyrics": "",
        "file_path": str(file_path),
        "file_type": "musicxml",
    }

    # Title: derive from filename (strip leading «NNN. » prefix)
    stem = file_path.stem
    title_match = re.match(r"^\d+[a-z]*\.\s*(.+)", stem)
    song["title"] = title_match.group(1).strip() if title_match else stem

    try:
        tree = ET.parse(file_path)
        root = tree.getroot()

        # Key signature (take the first one found)
        for key_el in root.iter("key"):
            fifths_el = key_el.find("fifths")
            if fifths_el is not None:
                song["key"] = _fifths_to_key(fifths_el.text)
                break

        # Time signature
        for time_el in root.iter("time"):
            beats = time_el.findtext("beats")
            beat_type = time_el.findtext("beat-type")
            if beats and beat_type:
                song["time_signature"] = f"{beats}/{beat_type}"
                break

        # Tempo (first metronome marking)
        per_min = root.findtext(".//metronome/per-minute")
        if per_min:
            try:
                song["tempo_bpm"] = int(float(per_min))
            except ValueError:
                pass

        # Also check <sound tempo="…"> attributes
        if song["tempo_bpm"] is None:
            for sound_el in root.iter("sound"):
                t = sound_el.get("tempo")
                if t:
                    try:
                        song["tempo_bpm"] = int(float(t))
                        break
                    except ValueError:
                        pass

        # Lyrics: collect all <text> elements inside <lyric>
        syllables: list[str] = []
        for lyric_el in root.iter("lyric"):
            text_el = lyric_el.find("text")
            if text_el is not None and text_el.text:
                syllables.append(text_el.text)
        song["lyrics"] = " ".join(syllables)

    except ET.ParseError:
        pass

    return song


# ---------------------------------------------------------------------------
# MuseScore (.mscz) parser
# ---------------------------------------------------------------------------

def _parse_mscz(file_path: Path) -> dict:
    """Extract metadata from a MuseScore (.mscz) file.

    .mscz files are ZIP archives that contain a .mscx XML file.
    Returns a partial song dict (without ``id``).
    """
    song: dict = {
        "title": file_path.stem,
        "key": "",
        "time_signature": "",
        "tempo_bpm": None,
        "lyrics": "",
        "file_path": str(file_path),
        "file_type": "musescore",
    }

    if not zipfile.is_zipfile(file_path):
        return song

    try:
        with zipfile.ZipFile(file_path) as zf:
            mscx_names = [n for n in zf.namelist() if n.endswith(".mscx")]
            if not mscx_names:
                return song
            with zf.open(mscx_names[0]) as mscx_file:
                tree = ET.parse(mscx_file)

        root = tree.getroot()

        # Title from workTitle meta tag
        for meta in root.iter("metaTag"):
            if meta.get("name") == "workTitle" and meta.text and meta.text.strip():
                song["title"] = meta.text.strip()
                break

        # Key signature
        key_el = root.find(".//KeySig/key")
        if key_el is not None:
            song["key"] = _musescore_key_to_name(key_el.text)

        # Time signature
        sig_n = root.findtext(".//TimeSig/sigN")
        sig_d = root.findtext(".//TimeSig/sigD")
        if sig_n and sig_d:
            song["time_signature"] = f"{sig_n}/{sig_d}"

        # Tempo: MuseScore uses tempo as beats-per-second in <Tempo>
        tempo_el = root.findtext(".//Tempo/tempo")
        if tempo_el:
            try:
                # MuseScore stores tempo in beats per second; convert to BPM
                bps = float(tempo_el)
                song["tempo_bpm"] = round(bps * 60)
            except ValueError:
                pass

        # Lyrics
        syllables: list[str] = []
        for lyric_el in root.iter("Lyrics"):
            text_el = lyric_el.find("text")
            if text_el is not None and text_el.text:
                syllables.append(text_el.text)
        song["lyrics"] = " ".join(syllables)

    except (zipfile.BadZipFile, ET.ParseError):
        pass

    return song


# ---------------------------------------------------------------------------
# Category helpers
# ---------------------------------------------------------------------------

def _relative_path_parts(file_path: Path, base: Path) -> list[str]:
    """Return path parts of *file_path* relative to *base*, excluding filename."""
    try:
        rel = file_path.relative_to(base)
    except ValueError:
        return []
    return list(rel.parts[:-1])


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_dataset() -> list[dict]:
    """Parse all files in the dataset directories and return a list of songs.

    Each song is a dict as described in the module docstring, with an
    additional integer ``id`` field (1-based index).
    """
    songs: list[dict] = []
    song_id = 1

    # ── Cancionero básico de Castilla y León (MusicXML) ──────────────────
    if CANCIONERO_DIR.is_dir():
        for xml_file in sorted(CANCIONERO_DIR.rglob("*.xml")):
            song = _parse_musicxml(xml_file)
            parts = _relative_path_parts(xml_file, CANCIONERO_DIR)
            song["collection"] = "Cancionero básico de Castilla y León"
            song["subcollection"] = parts[1] if len(parts) > 1 else ""
            song["category"] = parts[0] if parts else ""
            song["id"] = song_id
            songs.append(song)
            song_id += 1

    # ── Muiñeiras (MuseScore) ──────────────────────────────────────────────
    if MUINEIRAS_DIR.is_dir():
        for mscz_file in sorted(MUINEIRAS_DIR.rglob("*.mscz")):
            song = _parse_mscz(mscz_file)
            parts = _relative_path_parts(mscz_file, MUINEIRAS_DIR)
            song["collection"] = "Muiñeiras"
            song["subcollection"] = parts[0] if parts else ""
            song["category"] = "Muiñeira"
            song["id"] = song_id
            songs.append(song)
            song_id += 1

    return songs
