"""Extract rich metadata from EXIF and JSON sidecars for tooltip display."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def extract_metadata(media_path: Path, json_path: Optional[Path]) -> dict:
    """
    Extract rich metadata from EXIF (photos) and JSON sidecar for tooltip display.
    Returns a dict with available fields; missing fields are omitted.
    """
    meta = {}

    # --- EXIF metadata (photos only) ---
    ext = media_path.suffix.lower()
    if ext in {".jpg", ".jpeg", ".tiff", ".tif", ".png", ".heic", ".webp"}:
        try:
            from PIL import Image
            from PIL.ExifTags import Base as ExifBase
            img = Image.open(media_path)
            meta["dimensions"] = f"{img.width}\u00d7{img.height}"
            exif = img.getexif()
            if exif:
                make = exif.get(ExifBase.Make, "")
                model = exif.get(ExifBase.Model, "")
                camera = f"{make} {model}".strip()
                if camera:
                    meta["camera"] = camera
                iso = exif.get(ExifBase.ISOSpeedRatings)
                if iso:
                    meta["iso"] = f"ISO {iso}"
                focal = exif.get(ExifBase.FocalLength)
                if focal:
                    try:
                        meta["focal_length"] = f"{float(focal):.0f}mm"
                    except Exception:
                        meta["focal_length"] = str(focal)
                fnumber = exif.get(ExifBase.FNumber)
                if fnumber:
                    try:
                        meta["aperture"] = f"f/{float(fnumber):.1f}"
                    except Exception:
                        pass
                # GPS from EXIF IFD
                gps_ifd = exif.get_ifd(0x8825)
                if gps_ifd:
                    try:
                        def _dms_to_dd(dms, ref):
                            d, m, s = [float(x) for x in dms]
                            dd = d + m / 60 + s / 3600
                            return -dd if ref in ("S", "W") else dd
                        lat = _dms_to_dd(gps_ifd[2], gps_ifd[1])
                        lon = _dms_to_dd(gps_ifd[4], gps_ifd[3])
                        meta["gps"] = f"{lat:.4f}, {lon:.4f}"
                    except Exception:
                        pass
        except Exception:
            pass

    # --- JSON sidecar metadata ---
    if json_path:
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                jdata = json.load(f)

            # photoTakenTime
            try:
                ts = int(jdata["photoTakenTime"]["timestamp"])
                if ts > 0:
                    meta["photoTakenTime"] = datetime.fromtimestamp(
                        ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            except (KeyError, ValueError, TypeError):
                pass

            # creationTime
            try:
                ts = int(jdata["creationTime"]["timestamp"])
                if ts > 0:
                    meta["creationTime"] = datetime.fromtimestamp(
                        ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            except (KeyError, ValueError, TypeError):
                pass

            # geoData
            try:
                geo = jdata["geoData"]
                lat, lon = geo["latitude"], geo["longitude"]
                if lat != 0.0 or lon != 0.0:
                    meta["geo"] = f"{lat:.4f}, {lon:.4f}"
            except (KeyError, TypeError):
                pass

            # people
            try:
                people = jdata.get("people", [])
                names = [p["name"] for p in people if p.get("name")]
                if names:
                    meta["people"] = ", ".join(names)
            except (TypeError, KeyError):
                pass

            # description
            desc = jdata.get("description", "")
            if desc:
                meta["description"] = desc[:120]

            # device type / Google Photos URL
            url = jdata.get("url", "")
            if url:
                meta["google_url"] = url

            try:
                device = jdata.get("googlePhotosOrigin", {}).get("mobileUpload", {}).get("deviceType", "")
                if device:
                    meta["device_type"] = device
            except (AttributeError, TypeError):
                pass

        except Exception:
            pass

    return meta
