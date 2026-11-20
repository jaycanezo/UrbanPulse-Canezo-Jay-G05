from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


class RoleRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restricts a view to authenticated users whose role matches allowed_role."""

    allowed_role = None

    def test_func(self):
        return (self.request.user.role or "").upper() == self.allowed_role
