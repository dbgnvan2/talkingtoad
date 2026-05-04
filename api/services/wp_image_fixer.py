"""
WordPress image metadata and optimization functionality.

Handles image resolution, metadata updates, and optimization workflows.
"""

import logging
import re
from pathlib import Path
from urllib.parse import urlparse, unquote

from api.services.wp_client import WPClient
from api.services.job_store import SQLiteJobStore, RedisJobStore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Image metadata helpers
# ---------------------------------------------------------------------------

async def find_attachment_by_url(wp: WPClient, image_url: str, cache_bust: bool = False) -> dict | None:
    """Resolve an image URL to a WordPress media attachment.

    Tries the source_url filter first (exact match), then falls back to a
    filename search.  Returns a dict with keys: id, source_url, alt_text,
    title, caption, admin_url.  Returns None if not found.
    """
    import time

    # Add cache-busting parameter if requested
    cache_param = f"&_nocache={int(time.time() * 1000)}" if cache_bust else ""

    # Extract filename and convert to WordPress slug format
    filename = unquote(urlparse(image_url).path.split("/")[-1])
    # Remove extension first
    name_no_ext = re.sub(r'\.[^.]+$', '', filename).lower()
    # Strip WordPress size suffix (e.g. "-600x403", "-1024x683", "-150x150")
    name_base = re.sub(r'-\d+x\d+$', '', name_no_ext)
    # WordPress slug: special chars become hyphens
    slug = re.sub(r'[^a-z0-9]+', '-', name_base).strip('-')

    # Also build a slug from the raw name (with size suffix) as fallback
    slug_with_size = re.sub(r'[^a-z0-9]+', '-', name_no_ext).strip('-')

    # Build the expected source_url (original without size suffix) for matching
    # e.g. dissappointment-600x403.jpg → dissappointment.jpg
    image_path = urlparse(image_url).path
    ext_match = re.search(r'\.[^.]+$', filename)
    ext = ext_match.group(0) if ext_match else ''
    base_url = image_url.replace(filename, name_base + ext) if name_base != name_no_ext else None

    try:
        # Try base slug first (without size suffix), then with size suffix
        slugs_to_try = [slug]
        if slug_with_size != slug:
            slugs_to_try.append(slug_with_size)

        for try_slug in slugs_to_try:
            r = await wp.get(
                f"media?slug={try_slug}&_fields=id,source_url,alt_text,title,caption,description{cache_param}"
            )

            if r.status_code != 200:
                continue

            items = r.json()

            if not items:
                continue

            # Check each item for URL match
            for item in items:
                wp_data = _attachment_dict(item, wp.site_url)
                wp_url = wp_data.get('source_url', '')
                wp_id = wp_data.get('id')

                # Exact match
                if wp_url == image_url:
                    return wp_data

                # Size-variant match: page uses e.g. img-600x403.jpg,
                # WP source_url is img.jpg (same directory, same base name)
                if base_url and wp_url == base_url:
                    return wp_data

                # Same directory + base filename match (handles URL encoding diffs)
                wp_path = urlparse(wp_url).path
                wp_dir = wp_path.rsplit('/', 1)[0] if '/' in wp_path else ''
                img_dir = image_path.rsplit('/', 1)[0] if '/' in image_path else ''
                if wp_dir == img_dir:
                    wp_base = re.sub(r'-\d+x\d+(?=\.[^.]+$)', '', wp_path.rsplit('/', 1)[-1])
                    img_base = re.sub(r'-\d+x\d+(?=\.[^.]+$)', '', image_path.rsplit('/', 1)[-1])
                    if wp_base == img_base:
                        return wp_data

        # Slug queries failed — fall back to search API.
        # This catches cases where the WP slug doesn't match the filename
        # (e.g. file renamed after upload, or slug auto-generated from
        # a different original name like "Screenshot-17").
        search_term = name_base.replace('-', ' ')
        try:
            r = await wp.get(
                f"media?search={search_term}&_fields=id,source_url,alt_text,title,caption,description{cache_param}"
            )
            if r.status_code == 200:
                for item in r.json():
                    wp_data = _attachment_dict(item, wp.site_url)
                    wp_url = wp_data.get('source_url', '')
                    # Exact URL match required for search results (search is fuzzy)
                    if wp_url == image_url:
                        return wp_data
                    # Size-variant match
                    if base_url and wp_url == base_url:
                        return wp_data
        except Exception:
            pass

        return None
    except Exception as e:
        logger.debug(f"find_attachment_by_url exception: {e}")
        return None


