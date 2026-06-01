from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path

from chat.spa import SPAView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("chat.urls")),
]

# Serve uploaded media (in production this is also fine for self-host scale;
# put a reverse proxy in front for heavy traffic).
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# SPA fallback: any non-API, non-admin path serves the React index.html so
# client-side routing works on refresh/deep-links.
urlpatterns += [
    re_path(r"^(?!api/|admin/|media/|static/).*$", SPAView.as_view(), name="spa"),
    path("", SPAView.as_view(), name="spa-root"),
]
