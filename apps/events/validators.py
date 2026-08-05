from io import BytesIO
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.validators import FileExtensionValidator
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_IMAGE_SIZE = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000

image_extension_validator = FileExtensionValidator(
    allowed_extensions=("jpg", "jpeg", "png", "webp"),
    message="Supported image formats: JPEG, PNG, and WebP.",
)


def validate_image_upload(image) -> None:
    if image.size > MAX_IMAGE_SIZE:
        raise ValidationError("The image must not exceed 5 MB.")
    width = getattr(image, "width", 0) or 0
    height = getattr(image, "height", 0) or 0
    if width and height and width * height > MAX_IMAGE_PIXELS:
        raise ValidationError("The image resolution is too large.")


IMAGE_VALIDATORS = [image_extension_validator, validate_image_upload]


def sanitize_image_upload(upload):
    if not upload or upload is False:
        return upload
    try:
        upload.seek(0)
        with Image.open(upload) as source:
            image_format = (source.format or "").upper()
            image = ImageOps.exif_transpose(source)
            image.load()
    except (OSError, UnidentifiedImageError) as error:
        raise ValidationError("Upload a valid JPEG, PNG, or WebP image.") from error

    if image_format not in {"JPEG", "PNG", "WEBP"}:
        raise ValidationError("Supported image formats: JPEG, PNG, and WebP.")
    if image_format == "JPEG" and image.mode not in {"RGB", "L"}:
        image = image.convert("RGB")

    output = BytesIO()
    save_options = {
        "JPEG": {"quality": 88, "optimize": True},
        "PNG": {"optimize": True},
        "WEBP": {"quality": 88, "method": 4},
    }[image_format]
    image.save(output, format=image_format, **save_options)
    output.seek(0)

    extension = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}[image_format]
    filename = f"{Path(upload.name).stem}{extension}"
    content_type = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}[image_format]
    sanitized = InMemoryUploadedFile(
        output,
        getattr(upload, "field_name", None),
        filename,
        content_type,
        output.getbuffer().nbytes,
        None,
    )
    validate_image_upload(sanitized)
    return sanitized