def _attachment_dict(item: dict, site_url: str) -> dict:
    """Convert WordPress media item to standardized attachment dict."""
    def strip_html(text: str) -> str:
        """Remove HTML tags from text."""
        if not text:
            return ""
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        # Decode HTML entities
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        return text.strip()

    att_id = item["id"]

    # Get rendered fields and strip HTML
    title_raw = item.get("title", {}).get("rendered", "")
    caption_raw = item.get("caption", {}).get("rendered", "")
    description_raw = item.get("description", {}).get("rendered", "")

    return {
        "id":          att_id,
        "source_url":  item.get("source_url", ""),
        "alt_text":    item.get("alt_text", ""),
        "title":       strip_html(title_raw),
        "caption":     strip_html(caption_raw),
        "description": strip_html(description_raw),
        "admin_url":   f"{site_url.rstrip('/')}/wp-admin/post.php?post={att_id}&action=edit",
    }


async def get_attachment_info(wp: WPClient, image_url: str, cache_bust: bool = False) -> dict:
    """Return attachment metadata for *image_url*, or an error dict."""
    att = await find_attachment_by_url(wp, image_url, cache_bust=cache_bust)
    if not att:
        return {"success": False, "error": f"No WordPress media attachment found for: {image_url}"}
    return {"success": True, **att}


async def update_image_metadata(
    wp: WPClient,
    image_url: str,
    alt_text: str | None = None,
    title: str | None = None,
    caption: str | None = None,
    description: str | None = None,
) -> dict:
    """Update alt text, title, caption, and/or description for a WordPress media attachment.

    Finds the attachment by URL, then PATCHes only the provided fields.
    Returns a dict with keys: success, id, error.
    """
    att = await find_attachment_by_url(wp, image_url)
    if not att:
        return {"success": False, "error": f"No WordPress media attachment found for: {image_url}"}

    payload: dict = {}
    if alt_text is not None:
        payload["alt_text"] = alt_text
    if title is not None:
        payload["title"] = title
    if caption is not None:
        payload["caption"] = caption
    if description is not None:
        payload["description"] = description

    if not payload:
        return {"success": False, "error": "No fields to update."}

    try:
        r = await wp.patch(f"media/{att['id']}", json=payload)
        if r.status_code == 200:
            updated = r.json()
            return {
                "success":  True,
                "id":       att["id"],
                "alt_text": updated.get("alt_text", ""),
                "title":    updated.get("title", {}).get("rendered", ""),
                "caption":  updated.get("caption", {}).get("rendered", ""),
                "description": updated.get("description", {}).get("rendered", ""),
                "error":    None,
            }
        body = r.json()
        return {"success": False, "error": body.get("message", f"HTTP {r.status_code}")}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Image Optimization Module v1.9.1
# ---------------------------------------------------------------------------

