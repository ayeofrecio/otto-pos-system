# users/decorators.py

from django.contrib.auth.decorators import user_passes_test
from users.models import Users


# ---------------------------------------------------------
# Role hierarchy
# Higher number = higher privilege
# ---------------------------------------------------------

ROLE_LEVELS = {
    Users.ROLE_CASHIER: 1,
    Users.ROLE_SUPERVISOR: 2,
    Users.ROLE_MANAGER: 3,
    Users.ROLE_ADMIN: 4,
}


# # ---------------------------------------------------------
# # Helper: safely get user profile
# # ---------------------------------------------------------

# def _get_profile(user):
#     """
#     Safely retrieve profile.
#     Returns None if profile does not exist.
#     """
#     try:
#         return user.profile
#     except (AttributeError, Users.DoesNotExist):
#         return None


# ---------------------------------------------------------
# Core role-level decorator
# ---------------------------------------------------------

def role_required(min_role_level):

    def decorator(view_func):

        def check(user):

            if not user.is_authenticated:
                return False

            if user.is_suspended:
                return False

            user_level = ROLE_LEVELS.get(user.role, 0)

            return user_level >= min_role_level

        return user_passes_test(check)(view_func)

    return decorator


# ---------------------------------------------------------
# Specific role decorators
# ---------------------------------------------------------

def cashier_required(view_func):
    """
    Allows:
    Cashier, Supervisor, Manager, Admin
    """
    return role_required(
        ROLE_LEVELS[Users.ROLE_CASHIER]
    )(view_func)


def supervisor_required(view_func):
    """
    Allows:
    Supervisor, Manager, Admin
    """
    return role_required(
        ROLE_LEVELS[Users.ROLE_SUPERVISOR]
    )(view_func)


def manager_required(view_func):
    """
    Allows:
    Manager, Admin
    """
    return role_required(
        ROLE_LEVELS[Users.ROLE_MANAGER]
    )(view_func)


def admin_required(view_func):
    """
    Allows:
    Admin only
    """
    return role_required(
        ROLE_LEVELS[Users.ROLE_ADMIN]
    )(view_func)