from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, UpdateView

from .forms import CustomAuthenticationForm, CustomUserCreationForm, ProfileUpdateForm


class CustomLoginView(LoginView):
    """Handles user authentication inline without redirecting on invalid credentials."""

    authentication_form = CustomAuthenticationForm
    template_name = "registration/login.html"
    redirect_authenticated_user = True

    def form_valid(self, form):
        user = form.get_user()
        messages.success(self.request, f"Welcome back, {user.first_name or user.username}!")
        return super().form_valid(form)


class CustomLogoutView(LogoutView):
    """Ends the active session and informs the user."""

    def dispatch(self, request, *args, **kwargs):
        if request.method == "POST" and request.user.is_authenticated:
            messages.info(request, "You have been signed out safely.")
        return super().dispatch(request, *args, **kwargs)


class SignUpView(CreateView):
    """Public registration view for new Citizen accounts."""

    form_class = CustomUserCreationForm
    success_url = reverse_lazy("login")
    template_name = "registration/signup.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("dashboard_redirect")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Account created successfully! Please log in.")
        return response

    def form_invalid(self, form):
        messages.error(self.request, "Registration failed. Please fix the errors below.")
        return super().form_invalid(form)


class ProfileView(LoginRequiredMixin, DetailView):
    """Allows a logged-in user to view only their own profile."""

    template_name = "accounts/profile.html"
    context_object_name = "profile_user"

    def get_object(self, queryset=None):
        return self.request.user


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    """Allows a logged-in user to edit only their own profile."""

    form_class = ProfileUpdateForm
    template_name = "accounts/profile_edit.html"
    success_url = reverse_lazy("profile")

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Your profile has been updated.")
        return response

    def form_invalid(self, form):
        messages.error(self.request, "Please fix the errors in your profile form.")
        return super().form_invalid(form)