async def optimize_existing_image(
    wp: WPClient,
    image_url: str,
    page_urls: list[str],
    geo_config: "GeoConfig | None" = None,
    target_width: int = 1200,
    apply_gps: bool = True,
    seo_keyword: str | None = None,
    archive_path: Path | None = None,
    generate_geo_metadata: bool = False,
    page_h1: str = "",
    surrounding_text: str = "",
) -> dict:
    """
    Workflow A: Optimize an existing WordPress image.

    Downloads from WP, optimizes, uploads NEW version. Original STAYS in WP.
    User must manually replace the old image on pages.

    Args:
        wp: Authenticated WPClient
        image_url: URL of existing image in WordPress
        page_urls: List of page URLs where image is used (for user reference)
        geo_config: GeoConfig for GPS coordinates and metadata
        target_width: Max width after resize (default 1200)
        apply_gps: Whether to inject GPS EXIF (default True)
        seo_keyword: Keyword for SEO filename (optional)
        archive_path: Path to save original and optimized copies
        generate_geo_metadata: Whether to generate AI alt text, description, caption
        page_h1: H1 heading from the page (for GEO context)
        surrounding_text: Text context around the image (for GEO context)

    Returns:
        {
            success: bool,
            old_url: str (stays in WP),
            new_url: str (new optimized),
            new_media_id: int,
            page_urls: list[str] (where to replace),
            archive_paths: {original: str, optimized: str},
            file_size_kb: float,
            message: str,
            error: str | None,
            geo_metadata: {alt_text, description, caption} | None,
        }
    """
    from api.services.image_processor import ImageOptimizer, generate_seo_filename
    from api.services.exif_injector import inject_gps_coordinates, get_gps_from_geo_config
    from api.services.upload_validator import validate_for_upload
    from api.services.wp_fixer import replace_link_in_post
    import tempfile
    import shutil
    import httpx

    result = {
        "success": False,
        "old_url": image_url,
        "new_url": None,
        "new_media_id": None,
        "page_urls": page_urls,
        "archive_paths": {"original": None, "optimized": None},
        "file_size_kb": 0,
        "message": "",
        "error": None,
        "geo_metadata": None,
    }

    # Setup archive directory
    if archive_path:
        archive_path = Path(archive_path)
        (archive_path / "originals").mkdir(parents=True, exist_ok=True)
        (archive_path / "optimized").mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # 1. Download original
        original_filename = Path(urlparse(image_url).path).name
        input_path = tmp_path / original_filename

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.get(image_url)
                res.raise_for_status()
                with open(input_path, "wb") as f:
                    f.write(res.content)
        except Exception as exc:
            result["error"] = f"Failed to download image: {exc}"
            return result

        # 2. Archive original
        if archive_path:
            original_archive = archive_path / "originals" / original_filename
            shutil.copy2(input_path, original_archive)
            result["archive_paths"]["original"] = str(original_archive)

        # 3. Optimize (resize + WebP)
        optimizer = ImageOptimizer()
        output_path = optimizer.optimize(
            input_path,
            target_width=target_width,
            delete_original=False,  # Keep original for archiving
        )

        if not output_path:
            result["error"] = "Optimization failed or no size reduction achieved"
            return result

        # 4. Generate SEO filename
        city = geo_config.primary_location if geo_config else ""
        if seo_keyword or city:
            seo_name = generate_seo_filename(
                original_filename,
                keyword=seo_keyword or "",
                city=city,
            )
            final_path = output_path.with_name(seo_name)
            output_path.rename(final_path)
            output_path = final_path

        # 5. Inject GPS EXIF
        if apply_gps and geo_config:
            gps_coords = get_gps_from_geo_config(geo_config)
            if gps_coords:
                try:
                    inject_gps_coordinates(output_path, gps_coords[0], gps_coords[1])
                except Exception as exc:
                    logger.warning(f"GPS injection failed: {exc}")
                    # Continue without GPS

        # 6. Validate before upload
        validation = validate_for_upload(output_path, require_gps=apply_gps)
        if not validation.is_valid:
            result["error"] = f"Validation failed: {', '.join(validation.errors)}"
            return result

        result["file_size_kb"] = validation.file_size_kb

        # 7. Archive optimized
        if archive_path:
            optimized_archive = archive_path / "optimized" / output_path.name
            shutil.copy2(output_path, optimized_archive)
            result["archive_paths"]["optimized"] = str(optimized_archive)

        # 8. Upload to WordPress (NEW file, don't delete old)
        new_media = await wp.upload_media(output_path)
        if not new_media:
            result["error"] = "Failed to upload optimized image to WordPress"
            return result

        result["new_url"] = new_media.get("source_url")
        result["new_media_id"] = new_media.get("id")
        result["success"] = True

        # 9. Generate GEO AI metadata if requested
        if generate_geo_metadata and geo_config and result["new_media_id"]:
            try:
                from api.services.ai_analyzer import analyze_image_with_geo

                # Convert GeoConfig to dict for AI analyzer
                geo_dict = {
                    "org_name": geo_config.org_name if hasattr(geo_config, 'org_name') else geo_config.get("org_name", ""),
                    "primary_location": geo_config.primary_location if hasattr(geo_config, 'primary_location') else geo_config.get("primary_location", ""),
                    "location_pool": geo_config.location_pool if hasattr(geo_config, 'location_pool') else geo_config.get("location_pool", []),
                    "topic_entities": geo_config.topic_entities if hasattr(geo_config, 'topic_entities') else geo_config.get("topic_entities", []),
                }

                geo_result = await analyze_image_with_geo(
                    image_url=result["new_url"],
                    page_h1=page_h1,
                    surrounding_text=surrounding_text,
                    geo_config=geo_dict,
                )

                if geo_result.get("success"):
                    alt_text = geo_result.get("alt_text", "")
                    long_desc = geo_result.get("long_description", "")

                    # Update WordPress media with GEO metadata
                    await wp.update_media_metadata(
                        media_id=result["new_media_id"],
                        alt_text=alt_text,
                        description=long_desc,
                        caption=alt_text[:200] if alt_text else None,  # Caption is shorter version
                    )

                    result["geo_metadata"] = {
                        "alt_text": alt_text,
                        "description": long_desc,
                        "caption": alt_text[:200] if alt_text else "",
                        "entities_used": geo_result.get("entities_used", []),
                    }
                    logger.info("geo_metadata_applied", extra={"media_id": result["new_media_id"]})
                else:
                    logger.warning("geo_metadata_failed", extra={"error": geo_result.get("error")})
            except Exception as exc:
                logger.warning("geo_metadata_error", extra={"error": str(exc)})
                # Don't fail the whole operation if GEO fails

        # Build user message
        if page_urls:
            pages_str = ", ".join(page_urls[:3])
            if len(page_urls) > 3:
                pages_str += f" (+{len(page_urls) - 3} more)"
            result["message"] = f"Optimized image uploaded. Replace on: {pages_str}"
        else:
            result["message"] = "Optimized image uploaded. Link it to your pages manually."

        return result


