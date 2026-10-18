from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class Profile(models.Model):
    """用户画像，扩展 Django 内置 User"""

    GENDER_CHOICES = [
        ("M", "男"),
        ("F", "女"),
        ("U", "保密"),
    ]

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="profile", verbose_name="用户"
    )
    avatar = models.ImageField("头像", upload_to="avatars/", blank=True, null=True)
    gender = models.CharField("性别", max_length=1, choices=GENDER_CHOICES, default="U")
    bio = models.TextField("个人简介", blank=True, default="")
    fav_categories = models.CharField("偏好分类", max_length=200, blank=True, default="")
    onboarded = models.BooleanField("是否完成兴趣引导", default=False)
    created_at = models.DateTimeField("注册时间", auto_now_add=True)

    class Meta:
        verbose_name = "用户画像"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.user.username} 的画像"


@receiver(post_save, sender=User)
def create_or_update_profile(sender, instance, created, **kwargs):
    """新建用户时自动创建画像"""
    if created:
        Profile.objects.create(user=instance)
    else:
        Profile.objects.get_or_create(user=instance)
