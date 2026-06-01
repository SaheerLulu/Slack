from django.conf import settings
from django.http import HttpResponse
from django.views import View


class SPAView(View):
    """Serve the built React index.html for client-side routes.

    In development (no build present) it returns a helpful message pointing at
    the Vite dev server.
    """

    def get(self, request, *args, **kwargs):
        index = settings.FRONTEND_DIST / "index.html"
        if index.exists():
            return HttpResponse(index.read_bytes())
        return HttpResponse(
            "<h1>Slack-ish backend is running</h1>"
            "<p>The frontend has not been built. For development run the Vite "
            "dev server (<code>cd frontend &amp;&amp; npm run dev</code>) and open "
            "<a href='http://localhost:5173'>http://localhost:5173</a>.</p>",
            content_type="text/html",
        )
