from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .models import EventTheme, EventTranslation

IMAGE_FIELDS = {
    EventTranslation: ("banner_image",),
    EventTheme: ("background_image", "logo_image"),
}


def _is_referenced(name: str) -> bool:
    return (
        EventTranslation.objects.filter(banner_image=name).exists()
        or EventTheme.objects.filter(background_image=name).exists()
        or EventTheme.objects.filter(logo_image=name).exists()
    )


def _delete_when_unreferenced(storage, name: str) -> None:
    if not name:
        return

    def delete_file():
        if not _is_referenced(name):
            storage.delete(name)

    transaction.on_commit(delete_file)


@receiver(pre_save, sender=EventTranslation)
@receiver(pre_save, sender=EventTheme)
def remember_replaced_images(sender, instance, **kwargs):
    instance._replaced_image_files = []
    if not instance.pk:
        return
    try:
        previous = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return
    for field_name in IMAGE_FIELDS[sender]:
        old_file = getattr(previous, field_name)
        new_file = getattr(instance, field_name)
        if old_file.name and old_file.name != new_file.name:
            instance._replaced_image_files.append((old_file.storage, old_file.name))


@receiver(post_save, sender=EventTranslation)
@receiver(post_save, sender=EventTheme)
def delete_replaced_images(sender, instance, **kwargs):
    for storage, name in getattr(instance, "_replaced_image_files", []):
        _delete_when_unreferenced(storage, name)


@receiver(post_delete, sender=EventTranslation)
@receiver(post_delete, sender=EventTheme)
def delete_removed_images(sender, instance, **kwargs):
    for field_name in IMAGE_FIELDS[sender]:
        image = getattr(instance, field_name)
        if image.name:
            _delete_when_unreferenced(image.storage, image.name)