async def optimize_local_image(
    wp: WPClient,
    local_path: Path,
    geo_config: "GeoConfig | None" = None,
    target_width: int = 1200,
    apply_gps: bool = True,
    seo_keyword: str | None = None,
    archive_path: Path | None = None,
    generate_geo_metadata: bool = False,
) -> dict:
    """
    Workflow B: Optimize a local image and upload to WordPress.

    Takes a local file, optimizes it, uploads to WP. Only 1 file in WP.

    Args:
        wp: Authenticated WPClient
        local_path: Path to local image file
        geo_config: GeoConfig for GPS coordinates
        target_width: Max width after resize (default 1200)
        apply_gps: Whether to inject GPS EXIF (default True)
        seo_keyword: Keyword for SEO filename (optional)
        archive_path: Path to save original and optimized copies
        generate_geo_metadata: Whether to generate AI alt text, description, caption

    Returns:
        {
            success: bool,
            new_url: str,
            new_media_id: int,
            archive_paths: {original: str, optimized: str},
            file_size_kb: float,
            message: str,
            error: str | None,
            geo_metadata: {alt_text, description, caption} | None,
        }
    """
    from api.services.image_processor import ImageOptimizer, generate_seo_filename
    from api.services.exif_injector import inject_gps_coordinates, get_gps_from_geo_config
    from api.services.upload_validator import validate_for_upload
    import tempfile
    import shutil

    local_path = Path(local_path)
    result = {
        "success": False,
        "new_url": None,
        "new_media_id": None,
        "archive_paths": {"original": None, "optimized": None},
        "file_size_kb": 0,
        "message": "",
        "error": None,
        "geo_metadata": None,
    }

    if not local_path.exists():
        result["error"] = f"File not found: {local_path}"
        return result

    # Setup archive directory
    if archive_path:
        archive_path = Path(archive_path)
        (archive_path / "originals").mkdir(parents=True, exist_ok=True)
        (archive_path / "optimized").mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # 1. Copy to temp for processing
        original_filename = local_path.name
        input_path = tmp_path / original_filename
        shutil.copy2(local_path, input_path)

        # 2. Archive original
        if archive_path:
            original_archive = archive_path / "originals" / original_filename
            shutil.copy2(local_path, original_archive)
            result["archive_paths"]["original"] = str(original_archive)

        # 3. Optimize (resize + WebP)
        optimizer = ImageOptimizer()
        output_path = optimizer.optimize(
            input_path,
            target_width=target_width,
            delete_original=False,
        )

        if not output_path:
            result["error"] = "Optimization failed or no size reduction achieved"
            return result

        # 4. Generate SEO filename
        city = geo_config.primary_location if geo_config else ""
        if seo_keyword or city:
            seo_name = generate_seo_filename(
                original_filename,
                keyword=seo_keyword or "",
                city=city,
            )
            final_path = output_path.with_name(seo_name)
            output_path.rename(final_path)
            output_path = final_path

        # 5. Inject GPS EXIF
        if apply_gps and geo_config:
            gps_coords = get_gps_from_geo_config(geo_config)
            if gps_coords:
                try:
                    inject_gps_coordinates(output_path, gps_coords[0], gps_coords[1])
                except Exception as exc:
                    logger.warning(f"GPS injection failed: {exc}")

        # 6. Validate before upload
        validation = validate_for_upload(output_path, require_gps=apply_gps)
        if not validation.is_valid:
            result["error"] = f"Validation failed: {', '.join(validation.errors)}"
            return result

        result["file_size_kb"] = validation.file_size_kb

        # 7. Archive optimized
        if archive_path:
            optimized_archive = archive_path / "optimized" / output_path.name
            shutil.copy2(output_path, optimized_archive)
            result["archive_paths"]["optimized"] = str(optimized_archive)

        # 8. Upload to WordPress
        new_media = await wp.upload_media(output_path)
        if not new_media:
            result["error"] = "Failed to upload optimized image to WordPress"
            return result

        result["new_url"] = new_media.get("source_url")
        result["new_media_id"] = new_media.get("id")
        result["success"] = True
        result["message"] = "Image optimized and uploaded. Link it to your pages in WordPress."

        # 9. Generate GEO metadata if requested
        if generate_geo_metadata and geo_config and result["new_url"]:
            try:
                from api.services.ai_analyzer import analyze_image_with_geo

                geo_result = await analyze_image_with_geo(
                    image_url=result["new_url"],
                    page_h1="",  # No page context for local uploads
                    surrounding_text=seo_keyword or "",  # Use keyword as context
                    geo_config=geo_config,
                )

                if geo_result and geo_result.get("success"):
                    geo_data = geo_result.get("result", {})
                    alt_text = geo_data.get("alt_text", "")
                    description = geo_data.get("long_description", "")
                    caption = geo_data.get("caption", "")

                    # Update WordPress metadata
                    media_id = result["new_media_id"]
                    if media_id and (alt_text or description or caption):
                        await wp.update_media_metadata(
                            media_id=media_id,
                            alt_text=alt_text or None,
                            description=description or None,
                            caption=caption or None,
                        )

                    result["geo_metadata"] = {
                        "alt_text": alt_text,
                        "description": description,
                        "caption": caption,
                        "entities_used": geo_data.get("entities_used", []),
                    }
                else:
                    logger.warning(
                        "geo_metadata_skipped",
                        extra={"reason": geo_result.get("error", "Unknown")}
                    )
            except Exception as exc:
                logger.warning(f"GEO metadata generation failed: {exc}")

        return result


