from django.contrib.auth.views import LoginView, LogoutView

from .forms import CustomAuthenticationForm


class CustomLoginView(LoginView):
    form_class = CustomAuthenticationForm
    template_name = "semantic-ui/auth/login.html"
    redirect_authenticated_user = True
    extra_context = {"title": "Login"}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = self.extra_context["title"]
        return context


class CustomLogoutView(LogoutView):
    next_page = "accounts:login"
    template_name = "semantic-ui/auth/login.html"
    extra_context = {"title": "Logout"}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = self.extra_context["title"]
        return context
