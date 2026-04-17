"""
EXIF GPS injection for image optimization workflow.

Injects GPS coordinates into images before WordPress upload for GEO optimization.
Supports JPEG and WebP formats.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image

if TYPE_CHECKING:
    from api.models.geo_config import GeoConfig

logger = logging.getLogger(__name__)

# Static mapping of location names to GPS coordinates (lat, lon)
# Covers common locations from GeoConfig settings
LOCATION_COORDINATES: dict[str, tuple[float, float]] = {
    # Greater Vancouver
    "Vancouver": (49.2827, -123.1207),
    "North Vancouver": (49.3165, -123.0688),
    "West Vancouver": (49.3270, -123.1660),
    "Burnaby": (49.2488, -122.9805),
    "Richmond": (49.1666, -123.1336),
    "Surrey": (49.1913, -122.8490),
    "Coquitlam": (49.2838, -122.7932),
    "New Westminster": (49.2057, -122.9110),
    "Delta": (49.0847, -123.0587),
    "Langley": (49.1044, -122.6600),
    "Maple Ridge": (49.2193, -122.5984),
    "Port Moody": (49.2838, -122.8317),
    "White Rock": (49.0253, -122.8029),
    # Vancouver Island
    "Victoria": (48.4284, -123.3656),
    "Nanaimo": (49.1659, -123.9401),
    # Other BC
    "Kelowna": (49.8880, -119.4960),
    "Kamloops": (50.6745, -120.3273),
    "Prince George": (53.9171, -122.7497),
    # Alberta
    "Calgary": (51.0447, -114.0719),
    "Edmonton": (53.5461, -113.4938),
    # Ontario
    "Toronto": (43.6532, -79.3832),
    "Ottawa": (45.4215, -75.6972),
    "Mississauga": (43.5890, -79.6441),
    # Quebec
    "Montreal": (45.5017, -73.5673),
    "Quebec City": (46.8139, -71.2080),
    # US Cities (common cross-border)
    "Seattle": (47.6062, -122.3321),
    "Bellingham": (48.7519, -122.4787),
    "Portland": (45.5152, -122.6784),
    "San Francisco": (37.7749, -122.4194),
    "Los Angeles": (34.0522, -118.2437),
    "New York": (40.7128, -74.0060),
}


def get_gps_from_location(location_name: str) -> tuple[float, float] | None:
    """
    Look up GPS coordinates for a location name.

    Args:
        location_name: City/area name (case-insensitive, partial match supported)

    Returns:
        (latitude, longitude) tuple or None if not found
    """
    if not location_name:
        return None

    # Exact match (case-insensitive)
    location_lower = location_name.lower().strip()
    for name, coords in LOCATION_COORDINATES.items():
        if name.lower() == location_lower:
            return coords

    # Partial match (location contains the key or vice versa)
    for name, coords in LOCATION_COORDINATES.items():
        if location_lower in name.lower() or name.lower() in location_lower:
            return coords

    logger.warning(f"No GPS coordinates found for location: {location_name}")
    return None


def get_gps_from_geo_config(geo_config: "GeoConfig") -> tuple[float, float] | None:
    """
    Extract GPS coordinates from GeoConfig's primary_location.

    Args:
        geo_config: GeoConfig instance with primary_location set

    Returns:
        (latitude, longitude) tuple or None if not found
    """
    if not geo_config or not geo_config.primary_location:
        return None

    return get_gps_from_location(geo_config.primary_location)


def _decimal_to_dms(decimal_degrees: float) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int]]:
    """
    Convert decimal degrees to degrees, minutes, seconds format for EXIF.

    EXIF GPS stores DMS as rationals: ((degrees, 1), (minutes, 1), (seconds * 100, 100))

    Args:
        decimal_degrees: Coordinate in decimal degrees (e.g., 49.2827)

    Returns:
        Tuple of three rationals for EXIF GPS format
    """
    is_negative = decimal_degrees < 0
    decimal_degrees = abs(decimal_degrees)

    degrees = int(decimal_degrees)
    minutes_decimal = (decimal_degrees - degrees) * 60
    minutes = int(minutes_decimal)
    seconds = (minutes_decimal - minutes) * 60

    # EXIF stores as rationals - use precision of 100 for seconds
    seconds_rational = int(seconds * 100)

    return ((degrees, 1), (minutes, 1), (seconds_rational, 100))


def inject_gps_coordinates(
    image_path: Path,
    latitude: float,
    longitude: float,
    altitude: float = 0.0,
) -> Path:
    """
    Inject GPS EXIF data into an image file.

    Modifies the image in-place by adding GPS coordinates to EXIF metadata.
    Works with JPEG files directly. For WebP, embeds XMP metadata.

    Args:
        image_path: Path to the image file
        latitude: GPS latitude in decimal degrees (positive = North)
        longitude: GPS longitude in decimal degrees (positive = East)
        altitude: GPS altitude in meters (default 0)

    Returns:
        Path to the modified image (same as input, modified in-place)

    Raises:
        FileNotFoundError: If image doesn't exist
        ValueError: If image format is not supported
    """
    import piexif

    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    suffix = image_path.suffix.lower()

    # Determine GPS reference directions
    lat_ref = "N" if latitude >= 0 else "S"
    lon_ref = "E" if longitude >= 0 else "W"
    alt_ref = 0 if altitude >= 0 else 1  # 0 = above sea level, 1 = below

    # Convert to DMS format for EXIF
    lat_dms = _decimal_to_dms(latitude)
    lon_dms = _decimal_to_dms(longitude)

    # Build GPS IFD
    gps_ifd = {
        piexif.GPSIFD.GPSLatitudeRef: lat_ref.encode("ascii"),
        piexif.GPSIFD.GPSLatitude: lat_dms,
        piexif.GPSIFD.GPSLongitudeRef: lon_ref.encode("ascii"),
        piexif.GPSIFD.GPSLongitude: lon_dms,
        piexif.GPSIFD.GPSAltitudeRef: alt_ref,
        piexif.GPSIFD.GPSAltitude: (int(abs(altitude) * 100), 100),
    }

    if suffix in (".jpg", ".jpeg"):
        # JPEG: Use piexif directly
        try:
            exif_dict = piexif.load(str(image_path))
        except Exception:
            # No existing EXIF, create new
            exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}

        exif_dict["GPS"] = gps_ifd
        exif_bytes = piexif.dump(exif_dict)

        # Re-save image with new EXIF
        img = Image.open(image_path)
        img.save(str(image_path), exif=exif_bytes, quality=95)
        img.close()

        logger.info(f"Injected GPS coordinates into JPEG: {image_path}")

    elif suffix == ".webp":
        # WebP: piexif can work with WebP via Pillow
        try:
            img = Image.open(image_path)

            # Try to get existing EXIF
            try:
                exif_bytes = img.info.get("exif", b"")
                if exif_bytes:
                    exif_dict = piexif.load(exif_bytes)
                else:
                    exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
            except Exception:
                exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}

            exif_dict["GPS"] = gps_ifd
            exif_bytes = piexif.dump(exif_dict)

            # Save WebP with EXIF
            img.save(str(image_path), exif=exif_bytes, quality=80, method=6)
            img.close()

            logger.info(f"Injected GPS coordinates into WebP: {image_path}")

        except Exception as e:
            logger.warning(f"Could not inject GPS into WebP {image_path}: {e}")
            # WebP EXIF support can be limited - continue without GPS
            raise ValueError(f"WebP GPS injection failed: {e}")

    elif suffix == ".png":
        # PNG doesn't support EXIF natively, but we can add XMP
        logger.warning(f"PNG format does not support EXIF GPS: {image_path}")
        raise ValueError("PNG format does not support EXIF GPS metadata")

    else:
        raise ValueError(f"Unsupported image format for GPS injection: {suffix}")

    return image_path


def validate_has_gps(image_path: Path) -> bool:
    """
    Check if an image already has GPS EXIF data.

    Args:
        image_path: Path to the image file

    Returns:
        True if GPS coordinates are present, False otherwise
    """
    import piexif

    image_path = Path(image_path)
    if not image_path.exists():
        return False

    suffix = image_path.suffix.lower()

    try:
        if suffix in (".jpg", ".jpeg"):
            exif_dict = piexif.load(str(image_path))
            gps_data = exif_dict.get("GPS", {})
            return bool(gps_data.get(piexif.GPSIFD.GPSLatitude))

        elif suffix == ".webp":
            img = Image.open(image_path)
            exif_bytes = img.info.get("exif", b"")
            img.close()

            if not exif_bytes:
                return False

            exif_dict = piexif.load(exif_bytes)
            gps_data = exif_dict.get("GPS", {})
            return bool(gps_data.get(piexif.GPSIFD.GPSLatitude))

        else:
            # Other formats - assume no GPS
            return False

    except Exception as e:
        logger.debug(f"Error checking GPS in {image_path}: {e}")
        return False


def extract_gps_coordinates(image_path: Path) -> tuple[float, float] | None:
    """
    Extract GPS coordinates from an image's EXIF data.

    Args:
        image_path: Path to the image file

    Returns:
        (latitude, longitude) tuple or None if no GPS data
    """
    import piexif

    image_path = Path(image_path)
    if not image_path.exists():
        return None

    suffix = image_path.suffix.lower()

    try:
        if suffix in (".jpg", ".jpeg"):
            exif_dict = piexif.load(str(image_path))
        elif suffix == ".webp":
            img = Image.open(image_path)
            exif_bytes = img.info.get("exif", b"")
            img.close()
            if not exif_bytes:
                return None
            exif_dict = piexif.load(exif_bytes)
        else:
            return None

        gps_data = exif_dict.get("GPS", {})

        lat_data = gps_data.get(piexif.GPSIFD.GPSLatitude)
        lat_ref = gps_data.get(piexif.GPSIFD.GPSLatitudeRef, b"N")
        lon_data = gps_data.get(piexif.GPSIFD.GPSLongitude)
        lon_ref = gps_data.get(piexif.GPSIFD.GPSLongitudeRef, b"E")

        if not lat_data or not lon_data:
            return None

        # Convert DMS to decimal
        def dms_to_decimal(dms_tuple: tuple, ref: bytes) -> float:
            degrees = dms_tuple[0][0] / dms_tuple[0][1]
            minutes = dms_tuple[1][0] / dms_tuple[1][1]
            seconds = dms_tuple[2][0] / dms_tuple[2][1]
            decimal = degrees + minutes / 60 + seconds / 3600
            if ref in (b"S", b"W"):
                decimal = -decimal
            return decimal

        latitude = dms_to_decimal(lat_data, lat_ref)
        longitude = dms_to_decimal(lon_data, lon_ref)

        return (latitude, longitude)

    except Exception as e:
        logger.debug(f"Error extracting GPS from {image_path}: {e}")
        return None