async def preview_optimization(
    image_url: str | None = None,
    local_path: Path | None = None,
    target_width: int = 1200,
) -> dict:
    """
    Preview optimization results without uploading.

    Args:
        image_url: URL of existing image (for Workflow A)
        local_path: Path to local file (for Workflow B)
        target_width: Target width for resize

    Returns:
        {
            original_size_kb: float,
            estimated_size_kb: float,
            original_dimensions: tuple,
            target_dimensions: tuple,
            savings_percent: float,
        }
    """
    from api.services.upload_validator import estimate_optimized_size
    from PIL import Image
    import tempfile
    import httpx

    result = {
        "original_size_kb": 0,
        "estimated_size_kb": 0,
        "original_dimensions": None,
        "target_dimensions": None,
        "savings_percent": 0,
    }

    temp_file = None

    try:
        if image_url:
            # Download to temp for analysis
            with tempfile.NamedTemporaryFile(delete=False, suffix=".tmp") as f:
                temp_file = Path(f.name)
                async with httpx.AsyncClient(timeout=30.0) as client:
                    res = await client.get(image_url)
                    res.raise_for_status()
                    f.write(res.content)
            file_path = temp_file
        elif local_path:
            file_path = Path(local_path)
            if not file_path.exists():
                return result
        else:
            return result

        # Analyze original
        try:
            img = Image.open(file_path)
            result["original_dimensions"] = img.size
            result["original_size_kb"] = round(file_path.stat().st_size / 1024, 1)
        except Exception:
            return result

        # Estimate optimized size
        estimated = estimate_optimized_size(file_path, target_width=target_width)
        result["estimated_size_kb"] = estimated

        # Calculate target dimensions
        original_width, original_height = result["original_dimensions"]
        if original_width > target_width:
            scale = target_width / original_width
            target_height = int(original_height * scale)
            result["target_dimensions"] = (target_width, target_height)
        else:
            result["target_dimensions"] = result["original_dimensions"]

        # Calculate savings
        if result["original_size_kb"] > 0:
            result["savings_percent"] = round(
                ((result["original_size_kb"] - result["estimated_size_kb"]) / result["original_size_kb"]) * 100,
                1
            )

        return result
    except Exception as exc:
        logger.debug(f"preview_optimization exception: {exc}")
        return result
    finally:
        if temp_file and temp_file.exists():
            try:
                temp_file.unlink()
            except Exception:
                pass
