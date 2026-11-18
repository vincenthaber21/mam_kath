from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ManagedUserCreateForm, ManagedUserEditForm
from .models import User

PAGE_SIZE = 20


def manager_required(view):
    """Only administrators (or Django staff) may manage accounts."""

    @wraps(view)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not request.user.can_manage_users:
            messages.error(request, "Only administrators can manage users.")
            return redirect("history")
        return view(request, *args, **kwargs)

    return _wrapped


def _users_queryset(search, role):
    qs = User.objects.all()
    if role:
        qs = qs.filter(role=role)
    if search:
        qs = qs.filter(
            Q(username__icontains=search)
            | Q(email__icontains=search)
            | Q(name__icontains=search)
            | Q(first_name__icontains=search)
            | Q(middle_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(phone__icontains=search)
            | Q(barangay__icontains=search)
        )
    return qs


@manager_required
def user_list(request):
    role = request.GET.get("role") or ""
    if role not in {c.value for c in User.Role}:
        role = ""
    search = (request.GET.get("search") or "").strip()
    create_form = ManagedUserCreateForm()
    create_open = request.GET.get("new") == "1"

    if request.method == "POST" and request.POST.get("intent") == "create":
        create_form = ManagedUserCreateForm(request.POST)
        if create_form.is_valid():
            user = create_form.save()
            messages.success(request, f"Created {user.role_label.lower()} account for {user.email}.")
            return redirect("user_list")
        create_open = True

    page = Paginator(_users_queryset(search, role), PAGE_SIZE).get_page(request.GET.get("page"))
    query_parts = []
    if search:
        query_parts.append(f"search={search}")
    if role:
        query_parts.append(f"role={role}")
    return render(request, "accounts/users.html", {
        "page": page,
        "search": search,
        "role": role,
        "roles": User.Role.choices,
        "query": "&".join(query_parts),
        "nav": "users",
        "create_form": create_form,
        "create_open": create_open,
        "counts": {
            "all": User.objects.count(),
            "officer": User.objects.filter(role=User.Role.OFFICER).count(),
            "resident": User.objects.filter(role=User.Role.RESIDENT).count(),
            "admin": User.objects.filter(role=User.Role.ADMIN).count(),
        },
    })


@manager_required
def user_create(request):
    """Old /users/new/ address — open the dialog on the Users page instead."""
    return redirect("/users/?new=1")


@manager_required
def user_edit(request, pk):
    user = get_object_or_404(User, pk=pk)
    form = ManagedUserEditForm(request.POST or None, instance=user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Updated {user.display_name}.")
        return redirect("user_list")
    return render(request, "accounts/user_form.html", {
        "form": form,
        "edited_user": user,
        "title": f"Edit {user.display_name}",
        "subtitle": "Update role, contact details, or reset the password.",
        "nav": "users",
    })
