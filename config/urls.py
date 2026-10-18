from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.static import serve as static_serve

admin.site.site_header = "图书推荐系统管理后台"
admin.site.site_title = "图书推荐系统后台"
admin.site.index_title = "数据管理"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.books.urls")),
    path("accounts/", include("apps.users.urls")),
    path("recommend/", include("apps.recommender.urls")),
    path("analytics/", include("apps.analytics.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    # 生产环境（无 Nginx 单容器/Paas 场景）由 Django 直接提供封面等媒体文件
    urlpatterns += [
        path("media/<path:path>", static_serve,
             kwargs={"document_root": settings.MEDIA_ROOT}),
    ]
