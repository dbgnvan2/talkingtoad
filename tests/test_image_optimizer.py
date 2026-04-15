import os
import shutil
import pytest
from pathlib import Path
from PIL import Image
from api.services.image_processor import ImageOptimizer

@pytest.fixture
def temp_dirs(tmp_path):
    prod_dir = tmp_path / "production"
    archive_dir = tmp_path / "archive"
    prod_dir.mkdir()
    archive_dir.mkdir()
    return prod_dir, archive_dir

def create_dummy_image(path, size_kb=200, width=2000, height=2000):
    # Create an image that will likely be larger than the threshold
    img = Image.new('RGB', (width, height), color='red')
    img.save(path, "JPEG")
    
    # If we need to force it to be larger than size_kb, we can append garbage
    current_size = path.stat().st_size
    target_size = size_kb * 1024
    if current_size < target_size:
        with open(path, "ab") as f:
            f.write(b"\0" * (target_size - current_size))

def test_should_process(temp_dirs):
    prod_dir, archive_dir = temp_dirs
    optimizer = ImageOptimizer(archive_path=archive_dir)
    
    # Too small, small dimensions
    small_path = prod_dir / "small.jpg"
    create_dummy_image(small_path, size_kb=10, width=100, height=100)
    assert optimizer.should_process(small_path) is False
    
    # Large size
    large_size_path = prod_dir / "large_size.jpg"
    create_dummy_image(large_size_path, size_kb=200, width=100, height=100)
    assert optimizer.should_process(large_size_path) is True
    
    # Large dimensions
    large_dim_path = prod_dir / "large_dim.jpg"
    create_dummy_image(large_dim_path, size_kb=10, width=2000, height=2000)
    assert optimizer.should_process(large_dim_path) is True

def test_optimize_single(temp_dirs):
    prod_dir, archive_dir = temp_dirs
    optimizer = ImageOptimizer(archive_path=archive_dir)
    
    img_path = prod_dir / "test_image.jpg"
    create_dummy_image(img_path, size_kb=300, width=2000, height=2000)
    
    # Before optimization
    assert img_path.exists()
    
    result_path = optimizer.optimize(img_path, target_width=500)
    
    assert result_path is not None
    # Check if production file exists with -small suffix
    assert (prod_dir / "test_image-small.webp").exists()
    
    # Check if archive file exists
    assert (archive_dir / "optimized" / "test_image-small.webp").exists()
    
    # Check if original is DELETED according to spec §9
    assert not img_path.exists()

def test_bulk_optimize(temp_dirs):
    prod_dir, archive_dir = temp_dirs
    optimizer = ImageOptimizer(archive_path=archive_dir)
    
    # Create multiple images
    create_dummy_image(prod_dir / "img1.jpg", size_kb=200)
    create_dummy_image(prod_dir / "img2.png", size_kb=200)
    (prod_dir / "subdir").mkdir()
    create_dummy_image(prod_dir / "subdir" / "img3.jpg", size_kb=200)
    
    results = optimizer.bulk_optimize(prod_dir)
    assert len(results) == 3
    assert (prod_dir / "img1-small.webp").exists()
    assert (prod_dir / "img2-small.webp").exists()
    assert (prod_dir / "subdir" / "img3-small.webp").exists()
    
    # Originals should be deleted
    assert not (prod_dir / "img1.jpg").exists()
    assert not (prod_dir / "img2.png").exists()
    assert not (prod_dir / "subdir" / "img3.jpg").exists()
